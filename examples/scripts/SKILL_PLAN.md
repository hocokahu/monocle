# SKILL: Codebase Analysis for Instrumentation

## Overview

A set of scripts and a Claude CLI SKILL to analyze Python codebases and generate optimized `monocle.yaml` configurations for tracing.

---

## Folder Structure (Claude CLI Commands)

```
.claude/
├── commands/
│   └── ok/                             # Each command = separate .md file
│       ├── scan.md                     # /ok:scan - Full codebase scan
│       ├── detect.md                   # /ok:detect - Framework detection
│       ├── find.md                     # /ok:find - Semantic search
│       ├── trace.md                    # /ok:trace - Reverse trace to method
│       ├── plan.md                     # /ok:plan - Generate monocle.yaml
│       ├── instrument.md               # /ok:instrument - Run with tracing
│       └── view.md                     # /ok:view - View traces
│
└── scripts/                            # Helper scripts (shared across commands)
    ├── ast_parser.py                   # Extract classes, methods, args
    ├── call_graph.py                   # Build caller→callee relationships
    ├── entry_detector.py               # Find main, routes, workers
    ├── relevance_scorer.py             # Score module importance
    ├── arg_analyzer.py                 # Flag large/useless arguments
    ├── monocle_detector.py             # Detect monocle-supported frameworks
    ├── yaml_generator.py               # Generate monocle.yaml
    ├── instrument.py                   # Run app with instrumentation
    └── trace_minify.py                 # Format and display traces

# Working directory (created during analysis in target app folder)
<app_folder>/.analyze/                  # Generated analysis files
├── ast_data.json
├── call_graph.json
├── entry_points.json
├── relevance.json
├── arg_analysis.json
├── choices.json                        # User selections from AskUserQuestion
└── monocle_support.json

# Output files
<app_folder>/monocle.yaml               # Generated config
<app_folder>/.monocle/                  # Trace output files
```

### Command File Format (YAML Frontmatter + Markdown)

Each command `.md` file has this structure:

```yaml
---
name: ok:scan
description: Full codebase scan to recommend what to trace
allowed-tools:
  - Read
  - Bash
  - Write
  - Glob
  - Grep
  - AskUserQuestion                     # REQUIRED for interactive menus
---

# ok:scan

Instructions for Claude on how to execute this command...

## Steps
1. ...
2. **USE AskUserQuestion** to ask which entry points to analyze
3. ...

## Interactive Questions - USE AskUserQuestion TOOL

### Entry point selection:
{JSON example of AskUserQuestion parameters}
```

## Key Implementation Note: AskUserQuestion Tool

All interactive questions in /ok: commands MUST use the `AskUserQuestion` tool (not text-based prompts).
This provides proper UI menus in Claude CLI.

```json
{
  "questions": [{
    "question": "Your question here?",
    "header": "Short Label",           // Max 12 chars, shown as chip/tag
    "multiSelect": false,              // true for multiple selections
    "options": [
      {"label": "Option 1 (Recommended)", "description": "What this option does"},
      {"label": "Option 2", "description": "Alternative choice"}
    ]
  }]
}
```

---

## Problem Statement

When instrumenting an application with monocle, users face these challenges:

1. **Large codebases**: Don't know what to trace
2. **Noise**: Utils, models, helpers may or may not be relevant
3. **Large values**: Some args/outputs flood trace context
4. **Unknown paths**: Know target method but not entry points
5. **Manual YAML**: Writing monocle.yaml is tedious and error-prone

## Solution Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SKILL: /analyze-app                          │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: Deterministic Collection (Scripts)                    │
│    → AST parsing, call graphs, entry detection                  │
│    → Output: JSON files in .analyze/ folder                     │
├─────────────────────────────────────────────────────────────────┤
│  Phase 2: Interactive Analysis (LLM + User)                     │
│    → Review findings, ask clarifying questions                  │
│    → User makes decisions on what to trace                      │
├─────────────────────────────────────────────────────────────────┤
│  Phase 3: Generation                                            │
│    → Generate monocle.yaml with user's choices                  │
│    → Include smart defaults for arg filtering                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## SKILL Commands

Trigger via `/ok:[command]` in Claude CLI:

| Command | Description | Mode |
|---------|-------------|------|
| `/ok:detect` | Detect monocle-supported frameworks & suggest decorators | Mode 0 |
| `/ok:scan` | Full codebase scan, recommend what to trace | Mode 1 |
| `/ok:find [query]` | Semantic search for methods matching description | Mode 2 |
| `/ok:trace [class.method]` | Find all paths to a specific method | Mode 3 |
| `/ok:plan` | Generate monocle.yaml from analysis | Generate |
| `/ok:instrument` | Run instrumentation with current config | Execute |
| `/ok:view` | View recent traces with trace_minify | View |
| `/ok:view --errors` | View only error traces | View |

### Command Flow by Mode

#### Mode 0: Detect Frameworks (`/ok:detect`)

```
┌─────────────────────────────────────────────────────────────────┐
│ /ok:detect                                                      │
├─────────────────────────────────────────────────────────────────┤
│ 1. Scans imports for known frameworks                           │
│ 2. Shows what monocle auto-instruments vs needs decorators      │
│ 3. Suggests setup code                                          │
├─────────────────────────────────────────────────────────────────┤
│ If supported frameworks found:                                  │
│   → Just use setup_monocle_telemetry() + decorators             │
│   → Done, no custom YAML needed                                 │
│                                                                 │
│ If custom code found:                                           │
│   → Continue to /ok:scan or /ok:find                            │
└─────────────────────────────────────────────────────────────────┘

Flow:
  /ok:detect
      │
      ├── All supported? → Add setup code → /ok:instrument → Done
      │
      └── Custom code? → /ok:scan or /ok:find
```

#### Mode 1: Full Scan (`/ok:scan`)

```
┌─────────────────────────────────────────────────────────────────┐
│ /ok:scan                                                        │
├─────────────────────────────────────────────────────────────────┤
│ 1. Find entry points                                            │
│ 2. ASK: Which entry point(s) to analyze?                        │
│ 3. Build call graph from selected entries                       │
│ 4. Score module relevance                                       │
│ 5. ASK: Include medium-relevance modules?                       │
│ 6. Analyze args for size risks                                  │
│ 7. ASK: How to handle large args?                               │
│ 8. Output recommendations                                       │
├─────────────────────────────────────────────────────────────────┤
│ Next: /ok:plan to generate YAML                                 │
└─────────────────────────────────────────────────────────────────┘

Flow:
  /ok:scan
      │
      ├── AskUserQuestion: "Which entry point to analyze?"
      │       └── User selects from menu (single select)
      │
      ├── AskUserQuestion: "Which medium-relevance modules to include?"
      │       └── User selects from menu (multiSelect: true)
      │
      ├── AskUserQuestion: "How to handle large args for X.method()?"
      │       └── User selects handling strategy
      │
      └── Choices saved to .analyze/choices.json
              │
              └── /ok:plan → monocle.yaml
                      │
                      └── /ok:instrument → Run
                              │
                              └── /ok:view → Debug
```

#### Mode 2: Semantic Search (`/ok:find`)

```
┌─────────────────────────────────────────────────────────────────┐
│ /ok:find [description]                                          │
├─────────────────────────────────────────────────────────────────┤
│ 1. Search class/method names, docstrings, comments              │
│ 2. Rank by relevance to query                                   │
│ 3. ASK: Which method(s) to trace?                               │
│ 4. Find paths from entry points to selected methods             │
│ 5. Analyze args on the path                                     │
│ 6. Output focused recommendations                               │
├─────────────────────────────────────────────────────────────────┤
│ Next: /ok:plan to generate YAML                                 │
└─────────────────────────────────────────────────────────────────┘

Flow:
  /ok:find payment processing
      │
      ├── Display: "Found 5 matches for 'payment processing'..."
      │
      ├── AskUserQuestion: "Which methods should be traced?"
      │   options: [billing.Processor.charge, orders.Order.process_payment, ...]
      │   multiSelect: true
      │       └── User selects from menu
      │
      ├── Display: "Path to billing.Processor.charge:"
      │   "  api.routes:checkout → orders.Order.submit → [target]"
      │
      └── Choices saved to .analyze/choices.json
              │
              └── /ok:plan → /ok:instrument → /ok:view
```

#### Mode 3: Reverse Trace (`/ok:trace`)

```
┌─────────────────────────────────────────────────────────────────┐
│ /ok:trace [class.method]                                        │
├─────────────────────────────────────────────────────────────────┤
│ 1. Find all callers (reverse call graph)                        │
│ 2. Trace back to entry points                                   │
│ 3. Show all execution paths                                     │
│ 4. ASK: Which path(s) to instrument?                            │
│ 5. Analyze args on selected path                                │
│ 6. Output path-specific recommendations                         │
├─────────────────────────────────────────────────────────────────┤
│ Next: /ok:plan to generate YAML                                 │
└─────────────────────────────────────────────────────────────────┘

Flow:
  /ok:trace db.UserRepo.save
      │
      ├── Display: "Found 3 paths to db.UserRepo.save..."
      │
      ├── AskUserQuestion: "Which execution path(s) should be instrumented?"
      │   options: [Path A: main→cli→target, Path B: api→service→target, ...]
      │   multiSelect: true
      │       └── User selects from menu
      │
      └── Choices saved to .analyze/choices.json
              │
              └── /ok:plan → /ok:instrument → /ok:view
```

#### Generation & Execution (`/ok:plan`, `/ok:instrument`, `/ok:view`)

```
┌─────────────────────────────────────────────────────────────────┐
│ /ok:plan                                                        │
├─────────────────────────────────────────────────────────────────┤
│ 1. Read .analyze/*.json (from previous mode)                    │
│ 2. Apply user choices                                           │
│ 3. Generate monocle.yaml with:                                  │
│    - Selected methods                                           │
│    - Arg filters (include/exclude/truncate)                     │
│    - Output extractors                                          │
│ 4. Show preview, AskUserQuestion: Confirm or edit?               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ /ok:instrument [app.py]                                         │
├─────────────────────────────────────────────────────────────────┤
│ 1. Run: python instrument.py --config monocle.yaml app.py       │
│ 2. Show output                                                  │
│ 3. Traces saved to .monocle/                                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ /ok:view [options]                                              │
├─────────────────────────────────────────────────────────────────┤
│ Options:                                                        │
│   --last 5m        Show traces from last 5 minutes              │
│   --errors         Only show errors                             │
│   --flat           Flat list (no tree)                          │
│   --trace-id X     Specific trace                               │
│                                                                 │
│ Runs: python trace_minify.py [options]                          │
└─────────────────────────────────────────────────────────────────┘
```

#### Complete Workflow Examples

**Example 1: New to codebase**
```bash
/ok:detect              # Check what's already supported
                        # → "OpenAI detected, auto-instrumented"
                        # → "Custom code in services/ needs tracing"

/ok:scan                # Analyze custom code
                        # → Select entry points
                        # → Decide on modules
                        # → Handle large args

/ok:plan                # Generate monocle.yaml

/ok:instrument my_app.py    # Run with tracing

/ok:view --last 5m      # Check traces
```

**Example 2: Know what I want**
```bash
/ok:find payment flow   # Search for payment methods
                        # → Select billing.Processor.charge

/ok:plan                # Generate focused YAML

/ok:instrument          # Run

/ok:view                # Debug
```

**Example 3: Debug specific method**
```bash
/ok:trace db.UserRepo.save   # Find all paths to this method
                             # → Select Path B (API route)

/ok:plan                     # Generate path-specific YAML

/ok:instrument               # Run

/ok:view --errors            # Check for errors
```

**Example 4: Quick Azure Function**
```bash
/ok:detect              # "Azure Functions detected"
                        # → "Use @monocle_trace_azure_function_route"
                        # → Shows decorator code

# Add decorator to code, done - no YAML needed
```

---

## Four Usage Modes

### Mode 0: Detect Monocle-Supported Frameworks (`/ok:detect`)

**Purpose:** Before custom instrumentation, check what monocle already supports out-of-the-box.

**Input:** App folder path

**Process:**
1. Scan imports for known frameworks
2. Match against monocle's built-in support
3. Suggest appropriate approach (decorator vs auto-instrumentation)

**Monocle Built-in Support:**

| Category | Frameworks | Instrumentation |
|----------|------------|-----------------|
| **LLM Inference** | OpenAI, Anthropic, Azure AI, Bedrock, Gemini, LiteLLM, Mistral, HuggingFace | Auto (setup_monocle_telemetry) |
| **Agent Frameworks** | LangChain, LlamaIndex, LangGraph, CrewAI, Haystack, OpenAI Agents, MS AutoGen | Auto |
| **HTTP Frameworks** | Flask, FastAPI, AIOHTTP | Auto + decorators |
| **Cloud Functions** | Azure Functions, AWS Lambda | `@monocle_trace_azure_function_route`, `@monocle_trace_lambda_function_route` |
| **MCP** | FastMCP, MCP SDK | Auto |
| **Other** | Boto3/Botocore, Requests | Auto |

**Output:**
```
=== Monocle Framework Detection ===

Detected in your codebase:

  ✅ OpenAI (openai) - AUTO-INSTRUMENTED
     Found in: services/llm_client.py
     Action: Just call setup_monocle_telemetry()

  ✅ LangChain (langchain) - AUTO-INSTRUMENTED
     Found in: agents/qa_chain.py
     Action: Just call setup_monocle_telemetry()

  ✅ Azure Functions - USE DECORATOR
     Found in: api/functions.py
     Action: Add @monocle_trace_azure_function_route

  ⚠️ Custom code needs manual instrumentation:
     - services/payment.py (no framework detected)
     - utils/calculations.py (no framework detected)

Suggested setup:

  from monocle_apptrace import setup_monocle_telemetry
  from monocle_apptrace import monocle_trace_azure_function_route

  setup_monocle_telemetry(workflow_name="my_app")

  @monocle_trace_azure_function_route
  def my_azure_function(req):
      ...

AskUserQuestion: "Custom code detected. What would you like to do?"
  options: [Run /ok:scan, Run /ok:find, Just use auto-instrumentation]
```

**Available Decorators:**
```python
# HTTP Routes
from monocle_apptrace import monocle_trace_http_route

# Azure Functions
from monocle_apptrace import monocle_trace_azure_function_route

# AWS Lambda
from monocle_apptrace.instrumentation.metamodel.lambdafunc.wrapper import (
    monocle_trace_lambda_function_route
)

# General methods (no I/O capture)
from monocle_apptrace import monocle_trace_method
```

---

### Mode 1: Full Scan ("I'm lazy, analyze everything") (`/ok:scan`)

**Input:** App folder path
**Process:**
1. Find all entry points
2. Ask user to select relevant entry point(s)
3. Build reachable-only call graph from selected entries
4. Score module relevance
5. Ask about medium-relevance modules
6. Analyze args for size risks
7. Generate monocle.yaml

**Output:** Curated monocle.yaml with explanations

### Mode 2: Semantic Search ("I want to trace payment flow") (`/ok:find`)

**Input:** Natural language description
**Process:**
1. Search class/method names, docstrings, comments
2. Rank by relevance to query
3. Present candidates to user
4. User selects target(s)
5. Find paths from entry points to targets
6. Generate monocle.yaml for the path

**Output:** Focused monocle.yaml for specific flow

### Mode 3: Reverse Trace ("Trace db.UserRepo.save()") (`/ok:trace`)

**Input:** Exact class.method
**Process:**
1. Find all callers (reverse call graph)
2. Trace back to entry points
3. Show all execution paths
4. User selects which path(s) to trace
5. Generate monocle.yaml for selected path

**Output:** Path-specific monocle.yaml

---

## Scripts (Deterministic)

### 1. ast_parser.py

**Purpose:** Extract all classes, methods, arguments, return types, docstrings

**Input:** `python ast_parser.py /path/to/app`

**Output:** `.analyze/ast_data.json`
```json
{
  "modules": {
    "billing/processor.py": {
      "classes": {
        "PaymentProcessor": {
          "methods": {
            "charge": {
              "args": [
                {"name": "amount", "type": "Decimal", "default": null},
                {"name": "card_token", "type": "str", "default": null},
                {"name": "metadata", "type": "dict", "default": "{}"}
              ],
              "returns": "PaymentResult",
              "docstring": "Process a payment charge",
              "lineno": 45,
              "calls": ["self.validate", "self._send_to_stripe"]
            }
          }
        }
      },
      "functions": {}
    }
  }
}
```

### 2. call_graph.py

**Purpose:** Build caller→callee relationships

**Input:** `python call_graph.py .analyze/ast_data.json`

**Output:** `.analyze/call_graph.json`
```json
{
  "forward": {
    "api.routes:checkout": ["services.order:Order.submit", "..."],
    "services.order:Order.submit": ["billing.processor:PaymentProcessor.charge"]
  },
  "reverse": {
    "billing.processor:PaymentProcessor.charge": ["services.order:Order.submit"],
    "services.order:Order.submit": ["api.routes:checkout"]
  }
}
```

### 3. entry_detector.py

**Purpose:** Find application entry points

**Input:** `python entry_detector.py .analyze/ast_data.json`

**Output:** `.analyze/entry_points.json`
```json
{
  "entry_points": [
    {
      "type": "cli",
      "location": "main.py:main",
      "detection": "__main__ block",
      "reachable_methods": 45
    },
    {
      "type": "flask",
      "location": "api/app.py:create_app",
      "detection": "Flask factory pattern",
      "routes": ["GET /users", "POST /orders", "..."],
      "reachable_methods": 120
    },
    {
      "type": "worker",
      "location": "workers/consumer.py:start",
      "detection": "while True loop",
      "reachable_methods": 23
    }
  ]
}
```

### 4. relevance_scorer.py

**Purpose:** Score each module's importance

**Input:** `python relevance_scorer.py .analyze/call_graph.json --entry api.routes:checkout`

**Output:** `.analyze/relevance.json`
```json
{
  "high": [
    {
      "module": "billing/processor.py",
      "score": 0.95,
      "reasons": ["called 47x", "on critical path", "has I/O operations"]
    }
  ],
  "medium": [
    {
      "module": "utils/validation.py",
      "score": 0.65,
      "reasons": ["called 12x", "pure functions"]
    }
  ],
  "low": [
    {
      "module": "utils/constants.py",
      "score": 0.1,
      "reasons": ["no function calls", "only constants"]
    }
  ]
}
```

### 5. arg_analyzer.py

**Purpose:** Analyze arguments for size/usefulness

**Input:** `python arg_analyzer.py .analyze/ast_data.json`

**Output:** `.analyze/arg_analysis.json`
```json
{
  "billing.processor:PaymentProcessor.charge": {
    "args": {
      "amount": {"risk": "low", "type": "Decimal", "recommendation": "include"},
      "card_token": {"risk": "medium", "type": "str", "recommendation": "truncate:4"},
      "metadata": {"risk": "high", "type": "dict", "recommendation": "exclude_or_extract"}
    },
    "output": {
      "type": "PaymentResult",
      "fields": ["transaction_id", "status", "amount", "raw_response"],
      "recommendation": "extract:[transaction_id,status,amount]"
    }
  }
}
```

### 6. yaml_generator.py

**Purpose:** Generate monocle.yaml from analysis + user choices

**Input:** `python yaml_generator.py .analyze/ --choices choices.json`

**Output:** `monocle.yaml`

---

## Enhanced monocle.yaml Format

```yaml
workflow_name: my_app

instrument:
  # Basic method
  - package: api.routes
    method: checkout
    span_name: api.checkout

  # Class method with arg filtering
  - package: billing.processor
    class: PaymentProcessor
    method: charge
    span_name: payment.charge

    inputs:
      include: [amount, card_token]
      exclude: [metadata, logger, self]
      truncate:
        card_token: 4                    # Show last 4 only
      max_size: 1000                     # Truncate entire input if > 1000 chars

    output:
      extract: [transaction_id, status]  # Only these fields
      max_size: 500

    # Optional: conditional tracing
    condition: "kwargs.get('amount', 0) > 100"

  # Method with custom output transform
  - package: db.repository
    class: UserRepo
    method: query
    output:
      transform: "len(result)"           # Just log count, not full results
```

---

## Interactive Questions (USE AskUserQuestion TOOL)

All interactive questions MUST use the `AskUserQuestion` tool for proper UI menus.

### Entry Point Selection
```json
{
  "questions": [{
    "question": "Which entry point should I analyze for tracing?",
    "header": "Entry Point",
    "multiSelect": false,
    "options": [
      {"label": "main.py:main (Recommended)", "description": "CLI entry - reaches 45 methods"},
      {"label": "api/app.py:create_app", "description": "Flask app - reaches 120 methods"},
      {"label": "workers/consumer.py:start", "description": "Worker - reaches 23 methods"},
      {"label": "All entry points", "description": "Analyze all detected entry points"}
    ]
  }]
}
```

### Module Relevance (multiSelect)
```json
{
  "questions": [{
    "question": "Which medium-relevance modules should be included in tracing?",
    "header": "Modules",
    "multiSelect": true,
    "options": [
      {"label": "utils/validation.py", "description": "Called 12x by 5 modules - Pure validation logic"},
      {"label": "helpers/formatting.py", "description": "Called 8x by 3 modules - String formatting"},
      {"label": "Skip all medium modules", "description": "Only trace high-relevance modules"}
    ]
  }]
}
```

### Large Argument Handling
```json
{
  "questions": [{
    "question": "How should large arguments be handled for PaymentProcessor.charge()?",
    "header": "Arg Handling",
    "multiSelect": false,
    "options": [
      {"label": "Include full value", "description": "Capture entire argument (may be large)"},
      {"label": "Exclude entirely", "description": "Don't capture this argument"},
      {"label": "Extract specific keys", "description": "Only capture certain keys from dict/object"},
      {"label": "Truncate to 100 chars", "description": "Capture first 100 characters only"}
    ]
  }]
}
```

### Output Extraction
```json
{
  "questions": [{
    "question": "Which fields should be extracted from PaymentResult output?",
    "header": "Output",
    "multiSelect": true,
    "options": [
      {"label": "transaction_id", "description": "str - Transaction identifier"},
      {"label": "status", "description": "str - Payment status"},
      {"label": "amount", "description": "Decimal - Payment amount"},
      {"label": "All fields", "description": "Include raw_response and debug_info (potentially large)"}
    ]
  }]
}
```

---

## AST Limitations & Workarounds

### Cannot Determine at Static Analysis Time

| Limitation | Workaround |
|------------|------------|
| Actual runtime values | Use type hints + naming heuristics |
| Value sizes | Flag risky types (str, dict, List) |
| Which code path executes | Trace from entry points only |
| Dynamic method calls | Warn user, suggest runtime trace |
| Monkey-patched methods | Cannot detect, document limitation |

### Heuristics for Risk Assessment

**High-risk argument patterns:**
```python
LARGE_VALUE_INDICATORS = {
    'type_hints': ['str', 'bytes', 'List', 'Dict', 'Any', 'Optional[str]'],
    'name_patterns': ['content', 'body', 'text', 'prompt', 'document',
                      'payload', 'data', 'response', 'result', 'output'],
    'unbounded_collections': ['List', 'Dict', 'Set', 'Tuple'],
}
```

**Skip argument patterns:**
```python
SKIP_ARGUMENTS = {
    'names': ['self', 'cls', 'logger', 'log', 'config', 'settings',
              'conn', 'session', 'db', 'cursor', 'ctx', 'context'],
    'types': ['Logger', 'Connection', 'Session', 'Callable', 'Type',
              'Engine', 'Pool', 'Lock', 'Event'],
}
```

---

## File Structure

```
monocle/                               # Repository root
├── .claude/
│   ├── commands/
│   │   └── ok/                        # Command definitions
│   │       ├── scan.md                # /ok:scan
│   │       ├── detect.md              # /ok:detect
│   │       ├── find.md                # /ok:find
│   │       ├── trace.md               # /ok:trace
│   │       ├── plan.md                # /ok:plan
│   │       ├── instrument.md          # /ok:instrument
│   │       └── view.md                # /ok:view
│   │
│   └── scripts/                       # Helper scripts
│       ├── ast_parser.py              # Extract AST data
│       ├── call_graph.py              # Build call relationships
│       ├── entry_detector.py          # Find entry points
│       ├── relevance_scorer.py        # Score module importance
│       ├── arg_analyzer.py            # Analyze argument risks
│       ├── instrument.py              # Run app with tracing
│       └── trace_minify.py            # View/format traces
│
├── examples/
│   ├── scripts/
│   │   └── SKILL_PLAN.md              # This document
│   ├── my_app.py                      # Sample app
│   ├── my_functions.py                # Sample functions
│   ├── my_class.py                    # Sample classes
│   ├── monocle.yaml                   # Generated config
│   ├── .monocle/                      # Trace output
│   └── .analyze/                      # Analysis output folder
│       ├── ast_data.json
│       ├── call_graph.json
│       ├── entry_points.json
│       ├── relevance.json
│       ├── arg_analysis.json
│       └── choices.json               # User selections
```

---

## All Scripts List

| Script | Purpose | Input | Output | Status |
|--------|---------|-------|--------|--------|
| **Core Analysis** |||||
| `ast_parser.py` | Extract code structure | App folder | `ast_data.json` | ✅ |
| `call_graph.py` | Build call relationships | `ast_data.json` | `call_graph.json` | ✅ |
| `entry_detector.py` | Find entry points | `ast_data.json` | `entry_points.json` | ✅ |
| `relevance_scorer.py` | Score module importance | `call_graph.json` + entry | `relevance.json` | ✅ |
| `arg_analyzer.py` | Flag large/skip args | `ast_data.json` | `arg_analysis.json` | ✅ |
| **Detection** |||||
| `monocle_detector.py` | Find supported frameworks | App folder | `monocle_support.json` | ⏳ |
| **Generation** |||||
| `yaml_generator.py` | Create monocle.yaml | `.analyze/*.json` + choices | `monocle.yaml` | ⏳ |
| **Execution** |||||
| `instrument.py` | Run app with tracing | `monocle.yaml` + script | Traces | ✅ |
| `trace_minify.py` | View/format traces | `.monocle/` folder | Formatted output | ✅ |

---

## Implementation Status

### Phase 1: Core Scripts ✅ COMPLETE
   - [x] ast_parser.py - Extract all code structure
   - [x] call_graph.py - Build relationships
   - [x] entry_detector.py - Find entry points

### Phase 2: Analysis Scripts ✅ COMPLETE
   - [x] relevance_scorer.py - Score importance
   - [x] arg_analyzer.py - Flag large args

### Phase 3: Generation ⏳ IN PROGRESS
   - [ ] yaml_generator.py - Create monocle.yaml
   - [x] instrument.py - Run app with instrumentation
   - [x] trace_minify.py - View traces

### Phase 4: Command Integration ✅ COMPLETE
   - [x] /ok:scan - Full codebase scan with AskUserQuestion menus
   - [x] /ok:detect - Framework detection
   - [x] /ok:find - Semantic search
   - [x] /ok:trace - Reverse trace to method
   - [x] /ok:plan - Generate monocle.yaml
   - [x] /ok:instrument - Run with instrumentation
   - [x] /ok:view - View traces

### Scripts Location
All scripts are in `.claude/scripts/`:
```
.claude/scripts/
├── ast_parser.py          ✅
├── call_graph.py          ✅
├── entry_detector.py      ✅
├── relevance_scorer.py    ✅
├── arg_analyzer.py        ✅
├── instrument.py          ✅
├── trace_minify.py        ✅
├── monocle_detector.py    ⏳ TODO
└── yaml_generator.py      ⏳ TODO
```

---

## Open Questions

1. Should we support tracing third-party library calls? (e.g., `requests.get`)
2. How to handle async generators and context managers?
3. Should condition expressions be Python eval or a safe DSL?
4. How to persist user choices for re-analysis?

---

## References

- [Python AST module](https://docs.python.org/3/library/ast.html)
- [Monocle instrumentation](../README.md)
- [trace_minify.py](../trace_minify.py) - Trace viewer
