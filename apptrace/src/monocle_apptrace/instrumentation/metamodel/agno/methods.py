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
from monocle_apptrace.instrumentation.metamodel.agno.entities.tool import TOOL

AGNO_METHODS = [
    # Agent.run - main agent execution (sync)
    {
        "package": "agno.agent",
        "object": "Agent",
        "method": "run",
        "span_name": "agno.agent.run",
        "wrapper_method": task_wrapper,
        "span_handler": "agno_handler",
        "output_processor": AGENT,
    },
    # Agent.arun - main agent execution (async)
    {
        "package": "agno.agent",
        "object": "Agent",
        "method": "arun",
        "span_name": "agno.agent.arun",
        "wrapper_method": atask_iter_wrapper,
        "span_handler": "agno_handler",
        "output_processor": AGENT,
    },
    # Model.invoke - LLM inference (sync)
    {
        "package": "agno.models.base",
        "object": "Model",
        "method": "invoke",
        "span_name": "agno.model.invoke",
        "wrapper_method": task_wrapper,
        "span_handler": "non_framework_handler",
        "output_processor": INFERENCE,
    },
    # Model.ainvoke - LLM inference (async)
    {
        "package": "agno.models.base",
        "object": "Model",
        "method": "ainvoke",
        "span_name": "agno.model.ainvoke",
        "wrapper_method": atask_wrapper,
        "span_handler": "non_framework_handler",
        "output_processor": INFERENCE,
    },
    # Model.run_function_call - tool execution (sync)
    {
        "package": "agno.models.base",
        "object": "Model",
        "method": "run_function_call",
        "span_name": "agno.tool.run",
        "wrapper_method": task_wrapper,
        "output_processor": TOOL,
    },
    # Model.arun_function_call - tool execution (async)
    {
        "package": "agno.models.base",
        "object": "Model",
        "method": "arun_function_call",
        "span_name": "agno.tool.arun",
        "wrapper_method": atask_iter_wrapper,
        "output_processor": TOOL,
    },
]
