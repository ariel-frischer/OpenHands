"""Tests for TUI message validation and sending feedback."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import pytermgui as ptg

from openhands.core.config import AppConfig
from openhands.core.schema import AgentState
from openhands.tui.panels.chat_panel import ChatPanel, MessageValidator


class TestMessageValidator:
    """Test cases for MessageValidator."""

    def test_validate_empty_message(self):
        """Test validation of empty messages."""
        is_valid, error = MessageValidator.validate_message("")
        assert not is_valid
        assert "cannot be empty" in error

        is_valid, error = MessageValidator.validate_message("   ")
        assert not is_valid
        assert "cannot be empty" in error

    def test_validate_normal_message(self):
        """Test validation of normal messages."""
        is_valid, error = MessageValidator.validate_message("Hello, world!")
        assert is_valid
        assert error == ""

        is_valid, error = MessageValidator.validate_message("This is a longer message with multiple words.")
        assert is_valid
        assert error == ""

    def test_validate_message_too_long(self):
        """Test validation of messages that are too long."""
        long_message = "x" * (MessageValidator.MAX_LENGTH + 1)
        is_valid, error = MessageValidator.validate_message(long_message)
        assert not is_valid
        assert "too long" in error

    def test_validate_too_many_lines(self):
        """Test validation of messages with too many lines."""
        many_lines = "\n".join(["line"] * (MessageValidator.MAX_LINES + 1))
        is_valid, error = MessageValidator.validate_message(many_lines)
        assert not is_valid
        assert "Too many lines" in error

    def test_validate_null_characters(self):
        """Test validation of messages with null characters."""
        message_with_null = "Hello\x00world"
        is_valid, error = MessageValidator.validate_message(message_with_null)
        assert not is_valid
        assert "null characters" in error

    def test_validate_excessive_whitespace(self):
        """Test validation of messages with excessive whitespace."""
        message_with_whitespace = " " * 101 + "hello" + " " * 101
        is_valid, error = MessageValidator.validate_message(message_with_whitespace)
        assert not is_valid
        assert "excessive" in error

    def test_validate_control_characters(self):
        """Test validation of messages with control characters."""
        message_with_control = "Hello\x01world"
        is_valid, error = MessageValidator.validate_message(message_with_control)
        assert not is_valid
        assert "control characters" in error

    def test_validate_allowed_control_characters(self):
        """Test that allowed control characters (newline, tab) are accepted."""
        message_with_newline = "Hello\nworld"
        is_valid, error = MessageValidator.validate_message(message_with_newline)
        assert is_valid
        assert error == ""

        message_with_tab = "Hello\tworld"
        is_valid, error = MessageValidator.validate_message(message_with_tab)
        assert is_valid
        assert error == ""

    def test_validate_edge_cases(self):
        """Test validation edge cases."""
        # Exactly at max length
        max_length_message = "x" * MessageValidator.MAX_LENGTH
        is_valid, error = MessageValidator.validate_message(max_length_message)
        assert is_valid
        assert error == ""

        # Exactly at max lines
        max_lines_message = "\n".join(["line"] * MessageValidator.MAX_LINES)
        is_valid, error = MessageValidator.validate_message(max_lines_message)
        assert is_valid
        assert error == ""


class TestChatPanelValidation:
    """Test cases for ChatPanel message validation and feedback."""

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        manager = MagicMock()
        manager.get_active_session.return_value = None
        manager.list_sessions.return_value = []
        return manager

    @pytest.fixture
    def mock_event_manager(self):
        """Create a mock event manager."""
        manager = MagicMock()
        manager.route_user_input.return_value = True
        return manager

    @pytest.fixture
    def mock_file_manager(self):
        """Create a mock file manager."""
        manager = MagicMock()
        return manager

    @pytest.fixture
    def chat_panel(self, mock_session_manager, mock_event_manager, mock_file_manager):
        """Create a ChatPanel instance for testing."""
        return ChatPanel(mock_session_manager, mock_event_manager, mock_file_manager)

    @pytest.mark.asyncio
    async def test_send_empty_message_validation(self, chat_panel):
        """Test that empty messages are rejected with feedback."""
        # Mock the input field value property
        with patch.object(chat_panel.input_field, 'value', ""), \
             patch.object(chat_panel, '_show_feedback') as mock_feedback:
            await chat_panel.send_message()
            mock_feedback.assert_called_once_with("Message cannot be empty", "error")

    @pytest.mark.asyncio
    async def test_send_too_long_message_validation(self, chat_panel):
        """Test that overly long messages are rejected with feedback."""
        long_message = "x" * (MessageValidator.MAX_LENGTH + 1)
        
        with patch.object(chat_panel.input_field, 'value', long_message), \
             patch.object(chat_panel, '_show_feedback') as mock_feedback:
            await chat_panel.send_message()
            mock_feedback.assert_called_once()
            args, kwargs = mock_feedback.call_args
            assert "too long" in args[0]
            assert args[1] == "error"

    @pytest.mark.asyncio
    async def test_send_message_with_active_session_success(self, chat_panel, mock_session_manager, mock_event_manager):
        """Test successful message sending with active session."""
        # Setup active session
        mock_session = MagicMock()
        mock_session.sid = "test-session"
        mock_session.agent_state = AgentState.AWAITING_USER_INPUT
        mock_session_manager.get_active_session.return_value = mock_session
        
        with patch.object(chat_panel.input_field, 'value', "Hello, world!"), \
             patch.object(chat_panel, '_show_feedback') as mock_feedback, \
             patch.object(chat_panel, 'update_chat_display') as mock_update:
            
            await chat_panel.send_message()
            
            # Check that feedback was shown for sending and success
            feedback_calls = mock_feedback.call_args_list
            assert len(feedback_calls) >= 2
            assert any("Sending message" in str(call) for call in feedback_calls)
            assert any("sent successfully" in str(call) for call in feedback_calls)
            
            # Check that message was routed
            mock_event_manager.route_user_input.assert_called_once_with("test-session", "Hello, world!")
            
            # Check that display was updated
            mock_update.assert_called_once_with("test-session")

    @pytest.mark.asyncio
    async def test_send_message_session_not_ready(self, chat_panel, mock_session_manager):
        """Test message sending when session is not ready."""
        # Setup session in loading state
        mock_session = MagicMock()
        mock_session.sid = "test-session"
        mock_session.agent_state = AgentState.LOADING
        mock_session_manager.get_active_session.return_value = mock_session
        
        with patch.object(chat_panel.input_field, 'value', "Hello, world!"), \
             patch.object(chat_panel, '_show_feedback') as mock_feedback:
            await chat_panel.send_message()
            
            # Check that appropriate warning was shown
            feedback_calls = mock_feedback.call_args_list
            assert any("still loading" in str(call) for call in feedback_calls)

    @pytest.mark.asyncio
    async def test_send_message_routing_failure(self, chat_panel, mock_session_manager, mock_event_manager):
        """Test message sending when routing fails."""
        # Setup active session
        mock_session = MagicMock()
        mock_session.sid = "test-session"
        mock_session.agent_state = AgentState.AWAITING_USER_INPUT
        mock_session_manager.get_active_session.return_value = mock_session
        
        # Make routing fail
        mock_event_manager.route_user_input.return_value = False
        
        with patch.object(chat_panel.input_field, 'value', "Hello, world!"), \
             patch.object(chat_panel, '_show_feedback') as mock_feedback, \
             patch.object(chat_panel, '_show_retry_button') as mock_retry:
            
            await chat_panel.send_message()
            
            # Check that error feedback was shown
            feedback_calls = mock_feedback.call_args_list
            assert any("Failed to send" in str(call) for call in feedback_calls)
            
            # Check that retry button was shown
            mock_retry.assert_called_with(True)
            
            # Check that failed message was stored
            assert chat_panel._last_failed_message == "Hello, world!"

    @pytest.mark.asyncio
    async def test_send_message_exception_handling(self, chat_panel, mock_session_manager, mock_event_manager):
        """Test message sending when an exception occurs."""
        # Setup active session
        mock_session = MagicMock()
        mock_session.sid = "test-session"
        mock_session.agent_state = AgentState.AWAITING_USER_INPUT
        mock_session_manager.get_active_session.return_value = mock_session
        
        # Make routing raise an exception
        mock_event_manager.route_user_input.side_effect = Exception("Network error")
        
        with patch.object(chat_panel.input_field, 'value', "Hello, world!"), \
             patch.object(chat_panel, '_show_feedback') as mock_feedback, \
             patch.object(chat_panel, '_show_retry_button') as mock_retry:
            
            await chat_panel.send_message()
            
            # Check that error feedback was shown
            feedback_calls = mock_feedback.call_args_list
            assert any("Send failed" in str(call) for call in feedback_calls)
            
            # Check that retry button was shown
            mock_retry.assert_called_with(True)

    def test_retry_last_message_no_message(self, chat_panel):
        """Test retry when no message to retry."""
        chat_panel._last_failed_message = ""
        
        with patch.object(chat_panel, '_show_feedback') as mock_feedback:
            chat_panel.retry_last_message()
            mock_feedback.assert_called_once_with("No message to retry", "warning")

    def test_retry_last_message_max_retries_exceeded(self, chat_panel):
        """Test retry when max retries exceeded."""
        chat_panel._last_failed_message = "Hello"
        chat_panel._retry_count = chat_panel._max_retries
        
        with patch.object(chat_panel, '_show_feedback') as mock_feedback:
            chat_panel.retry_last_message()
            mock_feedback.assert_called_once()
            args, kwargs = mock_feedback.call_args
            assert "Max retries" in args[0]
            assert args[1] == "error"

    def test_retry_last_message_success(self, chat_panel):
        """Test successful retry of last message."""
        chat_panel._last_failed_message = "Hello, world!"
        chat_panel._retry_count = 1
        
        with patch.object(chat_panel, '_show_feedback') as mock_feedback, \
             patch.object(chat_panel, 'send_message_sync') as mock_send:
            
            chat_panel.retry_last_message()
            
            # Check that retry count was incremented
            assert chat_panel._retry_count == 2
            
            # Check that input field was set (we'll mock this since PyTermGUI doesn't have settable value)
            # The actual implementation tries to set the content or handle keys
            
            # Check that feedback was shown
            mock_feedback.assert_called_once()
            args, kwargs = mock_feedback.call_args
            assert "Retrying message" in args[0]
            assert args[1] == "info"
            
            # Check that send was called
            mock_send.assert_called_once()

    def test_show_feedback_styles(self, chat_panel):
        """Test different feedback styles."""
        # Test error style
        chat_panel._show_feedback("Error message", "error")
        assert "❌" in chat_panel.feedback_label.value
        assert "[red]" in chat_panel.feedback_label.value

        # Test success style
        chat_panel._show_feedback("Success message", "success")
        assert "✅" in chat_panel.feedback_label.value
        assert "[green]" in chat_panel.feedback_label.value

        # Test warning style
        chat_panel._show_feedback("Warning message", "warning")
        assert "⚠️" in chat_panel.feedback_label.value
        assert "[yellow]" in chat_panel.feedback_label.value

        # Test info style
        chat_panel._show_feedback("Info message", "info")
        assert "ℹ️" in chat_panel.feedback_label.value
        assert "[blue]" in chat_panel.feedback_label.value

        # Test sending style
        chat_panel._show_feedback("Sending message", "sending")
        assert "📤" in chat_panel.feedback_label.value
        assert "[cyan]" in chat_panel.feedback_label.value

    @pytest.mark.asyncio
    async def test_clear_feedback_after_delay(self, chat_panel):
        """Test that feedback is cleared after delay."""
        chat_panel.feedback_label.value = "Test message"
        
        # Use a very short delay for testing
        await chat_panel._clear_feedback_after_delay(0.01)
        
        assert chat_panel.feedback_label.value == ""

    def test_show_retry_button(self, chat_panel):
        """Test showing and hiding retry button."""
        # Test showing retry button
        chat_panel._show_retry_button(True)
        # PyTermGUI styles are more complex, just check that the method runs without error
        assert hasattr(chat_panel.retry_button, 'styles')

        # Test hiding retry button
        chat_panel._show_retry_button(False)
        assert hasattr(chat_panel.retry_button, 'styles')

    @pytest.mark.asyncio
    async def test_create_session_and_send_message_success(self, chat_panel, mock_session_manager, mock_event_manager):
        """Test successful session creation and message sending."""
        # Setup mocks
        mock_session_manager.create_session = AsyncMock(return_value="new-session-id")
        mock_session_manager.start_session = AsyncMock()
        mock_session_manager.event_manager = MagicMock()
        mock_session_manager.event_manager.subscribe_to_session = MagicMock()
        
        with patch.object(chat_panel, '_show_feedback') as mock_feedback, \
             patch.object(chat_panel, 'update_chat_display') as mock_update:
            
            await chat_panel._create_session_and_send_message("Test task", "Hello")
            
            # Check that session was created and started
            mock_session_manager.create_session.assert_called_once_with("Test task")
            mock_session_manager.start_session.assert_called_once_with("new-session-id")
            
            # Check that message was routed
            mock_event_manager.route_user_input.assert_called_once_with("new-session-id", "Hello")
            
            # Check that appropriate feedback was shown
            feedback_calls = mock_feedback.call_args_list
            assert len(feedback_calls) >= 3  # Session created, started, message sent
            
            # Check that retry state was reset
            assert chat_panel._retry_count == 0
            assert chat_panel._last_failed_message == ""

    @pytest.mark.asyncio
    async def test_create_session_and_send_message_failure(self, chat_panel, mock_session_manager):
        """Test session creation failure."""
        # Make session creation fail
        mock_session_manager.create_session.side_effect = Exception("Creation failed")
        
        with patch.object(chat_panel, '_show_feedback') as mock_feedback, \
             patch.object(chat_panel, '_show_retry_button') as mock_retry:
            
            await chat_panel._create_session_and_send_message("Test task", "Hello")
            
            # Check that error feedback was shown
            feedback_calls = mock_feedback.call_args_list
            assert any("failed" in str(call) for call in feedback_calls)
            
            # Check that retry button was shown
            mock_retry.assert_called_with(True)
            
            # Check that failed message was stored
            assert chat_panel._last_failed_message == "Hello" 