"""
Example 3: Using start_trace() / stop_trace() for manual control

This approach gives you fine-grained control over trace lifecycle.
Useful when you can't use context managers (e.g., callbacks, event handlers).

Usage:
    python example3_start_stop.py
"""
import asyncio
import json
import time
import sys
import os

# Add examples directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from monocle_apptrace.instrumentation.common.instrumentor import (
    setup_monocle_telemetry,
    start_trace,
    stop_trace,
)
from span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


# Create in-memory exporter to capture spans
exporter = InMemorySpanExporter()

# Setup Monocle telemetry
setup_monocle_telemetry(
    workflow_name="start_stop_example",
    span_processors=[SimpleSpanProcessor(exporter)]
)


# =============================================================================
# UNINSTRUMENTED FUNCTIONS
# =============================================================================

def calculate_sum(a: int, b: int) -> int:
    """Plain function."""
    time.sleep(0.01)
    return a + b


def calculate_product(a: int, b: int) -> int:
    """Plain function."""
    time.sleep(0.01)
    return a * b


def process_data(data: list) -> list:
    """Plain function that processes data."""
    time.sleep(0.01)
    return [x * 2 for x in data]


async def async_fetch_data(item_id: int) -> dict:
    """Plain async function."""
    await asyncio.sleep(0.01)
    return {"id": item_id, "name": f"Item {item_id}"}


class Calculator:
    """Plain calculator class."""

    def add(self, a: int, b: int) -> int:
        time.sleep(0.01)
        return a + b

    def multiply(self, a: int, b: int) -> int:
        time.sleep(0.01)
        return a * b


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_spans(title: str):
    """Print captured spans in JSON format."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)

    spans = exporter.get_captured_spans()
    for span in spans:
        span_dict = json.loads(span.to_json())
        print(json.dumps(span_dict, indent=2))

    exporter.clear()


# =============================================================================
# MAIN - Demonstrate start_trace / stop_trace usage
# =============================================================================

async def main():
    print("\n" + "="*60)
    print("EXAMPLE 3: start_trace() / stop_trace() Manual Control")
    print("="*60)

    # ----- Basic usage -----
    print("\n--- Basic start_trace / stop_trace ---")

    token = start_trace(span_name="basic_operation")
    result = calculate_sum(5, 3)
    print(f"calculate_sum(5, 3) = {result}")
    stop_trace(token)

    print_spans("Spans for basic start/stop:")

    # ----- With attributes at start -----
    print("\n--- With Start Attributes ---")

    token = start_trace(
        span_name="operation_with_start_attrs",
        attributes={
            "operation.type": "multiplication",
            "user.id": "user_456",
            "priority": "high"
        }
    )
    result = calculate_product(6, 7)
    print(f"calculate_product(6, 7) = {result}")
    stop_trace(token)

    print_spans("Spans with start attributes:")

    # ----- With events at start -----
    print("\n--- With Start Events ---")

    token = start_trace(
        span_name="operation_with_events",
        events=[
            {"name": "trace_initiated", "attributes": {"source": "main"}},
            {"name": "validation_passed"}
        ]
    )
    result = calculate_sum(100, 200)
    print(f"calculate_sum(100, 200) = {result}")
    stop_trace(token)

    print_spans("Spans with start events:")

    # ----- With final attributes at stop -----
    print("\n--- With Final Attributes at Stop ---")

    token = start_trace(
        span_name="operation_with_final_attrs",
        attributes={"start_time": "now"}
    )

    data = [1, 2, 3, 4, 5]
    result = process_data(data)
    print(f"process_data({data}) = {result}")

    stop_trace(
        token,
        final_attributes={
            "result.count": len(result),
            "result.sum": sum(result),
            "status": "success"
        }
    )

    print_spans("Spans with final attributes:")

    # ----- With final events at stop -----
    print("\n--- With Final Events at Stop ---")

    token = start_trace(span_name="operation_with_final_events")

    result = calculate_product(10, 10)
    print(f"calculate_product(10, 10) = {result}")

    stop_trace(
        token,
        final_events=[
            {"name": "calculation_complete", "attributes": {"result": result}},
            {"name": "trace_ended", "attributes": {"success": True}}
        ]
    )

    print_spans("Spans with final events:")

    # ----- Multiple operations in one trace -----
    print("\n--- Multiple Operations in One Trace ---")

    token = start_trace(
        span_name="batch_processing",
        attributes={"batch_id": "batch_001"}
    )

    results = []
    results.append(calculate_sum(1, 2))
    results.append(calculate_product(3, 4))
    results.append(calculate_sum(5, 6))
    print(f"Batch results: {results}")

    stop_trace(
        token,
        final_attributes={
            "total_operations": len(results),
            "final_sum": sum(results)
        }
    )

    print_spans("Spans for batch processing:")

    # ----- Error handling with try/finally -----
    print("\n--- Error Handling with try/finally ---")

    token = start_trace(span_name="safe_operation")
    try:
        result = calculate_sum(50, 50)
        print(f"calculate_sum(50, 50) = {result}")
        # Simulate potential error
        # raise ValueError("Simulated error")
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        stop_trace(
            token,
            final_attributes={"completed": True}
        )

    print_spans("Spans with error handling:")

    # ----- Class method tracing -----
    print("\n--- Tracing Class Methods ---")

    calc = Calculator()

    token = start_trace(
        span_name="calculator_session",
        attributes={"calculator": "Calculator"}
    )

    result1 = calc.add(10, 20)
    result2 = calc.multiply(result1, 2)
    final_result = calc.add(result2, 5)
    print(f"Calculator chain result: {final_result}")

    stop_trace(
        token,
        final_attributes={
            "final_result": final_result,
            "operations_count": 3
        }
    )

    print_spans("Spans for calculator session:")

    # ----- Async operations -----
    print("\n--- Async Operations ---")

    token = start_trace(
        span_name="async_fetch_session",
        attributes={"async": True}
    )

    item1 = await async_fetch_data(1)
    item2 = await async_fetch_data(2)
    item3 = await async_fetch_data(3)
    results = [item1, item2, item3]
    print(f"Async fetch results: {results}")

    stop_trace(
        token,
        final_attributes={
            "items_fetched": len(results)
        }
    )

    print_spans("Spans for async operations:")

    # ----- Callback-style usage (simulated) -----
    print("\n--- Callback-Style Usage ---")

    # Simulating a callback-based API where you can't use context managers
    def on_start():
        return start_trace(
            span_name="callback_operation",
            attributes={"callback": True}
        )

    def on_complete(token, result):
        stop_trace(
            token,
            final_attributes={"callback_result": result}
        )

    # Simulate callback flow
    token = on_start()
    result = calculate_sum(999, 1)
    print(f"Callback result: {result}")
    on_complete(token, result)

    print_spans("Spans for callback-style usage:")


if __name__ == "__main__":
    asyncio.run(main())
