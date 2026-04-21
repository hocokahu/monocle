"""
Span attribute builders for Claude Code instrumentation.

Each function corresponds to one span type and returns the attribute dict
for that span. This mirrors the entities/ pattern used in ADK and LangGraph
but as plain functions rather than accessor-lambda dicts, since Claude Code
works from a parsed transcript rather than live method interception.
"""

import uuid
from typing import Any, Dict, Optional

from monocle_apptrace.instrumentation.metamodel.claude_code._helper import (
    CLAUDE_CODE_AGENT_TYPE_KEY,
    CLAUDE_CODE_MCP_TOOL_TYPE_KEY,
    CLAUDE_CODE_SKILL_TYPE_KEY,
    CLAUDE_CODE_TOOL_TYPE_KEY,
    classify_tool,
    classify_tool_entity_type,
)


# ---------------------------------------------------------------------------
# Description deriver — maps tool input to a human-readable summary
# ---------------------------------------------------------------------------

# Common input field names that carry meaningful descriptions, in priority order.
# Works for built-in Claude Code tools and any future/external tool that follows
# similar conventions — no tool-name hardcoding required.
_DESCRIPTION_FIELDS = ("description", "command", "query", "url", "file_path", "pattern", "path", "skill")


def tool_description(tool_name: str, tool_input: Any) -> Optional[str]:
    """Derive a concise description from a tool's input without hardcoding tool names.

    MCP tools get their description from the tool name itself (server / method).
    Everything else: try common descriptive field names in priority order.
    """
    if not isinstance(tool_input, dict):
        return None
    if tool_name.startswith("mcp__"):
        parts = tool_name.split("__", 2)
        return f"{parts[1]} / {parts[2]}" if len(parts) == 3 else tool_name
    for field in _DESCRIPTION_FIELDS:
        val = tool_input.get(field)
        if val and isinstance(val, str):
            return val[:120]
    return None


# ---------------------------------------------------------------------------
# Span attribute builders
# ---------------------------------------------------------------------------

_COMMON = ("monocle_apptrace.version", "workflow.name")


def _scopes(session_id: str, turn_id: Optional[str] = None, invocation_id: Optional[str] = None) -> Dict[str, Any]:
    s: Dict[str, Any] = {"scope.agentic.session": session_id}
    if turn_id:
        s["scope.agentic.turn"] = turn_id
    if invocation_id:
        s["scope.agentic.invocation"] = invocation_id
    return s


def workflow_span_attrs(
    session_id: str,
    service_name: str,
    sdk_version: str,
    user_name: Optional[str] = None,
) -> Dict[str, Any]:
    attrs: Dict[str, Any] = {
        "span.type": "workflow",
        **_scopes(session_id),
        "entity.1.name": service_name,
        "entity.1.type": "workflow.claude_code",
        "entity.2.type": "app_hosting.generic",
        "entity.2.name": "generic",
        "monocle_apptrace.version": sdk_version,
        "monocle_apptrace.language": "python",
        "workflow.name": service_name,
    }
    if user_name:
        attrs["user.name"] = user_name
    return attrs


def turn_span_attrs(
    session_id: str,
    turn_id: str,
    service_name: str,
    sdk_version: str,
    user_name: Optional[str] = None,
) -> Dict[str, Any]:
    attrs: Dict[str, Any] = {
        "span.type": "agentic.turn",
        "span.subtype": "turn",
        **_scopes(session_id, turn_id),
        "entity.1.type": CLAUDE_CODE_AGENT_TYPE_KEY,
        "entity.1.name": "Claude",
        "workflow.name": service_name,
        "monocle_apptrace.version": sdk_version,
        "monocle.service.name": service_name,
    }
    if user_name:
        attrs["user.name"] = user_name
    return attrs


def invocation_span_attrs(
    session_id: str,
    turn_id: str,
    invocation_id: str,
    service_name: str,
    sdk_version: str,
) -> Dict[str, Any]:
    return {
        "span.type": "agentic.invocation",
        **_scopes(session_id, turn_id, invocation_id),
        "entity.1.type": CLAUDE_CODE_AGENT_TYPE_KEY,
        "entity.1.name": "Claude",
        "workflow.name": service_name,
        "monocle_apptrace.version": sdk_version,
    }


def inference_span_attrs(
    session_id: str,
    turn_id: str,
    invocation_id: str,
    model: str,
    msg_id: str,
    service_name: str,
    sdk_version: str,
) -> Dict[str, Any]:
    return {
        "span.type": "inference",
        **_scopes(session_id, turn_id, invocation_id),
        "entity.1.type": "inference.anthropic",
        "entity.1.provider_name": "anthropic",
        "entity.2.name": model,
        "entity.2.type": f"model.llm.{model}",
        "gen_ai.system": "anthropic",
        "gen_ai.request.model": model,
        "gen_ai.response.id": msg_id,
        "monocle_apptrace.version": sdk_version,
        "workflow.name": service_name,
    }


def tool_span_attrs(
    session_id: str,
    turn_id: str,
    invocation_id: str,
    tool_name: str,
    tool_input: Any,
    service_name: str,
    sdk_version: str,
    parent_invocation_span_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build attributes for a tool/agent/MCP/skill span.

    For Agent tool calls the invocation scope is replaced with a fresh UUID so
    the NarrativeGraph builder treats the subagent as a separate invocation.
    """
    attrs: Dict[str, Any] = {
        "span.type": classify_tool(tool_name),
        **_scopes(session_id, turn_id, invocation_id),
        "entity.1.type": classify_tool_entity_type(tool_name),
        "entity.1.name": tool_name,
        "monocle_apptrace.version": sdk_version,
        "workflow.name": service_name,
    }
    desc = tool_description(tool_name, tool_input)
    if desc:
        attrs["entity.1.description"] = desc

    if tool_name == "Agent" and isinstance(tool_input, dict):
        subagent_type = tool_input.get("subagent_type") or "sub-agent"
        attrs["entity.1.name"] = subagent_type
        attrs["entity.1.description"] = tool_input.get("description", "")
        if tool_input.get("model"):
            attrs["entity.1.model"] = tool_input["model"]
        attrs["entity.1.from_agent"] = "Claude"
        if parent_invocation_span_id:
            attrs["entity.1.from_agent_span_id"] = parent_invocation_span_id
        attrs["scope.agentic.invocation"] = str(uuid.uuid4())

    elif tool_name == "Skill" and isinstance(tool_input, dict):
        skill_nm = tool_input.get("skill", "unknown")
        attrs["entity.1.name"] = skill_nm
        attrs["entity.1.skill_name"] = skill_nm
        if tool_input.get("args"):
            attrs["entity.1.skill_args"] = tool_input["args"]

    return attrs


def skill_span_attrs(
    session_id: str,
    turn_id: str,
    invocation_id: str,
    skill_name: str,
    plugin_name: str,
    args: str,
    service_name: str,
    sdk_version: str,
) -> Dict[str, Any]:
    """Attributes for a harness-injected skill span (slash-command, no Skill tool call)."""
    attrs: Dict[str, Any] = {
        "span.type": "agentic.skill.invocation",
        **_scopes(session_id, turn_id, invocation_id),
        "entity.1.type": CLAUDE_CODE_SKILL_TYPE_KEY,
        "entity.1.name": skill_name,
        "entity.1.skill_name": skill_name,
        "entity.1.invocation": "harness",
        "monocle_apptrace.version": sdk_version,
        "workflow.name": service_name,
    }
    if args:
        attrs["entity.1.skill_args"] = args
    if plugin_name:
        attrs["entity.1.plugin_name"] = plugin_name
    return attrs
