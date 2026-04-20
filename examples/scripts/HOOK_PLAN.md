# Monocle Claude Code Hook - Design Document

## Overview

This document outlines the design for a Monocle hook that observes Claude Code CLI sessions, capturing traces with proper span hierarchy, session correlation, and subagent tracking.

### Goals

1. **Full observability** - Capture all Claude Code activity: inference, tool calls, subagents
2. **Session correlation** - Group all spans under `agentic.session` scope
3. **Subagent hierarchy** - Track parent-child relationships between main agent and subagents
4. **Token tracking** - Capture input/output tokens, cache usage
5. **Monocle-native spans** - Use proper span types from Monocle's metamodel

### Non-Goals

- Real-time streaming (post-hoc transcript parsing is sufficient)
- Multiple hook points (single Stop hook keeps it simple)

---

## Claude Code Hook System

### Available Hooks

| Hook | When Fired | Use Case |
|------|------------|----------|
| `PreToolUse` | Before a tool executes | Validation, logging |
| `PostToolUse` | After a tool executes | Result processing |
| `Notification` | On notifications | Status updates |
| `Stop` | Session/turn ends | **Our hook point** |

### Hook Payload (Stop)

```json
{
  "sessionId": "5dfd59f4-7eee-4de8-8c1c-c77ab630b1b4",
  "transcriptPath": "~/.claude/projects/{project-hash}/{session-id}.jsonl",
  "hook_type": "Stop"
}
```

### Configuration

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "python3 ~/.claude/hooks/monocle_hook.py"
      }
    ]
  }
}
```

---

## Transcript File Structure

### Locations

| Platform | Main Transcript | Subagent Transcripts |
|----------|-----------------|----------------------|
| **macOS/Linux** | `~/.claude/projects/{project-hash}/{session-id}.jsonl` | `~/.claude/projects/{project-hash}/{session-id}/subagents/agent-{agent-id}.jsonl` |
| **Windows** | `%APPDATA%\Claude\projects\{project-hash}\{session-id}.jsonl` | `%APPDATA%\Claude\projects\{project-hash}\{session-id}\subagents\agent-{agent-id}.jsonl` |

### JSONL Record Types

#### User Message
```json
{
  "type": "user",
  "sessionId": "5dfd59f4-...",
  "uuid": "73658d6e-...",
  "parentUuid": null,
  "timestamp": "2026-02-26T21:59:19.756Z",
  "message": {
    "role": "user",
    "content": "..."
  }
}
```

#### Assistant Message
```json
{
  "type": "assistant",
  "sessionId": "5dfd59f4-...",
  "uuid": "abc123...",
  "parentUuid": "73658d6e-...",
  "timestamp": "2026-02-26T21:59:25.123Z",
  "message": {
    "role": "assistant",
    "model": "claude-opus-4-5-20251101",
    "id": "msg_vrtx_01B1zgjy38Ffaif5pN2xz7VC",
    "content": [
      {"type": "text", "text": "I'll help you..."},
      {"type": "tool_use", "id": "tool_123", "name": "Read", "input": {"file_path": "/path/to/file"}}
    ],
    "usage": {
      "input_tokens": 1500,
      "output_tokens": 250,
      "cache_creation_input_tokens": 759,
      "cache_read_input_tokens": 11282
    }
  }
}
```

#### Tool Result (appears as user message)
```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "tool_123",
        "content": "file contents here..."
      }
    ]
  }
}
```

#### Subagent Record (in subagents/*.jsonl)
```json
{
  "sessionId": "5dfd59f4-...",
  "agentId": "a4bf810ad314b91c1",
  "slug": "happy-stirring-blossom",
  "isSidechain": true,
  "parentToolUseID": "toolu_abc123",
  "message": {...}
}
```

---

## Monocle Span Mapping

### Transcript JSON → Monocle Span Mapping

The table below shows exactly how each field in the Claude Code transcript JSONL (`~/.claude/projects/{hash}/{session}.jsonl`) maps to Monocle span attributes.

#### Workflow Span (root)

This span wraps all turns. It is NOT derived from any transcript JSON — it is synthesized by the processor.

| Span Attribute | Source | Example Value |
|---|---|---|
| `span.name` | hardcoded | `"workflow"` |
| `span.type` | hardcoded | `"workflow"` |
| `entity.1.name` | env `MONOCLE_SERVICE_NAME` or default | `"claude-cli"` |
| `entity.1.type` | hardcoded | `"workflow.claude_code"` |
| `entity.2.type` | hardcoded | `"app_hosting.generic"` |
| `entity.2.name` | hardcoded | `"generic"` |
| `monocle_apptrace.version` | `importlib.metadata.version("monocle_apptrace")` | `"0.7.6"` |
| `monocle_apptrace.language` | hardcoded | `"python"` |
| `workflow.name` | env `MONOCLE_SERVICE_NAME` or default | `"claude-cli"` |
| `status.code` | hardcoded | `"ok"` |

#### Turn Span (`agentic.turn`)

One per user→assistant exchange. Parent: workflow span.

| Span Attribute | Transcript JSON Field | Example Value |
|---|---|---|
| `span.name` | derived from turn index | `"Claude Code - Turn 1"` |
| `span.type` | hardcoded | `"agentic.turn"` |
| `span.subtype` | hardcoded | `"turn"` |
| `scope.agentic.session` | hook payload `sessionId` | `"5dfd59f4-7eee-..."` |
| `turn.number` | sequential counter (1-based) | `1` |
| `entity.1.type` | hardcoded | `"agent.claude_code"` |
| `workflow.name` | env or default | `"claude-cli"` |
| `monocle.service.name` | env or default | `"claude-cli"` |
| `monocle_apptrace.version` | SDK version | `"0.7.6"` |
| event `data.input` → `input` | user msg → `message.content` (text extracted) | `"hi"` |
| event `data.output` → `response` | assistant text + all `tool_result.content` joined | `"Hello! How can I help?"` |
| `status.code` | hardcoded | `"ok"` |

#### Inference Span (`inference`)

One per turn (uses last assistant message). Parent: turn span.

| Span Attribute | Transcript JSON Field | Example Value |
|---|---|---|
| `span.name` | hardcoded | `"Claude Inference"` |
| `span.type` | hardcoded | `"inference"` |
| `scope.agentic.session` | hook payload `sessionId` | `"5dfd59f4-7eee-..."` |
| `entity.1.type` | hardcoded | `"inference.anthropic"` |
| `entity.1.provider_name` | hardcoded | `"anthropic"` |
| `entity.2.name` | `message.model` | `"claude-sonnet-4-20250514"` |
| `entity.2.type` | `"model.llm." + message.model` | `"model.llm.claude-sonnet-4-20250514"` |
| `gen_ai.system` | hardcoded | `"anthropic"` |
| `gen_ai.request.model` | `message.model` | `"claude-sonnet-4-20250514"` |
| `gen_ai.response.id` | `message.id` | `"msg_vrtx_01B1zgjy..."` |
| event `data.input` → `input` | user msg → `message.content` (text) | `"hi"` |
| event `data.output` → `response` | assistant `message.content` (text only, no tools) | `"Hello!"` |
| event `metadata` → `completion_tokens` | `message.usage.output_tokens` | `250` |
| event `metadata` → `prompt_tokens` | `message.usage.input_tokens` | `1500` |
| event `metadata` → `cache_read_tokens` | `message.usage.cache_read_input_tokens` | `11282` |
| event `metadata` → `cache_creation_tokens` | `message.usage.cache_creation_input_tokens` | `759` |
| `status.code` | hardcoded | `"ok"` |

#### Tool Span (`agentic.tool.invocation`)

One per `tool_use` block (Read, Write, Bash, Edit, Glob, Grep, etc.). Parent: turn span.

| Span Attribute | Transcript JSON Field | Example Value |
|---|---|---|
| `span.name` | `"Tool: " + content[].name` | `"Tool: Bash"` |
| `span.type` | hardcoded | `"agentic.tool.invocation"` |
| `scope.agentic.session` | hook payload `sessionId` | `"5dfd59f4-7eee-..."` |
| `entity.1.type` | hardcoded | `"tool.claude_code"` |
| `entity.1.name` | `content[].name` | `"Bash"` |
| event `data.input` → `input` | `content[].input` (JSON stringified) | `'{"command": "ls"}'` |
| event `data.output` → `response` | matched `tool_result.content` by `tool_use_id` | `"README.md\napptrace\n..."` |
| `status.code` | hardcoded | `"ok"` |

#### Agent Span (`agentic.invocation`)

One per `tool_use` where `name == "Agent"`. Parent: turn span.

| Span Attribute | Transcript JSON Field | Example Value |
|---|---|---|
| `span.name` | hardcoded prefix + subagent_type | `"Sub-Agent: Explore"` |
| `span.type` | hardcoded | `"agentic.invocation"` |
| `scope.agentic.session` | hook payload `sessionId` | `"5dfd59f4-7eee-..."` |
| `entity.1.type` | hardcoded | `"agent.claude_code"` |
| `entity.1.name` | `content[].input.subagent_type` | `"Explore"` |
| `entity.1.description` | `content[].input.description` | `"Find HOOK_PLAN.md location"` |
| `entity.1.model` | `content[].input.model` (if present) | `"haiku"` |
| `entity.1.from_agent` | hardcoded | `"Claude"` |
| `entity.1.from_agent_span_id` | parent invocation span_id | `"70fb8834d8058664"` |
| event `data.input` → `input` | `content[].input` (JSON stringified) | `'{"subagent_type":...}'` |
| event `data.output` → `response` | matched `tool_result.content` by `tool_use_id` | `"The result is 2."` |
| `status.code` | hardcoded | `"ok"` |

#### MCP Tool Span (`agentic.mcp.invocation`)

One per `tool_use` where `name.startswith("mcp__")`. Parent: turn span.

| Span Attribute | Transcript JSON Field | Example Value |
|---|---|---|
| `span.name` | `"Tool: " + content[].name` | `"Tool: mcp__okahu-mcp__get_traces"` |
| `span.type` | hardcoded | `"agentic.mcp.invocation"` |
| `scope.agentic.session` | hook payload `sessionId` | `"5dfd59f4-7eee-..."` |
| `entity.1.type` | hardcoded | `"tool.mcp"` |
| `entity.1.name` | `content[].name` | `"mcp__okahu-mcp__get_traces"` |
| event `data.input` → `input` | `content[].input` (JSON stringified) | `'{"workflow_name":...}'` |
| event `data.output` → `response` | matched `tool_result.content` by `tool_use_id` | `'{"traces": [...]}'` |
| `status.code` | hardcoded | `"ok"` |

### Tool Classification Logic

```
tool_name == "Agent"       → span.type: agentic.invocation,     entity: agent.claude_code
tool_name.startswith("mcp__") → span.type: agentic.mcp.invocation, entity: tool.mcp
everything else            → span.type: agentic.tool.invocation, entity: tool.claude_code
```

### JSON-to-Span ID Linkage

| Transcript JSON | Used For |
|---|---|
| `content[].id` (tool_use) | Matching with `tool_result.tool_use_id` to pair input↔output |
| hook payload `sessionId` | `scope.agentic.session` on all non-workflow spans |
| hook payload `transcriptPath` | File to read JSONL from |
| `message.id` | `gen_ai.response.id` on inference span |
| `message.model` | `gen_ai.request.model` + entity type on inference span |
| `message.usage.*` | Token counts in inference `metadata` event |

---

## Real Example: JSONL to Spans

This section shows a real Claude Code round (from trace `0xfc8ac4b80f9a8ed695f83887a431e853`)
end-to-end: the raw JSONL lines the hook reads, the merge logic, and the Monocle spans produced.

### Source JSONL Lines (Round 1, `msg_01NusABygsi6HGenpY8WUMmw`)

Claude Code writes **streaming snapshots** — multiple JSONL lines for a single LLM call.
Each assistant snapshot adds content blocks as they arrive. The hook's `build_turns` merges
them into one logical assistant message before emitting spans.

| Line | Role | Content | Key Fields |
|------|------|---------|------------|
| 251 | user | `"i m not asking the id itself..."` (user prompt) | — |
| 252 | assistant | `thinking` block (streaming snapshot 1) | `id: msg_01NusA...`, `output_tokens: 39` |
| 253 | assistant | `text`: "You're right — I need to look at..." (snapshot 2) | same `id`, same `output_tokens: 39` |
| 254 | assistant | `tool_use`: Bash `wc -l` (snapshot 3) | same `id`, `tool_id: toolu_01LN8G...` |
| 257 | user | `tool_result` for `toolu_01LN8G...` | Bash output: `253 ...jsonl` |
| 258 | assistant | `tool_use`: Grep `trace_viewer` (snapshot 4, **final**) | same `id`, `stop_reason: tool_use`, `output_tokens: 1259` |
| 260 | user | `tool_result` for `toolu_01EsZk...` | Grep output: `Found 1 file` |

> **Lines 255–256, 259 are unrelated** (other message types); line numbers are not contiguous
> because the JSONL file interleaves all session activity.

### How `build_turns` Merges Streaming Snapshots

Lines 252, 253, 254, and 258 all share the same `message.id` (`msg_01NusABygsi6HGenpY8WUMmw`).
`build_turns` merges them into **one** assistant message:

```
Merged assistant message:
  content[0]: thinking  (from line 252)    ← skipped by span builder
  content[1]: text      (from line 253)    ← inference span output
  content[2]: tool_use  (from line 254)    ← Bash tool span input
  content[3]: tool_use  (from line 258)    ← Grep tool span input
  stop_reason: tool_use                    (from line 258, the final snapshot)
  output_tokens: 1259                      (from line 258, the final snapshot)
```

The rule: **last snapshot wins** for `usage`, `stop_reason`, and `model`. Content blocks are
accumulated across all snapshots for the same `message.id`.

### 3 Spans Produced

From this single merged message + its tool results, the hook emits 3 spans:

#### Span 1: Inference

```json
{
  "name": "Claude Inference (1/10)",
  "context": {
    "trace_id": "0xfc8ac4b80f9a8ed695f83887a431e853",
    "span_id": "0xac3ea585a842630c"
  },
  "parent_id": "0x7efa8f96eb5d5fa5",
  "attributes": {
    "span.type": "inference",
    "entity.2.name": "claude-opus-4-6",
    "entity.2.type": "model.llm.claude-opus-4-6",
    "gen_ai.request.model": "claude-opus-4-6",
    "gen_ai.response.id": "msg_01NusABygsi6HGenpY8WUMmw"
  },
  "events": [
    { "name": "data.input",  "attributes": { "input": "i m not asking the id itself..." } },
    { "name": "data.output", "attributes": { "response": "You're right — I need to look at..." } },
    { "name": "metadata",    "attributes": { "finish_reason": "tool_use", "completion_tokens": 1259 } }
  ]
}
```

**Field mapping:**
- `gen_ai.response.id` ← `message.id` from line 258
- `data.input` ← user message from line 251
- `data.output` ← first `text` block from merged content (line 253)
- `completion_tokens` ← `message.usage.output_tokens` from line 258 (final snapshot)

#### Span 2: Tool — Bash

```json
{
  "name": "Tool: Bash",
  "context": {
    "trace_id": "0xfc8ac4b80f9a8ed695f83887a431e853",
    "span_id": "0x456f256e3f5237a1"
  },
  "parent_id": "0x7efa8f96eb5d5fa5",
  "attributes": {
    "span.type": "agentic.tool.invocation",
    "entity.1.type": "tool.claude_code",
    "entity.1.name": "Bash",
    "entity.1.description": "Check total lines in session JSONL"
  },
  "events": [
    { "name": "data.input",  "attributes": { "input": "{\"command\": \"wc -l ~/.claude/projects/...jsonl\", \"description\": \"Check total lines in session JSONL\"}" } },
    { "name": "data.output", "attributes": { "response": "     253 /Users/.../3bd7efcf-...jsonl" } }
  ]
}
```

**Field mapping:**
- `entity.1.name` ← `tool_use.name` from line 254's content block
- `entity.1.description` ← `tool_use.input.description` (Bash-specific)
- `data.input` ← full `tool_use.input` JSON from line 254
- `data.output` ← `tool_result.content` from line 257 (matched by `tool_use_id: toolu_01LN8G...`)

#### Span 3: Tool — Grep

```json
{
  "name": "Tool: Grep",
  "context": {
    "trace_id": "0xfc8ac4b80f9a8ed695f83887a431e853",
    "span_id": "0x652a385e1eda6dc6"
  },
  "parent_id": "0x7efa8f96eb5d5fa5",
  "attributes": {
    "span.type": "agentic.tool.invocation",
    "entity.1.type": "tool.claude_code",
    "entity.1.name": "Grep",
    "entity.1.description": "trace_viewer in .claude/scripts"
  },
  "events": [
    { "name": "data.input",  "attributes": { "input": "{\"pattern\": \"trace_viewer\", \"path\": \".claude/scripts\", \"output_mode\": \"files_with_matches\"}" } },
    { "name": "data.output", "attributes": { "response": "Found 1 file\n.claude/scripts/trace_viewer.py" } }
  ]
}
```

**Field mapping:**
- `entity.1.name` ← `tool_use.name` from line 258's content block
- `entity.1.description` ← Bash has `description` field; Grep doesn't, so the hook synthesizes it from the input params
- `data.input` ← full `tool_use.input` JSON from line 258
- `data.output` ← `tool_result.content` from line 260 (matched by `tool_use_id: toolu_01EsZk...`)

### Key Observations

1. **All 3 spans share the same `parent_id`** (`0x7efa8f96eb5d5fa5`) — this is the
   `agentic.turn` span that groups one round of user→assistant→tools.

2. **Tool spans are siblings of the inference span**, not children — they represent
   the tools the model chose to call, each as a separate invocation under the turn.

3. **Streaming merge is invisible** in the output — consumers see one clean inference
   span even though 4 JSONL lines contributed to it.

4. **`tool_use_id` is the join key** between a `tool_use` content block (in the assistant
   message) and its `tool_result` (in the next user message). The hook uses this to pair
   input↔output for each tool span.

---

## Why the Hook Does Not Use `setup_monocle_telemetry()`

### How other frameworks work

Every other Monocle metamodel framework (openai, langchain, anthropic, etc.) relies on
`setup_monocle_telemetry()` to:

1. Create a `Resource` with `SERVICE_NAME`
2. Call `get_monocle_exporter()` to get exporters
3. Wrap each exporter in a `BatchSpanProcessor`
4. Create a `TracerProvider` with a `MonocleSynchronousMultiSpanProcessor`
5. Monkey-patch `ReadableSpan.to_json` (remove 0x prefix from IDs)
6. Set workflow name in OpenTelemetry context
7. **Monkey-patch framework methods** via the `METHODS` list (the main point)

The framework's `METHODS` list tells Monocle which Python methods to wrap (e.g.,
`openai.ChatCompletion.create`, `langchain.chains.LLMChain.__call__`). When those methods
are called at runtime, Monocle's wrappers emit spans automatically.

### Why Claude Code is different

Claude Code is a **compiled CLI binary** (Node.js), not a Python library. There are no
Python methods to monkey-patch. The `CLAUDE_CODE_METHODS` list is empty (`[]`).

Instead, the hook:
- Runs as a **short-lived process** triggered by Claude Code's Stop hook
- Reads the transcript JSONL **post-hoc** (after the turn completes)
- Emits spans by calling the tracer directly via `transcript_processor.py`

### What the hook replicates (and what it skips)

| Step | `setup_monocle_telemetry()` | Hook (`monocle_hook.py`) | Why |
|------|----------------------------|--------------------------|-----|
| 1. Resource | `Resource({SERVICE_NAME: name})` | Same | Identical |
| 2. Exporters | `get_monocle_exporter()` | Same | Identical |
| 3. Span processor | `BatchSpanProcessor` | **`SimpleSpanProcessor`** | Hook exits immediately — batch would lose unflushed spans |
| 4. TracerProvider | `TracerProvider` + `MonocleSynchronousMultiSpanProcessor` | `TracerProvider` (basic) | No need for multi-processor orchestration in a one-shot process |
| 5. ReadableSpan patch | `setup_readablespan_patch()` | Skipped | Not needed — spans are exported, not serialized locally |
| 6. Workflow context | `attach(set_value(...))` | Skipped | No long-running context to propagate |
| 7. Monkey-patching | Wraps framework methods | **Skipped** | Nothing to patch — CLI binary |

### Could the hook use `setup_monocle_telemetry()` instead?

Almost, but not directly:

- `setup_monocle_telemetry()` uses `BatchSpanProcessor`, which buffers spans and flushes
  them in the background. The hook process exits in <1 second — buffered spans would be
  lost before the batch flush fires.
- A `use_simple_processor=True` parameter would need to be added to
  `setup_monocle_telemetry()` to support short-lived processes like hooks.
- Until then, the manual setup (4 lines) is the pragmatic choice.

### No other metamodel framework does this

Claude Code is the only framework in the metamodel that bypasses `setup_monocle_telemetry()`.
All others use it because they instrument long-running Python processes where monkey-patching
and batch export work correctly.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Claude Code CLI                                 │
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │   Turn 1    │────▶│   Turn 2    │────▶│   Turn N    │                   │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                   │
│         │                   │                   │                           │
│         ▼                   ▼                   ▼                           │
│  ┌─────────────────────────────────────────────────────┐                   │
│  │              Transcript JSONL File                   │                   │
│  │  ~/.claude/projects/{hash}/{session}.jsonl          │                   │
│  └─────────────────────────────────────────────────────┘                   │
│         │                                                                   │
│         │ (subagents)                                                       │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────┐                   │
│  │           Subagent Transcript Files                  │                   │
│  │  {session}/subagents/agent-{id}.jsonl               │                   │
│  └─────────────────────────────────────────────────────┘                   │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════   │
│                          Stop Hook Fires                                    │
│  ═══════════════════════════════════════════════════════════════════════   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Monocle Hook (monocle_hook.py)                      │
│                                                                             │
│  1. Read hook payload (sessionId, transcriptPath)                          │
│  2. Load incremental state (last processed offset)                         │
│  3. Parse new JSONL records from main transcript                           │
│  4. Discover and parse subagent transcripts                                │
│  5. Build turn structure with tool call/result matching                    │
│  6. Emit Monocle spans with proper hierarchy                               │
│  7. Save state for next invocation                                         │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ State Mgmt   │  │ Transcript   │  │ Span Builder │  │ OTel Export  │   │
│  │              │  │ Parser       │  │              │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OpenTelemetry Backend                               │
│                     (Monocle, Jaeger, OTLP, etc.)                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Span Hierarchy

```
Session: 5dfd59f4-7eee-4de8-8c1c-c77ab630b1b4 (scope, not span)
│
├── Turn 1 (agentic.turn)
│   ├── Inference 1 (inference) - "I'll read the file"
│   │   └── tool_call decision
│   ├── Tool: Read (agentic.tool.invocation)
│   ├── Inference 2 (inference) - "Now I'll edit it"
│   │   └── tool_call decision
│   └── Tool: Edit (agentic.tool.invocation)
│
├── Turn 2 (agentic.turn)
│   ├── Inference 1 (inference) - "I'll spawn an agent"
│   │   └── delegation decision
│   └── Agent: explorer (agentic.invocation)
│       │
│       └── [Subagent Session: a4bf810ad314b91c1]
│           ├── Turn 1 (agentic.turn)
│           │   ├── Inference (inference)
│           │   └── Tool: Grep (agentic.tool.invocation)
│           └── Turn 2 (agentic.turn)
│               └── Inference (inference) - turn_end
│
└── Turn 3 (agentic.turn)
    └── Inference (inference) - "Here's the result"
        └── turn_end decision
```

---

## Implementation Plan

### Phase 1: Core Hook (MVP)

**Files:**
- `examples/scripts/claude_code_hook/monocle_hook.py` - Main hook script
- `examples/scripts/claude_code_hook/transcript_parser.py` - JSONL parsing
- `examples/scripts/claude_code_hook/span_emitter.py` - Monocle span creation

**Features:**
- [ ] Read Stop hook payload
- [ ] Parse main transcript JSONL incrementally
- [ ] Build turns (user → assistant with tools)
- [ ] Match tool_use with tool_result by ID
- [ ] Emit basic spans: turn, inference, tool
- [ ] State persistence (offset tracking)
- [ ] Session scope via `agentic.session`

### Phase 2: Subagent Support

**Features:**
- [x] Discover `subagents/` directory via `discover_subagents()` in `_helper.py`
- [x] Parse subagent JSONL files via `read_subagent_jsonl()` — filters to user/assistant messages
- [x] Read `agent-{id}.meta.json` for `agentType` and `description`
- [x] Emit subagent workflow→turn→invocation→inference+tool spans via `process_subagents()`
- [x] Link subagent spans to parent trace (shared trace_id via OTel context nesting)
- [x] Rename `"Tool: Agent"` to `"Sub-Agent: {type}"` span name
- [x] Track `subagents_processed` in state to avoid re-emitting
- [x] Capture requested `model` on Agent span as `entity.1.model`
- [ ] Correlate subagent→parent via `parentToolUseID` (subagent spans share trace but lack explicit parent link to the Agent tool_use span)

**Subagent file layout:**
```
{session-id}/subagents/
├── agent-a831441352ab78bfd.jsonl       # subagent transcript
├── agent-a831441352ab78bfd.meta.json   # {"agentType": "Explore", "description": "..."}
├── agent-aa4639f52dc3b7d07.jsonl
└── agent-aa4639f52dc3b7d07.meta.json
```

**Span hierarchy for subagents:**
```
workflow (parent session)
├── Turn N (agentic.turn)
│   └── Claude Invocation (agentic.invocation)
│       ├── Inference (inference)
│       └── Sub-Agent: Explore (agentic.invocation)  ← parent Agent tool span
│
└── Sub-Agent Workflow: Explore (workflow, subtype=subagent)  ← child of parent workflow
    └── Turn 1 (agentic.turn)
        └── Claude Invocation (agentic.invocation)
            ├── Inference (inference) — model from meta.json / JSONL
            └── Tool: Glob (agentic.tool.invocation)
```

### Phase 3: Rich Attributes

**Features:**
- [ ] Token usage (input, output, cache)
- [ ] Model tracking per inference
- [ ] Inference decision subtypes (tool_call, delegation, turn_end)
- [ ] Error tracking (failed tool calls)
- [ ] Timing reconstruction from timestamps

### Phase 4: Production Hardening

**Features:**
- [ ] Graceful failure (never block Claude Code)
- [ ] Log file for debugging
- [ ] Configuration via environment variables
- [ ] Large output truncation with metadata
- [ ] State file locking

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONOCLE_CLAUDE_ENABLED` | Enable/disable hook | `true` |
| `MONOCLE_EXPORTER_ENDPOINT` | OTLP endpoint | `http://localhost:4318` |
| `MONOCLE_CLAUDE_MAX_CHARS` | Max chars for tool output | `20000` |
| `MONOCLE_CLAUDE_DEBUG` | Enable debug logging | `false` |
| `MONOCLE_SERVICE_NAME` | Service name for spans | `claude-code` |

### State File

Location: `~/.claude/state/monocle_state.json`

```json
{
  "sessions": {
    "{session_key}": {
      "offset": 12345,
      "turn_count": 5,
      "subagents_processed": ["a4bf810ad314b91c1"],
      "updated": "2026-04-01T12:00:00Z"
    }
  }
}
```

---

## Advantages Over Langfuse

| Feature | Langfuse | Monocle |
|---------|----------|---------|
| Subagent traces | No (black box) | Yes, full hierarchy |
| Session correlation | Basic session_id | Native `agentic.session` scope |
| Span types | Generic (generation, tool) | Rich (inference, agentic.*, subtypes) |
| Token tracking | No | Full (input, output, cache) |
| Model per inference | Single assumption | Per-inference tracking |
| Parent-child hierarchy | Flat | Proper span tree |
| Timing | Message order only | Timestamp-based |
| Inference decisions | Not captured | tool_call, delegation, turn_end |

---

## File Structure

```
examples/scripts/claude_code_hook/
├── README.md                 # Setup instructions
├── monocle_hook.py          # Main entry point (called by Claude Code)
├── transcript_parser.py      # JSONL parsing and turn building
├── span_emitter.py          # Monocle span creation
├── state_manager.py         # Incremental state persistence
├── config.py                # Configuration handling
└── install.sh               # Installation script
```

### Installation Script

```bash
#!/bin/bash
# install.sh - Install Monocle hook for Claude Code

HOOK_DIR="$HOME/.claude/hooks"
mkdir -p "$HOOK_DIR"

# Copy hook files
cp monocle_hook.py "$HOOK_DIR/"
cp transcript_parser.py "$HOOK_DIR/"
cp span_emitter.py "$HOOK_DIR/"
cp state_manager.py "$HOOK_DIR/"
cp config.py "$HOOK_DIR/"

# Add to Claude Code settings
SETTINGS="$HOME/.claude/settings.json"
if [ -f "$SETTINGS" ]; then
    # Merge hook config (use jq or python)
    python3 -c "
import json
with open('$SETTINGS', 'r') as f:
    settings = json.load(f)
settings.setdefault('hooks', {}).setdefault('Stop', []).append({
    'type': 'command',
    'command': 'python3 ~/.claude/hooks/monocle_hook.py'
})
with open('$SETTINGS', 'w') as f:
    json.dump(settings, f, indent=2)
"
else
    echo '{"hooks":{"Stop":[{"type":"command","command":"python3 ~/.claude/hooks/monocle_hook.py"}]}}' > "$SETTINGS"
fi

echo "Monocle hook installed successfully!"
```

---

## Testing

### Manual Testing

1. Install hook
2. Start Claude Code session
3. Perform actions (read files, run tools, spawn agents)
4. Check spans in Monocle/Jaeger UI

### Automated Testing

```python
# test_transcript_parser.py
def test_parse_turn():
    """Test parsing a complete turn from JSONL"""

def test_match_tool_results():
    """Test matching tool_use with tool_result by ID"""

def test_discover_subagents():
    """Test finding subagent JSONL files"""

def test_incremental_read():
    """Test reading only new records since last offset"""
```

---

## Open Questions

1. **Timing accuracy**: Transcript timestamps are when messages were written, not actual execution time. Is this sufficient?

2. **Streaming inference**: Claude streams responses. The transcript captures final state. Do we need intermediate spans?

3. **Error handling**: How should we handle malformed JSONL records? Skip silently or log?

4. **State cleanup**: How long to keep state for old sessions? Auto-prune after N days?

5. **Multiple Claude processes**: Each process writes its own transcript. State keying by session+path handles this, but should we add process ID?

---

## References

- [Claude Code Hooks Documentation](https://docs.anthropic.com/en/docs/claude-code/hooks)
- [Monocle Span Types](../apptrace/src/monocle_apptrace/instrumentation/common/constants.py)
- [Langfuse Claude Code Integration](https://langfuse.com/integrations/other/claude-code)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
