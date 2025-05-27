"""Tests for TUI Chat Panel.

This module contains comprehensive tests for the ChatPanel class,
including responsive layout, message display, and user interaction functionality.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import pytermgui as ptg

from openhands.tui.panels.chat_panel import ChatPanel
from openhands.events.action import MessageAction
from openhands.events.observation import CmdOutputObservation
from openhands.events.stream import EventSource
from openhands.core.schema import AgentState


class TestChatPanel:
    """Test cases for ChatPanel functionality."""

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        manager = MagicMock()
        manager.get_active_session.return_value = None
        manager.get_session.return_value = None
        return manager

    @pytest.fixture
    def mock_event_manager(self):
        """Create a mock event manager."""
        manager = MagicMock()
        manager.route_user_input = AsyncMock()
        return manager

    @pytest.fixture
    def mock_file_manager(self):
        """Create a mock file manager."""
        manager = MagicMock()
        manager.update_chat_file = MagicMock()
        return manager

    @pytest.fixture
    def chat_panel(self, mock_session_manager, mock_event_manager, mock_file_manager):
        """Create a ChatPanel instance for testing."""
        # Mock the terminal object for responsive sizing
        with patch("openhands.tui.panels.chat_panel.ptg.terminal") as mock_terminal:
            mock_terminal.height = 50
            mock_terminal.width = 100
            return ChatPanel(
                mock_session_manager, mock_event_manager, mock_file_manager
            )

    def test_initialization(self, chat_panel):
        """Test ChatPanel initialization."""
        assert chat_panel.get_panel_name() == "chat"
        assert hasattr(chat_panel, "chat_display")
        assert hasattr(chat_panel, "input_field")
        assert hasattr(chat_panel, "send_button")
        assert hasattr(chat_panel, "pause_button")
        assert hasattr(chat_panel, "event_manager")
        assert chat_panel.max_messages == 50

    def test_get_panel_name(self, chat_panel):
        """Test getting panel name."""
        assert chat_panel.get_panel_name() == "chat"

    def test_wrap_message_content(self, chat_panel):
        """Test message content wrapping."""
        # Test normal message
        content = "This is a test message that should be wrapped properly"
        wrapped = chat_panel.wrap_message_content(content, 20)
        lines = wrapped.split("\n")
        assert all(len(line) <= 20 for line in lines)

    def test_wrap_message_content_empty(self, chat_panel):
        """Test wrapping empty message content."""
        wrapped = chat_panel.wrap_message_content("", 50)
        assert wrapped == ""

    def test_wrap_message_content_long_word(self, chat_panel):
        """Test wrapping content with very long words."""
        content = "supercalifragilisticexpialidocious"
        wrapped = chat_panel.wrap_message_content(content, 20)
        lines = wrapped.split("\n")
        assert len(lines) > 1  # Should be broken into multiple lines

    @patch("openhands.tui.panels.chat_panel.ptg.terminal")
    def test_create_message_widget_user_message(self, mock_terminal, chat_panel):
        """Test creating widget for user message."""
        mock_terminal.width = 100

        # Create a mock MessageAction with user source
        mock_source = MagicMock()
        mock_source.value = "user"

        message = MagicMock(spec=MessageAction)
        message.content = "Hello, this is a user message"
        message.source = mock_source

        widget = chat_panel.create_message_widget(message)
        assert widget is not None
        assert isinstance(widget, ptg.Label)

    @patch("openhands.tui.panels.chat_panel.ptg.terminal")
    def test_create_message_widget_agent_message(self, mock_terminal, chat_panel):
        """Test creating widget for agent message."""
        mock_terminal.width = 100

        # Create a mock MessageAction with agent source
        mock_source = MagicMock()
        mock_source.value = "agent"

        message = MagicMock(spec=MessageAction)
        message.content = "Hello, this is an agent response"
        message.source = mock_source

        widget = chat_panel.create_message_widget(message)
        assert widget is not None
        assert isinstance(widget, ptg.Label)

    @patch("openhands.tui.panels.chat_panel.ptg.terminal")
    def test_create_message_widget_cmd_output(self, mock_terminal, chat_panel):
        """Test creating widget for command output."""
        mock_terminal.width = 100

        output = MagicMock(spec=CmdOutputObservation)
        output.content = "Command executed successfully"

        widget = chat_panel.create_message_widget(output)
        assert widget is not None
        assert isinstance(widget, ptg.Label)

    @patch("openhands.tui.panels.chat_panel.ptg.terminal")
    def test_create_message_widget_long_output(self, mock_terminal, chat_panel):
        """Test creating widget for long command output."""
        mock_terminal.width = 100

        output = MagicMock(spec=CmdOutputObservation)
        output.content = "A" * 300  # Long content that should be truncated

        widget = chat_panel.create_message_widget(output)
        assert widget is not None
        assert isinstance(widget, ptg.Label)

    def test_create_message_widget_unknown_event(self, chat_panel):
        """Test creating widget for unknown event type."""
        unknown_event = MagicMock()
        widget = chat_panel.create_message_widget(unknown_event)
        assert widget is None

    @patch("openhands.tui.panels.chat_panel.ptg.terminal")
    def test_update_chat_display(self, mock_terminal, chat_panel, mock_session_manager):
        """Test updating chat display."""
        mock_terminal.height = 50
        mock_terminal.width = 100

        # Create mock session with event stream
        mock_session = MagicMock()
        mock_event_stream = MagicMock()

        # Create mock events
        mock_message = MagicMock(spec=MessageAction)
        mock_message.content = "Test message"
        mock_source = MagicMock()
        mock_source.value = "user"
        mock_message.source = mock_source

        mock_event_stream.get_events.return_value = [mock_message]
        mock_session.event_stream = mock_event_stream

        mock_session_manager.get_session.return_value = mock_session

        chat_panel.update_chat_display("test-session")

        # Verify session was retrieved and file manager was called
        assert mock_session_manager.get_session.call_count >= 1
        chat_panel.file_manager.update_chat_file.assert_called_once()

    def test_update_chat_display_no_session(self, chat_panel, mock_session_manager):
        """Test updating chat display when session not found."""
        mock_session_manager.get_session.return_value = None

        chat_panel.update_chat_display("nonexistent-session")

        # Should not crash and should log warning
        mock_session_manager.get_session.assert_called_once_with("nonexistent-session")

    @patch("openhands.tui.panels.chat_panel.ptg.terminal")
    def test_update_chat_display_no_event_stream(
        self, mock_terminal, chat_panel, mock_session_manager
    ):
        """Test updating chat display when session has no event stream."""
        mock_terminal.height = 50
        mock_terminal.width = 100

        mock_session = MagicMock()
        mock_session.event_stream = None
        mock_session_manager.get_session.return_value = mock_session

        chat_panel.update_chat_display("test-session")

        # Should show placeholder message
        assert len(chat_panel.chat_display._widgets) == 1

    def test_update_display(self, chat_panel, mock_session_manager):
        """Test update_display method."""
        # Test with session_id parameter
        with patch.object(chat_panel, "update_chat_display") as mock_update:
            chat_panel.update_display("test-session")
            mock_update.assert_called_once_with("test-session")

    def test_update_display_no_session_id(self, chat_panel, mock_session_manager):
        """Test update_display without session_id."""
        mock_session = MagicMock()
        mock_session.sid = "active-session"
        mock_session_manager.get_active_session.return_value = mock_session

        with patch.object(chat_panel, "update_chat_display") as mock_update:
            chat_panel.update_display()
            mock_update.assert_called_once_with("active-session")

    def test_update_display_no_active_session(self, chat_panel, mock_session_manager):
        """Test update_display when no active session."""
        mock_session_manager.get_active_session.return_value = None

        with patch.object(chat_panel, "update_chat_display") as mock_update:
            chat_panel.update_display()
            mock_update.assert_not_called()

    def test_handle_terminal_resize(self, chat_panel, mock_session_manager):
        """Test terminal resize handling."""
        mock_session = MagicMock()
        mock_session.sid = "active-session"
        mock_session_manager.get_active_session.return_value = mock_session

        with patch.object(chat_panel, "update_chat_display") as mock_update:
            chat_panel.handle_terminal_resize()
            mock_update.assert_called_once_with("active-session")

    def test_handle_terminal_resize_no_active_session(
        self, chat_panel, mock_session_manager
    ):
        """Test terminal resize handling when no active session."""
        mock_session_manager.get_active_session.return_value = None

        with patch.object(chat_panel, "update_chat_display") as mock_update:
            chat_panel.handle_terminal_resize()
            mock_update.assert_not_called()

    def test_get_chat_messages(self, chat_panel, mock_session_manager):
        """Test getting chat messages for file export."""
        # Create mock session with event stream
        mock_session = MagicMock()
        mock_event_stream = MagicMock()

        # Create mock message event
        mock_message = MagicMock(spec=MessageAction)
        mock_message.content = "Test message"
        mock_message.timestamp = "12:34:56"
        mock_source = MagicMock()
        mock_source.value = "user"
        mock_message.source = mock_source

        mock_event_stream.get_events.return_value = [mock_message]
        mock_session.event_stream = mock_event_stream
        mock_session_manager.get_session.return_value = mock_session

        messages = chat_panel.get_chat_messages("test-session")

        assert len(messages) == 1
        assert messages[0]["content"] == "Test message"
        assert messages[0]["sender"] == "user"

    def test_get_chat_messages_no_session(self, chat_panel, mock_session_manager):
        """Test getting chat messages when session not found."""
        mock_session_manager.get_session.return_value = None

        messages = chat_panel.get_chat_messages("nonexistent-session")
        assert messages == []

    @pytest.mark.asyncio
    async def test_send_message(
        self, chat_panel, mock_session_manager, mock_event_manager
    ):
        """Test sending a message."""
        # Set up input field with a message by inserting text
        chat_panel.input_field.insert_text("Test message")

        # Set up active session
        mock_session = MagicMock()
        mock_session.sid = "test-session"
        mock_session.agent_state = AgentState.AWAITING_USER_INPUT  # Ready state
        mock_session_manager.get_active_session.return_value = mock_session
        mock_event_manager.route_user_input.return_value = True

        with patch.object(chat_panel, "update_chat_display") as mock_update:
            await chat_panel.send_message()

            # Verify message was routed
            mock_event_manager.route_user_input.assert_called_once_with(
                "test-session", "Test message"
            )

            # Verify display was updated
            mock_update.assert_called_once_with("test-session")

            # Verify input field was cleared
            assert chat_panel.input_field.value == ""

    @pytest.mark.asyncio
    async def test_send_message_empty(self, chat_panel, mock_event_manager):
        """Test sending empty message."""
        # Insert whitespace only
        chat_panel.input_field.insert_text("   ")

        await chat_panel.send_message()

        # Should not route empty message
        mock_event_manager.route_user_input.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_message_no_active_session(
        self, chat_panel, mock_session_manager, mock_event_manager
    ):
        """Test sending message when no active session - should create task for new session automatically."""
        # Insert a test message
        chat_panel.input_field.insert_text("Test message")
        mock_session_manager.get_active_session.return_value = None
        
        # Set up async mocks for session creation
        mock_session_manager.create_session = AsyncMock(return_value="new-session-id")
        mock_session_manager.start_session = AsyncMock()
        mock_event_manager.route_user_input.return_value = True

        # Mock asyncio.create_task to capture the task creation
        with patch("asyncio.create_task") as mock_create_task:
            # Mock create_task to close the coroutine to avoid warnings
            def mock_create_task_impl(coro):
                # Close the coroutine to avoid "never awaited" warnings
                if hasattr(coro, "close"):
                    coro.close()
                return MagicMock()

            mock_create_task.side_effect = mock_create_task_impl

            await chat_panel.send_message()

            # Should create task for session creation
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_and_send_message(
        self, chat_panel, mock_session_manager, mock_event_manager
    ):
        """Test the _create_session_and_send_message helper method."""
        mock_session_manager.create_session = AsyncMock(return_value="new-session-id")
        mock_session_manager.start_session = AsyncMock()
        mock_event_manager.route_user_input.return_value = True

        # Mock the input field to have a value
        chat_panel.input_field.insert_text("Test message")

        with patch.object(chat_panel, "update_chat_display") as mock_update:
            await chat_panel._create_session_and_send_message(
                "Test task", "Test message"
            )

            # Verify session creation
            mock_session_manager.create_session.assert_called_once_with("Test task")
            # Verify session start
            mock_session_manager.start_session.assert_called_once_with("new-session-id")
            # Verify message routing
            mock_event_manager.route_user_input.assert_called_once_with(
                "new-session-id", "Test message"
            )
            # Verify display update
            mock_update.assert_called_once_with("new-session-id")
            # Verify input field was cleared
            assert chat_panel.input_field.value == ""

    @pytest.mark.asyncio
    async def test_send_message_auto_start_session(
        self, chat_panel, mock_session_manager, mock_event_manager
    ):
        """Test sending message shows warning when session is in LOADING state."""
        # Set up input field with a message
        chat_panel.input_field.insert_text("Test message")

        # Set up active session in LOADING state (not yet started)
        mock_session = MagicMock()
        mock_session.sid = "test-session"
        mock_session.agent_state = AgentState.LOADING
        mock_session_manager.get_active_session.return_value = mock_session
        mock_session_manager.start_session = AsyncMock()
        mock_event_manager.route_user_input.return_value = True

        with patch.object(chat_panel, "update_chat_display") as mock_update:
            await chat_panel.send_message()

            # Verify session was NOT started (session not ready)
            mock_session_manager.start_session.assert_not_called()

            # Verify message was NOT routed (session not ready)
            mock_event_manager.route_user_input.assert_not_called()

            # Verify display was NOT updated (no message sent)
            mock_update.assert_not_called()

            # Verify input field was NOT cleared (message not sent)
            assert chat_panel.input_field.value == "Test message"

    @pytest.mark.asyncio
    async def test_send_message_session_already_started(
        self, chat_panel, mock_session_manager, mock_event_manager
    ):
        """Test sending message when session is already started (not in LOADING state)."""
        # Set up input field with a message
        chat_panel.input_field.insert_text("Test message")

        # Set up active session in RUNNING state (already started)
        mock_session = MagicMock()
        mock_session.sid = "test-session"
        mock_session.agent_state = AgentState.RUNNING
        mock_session_manager.get_active_session.return_value = mock_session
        mock_session_manager.start_session = AsyncMock()
        mock_event_manager.route_user_input.return_value = True

        with patch.object(chat_panel, "update_chat_display") as mock_update:
            await chat_panel.send_message()

            # Verify session was NOT started (already running)
            mock_session_manager.start_session.assert_not_called()

            # Verify message was routed
            mock_event_manager.route_user_input.assert_called_once_with(
                "test-session", "Test message"
            )

            # Verify display was updated
            mock_update.assert_called_once_with("test-session")

            # Verify input field was cleared
            assert chat_panel.input_field.value == ""

    @pytest.mark.asyncio
    async def test_send_message_session_start_failure(
        self, chat_panel, mock_session_manager, mock_event_manager
    ):
        """Test sending message when session is in LOADING state (same as auto_start_session test)."""
        # Set up input field with a message
        chat_panel.input_field.insert_text("Test message")

        # Set up active session in LOADING state
        mock_session = MagicMock()
        mock_session.sid = "test-session"
        mock_session.agent_state = AgentState.LOADING
        mock_session_manager.get_active_session.return_value = mock_session
        mock_session_manager.start_session = AsyncMock(
            side_effect=Exception("Start failed")
        )

        with patch.object(chat_panel, "update_chat_display") as mock_update:
            await chat_panel.send_message()

            # Verify session start was NOT attempted (session not ready)
            mock_session_manager.start_session.assert_not_called()

            # Verify message was NOT routed (session not ready)
            mock_event_manager.route_user_input.assert_not_called()

            # Verify display was NOT updated (no message sent)
            mock_update.assert_not_called()

            # Input field should still contain the message (not cleared)
            assert chat_panel.input_field.value == "Test message"

    @pytest.mark.asyncio
    async def test_pause_agent(self, chat_panel, mock_session_manager):
        """Test pausing agent."""
        mock_session = MagicMock()
        mock_session.controller = MagicMock()
        mock_session_manager.get_active_session.return_value = mock_session

        await chat_panel.pause_agent()

        # Should not crash (pause logic is TODO)
        mock_session_manager.get_active_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_agent_no_session(self, chat_panel, mock_session_manager):
        """Test pausing agent when no active session."""
        mock_session_manager.get_active_session.return_value = None

        await chat_panel.pause_agent()

        # Should not crash
        mock_session_manager.get_active_session.assert_called_once()

    def test_handle_key_event_enter(self, chat_panel):
        """Test handling Enter key event."""
        with patch("asyncio.create_task") as mock_create_task:
            with patch("asyncio.get_running_loop") as mock_get_loop:
                mock_loop = MagicMock()
                mock_get_loop.return_value = mock_loop

                result = chat_panel.handle_key_event("Enter")
                assert result is True
                mock_create_task.assert_called_once()
                # Verify the task was created with a coroutine
                args, kwargs = mock_create_task.call_args
                assert len(args) == 1
                # The argument should be a coroutine
                import inspect

                assert inspect.iscoroutine(args[0])

    def test_handle_key_event_escape(self, chat_panel):
        """Test handling Escape key event."""
        # Insert some text first
        chat_panel.input_field.insert_text("Some text")
        assert chat_panel.input_field.value == "Some text"

        # Handle escape key
        result = chat_panel.handle_key_event("Escape")

        assert result is True
        # Verify that input field was cleared
        assert chat_panel.input_field.value == ""

    def test_handle_key_event_unhandled(self, chat_panel):
        """Test handling unhandled key event."""
        result = chat_panel.handle_key_event("F1")
        assert result is False

    def test_clear_chat(self, chat_panel):
        """Test clearing chat display."""
        # Add some widgets first
        chat_panel.chat_display += ptg.Label("Test message")
        assert len(chat_panel.chat_display._widgets) == 1

        # Clear chat
        chat_panel.clear_chat()

        # Should have one widget (the "cleared" message)
        assert len(chat_panel.chat_display._widgets) == 1

    def test_set_input_focus(self, chat_panel):
        """Test setting input focus."""
        # This is a TODO method, should not crash
        chat_panel.set_input_focus()

    @patch("openhands.tui.panels.chat_panel.ptg.terminal")
    def test_responsive_layout_small_terminal(
        self, mock_terminal, chat_panel, mock_session_manager
    ):
        """Test responsive layout with small terminal."""
        mock_terminal.height = 20
        mock_terminal.width = 60

        # Create mock session with many events
        mock_session = MagicMock()
        mock_event_stream = MagicMock()

        # Create many mock events
        events = []
        for i in range(30):
            mock_message = MagicMock(spec=MessageAction)
            mock_message.content = f"Message {i}"
            mock_source = MagicMock()
            mock_source.value = "user"
            mock_message.source = mock_source
            events.append(mock_message)

        mock_event_stream.get_events.return_value = events
        mock_session.event_stream = mock_event_stream
        mock_session_manager.get_session.return_value = mock_session

        chat_panel.update_chat_display("test-session")

        # Should limit number of displayed messages based on terminal height
        available_height = max(10, mock_terminal.height - 6)  # 14
        max_widgets = available_height - 2  # 12
        assert len(chat_panel.chat_display._widgets) <= max_widgets

    @patch("openhands.tui.panels.chat_panel.ptg.terminal")
    def test_message_wrapping_narrow_terminal(self, mock_terminal, chat_panel):
        """Test message wrapping with narrow terminal."""
        mock_terminal.width = 50

        # Create a long message
        mock_source = MagicMock()
        mock_source.value = "user"

        message = MagicMock(spec=MessageAction)
        message.content = "This is a very long message that should be wrapped when displayed in a narrow terminal window"
        message.source = mock_source

        widget = chat_panel.create_message_widget(message)
        assert widget is not None

        # The wrapped content should fit within the available width
        available_width = max(40, mock_terminal.width - 15)  # 35
        wrapped_content = chat_panel.wrap_message_content(
            message.content, available_width - 6
        )
        lines = wrapped_content.split("\n")
        assert all(len(line) <= available_width - 6 for line in lines)
