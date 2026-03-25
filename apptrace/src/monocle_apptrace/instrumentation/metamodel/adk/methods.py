from monocle_apptrace.instrumentation.common.wrapper import task_wrapper, atask_wrapper, atask_iter_wrapper
from monocle_apptrace.instrumentation.metamodel.adk.entities.agent import (
    AGENT, REQUEST, DELEGATION
)
from monocle_apptrace.instrumentation.metamodel.adk.entities.tool import (
    TOOL
)
from monocle_apptrace.instrumentation.metamodel.adk.entities.compaction import (
    COMPACTION, SUMMARIZATION
)

ADK_METHODS = [
    {
      "package": "google.adk.agents.base_agent",
      "object": "BaseAgent",
      "method": "run_async",
      "wrapper_method": atask_iter_wrapper,
      "output_processor": AGENT,
      "span_handler": "adk_handler",
  },
    {
      "package": "google.adk.tools.function_tool",
      "object": "FunctionTool",
      "method": "run_async",
      "wrapper_method": atask_wrapper,
      "output_processor": TOOL,
    },
    {
      "package": "google.adk.runners",
      "object": "Runner",
      "method": "run_async",
      "wrapper_method": atask_iter_wrapper,
      "span_handler": "adk_handler",
      "output_processor": REQUEST,
    },
    # Memory Compaction instrumentation
    {
      "package": "google.adk.apps.compaction",
      "object": "",
      "method": "_run_compaction_for_sliding_window",
      "wrapper_method": atask_wrapper,
      "output_processor": COMPACTION,
    },
    {
      "package": "google.adk.apps.compaction",
      "object": "",
      "method": "_run_compaction_for_token_threshold_config",
      "wrapper_method": atask_wrapper,
      "output_processor": COMPACTION,
    },
    {
      "package": "google.adk.apps.llm_event_summarizer",
      "object": "LlmEventSummarizer",
      "method": "maybe_summarize_events",
      "wrapper_method": atask_wrapper,
      "output_processor": SUMMARIZATION,
    },
]