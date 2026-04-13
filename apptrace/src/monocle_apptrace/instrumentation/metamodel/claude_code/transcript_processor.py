"""
Claude Code transcript processor.

Parses Claude Code JSONL transcript files and emits OpenTelemetry spans
following the Monocle metamodel pattern with proper entity attributes.

This is invoked by the Claude Code Stop hook (not via monkey-patching,
since Claude Code is a CLI binary, not a Python library).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from monocle_apptrace.instrumentation.metamodel.claude_code._helper import (
    Turn,
    build_turns,
    classify_tool,
    classify_tool_entity_type,
    extract_text,
    get_content,
    get_message_id,
    get_model,
    get_usage,
    iter_tool_uses,
    parse_command_skill,
    read_new_jsonl,
    SessionState,
    CLAUDE_CODE_AGENT_TYPE_KEY,
    CLAUDE_CODE_SKILL_TYPE_KEY,
)

logger = logging.getLogger(__name__)

SERVICE_NAME = "claude-cli"


def _build_full_response(turn):
    """Build the complete turn response: assistant text + all tool outputs."""
    parts = []
    for assistant_msg in turn.assistant_msgs:
        text = extract_text(get_content(assistant_msg))
        if text:
            parts.append(text)
    for tool_id, tool_output in turn.tool_results_by_id.items():
        if tool_output:
            output_str = tool_output if isinstance(tool_output, str) else json.dumps(tool_output)
            parts.append(output_str)
    return "\n".join(parts)


def _emit_turn(tracer, turn, turn_num, session_id, sdk_version, service_name):
    """Emit spans for a single turn: agentic.turn -> inference + tool spans."""
    user_text = extract_text(get_content(turn.user_msg))

    if not turn.assistant_msgs:
        return False

    last_assistant = turn.assistant_msgs[-1]
    assistant_text = extract_text(get_content(last_assistant))
    full_response = _build_full_response(turn)
    model = get_model(turn.assistant_msgs[0])
    usage = get_usage(last_assistant)

    with tracer.start_as_current_span(
        name=f"Claude Code - Turn {turn_num}",
        attributes={
            "span.type": "agentic.turn",
            "span.subtype": "turn",
            "scope.agentic.session": session_id,
            "turn.number": turn_num,
            "entity.1.type": CLAUDE_CODE_AGENT_TYPE_KEY,
            "workflow.name": service_name,
            "monocle_apptrace.version": sdk_version,
            "monocle.service.name": service_name,
        }
    ) as turn_span:
        turn_span.set_status(StatusCode.OK)
        turn_span.add_event("data.input", {"input": user_text})
        turn_span.add_event("data.output", {"response": full_response})

        # Inference span
        with tracer.start_as_current_span(
            name="Claude Inference",
            attributes={
                "span.type": "inference",
                "scope.agentic.session": session_id,
                "entity.1.type": "inference.anthropic",
                "entity.1.provider_name": "anthropic",
                "entity.2.name": model,
                "entity.2.type": f"model.llm.{model}",
                "gen_ai.system": "anthropic",
                "gen_ai.request.model": model,
                "gen_ai.response.id": get_message_id(last_assistant) or "",
                "monocle_apptrace.version": sdk_version,
                "workflow.name": service_name,
            }
        ) as inference_span:
            inference_span.set_status(StatusCode.OK)
            inference_span.add_event("data.input", {"input": user_text})
            inference_span.add_event("data.output", {"response": assistant_text})
            metadata_attrs = {}
            if usage.get("output_tokens"):
                metadata_attrs["completion_tokens"] = usage["output_tokens"]
            if usage.get("input_tokens"):
                metadata_attrs["prompt_tokens"] = usage["input_tokens"]
            if usage.get("cache_read_tokens"):
                metadata_attrs["cache_read_tokens"] = usage["cache_read_tokens"]
            if usage.get("cache_creation_tokens"):
                metadata_attrs["cache_creation_tokens"] = usage["cache_creation_tokens"]
            if metadata_attrs:
                inference_span.add_event("metadata", metadata_attrs)

        # Detect harness-injected skill (slash command like /internal-comms)
        # These bypass Tool: Skill — the harness injects content via <command-name> tags
        cmd_skill = parse_command_skill(user_text)
        has_explicit_skill = any(
            tu.get("name") == "Skill"
            for am in turn.assistant_msgs
            for tu in iter_tool_uses(get_content(am))
        )
        if cmd_skill and not has_explicit_skill:
            skill_name = cmd_skill["skill_name"]
            skill_input = {"skill": skill_name}
            if cmd_skill["args"]:
                skill_input["args"] = cmd_skill["args"]
            if cmd_skill["plugin_name"]:
                skill_input["plugin"] = cmd_skill["plugin_name"]

            with tracer.start_as_current_span(
                name=f"Skill: {skill_name}",
                attributes={
                    "span.type": "agentic.skill.invocation",
                    "scope.agentic.session": session_id,
                    "entity.1.type": CLAUDE_CODE_SKILL_TYPE_KEY,
                    "entity.1.name": skill_name,
                    "entity.1.skill_name": skill_name,
                    **({"entity.1.skill_args": cmd_skill["args"]} if cmd_skill["args"] else {}),
                    **({"entity.1.plugin_name": cmd_skill["plugin_name"]} if cmd_skill["plugin_name"] else {}),
                    "entity.1.invocation": "harness",
                    "monocle_apptrace.version": sdk_version,
                    "workflow.name": service_name,
                },
            ) as skill_span:
                skill_span.set_status(StatusCode.OK)
                skill_span.add_event("data.input", {"input": json.dumps(skill_input)})
                skill_span.add_event("data.output", {"response": f"/{cmd_skill['command_name']}"})

        # Tool spans
        for assistant_msg in turn.assistant_msgs:
            for tool_use in iter_tool_uses(get_content(assistant_msg)):
                tool_id = tool_use.get("id", "")
                tool_name = tool_use.get("name", "unknown")
                tool_input = tool_use.get("input", {})
                tool_output = turn.tool_results_by_id.get(tool_id, "")

                span_type = classify_tool(tool_name)
                entity_type = classify_tool_entity_type(tool_name)

                input_str = json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input)
                output_str = tool_output if isinstance(tool_output, str) else json.dumps(tool_output) if tool_output else ""

                span_attrs = {
                    "span.type": span_type,
                    "scope.agentic.session": session_id,
                    "entity.1.type": entity_type,
                    "entity.1.name": tool_name,
                    "monocle_apptrace.version": sdk_version,
                    "workflow.name": service_name,
                }

                if tool_name == "Agent" and isinstance(tool_input, dict):
                    subagent_type = tool_input.get("subagent_type", "general-purpose")
                    span_attrs["entity.1.name"] = subagent_type
                    span_attrs["entity.1.description"] = tool_input.get("description", "")

                span_name = f"Tool: {tool_name}"
                if tool_name == "Skill" and isinstance(tool_input, dict):
                    skill_name = tool_input.get("skill", "unknown")
                    span_attrs["entity.1.name"] = skill_name
                    span_attrs["entity.1.skill_name"] = skill_name
                    if tool_input.get("args"):
                        span_attrs["entity.1.skill_args"] = tool_input.get("args")
                    span_name = f"Skill: {skill_name}"

                with tracer.start_as_current_span(
                    name=span_name,
                    attributes=span_attrs,
                ) as tool_span:
                    tool_span.set_status(StatusCode.OK)
                    tool_span.add_event("data.input", {"input": input_str})
                    tool_span.add_event("data.output", {"response": output_str})

    return True


def process_transcript(
    session_id: str,
    turns: List[Turn],
    tracer: trace.Tracer,
    sdk_version: str,
    service_name: str = SERVICE_NAME,
    start_turn: int = 0,
) -> int:
    """
    Emit Monocle-compatible spans for a list of turns.

    Creates a workflow root span wrapping all turn spans.
    Okahu requires this workflow span for span detail retrieval.

    Returns the number of turns emitted.
    """
    if not turns:
        return 0

    emitted = 0

    with tracer.start_as_current_span(
        name="workflow",
        attributes={
            "span.type": "workflow",
            "entity.1.name": service_name,
            "entity.1.type": "workflow.claude_code",
            "entity.2.type": "app_hosting.generic",
            "entity.2.name": "generic",
            "monocle_apptrace.version": sdk_version,
            "monocle_apptrace.language": "python",
            "workflow.name": service_name,
        }
    ) as workflow_span:
        workflow_span.set_status(StatusCode.OK)
        for i, turn in enumerate(turns):
            turn_num = start_turn + i + 1
            if _emit_turn(tracer, turn, turn_num, session_id, sdk_version, service_name):
                emitted += 1

    return emitted


def process_transcript_file(
    session_id: str,
    transcript_path: Path,
    tracer: trace.Tracer,
    sdk_version: str,
    service_name: str = SERVICE_NAME,
    session_state: Optional[SessionState] = None,
) -> tuple:
    """
    Higher-level API: read new JSONL from a transcript file, build turns, emit spans.

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
        session_id=session_id,
        turns=turns,
        tracer=tracer,
        sdk_version=sdk_version,
        service_name=service_name,
        start_turn=session_state.turn_count,
    )
    session_state.turn_count += len(turns)

    return emitted, session_state
