"""Custom span handler for Agno to maintain trace context across agent calls."""

from monocle_apptrace.instrumentation.common.constants import AGENT_SESSION, AGENT_INVOCATION_SPAN_NAME
from monocle_apptrace.instrumentation.common.span_handler import SpanHandler
from monocle_apptrace.instrumentation.common.utils import set_scope


class AgnoSpanHandler(SpanHandler):
    """Custom span handler for Agno instrumentation that maintains trace context."""

    def pre_tracing(self, to_wrap, wrapped, instance, args, kwargs):
        """Set session scope before tracing begins to maintain single trace."""
        session_token = None

        # For Agent.run, set session scope using session_id if available
        if hasattr(instance, '__class__') and instance.__class__.__name__ == 'Agent':
            session_id = kwargs.get('session_id')
            if session_id:
                session_token = set_scope(AGENT_SESSION, session_id)
            else:
                # Use agent name as fallback session identifier
                agent_name = getattr(instance, 'name', None) or getattr(instance, 'id', 'agno_agent')
                session_token = set_scope(AGENT_INVOCATION_SPAN_NAME, str(id(instance)))

        return session_token, None
