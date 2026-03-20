"""Custom span handler for Agno to maintain trace context across agent calls."""

from monocle_apptrace.instrumentation.common.constants import AGENT_SESSION, AGENT_INVOCATION_SPAN_NAME
from monocle_apptrace.instrumentation.common.span_handler import SpanHandler
from monocle_apptrace.instrumentation.common.utils import set_scope


class AgnoSpanHandler(SpanHandler):
    """Custom span handler for Agno instrumentation that maintains trace context."""

    def pre_tracing(self, to_wrap, wrapped, instance, args, kwargs):
        """Set session scope before tracing begins to maintain single trace."""
        session_token = None

        class_name = instance.__class__.__name__ if hasattr(instance, '__class__') else ''

        # For Team.run, set session scope to keep all member agents in single trace
        if class_name == 'Team':
            session_id = kwargs.get('session_id') or getattr(instance, 'session_id', None)
            if session_id:
                session_token = set_scope(AGENT_SESSION, session_id)
            else:
                # Use team id/name as session identifier
                team_id = getattr(instance, 'id', None) or getattr(instance, 'name', None) or str(id(instance))
                session_token = set_scope(AGENT_SESSION, f"team_{team_id}")

        # For Agent.run, set session scope using session_id if available
        elif class_name == 'Agent':
            session_id = kwargs.get('session_id')
            if session_id:
                session_token = set_scope(AGENT_SESSION, session_id)
            else:
                # Use agent name as fallback session identifier
                agent_name = getattr(instance, 'name', None) or getattr(instance, 'id', 'agno_agent')
                session_token = set_scope(AGENT_INVOCATION_SPAN_NAME, str(id(instance)))

        return session_token, None
