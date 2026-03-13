"""Run Example 4 and save JSON output."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry
from monocle_apptrace.instrumentation.common.wrapper_method import WrapperMethod
from monocle_apptrace.instrumentation.common.wrapper import task_wrapper

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".monocle")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

# Import AFTER setup so instrumentation is applied
import my_functions
import my_class

print("EXAMPLE 4: WrapperMethod Configuration")
print("Running standalone functions from my_functions.py...")
my_functions.calculate_sum(5, 3)
my_functions.calculate_product(4, 7)

print("Running class methods from my_class.py...")
calc = my_class.Calculator("test_calc")
calc.add(10, 20)
calc.multiply(6, 7)

# Save spans
spans_data = [json.loads(span.to_json()) for span in exporter.get_captured_spans()]
filepath = os.path.join(OUTPUT_DIR, "example4_wrapper_method.json")
with open(filepath, 'w') as f:
    json.dump(spans_data, f, indent=2)
print(f"Saved {len(spans_data)} spans to {filepath}")
