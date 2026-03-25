"""
Helper functions for the ADK (Agent Development Kit) metamodel instrumentation.
This module provides utility functions to extract various attributes from agent and tool instances.
"""

from ast import arguments
import json
from typing import Any, Dict, Optional
from monocle_apptrace.instrumentation.metamodel.finish_types import map_adk_finish_reason_to_finish_type
from monocle_apptrace.instrumentation.common.span_handler import SpanHandler
from monocle_apptrace.instrumentation.common.utils import set_scope, remove_scope
from monocle_apptrace.instrumentation.common.constants import AGENT_INVOCATION_SPAN_NAME

def get_model_name(args):
    return args[0].model if hasattr(args[0], 'model') else None

def get_inference_type(arguments):
    """ Find inference type from argument """
    return 'inference.gemini' ## TBD verify non-gemini inference types

def extract_inference_endpoint(instance):
    """ Get inference service end point"""
    if hasattr(instance,'api_client') and hasattr(instance.api_client, '_api_client'):
        if hasattr(instance.api_client._api_client._http_options,'base_url'):
            return instance.api_client._api_client._http_options.base_url
    return None

def extract_message(arguments):
    return str(arguments['args'][0].contents)

def extract_assistant_message(arguments):
    return str(arguments['result'].content.parts)

def update_span_from_llm_response(response, instance):
    meta_dict = {}
    if response is not None and hasattr(response, "usage_metadata") and response.usage_metadata is not None:
        token_usage = response.usage_metadata
        if token_usage is not None:
            meta_dict.update({"completion_tokens": token_usage.candidates_token_count})
            meta_dict.update({"prompt_tokens": token_usage.prompt_token_count })
            meta_dict.update({"total_tokens": token_usage.total_token_count})
    return meta_dict

def extract_finish_reason(arguments):
    if arguments["exception"] is not None:
            return None
    if hasattr(arguments['result'], 'error_code'):
        return arguments['result'].error_code
    return None

def map_finish_reason_to_finish_type(finish_reason:str):
    return map_adk_finish_reason_to_finish_type(finish_reason)

def get_agent_name(instance: Any) -> str:
    """
    Extract the name of the agent from the given instance.

    Args:
        instance: The agent instance to extract name from

    Returns:
        str: The name of the agent, or a default value if not found
    """
    return getattr(instance, 'name', 'unknown_agent')

def get_agent_description(instance: Any) -> str:
    """
    Extract the description of the agent from the given instance.

    Args:
        instance: The agent instance to extract description from

    Returns:
        str: The description of the agent, or a default value if not found
    """
    return getattr(instance, 'description', 'No description available')


def extract_agent_input(arguments: Dict[str, Any]) -> Any:
    """
    Extract the input data from agent arguments.

    Args:
        arguments: Dictionary containing agent call arguments

    Returns:
        Any: The extracted input data
    """
    return [arguments['args'][0].user_content.parts[0].text]

def extract_agent_request_input(arguments: Dict[str, Any]) -> Any:
    """
    Extract the input data from agent request.

    Args:
        arguments: Dictionary containing agent call arguments

    Returns:
        Any: The extracted input data
    """
    return [arguments['kwargs']['new_message'].parts[0].text] if 'new_message' in arguments['kwargs'] else []

def extract_agent_response(result: Any) -> Any:
    """
    Extract the response data from agent result.

    Args:
        result: The result returned by the agent

    Returns:
        Any: The extracted response data
    """
    if result:
        return str(result.content.parts[0].text)
    else:
        return ""

def get_tool_name(instance: Any) -> str:
    """
    Extract the name of the tool from the given instance.

    Args:
        instance: The tool instance to extract name from

    Returns:
        str: The name of the tool, or a default value if not found
    """
    return getattr(instance, 'name', getattr(instance, '__name__', 'unknown_tool'))

def get_tool_description(instance: Any) -> str:
    """
    Extract the description of the tool from the given instance.

    Args:
        instance: The tool instance to extract description from

    Returns:
        str: The description of the tool, or a default value if not found
    """
    return getattr(instance, 'description', getattr(instance, '__doc__', 'No description available'))

def get_source_agent(arguments) -> str:
    """
    Get the name of the source agent (the agent that is calling a tool or delegating to another agent).

    Returns:
        str: The name of the source agent
    """
    return arguments['kwargs']['tool_context'].agent_name

def get_delegating_agent(arguments) -> str:
    """
    Get the name of the delegating agent (the agent that is delegating a task to another agent).

    Args:
        arguments: Dictionary containing agent call arguments 
    Returns:
        str: The name of the delegating agent
    """
    from_agent = arguments['args'][0].agent.name if hasattr(arguments['args'][0], 'agent') else None
    if from_agent is not None:
        if get_agent_name(arguments['instance']) == from_agent:
            return None
    return from_agent

def extract_from_agent_invocation_id(parent_span):
    if parent_span is not None:
        return parent_span.attributes.get("scope." + AGENT_INVOCATION_SPAN_NAME)
    return None

def should_skip_delegation(arguments):
    """
    Determine whether to skip the delegation based on the arguments.

    Args:
        arguments: Dictionary containing agent call arguments

    Returns:
        bool: True if delegation should be skipped, False otherwise
    """
    return get_delegating_agent(arguments) is None

def extract_tool_input(arguments: Dict[str, Any]) -> Any:
    """
    Extract the input data from tool arguments.

    Args:
        arguments: Dictionary containing tool call arguments

    Returns:
        Any: The extracted input data
    """
    return json.dumps(arguments['kwargs'].get('args', {}))


def extract_tool_response(result: Any) -> Any:
    """
    Extract the response data from tool result.

    Args:
        result: The result returned by the tool

    Returns:
        Any: The extracted response data
    """
    return str(result)

def get_target_agent(instance: Any) -> str:
    """
    Extract the name of the target agent (the agent being called/delegated to).

    Args:
        instance: The target agent instance

    Returns:
        str: The name of the target agent
    """
    return getattr(instance, 'name', getattr(instance, '__name__', 'unknown_target_agent'))


# =============================================================================
# COMPACTION HELPERS
# =============================================================================

ADK_COMPACTION_TYPE_KEY = "memory.compaction.adk"
ADK_SUMMARIZER_TYPE_KEY = "memory.summarizer.adk"


def get_compaction_type(arguments: Dict[str, Any]) -> str:
    """Return the compaction entity type key."""
    return ADK_COMPACTION_TYPE_KEY


def get_summarizer_type(arguments: Dict[str, Any]) -> str:
    """Return the summarizer entity type key."""
    return ADK_SUMMARIZER_TYPE_KEY


def get_compaction_mode(arguments: Dict[str, Any]) -> Optional[str]:
    """
    Determine the compaction mode (sliding_window or token_threshold).

    Args:
        arguments: Dictionary containing function call arguments

    Returns:
        str: 'sliding_window' or 'token_threshold' based on function name
    """
    # Check if this is token threshold compaction based on function context
    kwargs = arguments.get('kwargs', {})
    if kwargs.get('skip_token_compaction') is False:
        return 'token_threshold'
    return 'sliding_window'


def get_compaction_app_name(arguments: Dict[str, Any]) -> Optional[str]:
    """
    Extract the app name from compaction arguments.

    Args:
        arguments: Dictionary containing function call arguments

    Returns:
        str: The app name or None
    """
    args = arguments.get('args', ())
    if args and len(args) > 0:
        app = args[0]
        if hasattr(app, 'name'):
            return app.name
    return None


def get_compaction_session_id(arguments: Dict[str, Any]) -> Optional[str]:
    """
    Extract the session ID from compaction arguments.

    Args:
        arguments: Dictionary containing function call arguments

    Returns:
        str: The session ID or None
    """
    args = arguments.get('args', ())
    if args and len(args) > 1:
        session = args[1]
        if hasattr(session, 'id'):
            return session.id
    return None


def get_compaction_config(arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract compaction configuration details.

    Args:
        arguments: Dictionary containing function call arguments

    Returns:
        dict: Compaction config details or None
    """
    args = arguments.get('args', ())
    if args and len(args) > 0:
        app = args[0]
        if hasattr(app, 'events_compaction_config') and app.events_compaction_config:
            config = app.events_compaction_config
            return {
                'compaction_interval': getattr(config, 'compaction_interval', None),
                'overlap_size': getattr(config, 'overlap_size', None),
                'token_threshold': getattr(config, 'token_threshold', None),
                'event_retention_size': getattr(config, 'event_retention_size', None),
            }
    return None


def get_events_to_compact_count(arguments: Dict[str, Any]) -> Optional[int]:
    """
    Extract the count of events being compacted from summarizer arguments.

    Args:
        arguments: Dictionary containing function call arguments

    Returns:
        int: Number of events being compacted or None
    """
    kwargs = arguments.get('kwargs', {})
    events = kwargs.get('events', [])
    if events:
        return len(events)
    return None


def get_compaction_time_range(arguments: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """
    Extract the time range of events being compacted.

    Args:
        arguments: Dictionary containing function call arguments

    Returns:
        dict: Time range with start_timestamp and end_timestamp or None
    """
    kwargs = arguments.get('kwargs', {})
    events = kwargs.get('events', [])
    if events and len(events) > 0:
        start_ts = getattr(events[0], 'timestamp', None)
        end_ts = getattr(events[-1], 'timestamp', None)
        if start_ts is not None and end_ts is not None:
            return {
                'start_timestamp': start_ts,
                'end_timestamp': end_ts,
            }
    return None


def get_summarizer_model(instance: Any) -> Optional[str]:
    """
    Extract the model name from LlmEventSummarizer instance.

    Args:
        instance: The LlmEventSummarizer instance

    Returns:
        str: The model name or None
    """
    if hasattr(instance, '_llm'):
        llm = instance._llm
        if hasattr(llm, 'model'):
            return llm.model
    return None


def extract_summarizer_input(arguments: Dict[str, Any]) -> Optional[str]:
    """
    Extract the conversation history being summarized.

    Args:
        arguments: Dictionary containing function call arguments

    Returns:
        str: Formatted conversation history or None
    """
    kwargs = arguments.get('kwargs', {})
    events = kwargs.get('events', [])
    if not events:
        return None

    # Format similar to how LlmEventSummarizer does it
    formatted_history = []
    for event in events[:10]:  # Limit to first 10 events for brevity
        if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    author = getattr(event, 'author', 'unknown')
                    formatted_history.append(f'{author}: {part.text[:200]}')  # Truncate long messages

    if len(events) > 10:
        formatted_history.append(f'... and {len(events) - 10} more events')

    return '\n'.join(formatted_history) if formatted_history else None


def extract_compacted_summary(arguments: Dict[str, Any]) -> Optional[str]:
    """
    Extract the generated summary from compaction result.

    Args:
        arguments: Dictionary containing function call arguments with result

    Returns:
        str: The compacted summary text or None
    """
    result = arguments.get('result')
    if result is None:
        return None

    # Result is an Event with actions.compaction.compacted_content
    if hasattr(result, 'actions') and result.actions:
        compaction = getattr(result.actions, 'compaction', None)
        if compaction and hasattr(compaction, 'compacted_content'):
            content = compaction.compacted_content
            if content and hasattr(content, 'parts'):
                parts_text = []
                for part in content.parts:
                    if hasattr(part, 'text') and part.text:
                        parts_text.append(part.text[:500])  # Truncate
                return ' '.join(parts_text) if parts_text else None

    # Fallback: check for content directly
    if hasattr(result, 'content') and result.content:
        content = result.content
        if hasattr(content, 'parts'):
            parts_text = []
            for part in content.parts:
                if hasattr(part, 'text') and part.text:
                    parts_text.append(part.text[:500])
            return ' '.join(parts_text) if parts_text else None

    return None


def was_compaction_successful(arguments: Dict[str, Any]) -> bool:
    """
    Check if compaction was successful (produced a compacted event).

    Args:
        arguments: Dictionary containing function call arguments with result

    Returns:
        bool: True if compaction produced a result
    """
    result = arguments.get('result')
    return result is not None

