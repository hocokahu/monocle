"""
Run all 4 instrumentation examples and save JSON output to .monocle/
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".monocle")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_spans(exporter, filename):
    """Save captured spans to JSON file."""
    spans = exporter.get_captured_spans()
    spans_data = []
    for span in spans:
        spans_data.append(json.loads(span.to_json()))

    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(spans_data, f, indent=2)
    print(f"Saved {len(spans_data)} spans to {filepath}")
    exporter.clear()
    return spans_data


# =============================================================================
# EXAMPLE 1: @monocle_trace_method() Decorator
# =============================================================================

def run_example1():
    print("\n" + "="*60)
    print("EXAMPLE 1: @monocle_trace_method() Decorator")
    print("="*60)

    from monocle_apptrace.instrumentation.common.instrumentor import (
        setup_monocle_telemetry,
        monocle_trace_method,
    )

    exporter = InMemorySpanExporter()
    setup_monocle_telemetry(
        workflow_name="example1_decorator",
        span_processors=[SimpleSpanProcessor(exporter)]
    )

    # Standalone function
    @monocle_trace_method()
    def calculate_sum(a: int, b: int) -> int:
        time.sleep(0.01)
        return a + b

    @monocle_trace_method(span_name="custom_multiply")
    def calculate_product(a: int, b: int) -> int:
        time.sleep(0.01)
        return a * b

    # Class with methods
    class Calculator:
        @monocle_trace_method()
        def add(self, a: int, b: int) -> int:
            time.sleep(0.01)
            return a + b

        @monocle_trace_method(span_name="calc_multiply")
        def multiply(self, a: int, b: int) -> int:
            time.sleep(0.01)
            return a * b

    # Run standalone functions
    print("Running standalone functions...")
    calculate_sum(5, 3)
    calculate_product(4, 7)

    # Run class methods
    print("Running class methods...")
    calc = Calculator()
    calc.add(10, 20)
    calc.multiply(6, 7)

    save_spans(exporter, "example1_decorator.json")


# =============================================================================
# EXAMPLE 2: monocle_trace() Context Manager
# =============================================================================

def run_example2():
    print("\n" + "="*60)
    print("EXAMPLE 2: monocle_trace() Context Manager")
    print("="*60)

    from monocle_apptrace.instrumentation.common.instrumentor import (
        setup_monocle_telemetry,
        monocle_trace,
    )

    exporter = InMemorySpanExporter()
    setup_monocle_telemetry(
        workflow_name="example2_context_manager",
        span_processors=[SimpleSpanProcessor(exporter)]
    )

    # Plain functions (not instrumented)
    def calculate_sum(a: int, b: int) -> int:
        time.sleep(0.01)
        return a + b

    def calculate_product(a: int, b: int) -> int:
        time.sleep(0.01)
        return a * b

    # Plain class
    class Calculator:
        def add(self, a: int, b: int) -> int:
            time.sleep(0.01)
            return a + b

    # Wrap standalone functions
    print("Wrapping standalone functions...")
    with monocle_trace(span_name="sum_operation"):
        calculate_sum(5, 3)

    with monocle_trace(span_name="product_with_attrs", attributes={"operation": "multiply", "user.id": "123"}):
        calculate_product(4, 7)

    # Wrap class methods
    print("Wrapping class methods...")
    calc = Calculator()
    with monocle_trace(span_name="calculator_add"):
        calc.add(10, 20)

    # Nested context managers
    print("Running nested context managers...")
    with monocle_trace(span_name="outer_operation"):
        with monocle_trace(span_name="inner_op_1"):
            calculate_sum(1, 1)
        with monocle_trace(span_name="inner_op_2"):
            calculate_product(2, 2)

    save_spans(exporter, "example2_context_manager.json")


# =============================================================================
# EXAMPLE 3: start_trace() / stop_trace()
# =============================================================================

def run_example3():
    print("\n" + "="*60)
    print("EXAMPLE 3: start_trace() / stop_trace()")
    print("="*60)

    from monocle_apptrace.instrumentation.common.instrumentor import (
        setup_monocle_telemetry,
        start_trace,
        stop_trace,
    )

    exporter = InMemorySpanExporter()
    setup_monocle_telemetry(
        workflow_name="example3_start_stop",
        span_processors=[SimpleSpanProcessor(exporter)]
    )

    # Plain functions
    def calculate_sum(a: int, b: int) -> int:
        time.sleep(0.01)
        return a + b

    def calculate_product(a: int, b: int) -> int:
        time.sleep(0.01)
        return a * b

    # Plain class
    class Calculator:
        def add(self, a: int, b: int) -> int:
            time.sleep(0.01)
            return a + b

    # Trace standalone functions
    print("Tracing standalone functions...")
    token = start_trace(span_name="sum_trace")
    calculate_sum(5, 3)
    stop_trace(token)

    token = start_trace(span_name="product_trace", attributes={"operation": "multiply"})
    result = calculate_product(4, 7)
    stop_trace(token, final_attributes={"result": result})

    # Trace class methods
    print("Tracing class methods...")
    calc = Calculator()
    token = start_trace(span_name="calculator_session", attributes={"calculator": "Calculator"})
    calc.add(10, 20)
    calc.add(30, 40)
    stop_trace(token, final_attributes={"operations": 2})

    save_spans(exporter, "example3_start_stop.json")


# =============================================================================
# EXAMPLE 4: WrapperMethod Configuration
# =============================================================================

def run_example4():
    print("\n" + "="*60)
    print("EXAMPLE 4: WrapperMethod Configuration")
    print("="*60)

    # Import the module that has functions/classes to wrap
    # We'll use my_functions.py and my_class.py

    from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry
    from monocle_apptrace.instrumentation.common.wrapper_method import WrapperMethod
    from monocle_apptrace.instrumentation.common.wrapper import task_wrapper, atask_wrapper

    exporter = InMemorySpanExporter()

    # Define wrapper methods for my_functions.py and my_class.py
    wrapper_methods = [
        # Standalone functions from my_functions.py
        WrapperMethod(
            package="my_functions",
            object_name=None,  # None = standalone function
            method="calculate_sum",
            span_name="my_func_sum",
            wrapper_method=task_wrapper
        ),
        WrapperMethod(
            package="my_functions",
            object_name=None,
            method="calculate_product",
            span_name="my_func_product",
            wrapper_method=task_wrapper
        ),
        # Class methods from my_class.py
        WrapperMethod(
            package="my_class",
            object_name="Calculator",
            method="add",
            span_name="my_class_calc_add",
            wrapper_method=task_wrapper
        ),
        WrapperMethod(
            package="my_class",
            object_name="Calculator",
            method="multiply",
            span_name="my_class_calc_multiply",
            wrapper_method=task_wrapper
        ),
    ]

    setup_monocle_telemetry(
        workflow_name="example4_wrapper_method",
        span_processors=[SimpleSpanProcessor(exporter)],
        wrapper_methods=wrapper_methods,
        union_with_default_methods=False
    )

    # Import after setup so instrumentation is applied
    import my_functions
    import my_class

    # Run standalone functions
    print("Running standalone functions from my_functions.py...")
    my_functions.calculate_sum(5, 3)
    my_functions.calculate_product(4, 7)

    # Run class methods
    print("Running class methods from my_class.py...")
    calc = my_class.Calculator("test_calc")
    calc.add(10, 20)
    calc.multiply(6, 7)

    save_spans(exporter, "example4_wrapper_method.json")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("Running all 4 instrumentation examples...")
    print(f"Output directory: {OUTPUT_DIR}")

    run_example1()
    run_example2()
    run_example3()
    run_example4()

    print("\n" + "="*60)
    print("DONE! JSON files saved to examples/.monocle/")
    print("="*60)

    # List output files
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith('.json'):
            filepath = os.path.join(OUTPUT_DIR, f)
            size = os.path.getsize(filepath)
            print(f"  {f} ({size} bytes)")


if __name__ == "__main__":
    main()
