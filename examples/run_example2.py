"""Run Example 2 and save JSON output."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from monocle_apptrace.instrumentation.common.instrumentor import (
    setup_monocle_telemetry,
    monocle_trace,
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".monocle")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

print("EXAMPLE 2: monocle_trace() Context Manager")
print("Wrapping standalone functions...")
with monocle_trace(span_name="sum_operation"):
    calculate_sum(5, 3)

with monocle_trace(span_name="product_with_attrs", attributes={"operation": "multiply", "user.id": "123"}):
    calculate_product(4, 7)

print("Wrapping class methods...")
calc = Calculator()
with monocle_trace(span_name="calculator_add"):
    calc.add(10, 20)

print("Running nested context managers...")
with monocle_trace(span_name="outer_operation"):
    with monocle_trace(span_name="inner_op_1"):
        calculate_sum(1, 1)
    with monocle_trace(span_name="inner_op_2"):
        calculate_product(2, 2)

# Save spans
spans_data = [json.loads(span.to_json()) for span in exporter.get_captured_spans()]
filepath = os.path.join(OUTPUT_DIR, "example2_context_manager.json")
with open(filepath, 'w') as f:
    json.dump(spans_data, f, indent=2)
print(f"Saved {len(spans_data)} spans to {filepath}")
