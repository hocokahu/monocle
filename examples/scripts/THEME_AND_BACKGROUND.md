# Theme and Background: Developer Experiences and Productivity

## Theme

**Developer experiences and productivity** — measuring, understanding, and improving how developers interact with AI-assisted tooling.

## Background: From Logging to Telemetry

### The Problem with Traditional Logging

```python
# Traditional approach
langgraph_tool_handler()
logger.info("blah")
# Output: timestamp : LOG ....
```

Traditional logging produces:
- Flat, unstructured text
- No correlation between events
- No span hierarchy or context propagation
- Difficult to trace execution paths
- No standardized attributes

### The Monocle Telemetry Approach

```python
# Monocle approach
from monocle_apptrace.instrumentation.common.wrapper import setup_monocle_telemetry

setup_monocle_telemetry(
    workflow_name="my-agent",
    span_processors=[BatchSpanProcessor(exporter)]
)
```

OpenTelemetry primitives:
```python
# Manual instrumentation when needed
trace.start_span("operation")
trace.add_event("blah")
trace.add_attribute("key", "value")
trace.end()
```

Produces structured telemetry:
```json
{
    "timestamp": "2026-04-03T10:00:00Z",
    "trace_id": "abc123",
    "span_id": "def456",
    "parent_span_id": "ghi789",
    "name": "agentic.tool.invocation",
    "attributes": {
        "tool.name": "search",
        "span.type": "agentic.tool.invocation",
        "scope.agentic.session": "session-123"
    }
}
```

### Runtime Instrumentation

Monocle's metamodel captures runtime behavior automatically:
```python
langgraph_tool_handler()
# --> Monocle captures: input / output --> JSON span
```

This enables:
- Full execution traces
- Input/output correlation
- Duration and latency metrics
- Token usage tracking
- Session grouping

---

## Use Case 1: Claude CLI with Monocle

### Vision

Instrument Claude Code CLI to collect coding experiences and productivity metrics.

### What Can Be Captured

| Dimension | Metrics |
|-----------|---------|
| **Tools** | Which tools called, input/output, duration, tokens |
| **Subagents** | Which subagents spawned, input/output, duration, tokens |
| **Sessions** | All activity grouped per session with correlation IDs |
| **Skills** | Which skills invoked → tools used → git outcomes |
| **Hooks** | Custom validation (e.g., prevent commit unless tests pass) |

### Example: Productivity Metrics

```
Session: claude-2026-04-03-abc123
├── Duration: 45 minutes
├── Turns: 12
├── Total tokens: 125,000 (85k cached)
├── Tools called:
│   ├── Read: 45 calls, 12s total
│   ├── Grep: 23 calls, 8s total
│   ├── Edit: 18 calls, 2s total
│   ├── Bash: 31 calls, 45s total
│   └── Agent: 3 calls, 180s total
├── Subagents:
│   ├── Explore: 2 sessions, 15 files discovered
│   └── test-runner: 1 session, 23 tests run
└── Outcome: git push (3 commits, 450 LOC changed)
```

### Implementation Status

See [`claude_code_hook/`](./claude_code_hook/) for the working implementation:
- `monocle_hook.py` — Main hook that processes Claude CLI transcripts
- `install.sh` — One-line installation script
- `e2e_test.py` — End-to-end verification

### Hook-Based Enforcement

Claude Code hooks can enforce quality gates:

```json
{
  "hooks": {
    "PreCommit": [{
      "type": "command",
      "command": "python3 ~/.claude/hooks/require_tests.py"
    }]
  }
}
```

Example: Prevent commits unless specific tests pass:
```python
# require_tests.py
def check_tests():
    result = subprocess.run(["pytest", "tests/critical_test.py"])
    if result.returncode != 0:
        print("BLOCK: Critical tests must pass before commit")
        sys.exit(1)
```

### Skill Tracing

Track skill invocations through the entire workflow:

```
Skill: /ship
├── Pre-checks
│   ├── Tool: Bash (git status)
│   ├── Tool: Bash (npm test)
│   └── Tool: Read (VERSION)
├── Review phase
│   ├── Agent: code-reviewer
│   └── Inference: diff analysis
├── Commit phase
│   ├── Tool: Bash (git commit)
│   └── Tool: Bash (git push)
└── Duration: 3m 45s, Tokens: 28,000
```

---

## Use Case 2: Non-Agentic Codebase Instrumentation

### Vision

The `/ok-*` skill family generates instrumentation for any codebase using Monocle's metamodel framework.

### Metamodel Reference

Monocle provides instrumentation adapters for common frameworks:
- [monocle2ai/monocle/tree/main/apptrace/src/monocle_apptrace/instrumentation/metamodel](https://github.com/monocle2ai/monocle/tree/main/apptrace/src/monocle_apptrace/instrumentation/metamodel)

### Available Skills

| Skill | Purpose |
|-------|---------|
| `/ok-scan` | Full codebase scan to recommend what to trace |
| `/ok-instrument` | Add tracing to your app (zero-code or code-based) |
| `/ok-find` | Find methods by name, trace execution paths |
| `/ok-run` | Run your app with Monocle tracing enabled |
| `/ok-local-trace` | View local traces from `.monocle/` folder |
| `/ok-add-framework` | Add instrumentation for a new AI/ML framework |

### Zero-Code Instrumentation

For supported frameworks, Monocle patches automatically:

```python
# Before: Your existing code (unchanged)
from langchain.chat_models import ChatOpenAI
llm = ChatOpenAI()
response = llm.invoke("Hello")

# Setup: Add once at startup
from monocle_apptrace.instrumentation.common.wrapper import setup_monocle_telemetry
setup_monocle_telemetry(workflow_name="my-app")

# Result: All LLM calls automatically traced with:
# - Model name, provider
# - Input/output tokens
# - Latency
# - Input/output content (configurable)
```

### Code-Based Instrumentation

For custom functions, use decorators:

```python
from monocle_apptrace.wrap_common import task_wrapper, atask_wrapper

@task_wrapper(name="my_custom_function")
def my_custom_function(input_data):
    # Your logic here
    return result

@atask_wrapper(name="my_async_function")
async def my_async_function(input_data):
    # Async logic
    return result
```

### Framework Detection

`/ok-scan` detects and recommends instrumentation:

```
Detected frameworks:
├── LangChain (langchain==0.1.0)
│   └── Recommendation: Zero-code, setup_monocle_telemetry()
├── OpenAI (openai==1.12.0)
│   └── Recommendation: Zero-code, auto-patched
├── Custom agent loop (src/agent.py:45)
│   └── Recommendation: @task_wrapper decorator
└── FastAPI endpoints (src/api.py)
    └── Recommendation: Middleware instrumentation
```

---

## Telemetry Data Model

### Span Types

| Span Type | Description |
|-----------|-------------|
| `inference` | LLM call with model, tokens, latency |
| `agentic.tool.invocation` | Tool execution with input/output |
| `agentic.invocation` | Agent or subagent execution |
| `agentic.mcp.invocation` | MCP server tool call |
| `agentic.turn` | User→assistant interaction cycle |
| `agentic.session` | Top-level session scope |

### Standard Attributes

```
# Session context
scope.agentic.session: <session-id>
monocle.service.name: <service>

# Inference
gen_ai.system: anthropic | openai | ...
gen_ai.request.model: claude-opus-4-5
gen_ai.usage.input_tokens: 1500
gen_ai.usage.output_tokens: 250
gen_ai.usage.cache_read_tokens: 11282

# Tool
tool.name: Read | Write | Bash | ...
tool.id: toolu_xxx
```

---

## Benefits

### For Individual Developers

- Understand where time is spent in AI-assisted coding
- Identify bottlenecks (slow tools, expensive inference)
- Track productivity metrics over time
- Debug complex agent interactions

### For Teams

- Standardized telemetry across projects
- Cost attribution (tokens per feature/session)
- Quality gates enforced via hooks
- Shared dashboards and alerting

### For Tool Builders

- Understand how developers use AI tools
- A/B test different approaches
- Measure impact of changes
- Identify common pain points

---

## Getting Started

### Claude CLI Instrumentation

```bash
cd examples/scripts/claude_code_hook
./install.sh
```

### Non-Agentic Codebase

```bash
# In your project
claude
> /ok-scan          # Analyze codebase
> /ok-instrument    # Add tracing
> /ok-run           # Execute with tracing
> /ok-local-trace   # View traces
```

---

## Related Resources

- [Monocle Metamodel](https://github.com/monocle2ai/monocle/tree/main/apptrace/src/monocle_apptrace/instrumentation/metamodel)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/concepts/semantic-conventions/)
- [Claude Code Hooks](./claude_code_hook/README.md)
