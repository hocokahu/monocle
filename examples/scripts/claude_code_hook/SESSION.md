# Monocle Claude Code Hook - Session Progress

## Date: 2026-04-01 (Updated)

## Completed

### 1. Hook Implementation (original)
- Created `monocle_hook.py` - main hook script
- Created `run_hook.sh` - wrapper that sources .env
- Created `install.sh` - installation script
- Created `README.md` - documentation

### 2. Hook Installation
- Installed to `~/.claude/hooks/monocle_hook.py`
- Stop hook in `.claude/settings.local.json` (repo-scoped)
- Added `.mcp.json` with okahu-mcp config

### 3. Okahu Export - VERIFIED (original)
14 traces confirmed in Okahu for `claude-cli` workflow.

### 4. /ok-add-framework - COMPLETED
Claude Code added as a proper Monocle framework in the metamodel.

#### What was created
```
apptrace/src/monocle_apptrace/instrumentation/metamodel/claude_code/
├── __init__.py
├── _helper.py              # Transcript parsing (JSONL reader, turn builder, tool classifier)
├── transcript_processor.py  # Span emission engine with workflow root span
├── methods.py               # Empty METHODS list (CLI binary, not monkey-patchable)
└── entities/
    ├── __init__.py
    ├── turn.py              # agentic.turn entity
    ├── inference.py         # inference entity
    ├── tool.py              # agentic.tool.invocation entity
    ├── agent.py             # agentic.invocation entity (subagents)
    └── mcp.py               # agentic.mcp.invocation entity
```

#### Registration
- `CLAUDE_CODE_METHODS` added to `DEFAULT_METHODS_LIST` in `wrapper_method.py`
- `"claude_code": "workflow.claude_code"` added to `WORKFLOW_TYPE_MAP` in `span_handler.py`

#### monocle_hook.py refactored
- Now uses `transcript_processor.process_transcript()` instead of inline span emission
- Installed to `~/.claude/hooks/monocle_hook.py`

### 5. Root cause: Okahu span detail failure
Old hook traces had `0x`-prefixed trace IDs visible in listings but `GET /spans`
returned NOT_FOUND. **Root cause**: Missing `workflow` root span (`span.type: "workflow"`).
Okahu requires this for span detail retrieval. Fixed by wrapping all turns in a
workflow span with `entity.1.type: "workflow.claude_code"`.

### 6. E2E Tests - ALL PASS (3 rounds)

#### Round 1: Basic span emission
All 4 unit tests pass. 3 e2e tests emit to Okahu + .monocle/ successfully.

#### Round 2: Fixes applied
1. **Status code `unset` → `ok`**: Added `span.set_status(StatusCode.OK)` to all spans
2. **Response truncation**: Turn `data.output` now includes assistant text + all tool outputs (no truncation)
3. **Session propagation**: `scope.agentic.session` now on ALL child spans (inference, tool, agent), not just turn

#### Round 2 verified trace IDs
| Test | Trace ID | Status |
|------|----------|--------|
| Test 1: Prompt/Response (hi) | `0x5440072f31aaa488e592a4f44f4b5fdd` | PASS |
| Test 2: Bash Tool (ls) | `0x82b896546daf4eb2cb8578970e7c7c69` | PASS |
| Test 3: Subagent (1+1+1) | `0x39b531171813c7abff172a02da7b500e` | PASS |

All 3 retrieved via Okahu MCP with correct:
- `"code": "ok"` on every span
- Full response including tool outputs (not truncated)
- `scope.agentic.session` on every non-workflow span

### 7. Integration Tests
```
apptrace/tests/integration/test_claude_code.py
```
4 tests, all passing:
- `test_prompt_response_inference` - workflow + turn + inference with tokens
- `test_bash_tool_call` - tool.invocation with full (untrimmed) input/output
- `test_subagent_call` - agentic.invocation with subagent type
- `test_process_transcript_file` - end-to-end JSONL file processing

Tests verify:
- `_assert_workflow_span()` - workflow root span exists with correct entity attrs
- `_assert_all_spans_status_ok()` - every span has StatusCode.OK
- `_assert_all_spans_have_session()` - every non-workflow span has scope.agentic.session

## Span Hierarchy
```
workflow (workflow.claude_code, status=ok)
  └─ Claude Code - Turn N (agentic.turn, scope.agentic.session, status=ok)
       ├─ Claude Inference (inference, inference.anthropic, model, tokens, status=ok)
       ├─ Tool: Bash (agentic.tool.invocation, tool.claude_code, status=ok)
       ├─ Tool: Read (agentic.tool.invocation, tool.claude_code, status=ok)
       ├─ Tool: Agent (agentic.invocation, agent.claude_code, status=ok)
       └─ Tool: mcp__* (agentic.mcp.invocation, tool.mcp, status=ok)
```

## Key Technical Learnings

### Required Span Attributes for Okahu
- `monocle_apptrace.version` - MUST be present or `skip_export()` drops the span silently
- `workflow.name` - Okahu uses this to group spans into workflows
- `service.name` in TracerProvider Resource - maps to workflow name in Okahu
- `span.type: "workflow"` root span - REQUIRED for Okahu span detail retrieval
- `scope.agentic.session` - propagate to ALL child spans, not just root

### Exporter Notes
- `SimpleSpanProcessor` required (not `BatchSpanProcessor`) - hook is short-lived process
- Manual `TracerProvider` + `get_monocle_exporter()` + `SimpleSpanProcessor` works reliably
- Each test needs its own TracerProvider (use `provider.get_tracer()` not `trace.set_tracer_provider()`)

### Status Codes
- Must explicitly call `span.set_status(StatusCode.OK)` on every span
- Default is UNSET which shows as `"code": "unset"` in Okahu

### Response Completeness
- Turn `data.output` must include assistant text + all tool results (joined with newline)
- Tool spans get their own input/output without truncation
- Inference span gets only assistant text (not tool outputs)

## Files

| File | Purpose |
|------|---------|
| `apptrace/src/.../metamodel/claude_code/` | Framework package (entities, helper, processor) |
| `apptrace/tests/integration/test_claude_code.py` | 4 integration tests |
| `examples/scripts/claude_code_hook/monocle_hook.py` | Hook script (uses transcript_processor) |
| `examples/scripts/claude_code_hook/e2e_test.py` | E2E test script (emits to Okahu + .monocle/) |
| `examples/scripts/claude_code_hook/run_hook.sh` | Wrapper that sources .env |
| `.claude/settings.local.json` | Stop hook config |

## Environment
```
OKAHU_API_KEY=okh_TvXJNYyn_PLj0x0qXRcyafFXRydgA
OKAHU_INGESTION_ENDPOINT=https://ingest-stage.okahu.co/api/v1/trace/ingest
MONOCLE_EXPORTER=okahu,file
```

## Next Steps
- [ ] Commit changes to branch `hoc/claude-skill`
- [ ] Handle MCP tool spans (`mcp__*` prefix) in e2e testing
- [ ] Test with real Claude Code session (live hook, not simulated transcripts)
- [ ] PR to monocle2ai/monocle main branch
