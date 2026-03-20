"""
Helper functions for Agno framework instrumentation.
Extracts relevant data from Agno Agent, Model, and Tool executions.
"""

import logging
from typing import Any, Dict, List, Optional

from monocle_apptrace.instrumentation.metamodel.finish_types import (
    GEMINI_FINISH_REASON_MAPPING,
    FinishType,
)

logger = logging.getLogger(__name__)

AGNO_AGENT_TYPE_KEY = "agent.agno"
AGNO_TOOL_TYPE_KEY = "tool.agno"


def get_agent_name(instance) -> Optional[str]:
    """Extract agent name from Agent instance."""
    try:
        if hasattr(instance, 'name') and instance.name:
            return instance.name
        if hasattr(instance, 'id') and instance.id:
            return instance.id
        return type(instance).__name__
    except Exception as e:
        logger.debug(f"Error extracting agent name: {e}")
        return None


def get_agent_description(instance) -> Optional[str]:
    """Extract agent description from Agent instance."""
    try:
        if hasattr(instance, 'description') and instance.description:
            return instance.description
        return None
    except Exception as e:
        logger.debug(f"Error extracting agent description: {e}")
        return None


def get_agent_instructions(instance) -> Optional[str]:
    """Extract agent instructions from Agent instance."""
    try:
        if hasattr(instance, 'instructions') and instance.instructions:
            instructions = instance.instructions
            if isinstance(instructions, list):
                return " | ".join(str(i) for i in instructions[:3])
            return str(instructions)[:500]
        return None
    except Exception as e:
        logger.debug(f"Error extracting agent instructions: {e}")
        return None


def extract_agent_input(arguments: Dict[str, Any]) -> Optional[str]:
    """Extract input from agent run arguments."""
    try:
        args = arguments.get('args', ())
        kwargs = arguments.get('kwargs', {})

        # Check args first (positional input)
        if args and len(args) > 0:
            input_val = args[0]
            if isinstance(input_val, str):
                return input_val
            if hasattr(input_val, 'content'):
                return str(input_val.content)
            return str(input_val)[:1000]

        # Check kwargs for 'input' or 'message'
        for key in ['input', 'message', 'query', 'prompt']:
            if key in kwargs:
                val = kwargs[key]
                if isinstance(val, str):
                    return val
                return str(val)[:1000]

        return None
    except Exception as e:
        logger.debug(f"Error extracting agent input: {e}")
        return None


def extract_agent_response(result) -> Optional[str]:
    """Extract response from agent run result."""
    try:
        if result is None:
            return None

        # RunOutput object
        if hasattr(result, 'content'):
            content = result.content
            if isinstance(content, str):
                return content
            if hasattr(content, 'model_dump'):
                return str(content.model_dump())
            return str(content)[:2000]

        # Direct string
        if isinstance(result, str):
            return result

        # Iterator/generator - can't easily extract
        if hasattr(result, '__iter__') and hasattr(result, '__next__'):
            return "[streaming response]"

        return str(result)[:2000]
    except Exception as e:
        logger.debug(f"Error extracting agent response: {e}")
        return None


def get_model_name(instance) -> Optional[str]:
    """Extract model name from Model instance."""
    try:
        if hasattr(instance, 'id') and instance.id:
            return instance.id
        if hasattr(instance, 'model') and instance.model:
            return instance.model
        if hasattr(instance, 'model_name') and instance.model_name:
            return instance.model_name
        return type(instance).__name__
    except Exception as e:
        logger.debug(f"Error extracting model name: {e}")
        return None


def get_model_provider(instance) -> str:
    """Extract model provider from Model instance."""
    try:
        class_name = type(instance).__name__.lower()
        module_name = type(instance).__module__.lower()

        if 'gemini' in class_name or 'google' in module_name:
            return 'google'
        if 'openai' in class_name or 'gpt' in class_name:
            return 'openai'
        if 'anthropic' in class_name or 'claude' in class_name:
            return 'anthropic'
        if 'bedrock' in module_name or 'aws' in module_name:
            return 'aws_bedrock'

        return 'agno'
    except Exception as e:
        logger.debug(f"Error extracting model provider: {e}")
        return 'agno'


def extract_inference_input(arguments: Dict[str, Any]) -> Optional[str]:
    """Extract input messages from model invoke arguments."""
    try:
        args = arguments.get('args', ())
        kwargs = arguments.get('kwargs', {})

        messages = []

        # Check for messages in args
        if args:
            for arg in args:
                if isinstance(arg, list):
                    for msg in arg[:5]:  # Limit to first 5 messages
                        if hasattr(msg, 'content'):
                            messages.append(str(msg.content)[:500])
                        elif isinstance(msg, dict) and 'content' in msg:
                            messages.append(str(msg['content'])[:500])
                elif hasattr(arg, 'content'):
                    messages.append(str(arg.content)[:500])

        # Check kwargs
        for key in ['messages', 'input', 'prompt']:
            if key in kwargs:
                val = kwargs[key]
                if isinstance(val, list):
                    for msg in val[:5]:
                        if hasattr(msg, 'content'):
                            messages.append(str(msg.content)[:500])
                        elif isinstance(msg, dict) and 'content' in msg:
                            messages.append(str(msg['content'])[:500])
                elif isinstance(val, str):
                    messages.append(val[:500])

        if messages:
            return " | ".join(messages)

        return None
    except Exception as e:
        logger.debug(f"Error extracting inference input: {e}")
        return None


def extract_inference_response(arguments: Dict[str, Any]) -> Optional[str]:
    """Extract response from model invoke result."""
    try:
        result = arguments.get('result')
        if result is None:
            return None

        # ModelResponse object
        if hasattr(result, 'content'):
            content = result.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content[:5]:
                    if hasattr(item, 'text'):
                        parts.append(item.text)
                    elif isinstance(item, str):
                        parts.append(item)
                return " ".join(parts)[:2000]
            return str(content)[:2000]

        if isinstance(result, str):
            return result

        return str(result)[:2000]
    except Exception as e:
        logger.debug(f"Error extracting inference response: {e}")
        return None


def extract_token_usage(result) -> Dict[str, Any]:
    """Extract token usage from model response."""
    try:
        usage = {}

        if hasattr(result, 'metrics'):
            metrics = result.metrics
            if hasattr(metrics, 'input_tokens'):
                usage['input_tokens'] = metrics.input_tokens
            if hasattr(metrics, 'output_tokens'):
                usage['output_tokens'] = metrics.output_tokens
            if hasattr(metrics, 'total_tokens'):
                usage['total_tokens'] = metrics.total_tokens

        if hasattr(result, 'usage'):
            u = result.usage
            if hasattr(u, 'prompt_tokens'):
                usage['input_tokens'] = u.prompt_tokens
            if hasattr(u, 'completion_tokens'):
                usage['output_tokens'] = u.completion_tokens
            if hasattr(u, 'total_tokens'):
                usage['total_tokens'] = u.total_tokens

        return usage if usage else None
    except Exception as e:
        logger.debug(f"Error extracting token usage: {e}")
        return None


def update_span_from_llm_response(result) -> Optional[Dict[str, Any]]:
    """Extract metadata from LLM response for span."""
    try:
        metadata = {}

        usage = extract_token_usage(result)
        if usage:
            metadata.update(usage)

        return metadata if metadata else None
    except Exception as e:
        logger.debug(f"Error updating span from LLM response: {e}")
        return None


def extract_finish_reason(arguments: Dict[str, Any]) -> Optional[str]:
    """Extract finish reason from model response."""
    try:
        result = arguments.get('result')
        if result is None:
            return None

        # Check for finish_reason attribute
        if hasattr(result, 'finish_reason'):
            return str(result.finish_reason)

        # Check for stop_reason (Anthropic style)
        if hasattr(result, 'stop_reason'):
            return str(result.stop_reason)

        # Check in metrics
        if hasattr(result, 'metrics') and hasattr(result.metrics, 'finish_reason'):
            return str(result.metrics.finish_reason)

        return None
    except Exception as e:
        logger.debug(f"Error extracting finish reason: {e}")
        return None


def map_finish_reason_to_finish_type(finish_reason: Optional[str]) -> Optional[str]:
    """Map Agno/Gemini finish reason to standardized finish type."""
    if not finish_reason:
        return None

    # Try Gemini mapping first (most common for Agno)
    if finish_reason in GEMINI_FINISH_REASON_MAPPING:
        return GEMINI_FINISH_REASON_MAPPING[finish_reason]

    # Fallback mappings
    finish_reason_lower = finish_reason.lower()
    if any(kw in finish_reason_lower for kw in ['stop', 'end', 'complete', 'done']):
        return FinishType.SUCCESS.value
    if any(kw in finish_reason_lower for kw in ['length', 'token', 'max']):
        return FinishType.TRUNCATED.value
    if any(kw in finish_reason_lower for kw in ['tool', 'function']):
        return FinishType.TOOL_CALL.value
    if any(kw in finish_reason_lower for kw in ['filter', 'safety', 'block']):
        return FinishType.CONTENT_FILTER.value

    return None


def get_tool_name(function_call) -> Optional[str]:
    """Extract tool name from FunctionCall."""
    try:
        # Agno FunctionCall has function.name
        if hasattr(function_call, 'function') and function_call.function:
            func = function_call.function
            if hasattr(func, 'name') and func.name:
                return func.name
        if hasattr(function_call, 'name'):
            return function_call.name
        return None
    except Exception as e:
        logger.debug(f"Error extracting tool name: {e}")
        return None


def get_tool_description(function_call) -> Optional[str]:
    """Extract tool description from FunctionCall."""
    try:
        # Agno FunctionCall has function.description
        if hasattr(function_call, 'function') and function_call.function:
            func = function_call.function
            if hasattr(func, 'description') and func.description:
                return str(func.description)[:500]
        return None
    except Exception as e:
        logger.debug(f"Error extracting tool description: {e}")
        return None


def extract_tool_input(arguments: Dict[str, Any]) -> Optional[str]:
    """Extract tool input arguments."""
    try:
        args = arguments.get('args', ())

        # FunctionCall is usually first arg
        if args and len(args) > 0:
            function_call = args[0]
            # Agno FunctionCall.arguments is a dict
            if hasattr(function_call, 'arguments') and function_call.arguments:
                return str(function_call.arguments)

        return None
    except Exception as e:
        logger.debug(f"Error extracting tool input: {e}")
        return None


def extract_tool_response(result) -> Optional[str]:
    """Extract tool execution response."""
    try:
        if result is None:
            return None

        # Iterator - collect first few results
        if hasattr(result, '__iter__') and hasattr(result, '__next__'):
            return "[streaming tool response]"

        if isinstance(result, str):
            return result[:2000]

        if hasattr(result, 'content'):
            return str(result.content)[:2000]

        return str(result)[:2000]
    except Exception as e:
        logger.debug(f"Error extracting tool response: {e}")
        return None


def get_source_agent(arguments: Dict[str, Any]) -> Optional[str]:
    """Get the source agent that invoked the tool."""
    try:
        instance = arguments.get('instance')
        if instance is None:
            return None

        # Model instance might have agent reference
        if hasattr(instance, '_agent') and instance._agent:
            return get_agent_name(instance._agent)

        # Check parent_span for agent info
        parent_span = arguments.get('parent_span')
        if parent_span and hasattr(parent_span, 'attributes'):
            attrs = parent_span.attributes
            if isinstance(attrs, dict):
                return attrs.get('entity.1.name')

        return None
    except Exception as e:
        logger.debug(f"Error getting source agent: {e}")
        return None
