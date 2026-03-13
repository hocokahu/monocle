# Monocle Custom Instrumentation Examples

This directory contains examples demonstrating how to create custom instrumentation in Monocle for both **standalone functions** (not in a class) and **class methods**.

## Overview

Monocle provides 5 ways to instrument custom functions:

| Method | Best For | Modifies Source? | Production-Safe? |
|--------|----------|------------------|------------------|
| `instrument.py` CLI | Zero-code instrumentation | No | Yes (fail-open) |
| `@monocle_trace_method()` | Your own functions | Yes (decorator) | Yes |
| `monocle_trace()` context manager | Wrapping code blocks | No | Yes |
| `start_trace()` / `stop_trace()` | Callbacks, event handlers | No | Yes |
| `WrapperMethod` configuration | Third-party libraries | No | Yes |

---

## CLI-Style Instrumentation (Recommended for Production)

**File:** `instrument.py`

Zero-code instrumentation using YAML config with **fail-open behavior** (instrumentation errors won't crash your app).

### Quick Start

```bash
cd examples
source .env
python instrument.py --config monocle.yaml my_app.py
```

### monocle.yaml Format

```yaml
workflow_name: my_app_example

instrument:
  # Standalone function (no class)
  - package: my_functions
    method: calculate_sum
    span_name: func_calculate_sum

  # Class method
  - package: my_class
    class: Calculator
    method: add
    span_name: Calculator.add

  # Async function
  - package: my_module
    method: async_fetch
    async: true
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `MONOCLE_EXPORTER` | Exporters to use (e.g., `okahu,file`) |
| `OKAHU_INGESTION_ENDPOINT` | Okahu ingestion endpoint |
| `OKAHU_API_KEY` | Okahu API key |
| `MONOCLE_STRICT=true` | Fail if instrumentation breaks (for dev/testing) |
| `MONOCLE_SILENT=true` | Suppress warnings on failure |

### Fail-Open Behavior

By default, if instrumentation fails, the app **continues without instrumentation**:

```
[Monocle] WARNING: Instrumentation failed: YAML parse error
[Monocle] Continuing without instrumentation (fail-open mode)
[Monocle] Instrumentation: DISABLED
------------------------------------------------------------
(app runs normally)
```

For development/testing, use strict mode:
```bash
export MONOCLE_STRICT=true
python instrument.py --config monocle.yaml my_app.py
# Will exit with error if instrumentation fails
```

### Sample Output

```
[Monocle] OKAHU_INGESTION_ENDPOINT: https://ingest-stage.okahu.co/api/v1/trace/ingest
[Monocle] MONOCLE_EXPORTER: okahu,file
[Monocle] OKAHU_API_KEY: okh_TvXJ...ydgA
[Monocle] Workflow: my_app_example
[Monocle] Config: monocle.yaml
[Monocle] Instrumentation: ENABLED
------------------------------------------------------------
(your app output)
```

### Captured Input/Output

The CLI automatically captures function inputs (with actual parameter names) and outputs:

```json
{
  "name": "Calculator.multiply",
  "attributes": {
    "span_source": "my_class.py:15",
    "entity.1.name": "Calculator.multiply",
    "entity.1.type": "function.custom"
  },
  "events": [
    {"name": "data.input", "attributes": {"input": "{\"x\": 8, \"y\": 9}"}},
    {"name": "data.output", "attributes": {"output": "72"}}
  ]
}
```

Note: Parameter names (`x`, `y`) are extracted using Python's `inspect.signature()`, not generic `arg_0`, `arg_1`.

---

## Example 1: `@monocle_trace_method()` Decorator

**File:** `example1_decorator.py`

The simplest way to instrument functions. Just add the decorator.

### Standalone Function (No Class)

```python
from monocle_apptrace.instrumentation.common.instrumentor import (
    setup_monocle_telemetry,
    monocle_trace_method,
)

setup_monocle_telemetry(workflow_name="my_app")

@monocle_trace_method()  # Uses function name as span name
def calculate_sum(a: int, b: int) -> int:
    return a + b

@monocle_trace_method(span_name="custom_span_name")  # Custom span name
def calculate_product(a: int, b: int) -> int:
    return a * b

# Works with async too
@monocle_trace_method()
async def async_fetch(item_id: int) -> dict:
    return {"id": item_id}
```

### Class Method

```python
class Calculator:
    @monocle_trace_method()
    def add(self, a: int, b: int) -> int:
        return a + b

    @monocle_trace_method(span_name="calc_multiply")
    def multiply(self, a: int, b: int) -> int:
        return a * b
```

---

## Example 2: `monocle_trace()` Context Manager

**File:** `example2_context_manager.py`

Wrap code blocks without modifying function signatures.

```python
from monocle_apptrace.instrumentation.common.instrumentor import (
    setup_monocle_telemetry,
    monocle_trace,
    amonocle_trace,  # For async
)

setup_monocle_telemetry(workflow_name="my_app")

# Wrap any code block
with monocle_trace(span_name="my_operation"):
    result = some_function()

# With custom attributes
with monocle_trace(
    span_name="user_operation",
    attributes={"user.id": "123", "operation.type": "calculation"}
):
    result = calculate(x, y)

# Async version
async with amonocle_trace(span_name="async_op"):
    result = await async_function()
```

---

## Example 3: `start_trace()` / `stop_trace()` Manual Control

**File:** `example3_start_stop.py`

For fine-grained control when context managers don't fit.

```python
from monocle_apptrace.instrumentation.common.instrumentor import (
    setup_monocle_telemetry,
    start_trace,
    stop_trace,
)

setup_monocle_telemetry(workflow_name="my_app")

token = start_trace(span_name="my_operation")
result = some_function()
stop_trace(token)

# With attributes
token = start_trace(span_name="processing", attributes={"user.id": "123"})
result = process_data()
stop_trace(token, final_attributes={"result.count": len(result)})
```

---

## Example 4: `WrapperMethod` Configuration

**File:** `example4_wrapper_method.py`

Instrument functions at setup time without modifying source code.

```python
from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry
from monocle_apptrace.instrumentation.common.wrapper_method import WrapperMethod
from monocle_apptrace.instrumentation.common.wrapper import task_wrapper

wrapper_methods = [
    WrapperMethod(
        package="my_module",
        object_name=None,          # None = standalone function
        method="my_function",
        span_name="my_function",
        wrapper_method=task_wrapper
    ),
    WrapperMethod(
        package="my_module",
        object_name="MyClass",     # Class name for methods
        method="my_method",
        span_name="myclass_method",
        wrapper_method=task_wrapper
    ),
]

setup_monocle_telemetry(
    workflow_name="my_app",
    wrapper_methods=wrapper_methods,
    union_with_default_methods=False
)
```

---

## Files in This Directory

| File | Description |
|------|-------------|
| `instrument.py` | CLI wrapper with YAML config (fail-open) |
| `trace_minify.py` | Minify JSON traces for debugging |
| `monocle.yaml` | Sample YAML configuration |
| `my_app.py` | Sample app using my_functions + my_class |
| `my_functions.py` | Sample standalone functions (no class) |
| `my_class.py` | Sample class with methods |
| `.env` | Environment variables (Okahu credentials) |
| `.monocle/` | JSON trace output directory |
| `example1_decorator.py` | `@monocle_trace_method()` examples |
| `example2_context_manager.py` | `monocle_trace()` context manager examples |
| `example3_start_stop.py` | `start_trace()`/`stop_trace()` examples |
| `example4_wrapper_method.py` | `WrapperMethod` configuration examples |

---

## Key Differences

| Feature | CLI (instrument.py) | Decorator | Context Manager | WrapperMethod |
|---------|---------------------|-----------|-----------------|---------------|
| Modifies source | No | Yes | No | No |
| Config file | YAML | N/A | N/A | Python |
| Fail-open | Yes | No | No | No |
| Input/Output capture | Yes | No | No | Custom |
| Production-safe | Best | Good | Good | Good |

---

## Running the CLI Example

```bash
cd examples

# Set up environment
source .env

# Run with instrumentation
python instrument.py --config monocle.yaml my_app.py

# Check output
ls .monocle/
```

---

---

## Trace Minifier for Debugging

**File:** `trace_minify.py`

Converts verbose JSON trace files into a compact, readable format optimized for debugging and Claude CLI.

### Usage

```bash
# Latest traces (default: last 10 files)
python trace_minify.py

# Time-based filter
python trace_minify.py --last 5m      # Last 5 minutes
python trace_minify.py --last 1h      # Last hour

# Specific trace by ID
python trace_minify.py --trace-id af2ec960

# Output modes
python trace_minify.py                 # Tree view (default)
python trace_minify.py --flat          # Flat list (greppable)

# Filters
python trace_minify.py --errors-only   # Only spans with errors
python trace_minify.py --limit 5       # Max 5 trace files
```

### Output Format

**Tree View (default):**
```
--- trace: af2ec9609a25756b... (4 spans, 0 errors) ---
[Calculator.complex_operation] my_app.py:43 (25.5ms)
  IN:  {"x":10}
  OUT: 40
  └─ [Calculator.add] my_class.py:30 (12.2ms)
       IN:  {"a":10,"b":10}
       OUT: 20
  └─ [Calculator.multiply] my_class.py:31 (12.6ms)
       IN:  {"a":10,"b":2}
       OUT: 20
```

**Flat View (`--flat`):**
```
[Calculator.complex_operation] my_app.py:43 (25.5ms)
  IN:  {"x":10}
  OUT: 40
[Calculator.add] my_class.py:30 (12.2ms)
  IN:  {"a":10,"b":10}
  OUT: 20
[Calculator.multiply] my_class.py:31 (12.6ms)
  IN:  {"a":10,"b":2}
  OUT: 20
```

### Key Features

- **Code linking**: Each span shows `file:line` for direct navigation
- **Call tree**: Visualizes parent-child relationships between spans
- **Input/Output**: Shows function arguments and return values
- **Duration**: Timing in milliseconds for performance analysis
- **Error highlighting**: Flags spans with errors

---

## Debugging Approaches: Code Gen Logs vs Instrumentation

When debugging with Claude CLI, there are two main approaches:

### Comparison Table

| Factor | Code Gen Logs | instrument.py + trace_minify |
|--------|---------------|------------------------------|
| **Code ↔ Output linking** | Direct (Claude wrote the log) | `span_source` formatted as `file:line` |
| **Which file to read** | stdout | Single summary from trace_minify |
| **Iteration speed** | Slow (edit code → run) | Fast (just re-run) |
| **Error risk** | Can break code adding logs | None (no code changes) |
| **Custom context** | Flexible text messages | Structured input/output |
| **Call tree visibility** | Manual (add logs everywhere) | Auto-generated |
| **Inner loop debugging** | Can log inside loops | Only method in/out |
| **Dict/object inspection** | Manual JSON.stringify | Auto-parsed in trace |
| **Pattern detection** | Manual | Processor can flag issues |

### When to Use Each

| Use Case | Recommended Approach |
|----------|---------------------|
| Method-level debugging | **instrument.py** - faster, cleaner, auto call tree |
| Inner-loop / line-level debugging | **Code Gen Logs** - only way to see inside loops |
| Repeated iteration | **instrument.py** - no code changes needed |
| Understanding data flow | **instrument.py** - structured in/out |
| "Why is this variable X here?" | **Code Gen Logs** - specific context |
| Production debugging | **instrument.py** - zero code changes |

### Workflow Example

```bash
# 1. Define what to trace in monocle.yaml
# 2. Run with instrumentation
python instrument.py --config monocle.yaml my_app.py

# 3. View minified traces
python trace_minify.py --last 5m

# 4. If need inner-loop detail, add targeted print() statements
# 5. Re-run and check traces again
```

### What trace_minify.py Cannot See

```python
def process_items(items):
    for i, item in items:
        # trace_minify cannot see inside this loop
        transformed = transform(item)
        if transformed is None:
            # For this, use: print(f"Item {i} failed: {item}")
            continue
    return results
```

For inner-loop debugging, either:
1. Add targeted `print()` statements
2. Refactor the loop body to a separate function and instrument it

---

## Troubleshooting

### Spans not exporting to Okahu

The CLI automatically flushes spans on exit. You should see:
```
[Monocle] Spans flushed to exporters
```

If not, ensure:
1. `.env` has `export` prefix on all lines
2. Source before running: `source .env && python instrument.py ...`
3. Check API key is valid: `OKAHU_API_KEY: okh_TvXJ...ydgA`
