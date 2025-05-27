"""
Unit tests for TUI Event Manager.

Tests the TUIEventManager class that handles event routing between
OpenHands sessions and TUI panels.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from datetime import datetime

from openhands.core.config import AppConfig
from openhands.core.schema import AgentState
from openhands.events import Event, EventSource, EventStreamSubscriber
from openhands.events.action import (
    Action,
    ChangeAgentStateAction,
    CmdRunAction,
    MessageAction,
)
from openhands.events.observation import (
    AgentStateChangedObservation,
    CmdOutputObservation,
    ErrorObservation,
    FileEditObservation,
    FileReadObservation,
)

from openhands.tui.managers.event_manager import TUIEventManager
from openhands.tui.managers.session_manager import SessionManager, SessionContext
from openhands.tui.managers.file_manager import TUIPanelFileManager


class TestTUIEventManager:
    """Test cases for TUIEventManager."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock AppConfig."""
        config = MagicMock(spec=AppConfig)
        config.cli_multiline_input = False
        return config

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock SessionManager."""
        return MagicMock(spec=SessionManager)

    @pytest.fixture
    def mock_file_manager(self):
        """Create a mock TUIPanelFileManager."""
        return MagicMock(spec=TUIPanelFileManager)

    @pytest.fixture
    def mock_tui_app(self):
        """Create a mock TUI app."""
        app = MagicMock()
        app.chat_panel = MagicMock()
        app.logs_panel = MagicMock()
        return app

    @pytest.fixture
    def mock_session_context(self):
        """Create a mock SessionContext."""
        context = MagicMock(spec=SessionContext)
        context.session_id = "test_session"
        context.event_stream = MagicMock()
        context.event_stream.subscribe = MagicMock()
        context.event_stream.unsubscribe = MagicMock()
        context.event_stream.add_event = MagicMock()
        return context

    @pytest.fixture
    def event_manager(self, mock_session_manager, mock_file_manager, mock_config):
        """Create a TUIEventManager instance."""
        return TUIEventManager(
            session_manager=mock_session_manager,
            file_manager=mock_file_manager,
            config=mock_config
        )

    @pytest.fixture
    def event_manager_with_app(self, mock_session_manager, mock_file_manager, mock_config, mock_tui_app):
        """Create a TUIEventManager instance with TUI app."""
        return TUIEventManager(
            session_manager=mock_session_manager,
            file_manager=mock_file_manager,
            config=mock_config,
            tui_app=mock_tui_app
        )

    def test_initialization(self, event_manager, mock_session_manager, mock_file_manager, mock_config):
        """Test TUIEventManager initialization."""
        assert event_manager.session_manager == mock_session_manager
        assert event_manager.file_manager == mock_file_manager
        assert event_manager.config == mock_config
        assert event_manager.tui_app is None
        assert event_manager.event_subscriptions == {}
        assert event_manager.streaming_sessions == set()
        assert len(event_manager.event_handlers) == 7  # Number of event types handled

    def test_initialization_with_app(self, event_manager_with_app, mock_tui_app):
        """Test TUIEventManager initialization with TUI app."""
        assert event_manager_with_app.tui_app == mock_tui_app

    def test_subscribe_to_session_success(self, event_manager, mock_session_context):
        """Test successful session subscription."""
        session_id = "test_session"
        event_manager.session_manager.get_session.return_value = mock_session_context

        event_manager.subscribe_to_session(session_id)

        # Verify session was retrieved
        event_manager.session_manager.get_session.assert_called_once_with(session_id)
        
        # Verify subscription was created
        mock_session_context.event_stream.subscribe.assert_called_once()
        args = mock_session_context.event_stream.subscribe.call_args
        assert args[0][0] == EventStreamSubscriber.MAIN
        assert callable(args[0][1])  # callback function
        assert args[0][2] == f"tui_event_manager_{session_id}"
        
        # Verify subscription tracking
        assert session_id in event_manager.event_subscriptions
        assert event_manager.event_subscriptions[session_id] == f"tui_event_manager_{session_id}"

    def test_subscribe_to_session_not_found(self, event_manager):
        """Test subscription to non-existent session."""
        session_id = "nonexistent"
        event_manager.session_manager.get_session.return_value = None

        with pytest.raises(ValueError, match="Session nonexistent not found"):
            event_manager.subscribe_to_session(session_id)

    def test_subscribe_to_session_already_subscribed(self, event_manager, mock_session_context):
        """Test subscribing to already subscribed session."""
        session_id = "test_session"
        event_manager.event_subscriptions[session_id] = "existing_callback"
        event_manager.session_manager.get_session.return_value = mock_session_context

        # Should not raise error, just log warning
        event_manager.subscribe_to_session(session_id)
        
        # Should not call subscribe again
        mock_session_context.event_stream.subscribe.assert_not_called()

    def test_unsubscribe_from_session_success(self, event_manager, mock_session_context):
        """Test successful session unsubscription."""
        session_id = "test_session"
        callback_id = f"tui_event_manager_{session_id}"
        event_manager.event_subscriptions[session_id] = callback_id
        event_manager.streaming_sessions.add(session_id)
        event_manager.session_manager.get_session.return_value = mock_session_context

        event_manager.unsubscribe_from_session(session_id)

        # Verify unsubscription
        mock_session_context.event_stream.unsubscribe.assert_called_once_with(
            EventStreamSubscriber.MAIN, callback_id
        )
        
        # Verify cleanup
        assert session_id not in event_manager.event_subscriptions
        assert session_id not in event_manager.streaming_sessions

    def test_unsubscribe_from_session_not_subscribed(self, event_manager):
        """Test unsubscribing from non-subscribed session."""
        session_id = "not_subscribed"
        
        # Should not raise error, just log warning
        event_manager.unsubscribe_from_session(session_id)

    def test_handle_message_action(self, event_manager):
        """Test handling MessageAction events."""
        session_id = "test_session"
        event = MessageAction(content="Hello from agent")
        event._source = EventSource.AGENT

        event_manager._handle_message_action(session_id, event)

        event_manager.file_manager.update_chat_file.assert_called_once_with(
            session_id, "🤖 Agent: Hello from agent\n"
        )

    def test_handle_message_action_user_source(self, event_manager):
        """Test handling MessageAction from user (should be ignored)."""
        session_id = "test_session"
        event = MessageAction(content="Hello from user")
        event._source = EventSource.USER

        event_manager._handle_message_action(session_id, event)

        event_manager.file_manager.update_chat_file.assert_not_called()

    def test_handle_cmd_run_action(self, event_manager):
        """Test handling CmdRunAction events."""
        session_id = "test_session"
        event = CmdRunAction(command="ls -la")

        event_manager._handle_cmd_run_action(session_id, event)

        event_manager.file_manager.update_logs_file.assert_called_once_with(
            session_id, "$ ls -la\n"
        )

    def test_handle_cmd_output_observation(self, event_manager):
        """Test handling CmdOutputObservation events."""
        session_id = "test_session"
        event = CmdOutputObservation(content="file1.txt\nfile2.txt", command="ls")

        event_manager._handle_cmd_output_observation(session_id, event)

        event_manager.file_manager.update_logs_file.assert_called_once_with(
            session_id, "file1.txt\nfile2.txt\n"
        )

    def test_handle_file_edit_observation(self, event_manager):
        """Test handling FileEditObservation events."""
        session_id = "test_session"
        event = FileEditObservation(content="File was edited", path="/path/to/file.py")
        event.diff = "+print('hello')\n-print('goodbye')"

        event_manager._handle_file_edit_observation(session_id, event)

        expected_content = "📝 File edited: /path/to/file.py\nChanges:\n+print('hello')\n-print('goodbye')\n"
        event_manager.file_manager.update_logs_file.assert_called_once_with(
            session_id, expected_content
        )

    def test_handle_file_read_observation(self, event_manager):
        """Test handling FileReadObservation events."""
        session_id = "test_session"
        event = FileReadObservation(path="/path/to/file.py", content="print('hello')")

        event_manager._handle_file_read_observation(session_id, event)

        event_manager.file_manager.update_logs_file.assert_called_once_with(
            session_id, "📖 File read: /path/to/file.py\n"
        )

    def test_handle_agent_state_changed(self, event_manager):
        """Test handling AgentStateChangedObservation events."""
        session_id = "test_session"
        event = AgentStateChangedObservation(content="Agent state changed", agent_state=AgentState.RUNNING.value)

        event_manager._handle_agent_state_changed(session_id, event)

        event_manager.file_manager.update_logs_file.assert_called_once_with(
            session_id, "🔄 Agent state: running\n"
        )
        event_manager.session_manager.update_session_activity.assert_called_once_with(session_id)

    def test_handle_error_observation(self, event_manager):
        """Test handling ErrorObservation events."""
        session_id = "test_session"
        event = ErrorObservation(content="Something went wrong")

        event_manager._handle_error_observation(session_id, event)

        event_manager.file_manager.update_logs_file.assert_called_once_with(
            session_id, "❌ Error: Something went wrong\n"
        )

    def test_handle_generic_action_with_thoughts(self, event_manager):
        """Test handling generic Action events with thoughts."""
        session_id = "test_session"
        event = MagicMock(spec=Action)
        event.thought = "I need to think about this"
        event.final_thought = "Now I know what to do"

        event_manager._handle_generic_action(session_id, event)

        expected_content = "💭 Thought: I need to think about this\n🎯 Final thought: Now I know what to do\n"
        event_manager.file_manager.update_chat_file.assert_called_once_with(
            session_id, expected_content
        )

    def test_handle_session_event_with_handler(self, event_manager):
        """Test handling session event with registered handler."""
        session_id = "test_session"
        event = MessageAction(content="Test message")
        event._source = EventSource.AGENT

        # Mock the file manager to verify the handler was called
        event_manager._handle_session_event(session_id, event)
        
        # Verify the message was processed (handler was called)
        event_manager.file_manager.update_chat_file.assert_called_once_with(
            session_id, "🤖 Agent: Test message\n"
        )

    def test_handle_session_event_with_ui_update(self, event_manager_with_app, mock_tui_app):
        """Test handling session event with UI update."""
        session_id = "test_session"
        event = MessageAction(content="Test message")
        event._source = EventSource.AGENT
        event_manager_with_app.session_manager.active_session_id = session_id

        event_manager_with_app._handle_session_event(session_id, event)

        # Verify UI panels were updated
        mock_tui_app.chat_panel.update_chat_display.assert_called_once_with(session_id)
        mock_tui_app.logs_panel.update_logs_display.assert_called_once_with(session_id)

    def test_route_user_input_success(self, event_manager, mock_session_context):
        """Test successful user input routing."""
        session_id = "test_session"
        message = "Hello, agent!"
        event_manager.session_manager.get_session.return_value = mock_session_context

        result = event_manager.route_user_input(session_id, message)

        assert result is True
        
        # Verify MessageAction was created and sent
        mock_session_context.event_stream.add_event.assert_called_once()
        args = mock_session_context.event_stream.add_event.call_args
        assert isinstance(args[0][0], MessageAction)
        assert args[0][0].content == message
        assert args[0][1] == EventSource.USER
        
        # Verify chat was updated
        event_manager.file_manager.update_chat_file.assert_called_once_with(
            session_id, "👤 User: Hello, agent!\n"
        )
        
        # Verify session activity was updated
        event_manager.session_manager.update_session_activity.assert_called_once_with(session_id)

    def test_route_user_input_session_not_found(self, event_manager):
        """Test user input routing to non-existent session."""
        session_id = "nonexistent"
        message = "Hello, agent!"
        event_manager.session_manager.get_session.return_value = None

        result = event_manager.route_user_input(session_id, message)

        assert result is False

    def test_send_agent_state_change_success(self, event_manager, mock_session_context):
        """Test successful agent state change."""
        session_id = "test_session"
        new_state = AgentState.PAUSED
        event_manager.session_manager.get_session.return_value = mock_session_context

        result = event_manager.send_agent_state_change(session_id, new_state)

        assert result is True
        
        # Verify ChangeAgentStateAction was created and sent
        mock_session_context.event_stream.add_event.assert_called_once()
        args = mock_session_context.event_stream.add_event.call_args
        assert isinstance(args[0][0], ChangeAgentStateAction)
        assert args[0][0].agent_state == new_state
        assert args[0][1] == EventSource.USER

    def test_send_agent_state_change_session_not_found(self, event_manager):
        """Test agent state change for non-existent session."""
        session_id = "nonexistent"
        new_state = AgentState.PAUSED
        event_manager.session_manager.get_session.return_value = None

        result = event_manager.send_agent_state_change(session_id, new_state)

        assert result is False

    def test_cleanup_session_events(self, event_manager):
        """Test cleaning up session events."""
        session_id = "test_session"
        
        with patch.object(event_manager, 'unsubscribe_from_session') as mock_unsubscribe:
            event_manager.cleanup_session_events(session_id)
            mock_unsubscribe.assert_called_once_with(session_id)

    def test_cleanup_all_events(self, event_manager):
        """Test cleaning up all events."""
        session_ids = ["session1", "session2", "session3"]
        event_manager.event_subscriptions = {sid: f"callback_{sid}" for sid in session_ids}
        event_manager.streaming_sessions = set(session_ids)
        
        with patch.object(event_manager, 'cleanup_session_events') as mock_cleanup:
            event_manager.cleanup_all_events()
            
            # Verify all sessions were cleaned up
            expected_calls = [call(sid) for sid in session_ids]
            mock_cleanup.assert_has_calls(expected_calls, any_order=True)
            
            # Verify streaming sessions were cleared
            assert event_manager.streaming_sessions == set()

    def test_get_subscribed_sessions(self, event_manager):
        """Test getting subscribed sessions."""
        session_ids = ["session1", "session2", "session3"]
        event_manager.event_subscriptions = {sid: f"callback_{sid}" for sid in session_ids}

        result = event_manager.get_subscribed_sessions()

        assert set(result) == set(session_ids)

    def test_is_session_subscribed(self, event_manager):
        """Test checking if session is subscribed."""
        session_id = "test_session"
        event_manager.event_subscriptions[session_id] = "callback_id"

        assert event_manager.is_session_subscribed(session_id) is True
        assert event_manager.is_session_subscribed("other_session") is False

    def test_legacy_methods(self, event_manager):
        """Test legacy methods for backward compatibility."""
        session_id = "test_session"
        event = MessageAction(content="Test")
        
        # Test legacy handle_session_event
        with patch.object(event_manager, '_handle_session_event') as mock_handle:
            asyncio.run(event_manager.handle_session_event(session_id, event))
            mock_handle.assert_called_once_with(session_id, event)
        
        # Test legacy register/unregister methods (should not raise errors)
        event_manager.register_event_handler("test_type", lambda x: None)
        event_manager.unregister_event_handler("test_type")
        
        # Test legacy broadcast_event
        asyncio.run(event_manager.broadcast_event(event))


# Import asyncio for async test
import asyncio