"""
Simple in-memory span exporter for examples.
"""
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


class InMemorySpanExporter(SpanExporter):
    """Simple span exporter that stores spans in memory for inspection."""

    def __init__(self):
        self._spans = []

    def export(self, spans):
        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_captured_spans(self):
        return list(self._spans)

    def clear(self):
        self._spans.clear()

    def shutdown(self):
        self.clear()

    def force_flush(self, timeout_millis=30000):
        return True
