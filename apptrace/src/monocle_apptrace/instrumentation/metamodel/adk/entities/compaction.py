"""
ADK Memory Compaction entity processors for span creation.

This module defines span processors for:
- COMPACTION: The overall memory compaction operation
- SUMMARIZATION: The LLM-based summarization of events
"""

from monocle_apptrace.instrumentation.common.constants import SPAN_TYPES, SPAN_SUBTYPES
from monocle_apptrace.instrumentation.common.utils import get_error_message
from monocle_apptrace.instrumentation.metamodel.adk import _helper


COMPACTION = {
    "type": "memory.compaction",
    "subtype": SPAN_SUBTYPES.CONTENT_PROCESSING,
    "attributes": [
        [
            {
                "_comment": "compaction type",
                "attribute": "type",
                "accessor": lambda arguments: _helper.get_compaction_type(arguments)
            },
            {
                "_comment": "compaction mode (sliding_window or token_threshold)",
                "attribute": "mode",
                "accessor": lambda arguments: _helper.get_compaction_mode(arguments)
            },
            {
                "_comment": "app name",
                "attribute": "app_name",
                "accessor": lambda arguments: _helper.get_compaction_app_name(arguments)
            },
            {
                "_comment": "session id",
                "attribute": "session_id",
                "accessor": lambda arguments: _helper.get_compaction_session_id(arguments)
            },
        ]
    ],
    "events": [
        {
            "name": "data.input",
            "attributes": [
                {
                    "_comment": "compaction configuration",
                    "attribute": "config",
                    "accessor": lambda arguments: str(_helper.get_compaction_config(arguments))
                }
            ]
        },
        {
            "name": "data.output",
            "attributes": [
                {
                    "attribute": "error_code",
                    "accessor": lambda arguments: get_error_message(arguments)
                },
                {
                    "_comment": "whether compaction was performed",
                    "attribute": "compaction_performed",
                    "accessor": lambda arguments: str(_helper.was_compaction_successful(arguments))
                }
            ]
        }
    ]
}


SUMMARIZATION = {
    "type": SPAN_TYPES.MEMORY_COMPACTION,
    "subtype": SPAN_SUBTYPES.CONTENT_GENERATION,
    "attributes": [
        [
            {
                "_comment": "summarizer type",
                "attribute": "type",
                "accessor": lambda arguments: _helper.get_summarizer_type(arguments)
            },
            {
                "_comment": "number of events being summarized",
                "attribute": "event_count",
                "accessor": lambda arguments: _helper.get_events_to_compact_count(arguments)
            },
        ],
        [
            {
                "_comment": "LLM model used for summarization",
                "attribute": "name",
                "accessor": lambda arguments: _helper.get_summarizer_model(arguments['instance'])
            },
            {
                "attribute": "type",
                "accessor": lambda arguments: 'model.llm.' + (_helper.get_summarizer_model(arguments['instance']) or 'unknown')
            }
        ],
    ],
    "events": [
        {
            "name": "data.input",
            "attributes": [
                {
                    "_comment": "conversation history being summarized",
                    "attribute": "input",
                    "accessor": lambda arguments: _helper.extract_summarizer_input(arguments)
                },
                {
                    "_comment": "time range of events",
                    "attribute": "time_range",
                    "accessor": lambda arguments: str(_helper.get_compaction_time_range(arguments))
                }
            ]
        },
        {
            "name": "data.output",
            "attributes": [
                {
                    "attribute": "error_code",
                    "accessor": lambda arguments: get_error_message(arguments)
                },
                {
                    "_comment": "generated summary",
                    "attribute": "response",
                    "accessor": lambda arguments: _helper.extract_compacted_summary(arguments)
                }
            ]
        }
    ]
}
