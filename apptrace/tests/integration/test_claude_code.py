"""
Integration tests for Claude Code CLI transcript processing.

Tests that the transcript processor emits proper Monocle-compatible spans
with correct entity attributes, events, and hierarchy.

Test 1: Prompt/Response - inference span with model, tokens
Test 2: Bash Tool Call - agentic.tool.invocation span
Test 3: Subagent Call - agentic.invocation span
"""

import json
import tempfile
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import StatusCode

from monocle_apptrace.instrumentation.metamodel.claude_code._helper import build_turns
from monocle_apptrace.instrumentation.metamodel.claude_code.transcript_processor import (
    process_transcript,
    process_transcript_file,
)

SDK_VERSION = "0.7.6"
SESSION_ID = "test-session-001"
SERVICE_NAME = "claude-cli"


@pytest.fixture(scope="function")
def setup():
    """Set up a tracer with InMemorySpanExporter for test verification."""
    resource = Resource.create({"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    memory_exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(memory_exporter))

    tracer = provider.get_tracer("monocle.claude-code.test", "1.0.0")

    yield memory_exporter, tracer

    provider.shutdown()


def _assert_workflow_span(spans):
    """Verify a workflow root span exists with correct attributes and status."""
    for span in spans:
        attrs = span.attributes
        if attrs.get("span.type") == "workflow":
            assert attrs["entity.1.name"] == SERVICE_NAME
            assert attrs["entity.1.type"] == "workflow.claude_code"
            assert attrs["entity.2.type"] == "app_hosting.generic"
            assert attrs["monocle_apptrace.version"] == SDK_VERSION
            assert span.status.status_code == StatusCode.OK
            return
    raise AssertionError("workflow root span not found")


def _assert_all_spans_have_session(spans):
    """Verify all non-workflow spans have scope.agentic.session."""
    for span in spans:
        attrs = span.attributes
        if attrs.get("span.type") == "workflow":
            continue
        assert attrs.get("scope.agentic.session") == SESSION_ID, \
            f"span '{span.name}' (type={attrs.get('span.type')}) missing scope.agentic.session"


def _assert_all_spans_status_ok(spans):
    """Verify all spans have StatusCode.OK."""
    for span in spans:
        assert span.status.status_code == StatusCode.OK, \
            f"span '{span.name}' has status {span.status.status_code}, expected OK"


# --- Sample JSONL messages ---

def _user_msg(text):
    return {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
        "timestamp": "2026-04-01T10:00:00Z",
    }


def _assistant_msg(text, model="claude-sonnet-4-20250514", msg_id="msg_001",
                   input_tokens=100, output_tokens=50,
                   cache_read=80, cache_creation=10, tool_uses=None):
    content = []
    if tool_uses:
        content.extend(tool_uses)
    content.append({"type": "text", "text": text})
    return {
        "type": "assistant",
        "message": {
            "id": msg_id,
            "role": "assistant",
            "model": model,
            "content": content,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
            },
        },
        "timestamp": "2026-04-01T10:00:01Z",
    }


def _tool_result(tool_use_id, content):
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
            ],
        },
    }


# =============================================================================
# Test 1: Prompt/Response - inference span
# =============================================================================

def test_prompt_response_inference(setup):
    """Verify inference span with model, tokens, and cache tokens."""
    memory_exporter, tracer = setup

    messages = [
        _user_msg("What is Python?"),
        _assistant_msg(
            "Python is a programming language.",
            model="claude-sonnet-4-20250514",
            msg_id="msg_inference_001",
            input_tokens=150,
            output_tokens=42,
            cache_read=120,
            cache_creation=15,
        ),
    ]

    turns = build_turns(messages)
    assert len(turns) == 1

    emitted = process_transcript(
        session_id=SESSION_ID,
        turns=turns,
        tracer=tracer,
        sdk_version=SDK_VERSION,
        service_name=SERVICE_NAME,
    )
    assert emitted == 1

    spans = memory_exporter.get_finished_spans()

    _assert_workflow_span(spans)
    _assert_all_spans_status_ok(spans)
    _assert_all_spans_have_session(spans)

    found_turn = False
    found_inference = False

    for span in spans:
        attrs = span.attributes

        if attrs.get("span.type") == "agentic.turn":
            found_turn = True
            assert attrs["entity.1.type"] == "agent.claude_code"
            assert attrs["scope.agentic.session"] == SESSION_ID
            event_names = [e.name for e in span.events]
            assert "data.input" in event_names
            assert "data.output" in event_names

        if attrs.get("span.type") == "inference":
            found_inference = True
            assert attrs["entity.1.type"] == "inference.anthropic"
            assert attrs["entity.1.provider_name"] == "anthropic"
            assert attrs["entity.2.name"] == "claude-sonnet-4-20250514"
            assert attrs["entity.2.type"] == "model.llm.claude-sonnet-4-20250514"
            assert attrs["scope.agentic.session"] == SESSION_ID

            event_names = [e.name for e in span.events]
            assert "metadata" in event_names
            for event in span.events:
                if event.name == "metadata":
                    assert event.attributes["completion_tokens"] == 42
                    # prompt_tokens = input_tokens + cache_read + cache_creation (full context)
                    assert event.attributes["prompt_tokens"] == 285  # 150 + 120 + 15
                    assert event.attributes["total_tokens"] == 327   # 285 + 42
                    assert event.attributes["cache_read_tokens"] == 120
                    assert event.attributes["cache_creation_tokens"] == 15

    assert found_turn, "agentic.turn span not found"
    assert found_inference, "inference span not found"


# =============================================================================
# Test 2: Bash Tool Call - agentic.tool.invocation span
# =============================================================================

BASH_OUTPUT = "total 42\ndrwxr-xr-x  5 user  staff  160 Apr  1 10:00 .\n"

def test_bash_tool_call(setup):
    """Verify agentic.tool.invocation span for Bash tool with full output."""
    memory_exporter, tracer = setup

    bash_tool_use = {
        "type": "tool_use",
        "id": "tool_bash_001",
        "name": "Bash",
        "input": {"command": "ls -la", "description": "List files"},
    }

    messages = [
        _user_msg("List the files in the current directory"),
        _assistant_msg(
            "Here are the files:",
            tool_uses=[bash_tool_use],
            msg_id="msg_tool_001",
        ),
        _tool_result("tool_bash_001", BASH_OUTPUT),
    ]

    turns = build_turns(messages)
    assert len(turns) == 1

    emitted = process_transcript(
        session_id=SESSION_ID,
        turns=turns,
        tracer=tracer,
        sdk_version=SDK_VERSION,
        service_name=SERVICE_NAME,
    )
    assert emitted == 1

    spans = memory_exporter.get_finished_spans()

    _assert_workflow_span(spans)
    _assert_all_spans_status_ok(spans)
    _assert_all_spans_have_session(spans)

    found_tool = False
    found_turn = False
    for span in spans:
        attrs = span.attributes

        if attrs.get("span.type") == "agentic.turn":
            found_turn = True
            # Turn response should include assistant text + tool output (no truncation)
            for event in span.events:
                if event.name == "data.output":
                    response = event.attributes["response"]
                    assert "Here are the files:" in response
                    assert BASH_OUTPUT in response, \
                        f"Turn response missing tool output. Got: {response!r}"

        if attrs.get("span.type") == "agentic.tool.invocation":
            found_tool = True
            assert attrs["entity.1.type"] == "tool.claude_code"
            assert attrs["entity.1.name"] == "Bash"
            assert attrs["scope.agentic.session"] == SESSION_ID

            for event in span.events:
                if event.name == "data.input":
                    assert "ls -la" in event.attributes["input"]
                if event.name == "data.output":
                    # Full output, no truncation
                    assert event.attributes["response"] == BASH_OUTPUT

    assert found_turn, "agentic.turn span not found"
    assert found_tool, "agentic.tool.invocation span not found"


# =============================================================================
# Test 3: Subagent Call - agentic.invocation span
# =============================================================================

def test_subagent_call(setup):
    """Verify agentic.invocation span for Agent/subagent tool call."""
    memory_exporter, tracer = setup

    agent_tool_use = {
        "type": "tool_use",
        "id": "tool_agent_001",
        "name": "Agent",
        "input": {
            "subagent_type": "Explore",
            "description": "Search codebase",
            "prompt": "Find all Python files with async functions",
        },
    }

    messages = [
        _user_msg("Find all async functions in the codebase"),
        _assistant_msg(
            "I found several async functions.",
            tool_uses=[agent_tool_use],
            msg_id="msg_agent_001",
        ),
        _tool_result("tool_agent_001", "Found 15 files with async functions."),
    ]

    turns = build_turns(messages)
    assert len(turns) == 1

    emitted = process_transcript(
        session_id=SESSION_ID,
        turns=turns,
        tracer=tracer,
        sdk_version=SDK_VERSION,
        service_name=SERVICE_NAME,
    )
    assert emitted == 1

    spans = memory_exporter.get_finished_spans()

    _assert_workflow_span(spans)
    _assert_all_spans_status_ok(spans)
    _assert_all_spans_have_session(spans)

    found_agent = False
    for span in spans:
        attrs = span.attributes

        # Match the Agent subagent span specifically (not the "Claude Invocation" span,
        # which also has span.type="agentic.invocation" but entity.1.name="Claude")
        if attrs.get("span.type") == "agentic.invocation" and attrs.get("entity.1.name") == "Explore":
            found_agent = True
            assert attrs["entity.1.type"] == "agent.claude_code"
            assert attrs["scope.agentic.session"] == SESSION_ID
            # Delegation link: enables DELEGATES_TO edge in NarrativeGraph
            assert attrs["entity.1.from_agent"] == "Claude"
            assert attrs["entity.1.from_agent_span_id"]  # non-empty hex span id
            # Each Agent span gets its own invocation scope so the graph builder
            # doesn't re-process the parent Claude's tool spans under this anchor.
            assert attrs["scope.agentic.invocation"] != attrs["scope.agentic.turn"]

    assert found_agent, "agentic.invocation span for 'Explore' subagent not found"


# =============================================================================
# Test: File-based processing
# =============================================================================

def test_process_transcript_file(setup):
    """Verify end-to-end file-based processing with JSONL transcript."""
    memory_exporter, tracer = setup

    messages = [
        _user_msg("Hello"),
        _assistant_msg("Hi there!", msg_id="msg_file_001"),
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
        transcript_path = Path(f.name)

    try:
        emitted, state = process_transcript_file(
            session_id=SESSION_ID,
            transcript_path=transcript_path,
            tracer=tracer,
            sdk_version=SDK_VERSION,
            service_name=SERVICE_NAME,
        )
        assert emitted == 1
        assert state.offset > 0

        emitted2, state2 = process_transcript_file(
            session_id=SESSION_ID,
            transcript_path=transcript_path,
            tracer=tracer,
            sdk_version=SDK_VERSION,
            service_name=SERVICE_NAME,
            session_state=state,
        )
        assert emitted2 == 0
    finally:
        transcript_path.unlink(missing_ok=True)
