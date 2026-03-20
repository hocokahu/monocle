"""
Agno framework method instrumentation definitions.
"""

from monocle_apptrace.instrumentation.common.wrapper import (
    task_wrapper,
    atask_wrapper,
    atask_iter_wrapper,
)
from monocle_apptrace.instrumentation.metamodel.agno.entities.agent import AGENT
from monocle_apptrace.instrumentation.metamodel.agno.entities.inference import INFERENCE
from monocle_apptrace.instrumentation.metamodel.agno.entities.team import TEAM
from monocle_apptrace.instrumentation.metamodel.agno.entities.tool import TOOL

AGNO_METHODS = [
    # Team.run - team orchestration (sync)
    {
        "package": "agno.team.team",
        "object": "Team",
        "method": "run",
        "wrapper_method": task_wrapper,
        "span_handler": "agno_handler",
        "output_processor": TEAM,
    },
    # Team.arun - team orchestration (async)
    {
        "package": "agno.team.team",
        "object": "Team",
        "method": "arun",
        "wrapper_method": atask_iter_wrapper,
        "span_handler": "agno_handler",
        "output_processor": TEAM,
    },
    # Agent.run - main agent execution (sync)
    {
        "package": "agno.agent",
        "object": "Agent",
        "method": "run",
        "wrapper_method": task_wrapper,
        "span_handler": "agno_handler",
        "output_processor": AGENT,
    },
    # Agent.arun - main agent execution (async)
    {
        "package": "agno.agent",
        "object": "Agent",
        "method": "arun",
        "wrapper_method": atask_iter_wrapper,
        "span_handler": "agno_handler",
        "output_processor": AGENT,
    },
    # Model.invoke - LLM inference (sync)
    {
        "package": "agno.models.base",
        "object": "Model",
        "method": "invoke",
        "wrapper_method": task_wrapper,
        "span_handler": "non_framework_handler",
        "output_processor": INFERENCE,
    },
    # Model.ainvoke - LLM inference (async)
    {
        "package": "agno.models.base",
        "object": "Model",
        "method": "ainvoke",
        "wrapper_method": atask_wrapper,
        "span_handler": "non_framework_handler",
        "output_processor": INFERENCE,
    },
]
