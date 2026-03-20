"""
Agno Agent entity processors for span creation.
"""

from monocle_apptrace.instrumentation.common.constants import SPAN_SUBTYPES, SPAN_TYPES
from monocle_apptrace.instrumentation.common.utils import get_error_message
from monocle_apptrace.instrumentation.metamodel.agno import _helper

AGENT = {
    "type": SPAN_TYPES.AGENTIC_INVOCATION,
    "subtype": SPAN_SUBTYPES.CONTENT_PROCESSING,
    "attributes": [
        [
            {
                "_comment": "agent type",
                "attribute": "type",
                "accessor": lambda arguments: _helper.AGNO_AGENT_TYPE_KEY
            },
            {
                "_comment": "name of the agent",
                "attribute": "name",
                "accessor": lambda arguments: _helper.get_agent_name(arguments['instance'])
            },
            {
                "_comment": "agent description",
                "attribute": "description",
                "accessor": lambda arguments: _helper.get_agent_description(arguments['instance'])
            },
            {
                "_comment": "agent instructions",
                "attribute": "instructions",
                "accessor": lambda arguments: _helper.get_agent_instructions(arguments['instance'])
            },
        ]
    ],
    "events": [
        {
            "name": "data.input",
            "attributes": [
                {
                    "_comment": "this is Agent input",
                    "attribute": "input",
                    "accessor": lambda arguments: _helper.extract_agent_input(arguments)
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
                    "_comment": "this is response from Agent",
                    "attribute": "response",
                    "accessor": lambda arguments: _helper.extract_agent_response(arguments['result'])
                }
            ]
        }
    ]
}
