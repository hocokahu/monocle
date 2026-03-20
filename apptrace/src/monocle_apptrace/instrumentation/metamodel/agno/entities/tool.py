"""
Agno Tool invocation entity processor for span creation.
"""

from monocle_apptrace.instrumentation.common.constants import SPAN_SUBTYPES, SPAN_TYPES
from monocle_apptrace.instrumentation.common.utils import get_error_message
from monocle_apptrace.instrumentation.metamodel.agno import _helper

TOOL = {
    "type": SPAN_TYPES.AGENTIC_TOOL_INVOCATION,
    "subtype": SPAN_SUBTYPES.CONTENT_GENERATION,
    "attributes": [
        [
            {
                "_comment": "tool type",
                "attribute": "type",
                "accessor": lambda arguments: _helper.AGNO_TOOL_TYPE_KEY
            },
            {
                "_comment": "name of the tool",
                "attribute": "name",
                "accessor": lambda arguments: _helper.get_tool_name(arguments['args'][0]) if arguments.get('args') else None
            },
            {
                "_comment": "tool description",
                "attribute": "description",
                "accessor": lambda arguments: _helper.get_tool_description(arguments['args'][0]) if arguments.get('args') else None
            }
        ],
        [
            {
                "_comment": "name of the source agent",
                "attribute": "name",
                "accessor": lambda arguments: _helper.get_source_agent(arguments)
            },
            {
                "_comment": "agent type",
                "attribute": "type",
                "accessor": lambda arguments: _helper.AGNO_AGENT_TYPE_KEY
            }
        ]
    ],
    "events": [
        {
            "name": "data.input",
            "attributes": [
                {
                    "_comment": "this is Tool input",
                    "attribute": "input",
                    "accessor": lambda arguments: _helper.extract_tool_input(arguments)
                },
            ]
        },
        {
            "name": "data.output",
            "attributes": [
                {
                    "_comment": "this is response from Tool",
                    "attribute": "response",
                    "accessor": lambda arguments: _helper.extract_tool_response(arguments['result'])
                },
                {
                    "attribute": "error_code",
                    "accessor": lambda arguments: get_error_message(arguments)
                },
            ]
        }
    ]
}
