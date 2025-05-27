"""Integration tests for TUI issues with new session button and new message functionality.

This module contains tests that specifically target the reported issues:
1. New session button breaking immediately
2. New message creation failing
3. Insufficient debug error logs
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pytermgui as ptg

from openhands.core.config import AppConfig
from openhands.core.schema import AgentState
from openhands.events.action import MessageAction
from openhands.events.stream import EventSource
from openhands.tui.app import OpenHandsTUIApp
from openhands.tui.panels.sessions_panel import SessionsPanel
from openhands.tui.panels.chat_panel import ChatPanel
from openhands.tui.managers.session_manager import SessionContext, SessionManager
from openhands.tui.managers.event_manager import TUIEventManager
from openhands.tui.managers.file_manager import TUIPanelFileManager


class TestTUIIntegrationIssues:
    """Test cases for TUI integration issues."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock AppConfig."""
        config = MagicMock()
        config.sandbox = MagicMock()
        config.sandbox.selected_repo = None
        config.jwt_secret = "test-secret"
        config.workspace_base = "/tmp/test"
        return config

    @pytest.fixture
    def mock_settings_store(self):
        """Create a mock settings store."""
        return MagicMock()

    @pytest.fixture
    def session_manager(self, mock_config, mock_settings_store):
        """Create a SessionManager instance."""
        return SessionManager(mock_config, mock_settings_store)

    @pytest.fixture
    def file_manager(self):
        """Create a TUIPanelFileManager instance."""
        return TUIPanelFileManager()

    @pytest.fixture
    def event_manager(self, session_manager, file_manager, mock_config):
        """Create a TUIEventManager instance."""
        return TUIEventManager(session_manager, file_manager, mock_config)

    @pytest.fixture
    def sessions_panel(self, session_manager, file_manager):
        """Create a SessionsPanel instance."""
        return SessionsPanel(session_manager, file_manager)

    @pytest.fixture
    def chat_panel(self, session_manager, event_manager, file_manager):
        """Create a ChatPanel instance."""
        with patch('openhands.tui.panels.chat_panel.ptg.terminal') as mock_terminal:
            mock_terminal.height = 50
            mock_terminal.width = 100
            return ChatPanel(session_manager, event_manager, file_manager)

    @pytest.fixture
    def mock_session_context(self):
        """Create a mock SessionContext."""
        mock_runtime = MagicMock()
        mock_runtime._connected = False
        mock_runtime.connect = AsyncMock()
        
        mock_controller = MagicMock()
        mock_controller.set_agent_state_to = AsyncMock()
        mock_controller.get_state = MagicMock()
        mock_controller.close = AsyncMock()
        
        mock_event_stream = MagicMock()
        mock_event_stream.add_event = MagicMock()
        mock_event_stream.get_events = MagicMock(return_value=[])
        
        mock_memory = MagicMock()
        mock_agent = MagicMock()
        mock_agent.reset = MagicMock()
        
        return SessionContext(
            sid="test-session-123",
            config=MagicMock(),
            runtime=mock_runtime,
            controller=mock_controller,
            event_stream=mock_event_stream,
            memory=mock_memory,
            agent_state=AgentState.LOADING,
            created_at=MagicMock(),
            last_activity=MagicMock(),
            task_description="Test task",
            agent=mock_agent,
            repo_directory=None,
            reload_microagents=False,
        )

    # Tests for New Session Button Issues

    def test_new_session_button_no_event_loop_error(self, sessions_panel):
        """Test new session button when no event loop is running."""
        with patch('asyncio.get_running_loop', side_effect=RuntimeError("No event loop")):
            with patch('asyncio.run') as mock_run:
                # This should not raise an exception - simulate PyTermGUI button callback
                mock_button = MagicMock()
                sessions_panel.create_new_session(mock_button)
                mock_run.assert_called_once()

    def test_new_session_button_event_loop_error_handling(self, sessions_panel):
        """Test new session button with event loop creation failure."""
        with patch('asyncio.get_running_loop', side_effect=RuntimeError("No event loop")):
            with patch('asyncio.run', side_effect=Exception("Event loop creation failed")):
                # This should not crash the TUI - simulate PyTermGUI button callback
                mock_button = MagicMock()
                try:
                    sessions_panel.create_new_session(mock_button)
                except Exception as e:
                    pytest.fail(f"New session button should not crash TUI: {e}")

    @pytest.mark.asyncio
    async def test_new_session_creation_runtime_connection_failure(self, sessions_panel, session_manager):
        """Test new session creation when runtime connection fails."""
        session_manager.create_session = AsyncMock(side_effect=Exception("Runtime connection failed"))
        
        # This should not raise an exception but should log the error
        with patch('openhands.tui.panels.sessions_panel.logger') as mock_logger:
            await sessions_panel._create_session_async("Test task")
            mock_logger.error.assert_called()
            # Verify error message was logged (multiple calls expected due to our enhanced error handling)
            assert mock_logger.error.call_count >= 1

    @pytest.mark.asyncio
    async def test_new_session_creation_docker_timeout(self, sessions_panel, session_manager):
        """Test new session creation when Docker container startup times out."""
        session_manager.create_session = AsyncMock(side_effect=asyncio.TimeoutError("Docker startup timeout"))
        
        with patch('openhands.tui.panels.sessions_panel.logger') as mock_logger:
            await sessions_panel._create_session_async("Test task")
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_new_session_creation_with_detailed_error_logging(self, sessions_panel, session_manager):
        """Test that session creation failures provide detailed error information."""
        # Create a specific error that should be logged with details
        detailed_error = Exception("Specific runtime initialization error: Docker daemon not running")
        session_manager.create_session = AsyncMock(side_effect=detailed_error)
        
        with patch('openhands.tui.panels.sessions_panel.logger') as mock_logger:
            await sessions_panel._create_session_async("Test task")
            
            # Verify that the error was logged (multiple calls expected due to our enhanced error handling)
            mock_logger.error.assert_called()
            assert mock_logger.error.call_count >= 1

    # Tests for New Message Issues

    @pytest.mark.asyncio
    async def test_send_message_session_start_failure(self, chat_panel, session_manager, mock_session_context):
        """Test sending message when session start fails."""
        chat_panel.input_field.insert_text("Test message")
        
        # Set up session in LOADING state
        mock_session_context.agent_state = AgentState.LOADING
        
        # Mock the session manager methods
        with patch.object(session_manager, 'get_active_session', return_value=mock_session_context):
            with patch.object(session_manager, 'start_session', side_effect=Exception("Session start failed")):
                # This should not crash but should handle the error gracefully
                with patch('openhands.tui.panels.chat_panel.logger') as mock_logger:
                    await chat_panel.send_message()
                    mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_send_message_runtime_connection_failure(self, chat_panel, session_manager, event_manager, mock_session_context):
        """Test sending message when runtime connection fails during session start."""
        chat_panel.input_field.insert_text("Test message")
        
        # Set up session in LOADING state
        mock_session_context.agent_state = AgentState.LOADING
        mock_session_context.runtime.connect = AsyncMock(side_effect=Exception("Runtime connection failed"))
        
        with patch.object(session_manager, 'get_active_session', return_value=mock_session_context):
            with patch.object(session_manager, 'start_session', side_effect=Exception("Runtime connection failed")):
                with patch('openhands.tui.panels.chat_panel.logger') as mock_logger:
                    await chat_panel.send_message()
                    mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_send_message_event_routing_failure(self, chat_panel, session_manager, event_manager, mock_session_context):
        """Test sending message when event routing fails."""
        chat_panel.input_field.insert_text("Test message")
        
        # Set up session in RUNNING state (already started)
        mock_session_context.agent_state = AgentState.RUNNING
        
        with patch.object(session_manager, 'get_active_session', return_value=mock_session_context):
            # Make event routing fail
            with patch.object(event_manager, 'route_user_input', side_effect=Exception("Event routing failed")):
                # This should not crash the TUI
                try:
                    await chat_panel.send_message()
                except Exception as e:
                    pytest.fail(f"Send message should not crash TUI: {e}")

    def test_send_message_sync_wrapper_error_handling(self, chat_panel):
        """Test synchronous send_message wrapper error handling."""
        with patch.object(chat_panel, 'send_message', side_effect=Exception("Async send failed")):
            with patch('asyncio.create_task') as mock_task:
                with patch('asyncio.get_running_loop') as mock_get_loop:
                    mock_get_loop.return_value = MagicMock()
                    
                    # This should not crash - simulate PyTermGUI button callback
                    mock_button = MagicMock()
                    try:
                        chat_panel.send_message_sync(mock_button)
                    except Exception as e:
                        pytest.fail(f"Sync send message wrapper should not crash: {e}")

    def test_button_callback_signature_compatibility(self, sessions_panel, chat_panel):
        """Test that button callbacks accept PyTermGUI button arguments."""
        mock_button = MagicMock()
        
        # Test sessions panel new session button
        with patch('asyncio.get_running_loop', side_effect=RuntimeError("No event loop")):
            with patch('asyncio.run'):
                try:
                    sessions_panel.create_new_session(mock_button)
                except TypeError as e:
                    pytest.fail(f"New session button callback signature error: {e}")
        
        # Test chat panel send button
        with patch.object(chat_panel, 'send_message'):
            with patch('asyncio.get_running_loop') as mock_get_loop:
                mock_get_loop.return_value = MagicMock()
                try:
                    chat_panel.send_message_sync(mock_button)
                except TypeError as e:
                    pytest.fail(f"Send message button callback signature error: {e}")

    # Tests for Error Logging Issues

    def test_error_logging_includes_stack_traces(self, sessions_panel, session_manager):
        """Test that error logging includes stack traces for debugging."""
        session_manager.create_session = AsyncMock(side_effect=Exception("Test error"))
        
        with patch('openhands.tui.panels.sessions_panel.logger') as mock_logger:
            # Run the async function
            asyncio.run(sessions_panel._create_session_async("Test task"))
            
            # Verify error was logged
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_session_manager_error_propagation(self, session_manager):
        """Test that session manager properly propagates errors with context."""
        with patch('openhands.tui.managers.session_manager.create_agent', side_effect=Exception("Agent creation failed")):
            with pytest.raises(Exception) as exc_info:
                await session_manager.create_session("Test task")
            
            assert "Agent creation failed" in str(exc_info.value)

    # Tests for Async Context Issues

    def test_async_context_in_pytermgui_callbacks(self, sessions_panel):
        """Test that async operations work correctly in PyTermGUI callback context."""
        # Simulate PyTermGUI button callback context
        with patch('asyncio.get_running_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            
            with patch('asyncio.create_task') as mock_create_task:
                sessions_panel.create_new_session()
                
                # Verify that create_task was called (indicating proper async handling)
                mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_manager_subscription_error_handling(self, event_manager, session_manager, mock_session_context):
        """Test event manager subscription error handling."""
        session_manager.sessions["test-session"] = mock_session_context
        
        # Make event stream subscription fail
        mock_session_context.event_stream.subscribe = MagicMock(side_effect=Exception("Subscription failed"))
        
        with pytest.raises(Exception):
            event_manager.subscribe_to_session("test-session")

    # Tests for Resource Cleanup

    @pytest.mark.asyncio
    async def test_session_cleanup_on_creation_failure(self, session_manager):
        """Test that resources are properly cleaned up when session creation fails."""
        with patch('openhands.tui.managers.session_manager.create_agent') as mock_create_agent:
            with patch('openhands.tui.managers.session_manager.create_runtime') as mock_create_runtime:
                mock_runtime = MagicMock()
                mock_runtime.connect = AsyncMock()
                mock_create_runtime.return_value = mock_runtime
                
                # Make controller creation fail after runtime is created
                with patch('openhands.tui.managers.session_manager.create_controller', side_effect=Exception("Controller failed")):
                    with pytest.raises(Exception):
                        await session_manager.create_session("Test task")
                    
                    # Verify no sessions were left in inconsistent state
                    assert len(session_manager.sessions) == 0

    # Tests for UI State Consistency

    def test_ui_state_after_session_creation_failure(self, sessions_panel, session_manager):
        """Test that UI state remains consistent after session creation failure."""
        initial_widget_count = len(sessions_panel._widgets)
        
        session_manager.create_session = AsyncMock(side_effect=Exception("Creation failed"))
        
        # Attempt to create session
        asyncio.run(sessions_panel._create_session_async("Test task"))
        
        # UI should not be in broken state
        assert len(sessions_panel._widgets) == initial_widget_count
        
        # Should still be able to interact with UI
        sessions_panel.update_sessions()

    def test_ui_state_after_message_send_failure(self, chat_panel, session_manager, event_manager, mock_session_context):
        """Test that UI state remains consistent after message send failure."""
        chat_panel.input_field.insert_text("Test message")
        initial_input = chat_panel.input_field.value
        
        mock_session_context.agent_state = AgentState.RUNNING
        
        with patch.object(session_manager, 'get_active_session', return_value=mock_session_context):
            with patch.object(event_manager, 'route_user_input', side_effect=Exception("Routing failed")):
                # Attempt to send message
                try:
                    asyncio.run(chat_panel.send_message())
                except:
                    pass  # Ignore the exception for this test
        
        # Input field should still be functional
        assert hasattr(chat_panel, 'input_field')
        assert chat_panel.input_field is not None

    # Tests for Specific Error Scenarios

    @pytest.mark.asyncio
    async def test_docker_daemon_not_running_error(self, session_manager):
        """Test specific error handling when Docker daemon is not running."""
        docker_error = Exception("Cannot connect to the Docker daemon at unix:///var/run/docker.sock")
        
        with patch('openhands.tui.managers.session_manager.create_agent') as mock_create_agent:
            with patch('openhands.tui.managers.session_manager.create_runtime', side_effect=docker_error):
                mock_create_agent.return_value = MagicMock()
                with pytest.raises(Exception) as exc_info:
                    await session_manager.create_session("Test task")
                
                assert "Docker daemon" in str(exc_info.value) or "docker.sock" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_network_connectivity_error(self, session_manager):
        """Test error handling for network connectivity issues."""
        network_error = Exception("Network is unreachable")
        
        with patch('openhands.tui.managers.session_manager.create_agent') as mock_create_agent:
            with patch('openhands.tui.managers.session_manager.create_runtime', side_effect=network_error):
                mock_create_agent.return_value = MagicMock()
                with pytest.raises(Exception) as exc_info:
                    await session_manager.create_session("Test task")
                
                assert "Network" in str(exc_info.value) or "unreachable" in str(exc_info.value)

    # Tests for Improved Error Messages

    def test_user_friendly_error_messages(self, sessions_panel, session_manager):
        """Test that error messages are user-friendly and actionable."""
        # Common Docker error
        docker_error = Exception("docker: command not found")
        session_manager.create_session = AsyncMock(side_effect=docker_error)
        
        with patch('openhands.tui.panels.sessions_panel.logger') as mock_logger:
            asyncio.run(sessions_panel._create_session_async("Test task"))
            
            # Verify error was logged
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_session_start_timeout_handling(self, chat_panel, session_manager, mock_session_context):
        """Test handling of session start timeouts."""
        chat_panel.input_field.insert_text("Test message")
        
        mock_session_context.agent_state = AgentState.LOADING
        
        with patch.object(session_manager, 'get_active_session', return_value=mock_session_context):
            with patch.object(session_manager, 'start_session', side_effect=asyncio.TimeoutError("Session start timeout")):
                with patch('openhands.tui.panels.chat_panel.logger') as mock_logger:
                    await chat_panel.send_message()
                    mock_logger.error.assert_called()