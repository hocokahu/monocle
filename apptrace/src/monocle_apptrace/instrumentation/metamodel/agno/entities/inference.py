"""
Agno Model inference entity processor for span creation.
"""

from monocle_apptrace.instrumentation.common.constants import SPAN_TYPES
from monocle_apptrace.instrumentation.common.utils import get_error_message
from monocle_apptrace.instrumentation.metamodel.agno import _helper

INFERENCE = {
    "type": SPAN_TYPES.INFERENCE,
    "attributes": [
        [
            {
                "_comment": "provider type, name, deployment, inference_endpoint",
                "attribute": "type",
                "accessor": lambda arguments: 'inference.' + _helper.get_model_provider(arguments['instance'])
            },
            {
                "attribute": "provider_name",
                "accessor": lambda arguments: _helper.get_model_provider(arguments['instance'])
            },
        ],
        [
            {
                "_comment": "LLM Model",
                "attribute": "name",
                "accessor": lambda arguments: _helper.get_model_name(arguments['instance'])
            },
            {
                "attribute": "type",
                "accessor": lambda arguments: 'model.llm.' + (_helper.get_model_name(arguments['instance']) or 'unknown')
            }
        ],
    ],
    "events": [
        {
            "name": "data.input",
            "attributes": [
                {
                    "_comment": "this is instruction and user query to LLM",
                    "attribute": "input",
                    "accessor": lambda arguments: _helper.extract_inference_input(arguments)
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
                    "_comment": "this is result from LLM",
                    "attribute": "response",
                    "accessor": lambda arguments: _helper.extract_inference_response(arguments)
                }
            ]
        },
        {
            "name": "metadata",
            "attributes": [
                {
                    "_comment": "this is metadata usage from LLM",
                    "accessor": lambda arguments: _helper.update_span_from_llm_response(arguments['result'])
                },
                {
                    "attribute": "finish_reason",
                    "accessor": lambda arguments: _helper.extract_finish_reason(arguments)
                },
                {
                    "attribute": "finish_type",
                    "accessor": lambda arguments: _helper.map_finish_reason_to_finish_type(
                        _helper.extract_finish_reason(arguments)
                    )
                }
            ]
        }
    ]
}
