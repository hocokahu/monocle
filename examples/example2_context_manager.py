"""
Example 2: Using monocle_trace() / amonocle_trace() context managers

Context managers wrap blocks of code and automatically create spans.
Good for wrapping existing code without modifying function signatures.

Usage:
    python example2_context_manager.py
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
    monocle_trace,
    amonocle_trace,
)
from span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


# Create in-memory exporter to capture spans
exporter = InMemorySpanExporter()

# Setup Monocle telemetry
setup_monocle_telemetry(
    workflow_name="context_manager_example",
    span_processors=[SimpleSpanProcessor(exporter)]
)


# =============================================================================
# UNINSTRUMENTED FUNCTIONS (will be wrapped by context managers)
# =============================================================================

def calculate_sum(a: int, b: int) -> int:
    """Plain function - not instrumented."""
    time.sleep(0.01)
    return a + b


def calculate_product(a: int, b: int) -> int:
    """Plain function - not instrumented."""
    time.sleep(0.01)
    return a * b


async def async_fetch_data(item_id: int) -> dict:
    """Plain async function - not instrumented."""
    await asyncio.sleep(0.01)
    return {"id": item_id, "name": f"Item {item_id}"}


class Calculator:
    """Plain class - not instrumented."""

    def add(self, a: int, b: int) -> int:
        time.sleep(0.01)
        return a + b

    def multiply(self, a: int, b: int) -> int:
        time.sleep(0.01)
        return a * b


class AsyncService:
    """Plain async service - not instrumented."""

    async def fetch_item(self, item_id: int) -> dict:
        await asyncio.sleep(0.01)
        return {"id": item_id, "data": "fetched"}


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
# MAIN - Demonstrate context manager usage
# =============================================================================

async def main():
    print("\n" + "="*60)
    print("EXAMPLE 2: monocle_trace() / amonocle_trace() Context Managers")
    print("="*60)

    # ----- Basic usage -----
    print("\n--- Basic Context Manager Usage ---")

    with monocle_trace(span_name="sum_operation"):
        result = calculate_sum(5, 3)
        print(f"calculate_sum(5, 3) = {result}")

    print_spans("Spans for basic monocle_trace:")

    # ----- With custom attributes -----
    print("\n--- Context Manager with Attributes ---")

    with monocle_trace(
        span_name="product_with_attrs",
        attributes={
            "operation.type": "multiplication",
            "input.a": 4,
            "input.b": 7,
            "user.id": "user_123"
        }
    ):
        result = calculate_product(4, 7)
        print(f"calculate_product(4, 7) = {result}")

    print_spans("Spans with custom attributes:")

    # ----- With events -----
    print("\n--- Context Manager with Events ---")

    with monocle_trace(
        span_name="operation_with_events",
        events=[
            {"name": "calculation_started", "attributes": {"step": "init"}},
            {"name": "input_validated", "attributes": {"valid": True}}
        ]
    ):
        result = calculate_sum(10, 20)
        print(f"calculate_sum(10, 20) = {result}")

    print_spans("Spans with events:")

    # ----- Wrapping multiple operations -----
    print("\n--- Wrapping Multiple Operations ---")

    with monocle_trace(span_name="batch_calculations"):
        results = []
        results.append(calculate_sum(1, 2))
        results.append(calculate_product(3, 4))
        results.append(calculate_sum(5, 6))
        print(f"Batch results: {results}")

    print_spans("Spans for batch operations:")

    # ----- Nested context managers -----
    print("\n--- Nested Context Managers ---")

    with monocle_trace(span_name="outer_operation"):
        with monocle_trace(span_name="inner_operation_1"):
            result1 = calculate_sum(1, 1)
        with monocle_trace(span_name="inner_operation_2"):
            result2 = calculate_product(2, 2)
        final = result1 + result2
        print(f"Nested result: {final}")

    print_spans("Spans for nested context managers:")

    # ----- Async context manager -----
    print("\n--- Async Context Manager (amonocle_trace) ---")

    async with amonocle_trace(span_name="async_fetch_operation"):
        result = await async_fetch_data(42)
        print(f"async_fetch_data(42) = {result}")

    print_spans("Spans for async context manager:")

    # ----- Async with attributes -----
    print("\n--- Async Context Manager with Attributes ---")

    async with amonocle_trace(
        span_name="async_batch_fetch",
        attributes={
            "operation": "batch_fetch",
            "item_count": 3
        }
    ):
        results = []
        for i in [1, 2, 3]:
            data = await async_fetch_data(i)
            results.append(data)
        print(f"Async batch results: {results}")

    print_spans("Spans for async batch with attributes:")

    # ----- Wrapping class methods -----
    print("\n--- Wrapping Class Methods ---")

    calc = Calculator()

    with monocle_trace(span_name="calculator_operations"):
        result = calc.add(10, 20)
        result = calc.multiply(result, 2)
        print(f"Calculator result: {result}")

    print_spans("Spans for wrapped class methods:")

    # ----- Async class methods -----
    print("\n--- Wrapping Async Class Methods ---")

    service = AsyncService()

    async with amonocle_trace(
        span_name="service_operations",
        attributes={"service": "AsyncService"}
    ):
        item1 = await service.fetch_item(1)
        item2 = await service.fetch_item(2)
        print(f"Service results: {[item1, item2]}")

    print_spans("Spans for wrapped async class methods:")


if __name__ == "__main__":
    asyncio.run(main())
