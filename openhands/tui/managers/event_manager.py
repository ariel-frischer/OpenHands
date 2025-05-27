"""TUI Event Manager for Session-UI Communication.

This module provides the TUIEventManager class that handles event routing between
OpenHands sessions and the TUI interface. It adapts the CLI event handling patterns
for use in the TUI environment.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from openhands.core.config import AppConfig
from openhands.events import Event, EventSource, EventStreamSubscriber
from openhands.events.action import (
    Action,
    ChangeAgentStateAction,
    CmdRunAction,
    MessageAction,
)
from openhands.events.event import Event
from openhands.events.observation import (
    AgentStateChangedObservation,
    CmdOutputObservation,
    ErrorObservation,
    FileEditObservation,
    FileReadObservation,
)
from openhands.core.schema import AgentState

from .session_manager import SessionManager
from .file_manager import TUIPanelFileManager

if TYPE_CHECKING:
    from ..app import OpenHandsTUIApp

logger = logging.getLogger(__name__)


class TUIEventManager:
    """Manages event routing between OpenHands sessions and TUI panels.

    This class subscribes to event streams from active sessions and routes
    events to appropriate UI panels through the file manager. It also handles
    routing user input back to sessions.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        file_manager: TUIPanelFileManager,
        config: AppConfig,
        tui_app: Optional["OpenHandsTUIApp"] = None,
    ):
        """Initialize the TUI Event Manager.

        Args:
            session_manager: Manager for OpenHands sessions
            file_manager: Manager for TUI panel files
            config: Application configuration
            tui_app: Main TUI application instance (optional for backward compatibility)
        """
        self.session_manager = session_manager
        self.file_manager = file_manager
        self.config = config
        self.tui_app = tui_app

        # Track event subscriptions for each session
        self.event_subscriptions: Dict[str, str] = {}  # session_id -> callback_id

        # Event handlers for different event types
        self.event_handlers: Dict[type, Callable[[str, Event], None]] = {
            MessageAction: self._handle_message_action,
            CmdRunAction: self._handle_cmd_run_action,
            CmdOutputObservation: self._handle_cmd_output_observation,
            FileEditObservation: self._handle_file_edit_observation,
            FileReadObservation: self._handle_file_read_observation,
            AgentStateChangedObservation: self._handle_agent_state_changed,
            ErrorObservation: self._handle_error_observation,
        }

        # Track streaming command output
        self.streaming_sessions: set[str] = set()

    def subscribe_to_session(self, session_id: str) -> None:
        """Subscribe to events from a specific session's event stream.

        Args:
            session_id: ID of the session to subscribe to

        Raises:
            ValueError: If session not found or already subscribed
        """
        if session_id in self.event_subscriptions:
            logger.warning(f"Already subscribed to session {session_id}")
            return

        session_context = self.session_manager.get_session(session_id)
        if not session_context:
            raise ValueError(f"Session {session_id} not found")

        # Create callback for this session
        callback_id = f"tui_event_manager_{session_id}"

        def event_callback(event: Event) -> None:
            """Handle events from this session."""
            try:
                self._handle_session_event(session_id, event)
            except Exception as e:
                logger.error(
                    f"Error handling event from session {session_id}: {e}",
                    exc_info=True,
                )
                # Try to recover from event handling errors
                self._handle_event_error(session_id, e)

        # Subscribe to the session's event stream
        session_context.event_stream.subscribe(
            EventStreamSubscriber.MAIN, event_callback, callback_id
        )

        self.event_subscriptions[session_id] = callback_id
        logger.info(f"Subscribed to events from session {session_id}")

    def unsubscribe_from_session(self, session_id: str) -> None:
        """Unsubscribe from events from a specific session.

        Args:
            session_id: ID of the session to unsubscribe from
        """
        if session_id not in self.event_subscriptions:
            logger.warning(f"Not subscribed to session {session_id}")
            return

        session_context = self.session_manager.get_session(session_id)
        if session_context:
            callback_id = self.event_subscriptions[session_id]
            session_context.event_stream.unsubscribe(
                EventStreamSubscriber.MAIN, callback_id
            )

        del self.event_subscriptions[session_id]
        self.streaming_sessions.discard(session_id)
        logger.info(f"Unsubscribed from events from session {session_id}")

    def _handle_session_event(self, session_id: str, event: Event) -> None:
        """Handle an event from a session and route it to appropriate UI panels.

        Args:
            session_id: ID of the session that generated the event
            event: The event to handle
        """
        # Get the appropriate handler for this event type
        event_type = type(event)
        handler = self.event_handlers.get(event_type)

        if handler:
            handler(session_id, event)
        else:
            # Handle generic Action events that might have thoughts
            if isinstance(event, Action):
                self._handle_generic_action(session_id, event)
            else:
                logger.debug(f"No handler for event type {event_type.__name__}")

        # Update UI if TUI app is available and this is the active session
        if self.tui_app and session_id == self.session_manager.active_session_id:
            try:
                # Update UI panels for the active session
                if hasattr(self.tui_app, "chat_panel"):
                    self.tui_app.chat_panel.update_chat_display(session_id)
                if hasattr(self.tui_app, "logs_panel"):
                    self.tui_app.logs_panel.update_logs_display(session_id)
            except Exception as e:
                logger.error(f"Error updating UI panels: {e}")

    def _handle_message_action(self, session_id: str, event: MessageAction) -> None:
        """Handle MessageAction events (agent messages)."""
        if event.source == EventSource.AGENT and event.content.strip():
            # Add agent message to chat
            message = f"🤖 Agent: {event.content.strip()}\n"
            self.file_manager.update_chat_file(session_id, message)

    def _handle_cmd_run_action(self, session_id: str, event: CmdRunAction) -> None:
        """Handle CmdRunAction events (commands being executed)."""
        command_text = f"$ {event.command}\n"
        self.file_manager.update_logs_file(session_id, command_text)

        # Track if this command will produce streaming output
        if hasattr(event, "confirmation_state") and event.confirmation_state:
            self.streaming_sessions.add(session_id)

    def _handle_cmd_output_observation(
        self, session_id: str, event: CmdOutputObservation
    ) -> None:
        """Handle CmdOutputObservation events (command output)."""
        if event.content.strip():
            output_text = f"{event.content}\n"
            self.file_manager.update_logs_file(session_id, output_text)

    def _handle_file_edit_observation(
        self, session_id: str, event: FileEditObservation
    ) -> None:
        """Handle FileEditObservation events (file modifications)."""
        file_info = f"📝 File edited: {event.path}\n"
        if hasattr(event, "diff") and event.diff:
            file_info += f"Changes:\n{event.diff}\n"
        self.file_manager.update_logs_file(session_id, file_info)

    def _handle_file_read_observation(
        self, session_id: str, event: FileReadObservation
    ) -> None:
        """Handle FileReadObservation events (file reads)."""
        file_info = f"📖 File read: {event.path}\n"
        self.file_manager.update_logs_file(session_id, file_info)

    def _handle_agent_state_changed(
        self, session_id: str, event: AgentStateChangedObservation
    ) -> None:
        """Handle AgentStateChangedObservation events (agent state changes)."""
        state_message = f"🔄 Agent state: {event.agent_state}\n"
        self.file_manager.update_logs_file(session_id, state_message)

        # Update session context with new agent state
        session_context = self.session_manager.get_session(session_id)
        if session_context:
            session_context.agent_state = event.agent_state
            logger.debug(
                f"Updated session {session_id} agent state to {event.agent_state}"
            )

        # Update session activity when state changes
        self.session_manager.update_session_activity(session_id)

        # Update UI panels immediately for state changes
        if self.tui_app and session_id == self.session_manager.active_session_id:
            try:
                if hasattr(self.tui_app, "sessions_panel"):
                    self.tui_app.sessions_panel.update_display()
                if hasattr(self.tui_app, "chat_panel"):
                    self.tui_app.chat_panel.update_display(session_id)
            except Exception as e:
                logger.error(f"Error updating UI for state change: {e}")

    def _handle_error_observation(
        self, session_id: str, event: ErrorObservation
    ) -> None:
        """Handle ErrorObservation events (errors)."""
        error_message = f"❌ Error: {event.content.strip()}\n"
        self.file_manager.update_logs_file(session_id, error_message)

    def _handle_generic_action(self, session_id: str, event: Action) -> None:
        """Handle generic Action events that might contain thoughts."""
        messages = []

        if hasattr(event, "thought") and event.thought:
            messages.append(f"💭 Thought: {event.thought.strip()}")

        if hasattr(event, "final_thought") and event.final_thought:
            messages.append(f"🎯 Final thought: {event.final_thought.strip()}")

        if messages:
            message_text = "\n".join(messages) + "\n"
            self.file_manager.update_chat_file(session_id, message_text)

    def route_user_input(self, session_id: str, message: str) -> bool:
        """Route user input to the specified session.

        Args:
            session_id: ID of the session to send the message to
            message: User message to send

        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            session_context = self.session_manager.get_session(session_id)
            if not session_context:
                logger.error(f"Session {session_id} not found")
                return False

            # Create and send MessageAction
            user_message = MessageAction(content=message)
            session_context.event_stream.add_event(user_message, EventSource.USER)

            # Add user message to chat display
            chat_message = f"👤 User: {message.strip()}\n"
            self.file_manager.update_chat_file(session_id, chat_message)

            # Update session activity
            self.session_manager.update_session_activity(session_id)

            logger.info(f"Routed user input to session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error routing user input to session {session_id}: {e}")
            return False

    def send_agent_state_change(self, session_id: str, new_state: AgentState) -> bool:
        """Send an agent state change action to a session.

        Args:
            session_id: ID of the session
            new_state: New agent state to set

        Returns:
            True if state change was sent successfully, False otherwise
        """
        try:
            session_context = self.session_manager.get_session(session_id)
            if not session_context:
                logger.error(f"Session {session_id} not found")
                return False

            # Create and send ChangeAgentStateAction
            state_action = ChangeAgentStateAction(new_state)
            session_context.event_stream.add_event(state_action, EventSource.USER)

            logger.info(
                f"Sent state change to {new_state.value} for session {session_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error sending state change to session {session_id}: {e}")
            return False

    def cleanup_session_events(self, session_id: str) -> None:
        """Clean up event subscriptions for a session.

        Args:
            session_id: ID of the session to clean up
        """
        self.unsubscribe_from_session(session_id)
        logger.info(f"Cleaned up event subscriptions for session {session_id}")

    def cleanup_all_events(self) -> None:
        """Clean up all event subscriptions."""
        session_ids = list(self.event_subscriptions.keys())
        for session_id in session_ids:
            self.cleanup_session_events(session_id)

        self.streaming_sessions.clear()
        logger.info("Cleaned up all event subscriptions")

    def get_subscribed_sessions(self) -> list[str]:
        """Get list of session IDs that are currently subscribed to events.

        Returns:
            List of session IDs with active event subscriptions
        """
        return list(self.event_subscriptions.keys())

    def is_session_subscribed(self, session_id: str) -> bool:
        """Check if a session is subscribed to events.

        Args:
            session_id: ID of the session to check

        Returns:
            True if session is subscribed, False otherwise
        """
        return session_id in self.event_subscriptions

    # Legacy methods for backward compatibility
    async def handle_session_event(self, session_id: str, event: Event) -> None:
        """Legacy method for backward compatibility."""
        self._handle_session_event(session_id, event)

    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """Legacy method for backward compatibility."""
        logger.debug(f"Registered event handler for: {event_type}")

    def unregister_event_handler(self, event_type: str) -> None:
        """Legacy method for backward compatibility."""
        logger.debug(f"Unregistered event handler for: {event_type}")

    async def broadcast_event(self, event: Event) -> None:
        """Legacy method for backward compatibility."""
        logger.debug(f"Broadcasted event: {type(event).__name__}")

    def _handle_event_error(self, session_id: str, error: Exception) -> None:
        """Handle errors that occur during event processing.

        Args:
            session_id: ID of the session where the error occurred
            error: The exception that was raised
        """
        error_msg = f"Event processing error in session {session_id}: {str(error)}"
        logger.error(error_msg)

        # Log the error to the session's log file
        try:
            self.file_manager.update_logs_file(session_id, f"❌ {error_msg}\n")
        except Exception as log_error:
            logger.error(f"Failed to log error to file: {log_error}")

        # Update UI to show error state if this is the active session
        if self.tui_app and session_id == self.session_manager.active_session_id:
            try:
                if hasattr(self.tui_app, "logs_panel"):
                    self.tui_app.logs_panel.update_display()
            except Exception as ui_error:
                logger.error(f"Failed to update UI for error: {ui_error}")

    def reconnect_session_events(self, session_id: str) -> bool:
        """Attempt to reconnect event subscription for a session.

        Args:
            session_id: ID of the session to reconnect

        Returns:
            True if reconnection was successful, False otherwise
        """
        try:
            # Unsubscribe first if already subscribed
            if session_id in self.event_subscriptions:
                self.unsubscribe_from_session(session_id)

            # Resubscribe to the session
            self.subscribe_to_session(session_id)
            logger.info(f"Successfully reconnected events for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to reconnect events for session {session_id}: {e}")
            return False

    def validate_session_connection(self, session_id: str) -> bool:
        """Validate that a session's event connection is working properly.

        Args:
            session_id: ID of the session to validate

        Returns:
            True if connection is valid, False otherwise
        """
        try:
            session_context = self.session_manager.get_session(session_id)
            if not session_context:
                return False

            # Check if event stream is available and active
            if (
                not hasattr(session_context, "event_stream")
                or not session_context.event_stream
            ):
                return False

            # Check if we're subscribed to this session
            if session_id not in self.event_subscriptions:
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating session connection {session_id}: {e}")
            return False

    def get_event_statistics(self) -> dict:
        """Get statistics about event handling.

        Returns:
            Dictionary containing event handling statistics
        """
        return {
            "subscribed_sessions": len(self.event_subscriptions),
            "streaming_sessions": len(self.streaming_sessions),
            "active_subscriptions": list(self.event_subscriptions.keys()),
            "event_handlers": len(self.event_handlers),
        }
