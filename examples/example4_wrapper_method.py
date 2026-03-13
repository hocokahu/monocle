"""
Example 4: Using WrapperMethod configuration for automatic instrumentation

This approach instruments functions/methods at import time based on configuration.
Best for instrumenting third-party libraries or when you can't modify source code.

Key difference from decorators:
- Decorators: You modify the function definition
- WrapperMethod: You configure which functions to wrap externally

Usage:
    python example4_wrapper_method.py
"""
import asyncio
import json
import time
import sys
import os

# Add examples directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# =============================================================================
# DEFINE FUNCTIONS/CLASSES BEFORE INSTRUMENTATION SETUP
# These are defined in separate modules in real-world usage
# =============================================================================

# --- Module-level standalone functions ---
# In real usage, these would be in a separate module like "my_functions.py"

def standalone_sum(a: int, b: int) -> int:
    """Standalone function to be instrumented via WrapperMethod."""
    time.sleep(0.01)
    return a + b


def standalone_product(a: int, b: int) -> int:
    """Another standalone function to be instrumented."""
    time.sleep(0.01)
    return a * b


async def async_standalone_fetch(item_id: int) -> dict:
    """Async standalone function to be instrumented."""
    await asyncio.sleep(0.01)
    return {"id": item_id, "data": f"item_{item_id}"}


# --- Class-based functions ---
# In real usage, this would be in a separate module like "my_class.py"

class MyCalculator:
    """Calculator class to be instrumented via WrapperMethod."""

    def __init__(self, name: str = "calc"):
        self.name = name

    def add(self, a: int, b: int) -> int:
        """Method to be instrumented."""
        time.sleep(0.01)
        return a + b

    def multiply(self, a: int, b: int) -> int:
        """Method to be instrumented."""
        time.sleep(0.01)
        return a * b

    def chain_operation(self, x: int) -> int:
        """Method that calls other instrumented methods."""
        return self.add(x, x) + self.multiply(x, 2)


class MyAsyncService:
    """Async service class to be instrumented."""

    async def fetch_item(self, item_id: int) -> dict:
        """Async method to be instrumented."""
        await asyncio.sleep(0.01)
        return {"id": item_id, "fetched": True}

    async def fetch_batch(self, ids: list) -> list:
        """Async method calling other instrumented methods."""
        return [await self.fetch_item(i) for i in ids]


# =============================================================================
# SETUP INSTRUMENTATION
# =============================================================================

from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry
from monocle_apptrace.instrumentation.common.wrapper_method import WrapperMethod
from monocle_apptrace.instrumentation.common.wrapper import task_wrapper, atask_wrapper
from span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


# Create in-memory exporter to capture spans
exporter = InMemorySpanExporter()

# Define which functions/methods to instrument using WrapperMethod
wrapper_methods = [
    # --- Standalone functions (object_name=None) ---
    WrapperMethod(
        package="__main__",           # Module where function is defined
        object_name=None,             # None = module-level function (NOT in a class)
        method="standalone_sum",      # Function name
        span_name="standalone_sum",   # Span name (optional, defaults to method name)
        wrapper_method=task_wrapper   # Use task_wrapper for sync functions
    ),
    WrapperMethod(
        package="__main__",
        object_name=None,
        method="standalone_product",
        span_name="custom_product_span",  # Custom span name
        wrapper_method=task_wrapper
    ),
    # --- Async standalone function ---
    WrapperMethod(
        package="__main__",
        object_name=None,
        method="async_standalone_fetch",
        span_name="async_fetch",
        wrapper_method=atask_wrapper  # Use atask_wrapper for async functions
    ),
    # --- Class methods ---
    WrapperMethod(
        package="__main__",
        object_name="MyCalculator",   # Class name
        method="add",                 # Method name
        span_name="calculator_add",
        wrapper_method=task_wrapper
    ),
    WrapperMethod(
        package="__main__",
        object_name="MyCalculator",
        method="multiply",
        span_name="calculator_multiply",
        wrapper_method=task_wrapper
    ),
    WrapperMethod(
        package="__main__",
        object_name="MyCalculator",
        method="chain_operation",
        span_name="calculator_chain",
        wrapper_method=task_wrapper
    ),
    # --- Async class methods ---
    WrapperMethod(
        package="__main__",
        object_name="MyAsyncService",
        method="fetch_item",
        span_name="service_fetch_item",
        wrapper_method=atask_wrapper
    ),
    WrapperMethod(
        package="__main__",
        object_name="MyAsyncService",
        method="fetch_batch",
        span_name="service_fetch_batch",
        wrapper_method=atask_wrapper
    ),
]

# Setup Monocle telemetry with custom wrapper methods
# IMPORTANT: union_with_default_methods=False means ONLY use our custom wrappers
setup_monocle_telemetry(
    workflow_name="wrapper_method_example",
    span_processors=[SimpleSpanProcessor(exporter)],
    wrapper_methods=wrapper_methods,
    union_with_default_methods=False  # Don't include default framework instrumentations
)


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
# MAIN - Run examples and show trace output
# =============================================================================

async def main():
    print("\n" + "="*60)
    print("EXAMPLE 4: WrapperMethod Configuration-Based Instrumentation")
    print("="*60)

    # ----- Standalone functions -----
    print("\n--- Testing Standalone Functions (object_name=None) ---")

    result = standalone_sum(5, 3)
    print(f"standalone_sum(5, 3) = {result}")
    print_spans("Spans for standalone_sum:")

    result = standalone_product(4, 7)
    print(f"standalone_product(4, 7) = {result}")
    print_spans("Spans for standalone_product (custom span name):")

    # ----- Async standalone function -----
    print("\n--- Testing Async Standalone Function ---")

    result = await async_standalone_fetch(42)
    print(f"async_standalone_fetch(42) = {result}")
    print_spans("Spans for async_standalone_fetch:")

    # ----- Class methods -----
    print("\n--- Testing Class Methods ---")

    calc = MyCalculator("my_calc")

    result = calc.add(10, 20)
    print(f"calc.add(10, 20) = {result}")
    print_spans("Spans for MyCalculator.add:")

    result = calc.multiply(6, 7)
    print(f"calc.multiply(6, 7) = {result}")
    print_spans("Spans for MyCalculator.multiply:")

    # ----- Nested method calls -----
    print("\n--- Testing Nested Method Calls ---")

    result = calc.chain_operation(5)
    print(f"calc.chain_operation(5) = {result}")
    print_spans("Spans for chain_operation (calls add + multiply):")

    # ----- Async class methods -----
    print("\n--- Testing Async Class Methods ---")

    service = MyAsyncService()

    result = await service.fetch_item(1)
    print(f"service.fetch_item(1) = {result}")
    print_spans("Spans for MyAsyncService.fetch_item:")

    # ----- Nested async calls -----
    print("\n--- Testing Nested Async Calls ---")

    result = await service.fetch_batch([1, 2, 3])
    print(f"service.fetch_batch([1, 2, 3]) = {result}")
    print_spans("Spans for fetch_batch (calls fetch_item x3):")

    # ----- Dict-based configuration (alternative to WrapperMethod) -----
    print("\n" + "="*60)
    print("NOTE: You can also use dict format instead of WrapperMethod:")
    print("="*60)
    print("""
# Dict format (equivalent to WrapperMethod):
wrapper_methods = [
    {
        "package": "my_module",
        "object": None,              # None for standalone functions
        "method": "my_function",
        "span_name": "my_function",
        "wrapper_method": task_wrapper
    },
    {
        "package": "my_module",
        "object": "MyClass",         # Class name for methods
        "method": "my_method",
        "span_name": "my_method",
        "wrapper_method": task_wrapper
    }
]
""")


if __name__ == "__main__":
    asyncio.run(main())
