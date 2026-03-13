"""Run Example 3 and save JSON output."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from monocle_apptrace.instrumentation.common.instrumentor import (
    setup_monocle_telemetry,
    start_trace,
    stop_trace,
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".monocle")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

print("EXAMPLE 3: start_trace() / stop_trace()")
print("Tracing standalone functions...")
token = start_trace(span_name="sum_trace")
calculate_sum(5, 3)
stop_trace(token)

token = start_trace(span_name="product_trace", attributes={"operation": "multiply"})
result = calculate_product(4, 7)
stop_trace(token, final_attributes={"result": result})

print("Tracing class methods...")
calc = Calculator()
token = start_trace(span_name="calculator_session", attributes={"calculator": "Calculator"})
calc.add(10, 20)
calc.add(30, 40)
stop_trace(token, final_attributes={"operations": 2})

# Save spans
spans_data = [json.loads(span.to_json()) for span in exporter.get_captured_spans()]
filepath = os.path.join(OUTPUT_DIR, "example3_start_stop.json")
with open(filepath, 'w') as f:
    json.dump(spans_data, f, indent=2)
print(f"Saved {len(spans_data)} spans to {filepath}")
