"""
Claude Code transcript processor.

Parses Claude Code JSONL transcript files and emits OpenTelemetry spans
following the Monocle metamodel pattern.

Invoked by the Claude Code Stop hook — not via monkey-patching, since
Claude Code is a CLI binary rather than a Python library.
"""

import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from opentelemetry import context as otel_context, trace
from opentelemetry.trace import StatusCode

from monocle_apptrace.instrumentation.metamodel.claude_code._helper import (
    SessionState,
    SubagentInfo,
    Turn,
    build_turns,
    extract_text,
    get_content,
    get_message_id,
    get_model,
    get_stop_reason,
    get_timestamp,
    get_usage,
    iter_tool_uses,
    parse_command_skill,
    read_new_jsonl,
    read_subagent_jsonl,
)
from monocle_apptrace.instrumentation.metamodel.claude_code.entities import (
    inference_span_attrs,
    invocation_span_attrs,
    skill_span_attrs,
    tool_span_attrs,
    turn_span_attrs,
    workflow_span_attrs,
)

logger = logging.getLogger(__name__)

SERVICE_NAME = "claude-cli"


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------

def _parse_timestamp_ns(ts: Optional[str]) -> Optional[int]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1_000_000_000)
    except Exception:
        return None


@contextmanager
def _timed_span(
    tracer: trace.Tracer,
    name: str,
    attributes: Dict[str, Any],
    start_ns: Optional[int],
    end_ns: Optional[int],
) -> Generator:
    """Span with explicit start/end times for replaying transcript timestamps."""
    span = tracer.start_span(name=name, start_time=start_ns, attributes=attributes)
    token = otel_context.attach(trace.set_span_in_context(span))
    try:
        yield span
    finally:
        otel_context.detach(token)
        span.end(end_time=end_ns)


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def _build_full_response(turn: Turn) -> str:
    parts = []
    for assistant_msg in turn.assistant_msgs:
        text = extract_text(get_content(assistant_msg))
        if text:
            parts.append(text)
    for tool_output in turn.tool_results_by_id.values():
        if tool_output:
            parts.append(tool_output if isinstance(tool_output, str) else json.dumps(tool_output))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Per-round helpers
# ---------------------------------------------------------------------------

def _round_inference_start_ns(turn: Turn, round_index: int, turn_start_ns: Optional[int]) -> Optional[int]:
    """Return the start timestamp (ns) for a given inference round."""
    if round_index == 0:
        return turn_start_ns
    prev_tool_ids = [
        tu.get("id")
        for tu in iter_tool_uses(get_content(turn.assistant_msgs[round_index - 1]))
    ]
    prev_end_times = [
        _parse_timestamp_ns(turn.tool_result_times_by_id.get(tid))
        for tid in prev_tool_ids if tid
    ]
    prev_end_times = [t for t in prev_end_times if t]
    if prev_end_times:
        return max(prev_end_times)
    return _parse_timestamp_ns(get_timestamp(turn.assistant_msgs[round_index - 1]))


def _build_inference_metadata(
    round_usage: Dict[str, int],
    stop_reason: str,
) -> Dict[str, Any]:
    """Build metadata for one inference span using only that round's token counts.

    prompt_tokens = input_tokens + cache_read_input_tokens + cache_creation_input_tokens
    This is the true full context size sent to the model for this LLM call.
    Reporting input_tokens alone would be misleading because Claude Code uses
    aggressive prompt caching, making raw input_tokens as small as 3.
    """
    finish_type = "tool_call" if stop_reason == "tool_use" else "success"
    metadata: Dict[str, Any] = {
        "finish_reason": stop_reason,
        "finish_type": finish_type,
    }

    input_t = round_usage.get("input_tokens") or 0
    cache_read_t = round_usage.get("cache_read_tokens") or 0
    cache_creation_t = round_usage.get("cache_creation_tokens") or 0
    output_t = round_usage.get("output_tokens") or 0
    prompt_t = input_t + cache_read_t + cache_creation_t

    if prompt_t:
        metadata["prompt_tokens"] = prompt_t
    if output_t:
        metadata["completion_tokens"] = output_t
    if prompt_t or output_t:
        metadata["total_tokens"] = prompt_t + output_t
    if cache_read_t:
        metadata["cache_read_tokens"] = cache_read_t
    if cache_creation_t:
        metadata["cache_creation_tokens"] = cache_creation_t

    return metadata


def _round_output_text(assistant_msg: Dict[str, Any]) -> str:
    """Return the assistant's text for this round, or a dispatch summary if none."""
    text = extract_text(get_content(assistant_msg))
    if text:
        return text
    dispatched = []
    for tu in iter_tool_uses(get_content(assistant_msg)):
        name = tu.get("name", "unknown")
        if name == "Agent":
            subtype = tu.get("input", {}).get("subagent_type", "agent")
            dispatched.append(f"Agent({subtype})")
        else:
            dispatched.append(name)
    return f"[Dispatched: {', '.join(dispatched)}]" if dispatched else "[tool dispatch]"


# ---------------------------------------------------------------------------
# Span emitters
# ---------------------------------------------------------------------------

def _emit_skill_span(
    tracer: trace.Tracer,
    cmd_skill: Dict[str, str],
    session_id: str,
    turn_id: str,
    invocation_id: str,
    service_name: str,
    sdk_version: str,
    turn_start_ns: Optional[int],
    turn_end_ns: Optional[int],
) -> None:
    skill_name = cmd_skill["skill_name"]
    skill_input: Dict[str, Any] = {"skill": skill_name}
    if cmd_skill["args"]:
        skill_input["args"] = cmd_skill["args"]
    if cmd_skill["plugin_name"]:
        skill_input["plugin"] = cmd_skill["plugin_name"]

    attrs = skill_span_attrs(
        session_id, turn_id, invocation_id,
        skill_name, cmd_skill["plugin_name"], cmd_skill["args"],
        service_name, sdk_version,
    )
    with _timed_span(tracer, f"Skill: {skill_name}", attrs, turn_start_ns, turn_end_ns) as span:
        span.set_status(StatusCode.OK)
        span.add_event("data.input", {"input": json.dumps(skill_input)})
        span.add_event("data.output", {"response": f"/{cmd_skill['command_name']}"})


def _emit_inference_span(
    tracer: trace.Tracer,
    assistant_msg: Dict[str, Any],
    round_index: int,
    num_rounds: int,
    turn: Turn,
    session_id: str,
    turn_id: str,
    invocation_id: str,
    model: str,
    user_text: str,
    service_name: str,
    sdk_version: str,
    turn_start_ns: Optional[int],
) -> None:
    stop_reason = get_stop_reason(assistant_msg) or "end_turn"
    msg_id = get_message_id(assistant_msg) or ""
    start_ns = _round_inference_start_ns(turn, round_index, turn_start_ns)
    end_ns = _parse_timestamp_ns(get_timestamp(assistant_msg))
    metadata = _build_inference_metadata(get_usage(assistant_msg), stop_reason)
    name = "Claude Inference" if num_rounds == 1 else f"Claude Inference ({round_index + 1}/{num_rounds})"
    attrs = inference_span_attrs(session_id, turn_id, invocation_id, model, msg_id, service_name, sdk_version)

    with _timed_span(tracer, name, attrs, start_ns, end_ns) as span:
        span.set_status(StatusCode.OK)
        span.add_event("data.input", {"input": user_text})
        span.add_event("data.output", {"response": _round_output_text(assistant_msg)})
        span.add_event("metadata", metadata)


def _emit_tool_span(
    tracer: trace.Tracer,
    tool_use: Dict[str, Any],
    turn: Turn,
    session_id: str,
    turn_id: str,
    invocation_id: str,
    service_name: str,
    sdk_version: str,
    start_ns: Optional[int],
    turn_end_ns: Optional[int],
    parent_invocation_span_id: str,
) -> None:
    tool_id = tool_use.get("id", "")
    tool_name = tool_use.get("name", "unknown")
    tool_input = tool_use.get("input", {})
    tool_output = turn.tool_results_by_id.get(tool_id, "")
    end_ns = _parse_timestamp_ns(turn.tool_result_times_by_id.get(tool_id)) or turn_end_ns

    input_str = json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input)
    output_str = tool_output if isinstance(tool_output, str) else (json.dumps(tool_output) if tool_output else "")

    attrs = tool_span_attrs(
        session_id, turn_id, invocation_id,
        tool_name, tool_input,
        service_name, sdk_version,
        parent_invocation_span_id=parent_invocation_span_id,
    )

    if tool_name == "Agent" and isinstance(tool_input, dict):
        subagent_type = tool_input.get("subagent_type") or "sub-agent"
        span_name = f"Sub-Agent: {subagent_type}"
    elif tool_name == "Skill" and isinstance(tool_input, dict):
        span_name = f"Skill: {tool_input.get('skill', 'unknown')}"
    else:
        span_name = f"Tool: {tool_name}"

    with _timed_span(tracer, span_name, attrs, start_ns, end_ns) as span:
        span.set_status(StatusCode.OK)
        span.add_event("data.input", {"input": input_str})
        span.add_event("data.output", {"response": output_str})


# ---------------------------------------------------------------------------
# Turn emitter
# ---------------------------------------------------------------------------

def _emit_turn(
    tracer: trace.Tracer,
    turn: Turn,
    session_id: str,
    sdk_version: str,
    service_name: str,
    user_name: Optional[str] = None,
    span_name_prefix: str = "Claude Code",
) -> bool:
    if not turn.assistant_msgs:
        return False

    user_text = extract_text(get_content(turn.user_msg))
    full_response = _build_full_response(turn)
    model = get_model(turn.assistant_msgs[0])
    turn_start_ns = _parse_timestamp_ns(turn.start_time)
    turn_end_ns = _parse_timestamp_ns(turn.end_time)
    turn_id = str(uuid.uuid4())
    invocation_id = str(uuid.uuid4())

    with _timed_span(
        tracer, span_name_prefix,
        turn_span_attrs(session_id, turn_id, service_name, sdk_version, user_name),
        turn_start_ns, turn_end_ns,
    ) as turn_span:
        turn_span.set_status(StatusCode.OK)
        turn_span.add_event("data.input", {"input": user_text})
        turn_span.add_event("data.output", {"response": full_response})

        with _timed_span(
            tracer, "Claude Invocation",
            invocation_span_attrs(session_id, turn_id, invocation_id, service_name, sdk_version),
            turn_start_ns, turn_end_ns,
        ) as invocation_span:
            invocation_span.set_status(StatusCode.OK)
            invocation_span.add_event("data.input", {"input": user_text})
            invocation_span.add_event("data.output", {"response": full_response})

            # Harness-injected skill (slash-command with no explicit Skill tool call)
            cmd_skill = parse_command_skill(user_text)
            has_explicit_skill = any(
                tu.get("name") == "Skill"
                for am in turn.assistant_msgs
                for tu in iter_tool_uses(get_content(am))
            )
            if cmd_skill and not has_explicit_skill:
                _emit_skill_span(
                    tracer, cmd_skill,
                    session_id, turn_id, invocation_id,
                    service_name, sdk_version,
                    turn_start_ns, turn_end_ns,
                )

            parent_span_id = format(invocation_span.get_span_context().span_id, "016x")
            num_rounds = len(turn.assistant_msgs)
            total_tool_spans = 0

            for i, assistant_msg in enumerate(turn.assistant_msgs):
                _emit_inference_span(
                    tracer, assistant_msg, i, num_rounds, turn,
                    session_id, turn_id, invocation_id, model, user_text,
                    service_name, sdk_version, turn_start_ns,
                )

                tool_start_ns = _parse_timestamp_ns(get_timestamp(assistant_msg))
                for tool_use in iter_tool_uses(get_content(assistant_msg)):
                    _emit_tool_span(
                        tracer, tool_use, turn,
                        session_id, turn_id, invocation_id,
                        service_name, sdk_version,
                        tool_start_ns, turn_end_ns,
                        parent_invocation_span_id=parent_span_id,
                    )
                    total_tool_spans += 1

            logger.debug("%s: %d LLM rounds, %d tool spans", span_name_prefix, num_rounds, total_tool_spans)

    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_transcript(
    session_id: str,
    turns: List[Turn],
    tracer: trace.Tracer,
    sdk_version: str,
    service_name: str = SERVICE_NAME,
    user_name: Optional[str] = None,
    subagents: Optional[List[SubagentInfo]] = None,
) -> int:
    """Emit Monocle-compatible spans for a list of turns under a workflow root span.

    Returns the number of turns emitted (excludes subagent turns).
    """
    if not turns and not subagents:
        return 0

    workflow_start_ns = _parse_timestamp_ns(turns[0].start_time) if turns else None
    workflow_end_ns = _parse_timestamp_ns(turns[-1].end_time) if turns else None

    with _timed_span(
        tracer, "workflow",
        workflow_span_attrs(session_id, service_name, sdk_version, user_name),
        workflow_start_ns, workflow_end_ns,
    ) as workflow_span:
        workflow_span.set_status(StatusCode.OK)
        emitted = sum(
            1 for turn in turns
            if _emit_turn(tracer, turn, session_id, sdk_version, service_name, user_name)
        )
        if subagents:
            process_subagents(subagents, tracer, session_id, sdk_version, service_name, user_name)

    return emitted


def process_subagents(
    subagents: List[SubagentInfo],
    tracer: trace.Tracer,
    parent_session_id: str,
    sdk_version: str,
    service_name: str = SERVICE_NAME,
    user_name: Optional[str] = None,
) -> int:
    """Emit spans for subagent JSONL files under the current OTel context.

    The Agent tool is not available to subagents, so the hierarchy is always
    exactly one level deep: main session → subagents. All subagent JSONLs are
    stored flat under {session-uuid}/subagents/ regardless of which turn
    triggered them.

    Each subagent uses its agent_id as scope.agentic.session so its spans are
    distinguishable from the parent while sharing the same trace_id.

    Returns total subagent turns emitted.
    """
    total_emitted = 0
    for sa in subagents:
        msgs = read_subagent_jsonl(sa.jsonl_path)
        if not msgs:
            logger.debug("subagent %s: no messages", sa.agent_id)
            continue
        turns = build_turns(msgs)
        if not turns:
            logger.debug("subagent %s: no complete turns", sa.agent_id)
            continue
        prefix = f"Sub-Agent: {sa.agent_type}" if sa.agent_type != "sub-agent" else "Sub-Agent"
        for turn in turns:
            if _emit_turn(tracer, turn, sa.agent_id, sdk_version, service_name, user_name, span_name_prefix=prefix):
                total_emitted += 1
    return total_emitted


def process_transcript_file(
    session_id: str,
    transcript_path: Path,
    tracer: trace.Tracer,
    sdk_version: str,
    service_name: str = SERVICE_NAME,
    session_state: Optional[SessionState] = None,
    user_name: Optional[str] = None,
) -> tuple:
    """Read new JSONL from a transcript file, build turns, emit spans.

    Returns (emitted_count, updated_session_state).
    """
    if session_state is None:
        session_state = SessionState()
    msgs, session_state = read_new_jsonl(transcript_path, session_state)
    if not msgs:
        return 0, session_state
    turns = build_turns(msgs)
    if not turns:
        return 0, session_state
    emitted = process_transcript(
        session_id=session_id, turns=turns, tracer=tracer,
        sdk_version=sdk_version, service_name=service_name, user_name=user_name,
    )
    return emitted, session_state
