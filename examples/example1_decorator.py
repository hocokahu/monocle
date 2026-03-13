"""
Example 1: Using @monocle_trace_method() decorator

This is the simplest way to instrument functions (both standalone and class methods).
The decorator automatically creates spans for each function call.

Usage:
    python example1_decorator.py
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
    monocle_trace_method,
)
from span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


# Create in-memory exporter to capture spans
exporter = InMemorySpanExporter()

# Setup Monocle telemetry
setup_monocle_telemetry(
    workflow_name="decorator_example",
    span_processors=[SimpleSpanProcessor(exporter)]
)


# =============================================================================
# STANDALONE FUNCTIONS with @monocle_trace_method decorator
# =============================================================================

@monocle_trace_method()  # Uses function name as span name
def calculate_sum(a: int, b: int) -> int:
    """Instrumented standalone function - uses function name as span."""
    time.sleep(0.01)
    return a + b


@monocle_trace_method(span_name="custom_multiply_span")  # Custom span name
def calculate_product(a: int, b: int) -> int:
    """Instrumented standalone function - with custom span name."""
    time.sleep(0.01)
    return a * b


@monocle_trace_method(span_name="complex_calc")
def complex_calculation(x: int) -> int:
    """Instrumented function that calls other instrumented functions."""
    sum_result = calculate_sum(x, x)
    product_result = calculate_product(x, 2)
    return sum_result + product_result


# =============================================================================
# ASYNC FUNCTIONS with @monocle_trace_method decorator
# =============================================================================

@monocle_trace_method()
async def async_fetch_data(item_id: int) -> dict:
    """Instrumented async function."""
    await asyncio.sleep(0.01)
    return {"id": item_id, "name": f"Item {item_id}"}


@monocle_trace_method(span_name="async_process")
async def async_process_items(item_ids: list) -> list:
    """Instrumented async function calling other instrumented async functions."""
    results = []
    for item_id in item_ids:
        data = await async_fetch_data(item_id)
        results.append(data)
    return results


# =============================================================================
# CLASS METHODS with @monocle_trace_method decorator
# =============================================================================

class Calculator:
    """Calculator class with instrumented methods."""

    def __init__(self, name: str = "Calculator"):
        self.name = name

    @monocle_trace_method()
    def add(self, a: int, b: int) -> int:
        """Instrumented class method."""
        time.sleep(0.01)
        return a + b

    @monocle_trace_method(span_name="calculator_multiply")
    def multiply(self, a: int, b: int) -> int:
        """Instrumented class method with custom span name."""
        time.sleep(0.01)
        return a * b

    @monocle_trace_method()
    def complex_operation(self, x: int) -> int:
        """Instrumented method calling other instrumented methods."""
        return self.add(x, x) + self.multiply(x, 2)


class AsyncService:
    """Async service class with instrumented methods."""

    @monocle_trace_method()
    async def fetch_item(self, item_id: int) -> dict:
        """Instrumented async class method."""
        await asyncio.sleep(0.01)
        return {"id": item_id, "data": "fetched"}

    @monocle_trace_method(span_name="service_fetch_all")
    async def fetch_all(self, ids: list) -> list:
        """Instrumented async method calling other instrumented methods."""
        return [await self.fetch_item(i) for i in ids]


# =============================================================================
# MAIN - Run examples and show trace output
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


async def main():
    print("\n" + "="*60)
    print("EXAMPLE 1: @monocle_trace_method() Decorator")
    print("="*60)

    # Test standalone functions
    print("\n--- Testing Standalone Functions ---")
    result = calculate_sum(5, 3)
    print(f"calculate_sum(5, 3) = {result}")
    print_spans("Spans for calculate_sum:")

    result = calculate_product(4, 7)
    print(f"calculate_product(4, 7) = {result}")
    print_spans("Spans for calculate_product (custom span name):")

    result = complex_calculation(5)
    print(f"complex_calculation(5) = {result}")
    print_spans("Spans for complex_calculation (nested calls):")

    # Test async functions
    print("\n--- Testing Async Functions ---")
    result = await async_fetch_data(42)
    print(f"async_fetch_data(42) = {result}")
    print_spans("Spans for async_fetch_data:")

    result = await async_process_items([1, 2, 3])
    print(f"async_process_items([1, 2, 3]) = {result}")
    print_spans("Spans for async_process_items (nested async calls):")

    # Test class methods
    print("\n--- Testing Class Methods ---")
    calc = Calculator("MyCalc")

    result = calc.add(10, 20)
    print(f"calc.add(10, 20) = {result}")
    print_spans("Spans for Calculator.add:")

    result = calc.complex_operation(5)
    print(f"calc.complex_operation(5) = {result}")
    print_spans("Spans for Calculator.complex_operation (nested method calls):")

    # Test async class methods
    print("\n--- Testing Async Class Methods ---")
    service = AsyncService()

    result = await service.fetch_all([1, 2])
    print(f"service.fetch_all([1, 2]) = {result}")
    print_spans("Spans for AsyncService.fetch_all:")


if __name__ == "__main__":
    asyncio.run(main())
