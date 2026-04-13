"""
Helper functions for Claude Code CLI transcript parsing.

Claude Code writes transcript JSONL files at:
  macOS/Linux: ~/.claude/projects/{hash}/{session}.jsonl
  Windows:     %APPDATA%\\Claude\\projects\\{hash}\\{session}.jsonl

These contain user/assistant messages, tool_use/tool_result blocks,
and subagent transcripts.

This module extracts structured data from those transcripts for span creation.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CLAUDE_CODE_AGENT_TYPE_KEY = "agent.claude_code"
CLAUDE_CODE_TOOL_TYPE_KEY = "tool.claude_code"
CLAUDE_CODE_MCP_TOOL_TYPE_KEY = "tool.mcp"
CLAUDE_CODE_SKILL_TYPE_KEY = "skill.claude_code"

MAX_CHARS = 20000


@dataclass
class SessionState:
    """Tracks incremental parsing position in a transcript file."""
    offset: int = 0
    buffer: str = ""
    turn_count: int = 0
    subagents_processed: List[str] = field(default_factory=list)


@dataclass
class Turn:
    """A user->assistant turn with associated tool calls and results."""
    user_msg: Dict[str, Any]
    assistant_msgs: List[Dict[str, Any]]
    tool_results_by_id: Dict[str, Any]


def get_content(msg: Dict[str, Any]) -> Any:
    if not isinstance(msg, dict):
        return None
    if "message" in msg and isinstance(msg.get("message"), dict):
        return msg["message"].get("content")
    return msg.get("content")


def get_role(msg: Dict[str, Any]) -> Optional[str]:
    t = msg.get("type")
    if t in ("user", "assistant"):
        return t
    m = msg.get("message")
    if isinstance(m, dict):
        r = m.get("role")
        if r in ("user", "assistant"):
            return r
    return None


def is_tool_result(msg: Dict[str, Any]) -> bool:
    role = get_role(msg)
    if role != "user":
        return False
    content = get_content(msg)
    if isinstance(content, list):
        return any(isinstance(x, dict) and x.get("type") == "tool_result" for x in content)
    return False


def iter_tool_results(content: Any) -> List[Dict[str, Any]]:
    out = []
    if isinstance(content, list):
        for x in content:
            if isinstance(x, dict) and x.get("type") == "tool_result":
                out.append(x)
    return out


def iter_tool_uses(content: Any) -> List[Dict[str, Any]]:
    out = []
    if isinstance(content, list):
        for x in content:
            if isinstance(x, dict) and x.get("type") == "tool_use":
                out.append(x)
    return out


def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for x in content:
            if isinstance(x, dict) and x.get("type") == "text":
                parts.append(x.get("text", ""))
            elif isinstance(x, str):
                parts.append(x)
        return "\n".join([p for p in parts if p])
    return ""


def truncate(s: str, max_chars: int = MAX_CHARS) -> str:
    if s is None:
        return ""
    return s[:max_chars]


def get_model(msg: Dict[str, Any]) -> str:
    m = msg.get("message")
    if isinstance(m, dict):
        return m.get("model") or "claude"
    return "claude"


def get_message_id(msg: Dict[str, Any]) -> Optional[str]:
    m = msg.get("message")
    if isinstance(m, dict):
        mid = m.get("id")
        if isinstance(mid, str) and mid:
            return mid
    return None


def get_usage(msg: Dict[str, Any]) -> Dict[str, int]:
    m = msg.get("message")
    if isinstance(m, dict):
        usage = m.get("usage", {})
        return {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
            "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
        }
    return {}


def read_new_jsonl(transcript_path: Path, ss: SessionState) -> Tuple[List[Dict[str, Any]], SessionState]:
    """Read only new bytes since last offset, handling partial lines."""
    if not transcript_path.exists():
        return [], ss

    with open(transcript_path, "rb") as f:
        f.seek(ss.offset)
        chunk = f.read()
        new_offset = f.tell()

    if not chunk:
        return [], ss

    text = chunk.decode("utf-8", errors="replace")
    combined = ss.buffer + text
    lines = combined.split("\n")
    ss.buffer = lines[-1]
    ss.offset = new_offset

    msgs: List[Dict[str, Any]] = []
    for line in lines[:-1]:
        line = line.strip()
        if not line:
            continue
        try:
            msgs.append(json.loads(line))
        except Exception:
            continue

    return msgs, ss


def build_turns(messages: List[Dict[str, Any]]) -> List[Turn]:
    """Group messages into turns (user -> assistant with tools)."""
    turns: List[Turn] = []
    current_user: Optional[Dict[str, Any]] = None
    assistant_order: List[str] = []
    assistant_latest: Dict[str, Dict[str, Any]] = {}
    tool_results_by_id: Dict[str, Any] = {}

    def flush_turn():
        nonlocal current_user, assistant_order, assistant_latest, tool_results_by_id
        if current_user is None or not assistant_latest:
            return
        assistants = [assistant_latest[mid] for mid in assistant_order if mid in assistant_latest]
        turns.append(Turn(
            user_msg=current_user,
            assistant_msgs=assistants,
            tool_results_by_id=dict(tool_results_by_id),
        ))

    for msg in messages:
        role = get_role(msg)

        if is_tool_result(msg):
            for tr in iter_tool_results(get_content(msg)):
                tid = tr.get("tool_use_id")
                if tid:
                    tool_results_by_id[str(tid)] = tr.get("content")
            continue

        if role == "user":
            flush_turn()
            current_user = msg
            assistant_order = []
            assistant_latest = {}
            tool_results_by_id = {}
            continue

        if role == "assistant":
            if current_user is None:
                continue
            mid = get_message_id(msg) or f"noid:{len(assistant_order)}"
            if mid not in assistant_latest:
                assistant_order.append(mid)
            assistant_latest[mid] = msg
            continue

    flush_turn()
    return turns


def parse_command_skill(user_text: str) -> Optional[Dict[str, str]]:
    """Detect harness-injected skill invocations from <command-name>/<command-message> tags.

    When a user types /skill-name in Claude Code CLI, the harness intercepts
    and injects the skill content directly as user message tags instead of
    going through the Tool: Skill call. This function detects those tags
    so we can emit a synthetic skill span.

    Returns dict with 'skill_name', 'plugin_name', 'command_name', 'args'
    or None if no skill command found.
    """
    # Match <command-name>/some-skill</command-name>
    cn_match = re.search(r"<command-name>/([^<]+)</command-name>", user_text)
    if not cn_match:
        return None

    command_name = cn_match.group(1).strip()

    # Match <command-message>...</command-message>
    cm_match = re.search(r"<command-message>([^<]+)</command-message>", user_text)
    command_message = cm_match.group(1).strip() if cm_match else command_name

    # Match <command-args>...</command-args>
    args_match = re.search(r"<command-args>([^<]*)</command-args>", user_text)
    args = args_match.group(1).strip() if args_match else ""

    # Parse plugin_name:skill_name from command_message
    if ":" in command_message:
        plugin_name, skill_name = command_message.split(":", 1)
    else:
        plugin_name = ""
        skill_name = command_message

    # Skip built-in CLI commands (clear, exit, help, etc.)
    builtins = {"clear", "exit", "help", "compact", "config", "mcp", "skills",
                "init", "login", "logout", "doctor", "review", "cost", "fast"}
    if skill_name in builtins:
        return None

    return {
        "skill_name": skill_name,
        "plugin_name": plugin_name,
        "command_name": command_name,
        "args": args,
    }


def classify_tool(tool_name: str) -> str:
    """Return span type based on tool name."""
    if tool_name == "Agent":
        return "agentic.invocation"
    elif tool_name == "Skill":
        return "agentic.skill.invocation"
    elif tool_name.startswith("mcp__"):
        return "agentic.mcp.invocation"
    else:
        return "agentic.tool.invocation"


def classify_tool_entity_type(tool_name: str) -> str:
    """Return entity type key based on tool name."""
    if tool_name == "Agent":
        return CLAUDE_CODE_AGENT_TYPE_KEY
    elif tool_name == "Skill":
        return CLAUDE_CODE_SKILL_TYPE_KEY
    elif tool_name.startswith("mcp__"):
        return CLAUDE_CODE_MCP_TOOL_TYPE_KEY
    else:
        return CLAUDE_CODE_TOOL_TYPE_KEY
