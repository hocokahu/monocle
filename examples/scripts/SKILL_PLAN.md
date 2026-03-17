# SKILL: Codebase Analysis for Instrumentation

## Overview

A set of scripts and Claude CLI skills to analyze Python codebases and add monocle tracing.

---

## KEY RULES (MUST FOLLOW)

### 1. Framework Priority
**If `/ok:scan` detects monocle-supported frameworks (OpenAI, LangChain, Flask, etc.), PRIORITIZE using monocle's built-in auto-instrumentation.** Do NOT reinvent the wheel with custom tracing when monocle already supports it.

### 2. Dependencies - requirements.txt
When instrumenting code or generating okahu.yaml that requires `monocle_apptrace`, **ALWAYS update requirements.txt**:
```
monocle_apptrace
```

### 3. Prefer monocle_apptrace over OpenTelemetry
**NEVER use opentelemetry directly** unless the feature is not available in monocle_apptrace. Monocle wraps OpenTelemetry - always use monocle's API.

### 4. Skip Patterns - DO NOT INSTRUMENT
**NEVER instrument these:**
- `__init__.py` files - Package initializers, not business logic
- `__init__` methods - Constructor setup, not traceable operations
- `__str__`, `__repr__`, `__eq__`, etc. - Dunder/magic methods
- Files in `tests/`, `test_*.py`, `*_test.py` - Test files
- Files in `migrations/`, `alembic/` - Database migrations
- Files in `.venv/`, `venv/`, `site-packages/` - Virtual environments

---

## SKILL Commands

| Skill | Arguments | Description |
|-------|-----------|-------------|
| `/ok:scan` | `[folder]` optional | Full codebase analysis. Asks for folder if not provided. |
| `/ok:find` | `[query]` optional | Find methods by search or `Class.method`. Asks if not provided. |
| `/ok:instrument` | none | Add tracing - prompts **Zero-code** or **Code-based** |
| `/ok:run` | `[command]` optional | Smart runner - auto-detects or prompts. See behavior below. |
| `/ok:local-trace` | `[query]` optional | View local traces. Accepts natural language. Falls back to Okahu MCP if no local traces. |
| `/ok:status` | `[folder]` optional | Resume session. Finds SESSION.md automatically. |

---

## Workflow

```
/ok:scan or /ok:find → /ok:instrument → /ok:run → /ok:local-trace
```

### `/ok:run` Smart Behavior

```
/ok:run
    │
    ├─ Command provided? → Use it
    │
    ├─ Only 1 entry point? → Run it automatically
    │
    └─ Multiple options? → Prompt:
         ○ python main.py (detected)
         ○ flask run -p 8080
         ○ uvicorn app:app
         ○ Enter custom command
         ○ Don't run - exit

    Then:
    ├─ Zero-code → okahu-instrument <command>
    └─ Code-based → <command> directly
```

Servers that listen on ports run in foreground (user can Ctrl+C to stop).

---

## Workflow Examples

**Example 1: Full scan (zero-code)**
```bash
/ok:scan                # Analyze codebase
/ok:instrument          # Choose "Zero-code" → generates okahu.yaml
/ok:run                 # Auto-detects or prompts for run command
/ok:local-trace         # "show me recent errors"
```

**Example 2: Targeted tracing (code-based)**
```bash
/ok:find payment flow   # Search for payment methods
/ok:instrument          # Choose "Code-based" → injects setup code
flask run               # Run normally - tracing enabled
/ok:local-trace         # Debug
```

**Example 3: Direct method lookup**
```bash
/ok:find db.UserRepo.save    # Direct mode - exact method
/ok:instrument               # Set up tracing
/ok:run uvicorn app:app      # Run with explicit command
/ok:local-trace --errors     # Check for errors
```

---

## Folder Structure

```
.claude/
├── commands/
│   └── ok/                             # Each command = separate .md file
│       ├── scan.md                     # /ok:scan
│       ├── find.md                     # /ok:find
│       ├── instrument.md               # /ok:instrument
│       ├── run.md                      # /ok:run
│       ├── local-trace.md              # /ok:local-trace
│       └── status.md                   # /ok:status
│
└── scripts/                            # Helper scripts
    ├── ast_parser.py                   # Extract classes, methods, args
    ├── call_graph.py                   # Build caller→callee relationships
    ├── entry_detector.py               # Find main, routes, workers
    ├── relevance_scorer.py             # Score module importance
    ├── arg_analyzer.py                 # Flag large/useless arguments
    ├── okahu_instrument.py             # Zero-code CLI (like opentelemetry-instrument)
    └── trace_minify.py                 # Format and display traces

# Working directory (created during analysis in target app folder)
<app_folder>/.analyze/                  # Generated analysis files
├── ast_data.json
├── call_graph.json
├── entry_points.json
├── relevance.json
├── arg_analysis.json
├── choices.json                        # User selections
└── SESSION.md                          # Session state (persists across /clear)

# Output files
<app_folder>/okahu.yaml                 # Generated config (zero-code)
<app_folder>/.monocle/                  # Trace output files
```

---

## Instrumentation Approaches

### Zero-code (Recommended)
- Generates `okahu.yaml` config
- No code changes to your app
- Run via `okahu-instrument <command>`
- Like `opentelemetry-instrument` but for monocle

```bash
okahu-instrument python app.py
okahu-instrument flask run
okahu-instrument uvicorn app:app --reload
```

### Code-based
- Injects `setup_monocle_telemetry()` into entry point
- Works with any run method
- Run your app normally

```python
# Injected at top of entry point
from monocle_apptrace.instrumentation import setup_monocle_telemetry
setup_monocle_telemetry(workflow_name="my_app")
```

---

## Monocle Built-in Support

These frameworks are auto-instrumented by monocle - no custom YAML needed:

| Category | Frameworks | Instrumentation |
|----------|------------|-----------------|
| **LLM Inference** | OpenAI, Anthropic, Azure AI, Bedrock, Gemini, LiteLLM, Mistral, HuggingFace | Auto |
| **Agent Frameworks** | LangChain, LlamaIndex, LangGraph, CrewAI, Haystack, OpenAI Agents, AutoGen | Auto |
| **HTTP Frameworks** | Flask, FastAPI, AIOHTTP | Auto + decorators |
| **Cloud Functions** | Azure Functions, AWS Lambda | Decorators required |
| **MCP** | FastMCP, MCP SDK | Auto |

---

## okahu.yaml Format

```yaml
workflow_name: my_app

instrument:
  - package: billing.processor
    class: PaymentProcessor
    method: charge
    span_name: payment.charge

    inputs:
      include: [amount, card_token]
      exclude: [metadata, logger, self]
      truncate:
        card_token: 4

    output:
      extract: [transaction_id, status]
      max_size: 500
```

---

## Scripts

| Script | Purpose | Status |
|--------|---------|--------|
| `ast_parser.py` | Extract code structure | ✅ |
| `call_graph.py` | Build call relationships | ✅ |
| `entry_detector.py` | Find entry points | ✅ |
| `relevance_scorer.py` | Score module importance | ✅ |
| `arg_analyzer.py` | Flag large/skip args | ✅ |
| `okahu_instrument.py` | Zero-code CLI wrapper | ✅ |
| `trace_minify.py` | View/format traces | ✅ |
| `monocle_detector.py` | Find supported frameworks | ⏳ TODO |
| `yaml_generator.py` | Create okahu.yaml | ⏳ TODO |

---

## Interactive Questions

All interactive questions use the `AskUserQuestion` tool for proper UI menus:

```json
{
  "questions": [{
    "question": "Your question here?",
    "header": "Short Label",
    "multiSelect": false,
    "options": [
      {"label": "Option 1 (Recommended)", "description": "What this option does"},
      {"label": "Option 2", "description": "Alternative choice"}
    ]
  }]
}
```

---

## Environment Variables

```bash
MONOCLE_STRICT=true       # Fail if instrumentation breaks (default: false)
MONOCLE_SILENT=true       # Suppress warnings (default: false)
OKAHU_INGESTION_ENDPOINT  # Okahu cloud endpoint
OKAHU_API_KEY             # Okahu API key
```
