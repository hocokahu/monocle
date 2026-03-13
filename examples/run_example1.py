"""Run Example 1 and save JSON output."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from monocle_apptrace.instrumentation.common.instrumentor import (
    setup_monocle_telemetry,
    monocle_trace_method,
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".monocle")
os.makedirs(OUTPUT_DIR, exist_ok=True)

exporter = InMemorySpanExporter()
setup_monocle_telemetry(
    workflow_name="example1_decorator",
    span_processors=[SimpleSpanProcessor(exporter)]
)

# Standalone functions
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

print("EXAMPLE 1: @monocle_trace_method() Decorator")
print("Running standalone functions...")
calculate_sum(5, 3)
calculate_product(4, 7)

print("Running class methods...")
calc = Calculator()
calc.add(10, 20)
calc.multiply(6, 7)

# Save spans
spans_data = [json.loads(span.to_json()) for span in exporter.get_captured_spans()]
filepath = os.path.join(OUTPUT_DIR, "example1_decorator.json")
with open(filepath, 'w') as f:
    json.dump(spans_data, f, indent=2)
print(f"Saved {len(spans_data)} spans to {filepath}")
