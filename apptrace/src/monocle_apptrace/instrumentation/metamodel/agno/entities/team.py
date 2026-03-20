"""
Agno Team entity processors for span creation.
"""

from monocle_apptrace.instrumentation.common.constants import SPAN_SUBTYPES, SPAN_TYPES
from monocle_apptrace.instrumentation.common.utils import get_error_message
from monocle_apptrace.instrumentation.metamodel.agno import _helper

TEAM = {
    "type": SPAN_TYPES.AGENTIC_INVOCATION,
    "subtype": SPAN_SUBTYPES.ROUTING,
    "attributes": [
        [
            {
                "_comment": "team type",
                "attribute": "type",
                "accessor": lambda arguments: _helper.AGNO_TEAM_TYPE_KEY
            },
            {
                "_comment": "name of the team",
                "attribute": "name",
                "accessor": lambda arguments: _helper.get_team_name(arguments['instance'])
            },
            {
                "_comment": "team description",
                "attribute": "description",
                "accessor": lambda arguments: _helper.get_team_description(arguments['instance'])
            },
            {
                "_comment": "team instructions",
                "attribute": "instructions",
                "accessor": lambda arguments: _helper.get_team_instructions(arguments['instance'])
            },
            {
                "_comment": "team mode (coordinate, route, collaborate, tasks)",
                "attribute": "mode",
                "accessor": lambda arguments: _helper.get_team_mode(arguments['instance'])
            },
        ]
    ],
    "events": [
        {
            "name": "data.input",
            "attributes": [
                {
                    "_comment": "this is Team input",
                    "attribute": "input",
                    "accessor": lambda arguments: _helper.extract_team_input(arguments)
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
                    "_comment": "this is response from Team",
                    "attribute": "response",
                    "accessor": lambda arguments: _helper.extract_team_response(arguments['result'])
                }
            ]
        }
    ]
}
