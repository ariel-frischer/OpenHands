"""Tests for TUI CLI integration utilities."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openhands.core.config import AppConfig
from openhands.events.event import Event
from openhands.storage.settings.file_settings_store import FileSettingsStore
from openhands.tui.utils.cli_integration import (
    SessionContext,
    adapt_cli_event_handler,
    cleanup_session_context,
    create_session_context,
    create_stream_callback,
    display_cli_settings,
    extract_cli_config_setup,
    handle_cli_command,
    reuse_cli_security_check,
)


class TestSessionContext:
    """Test SessionContext class."""

    def test_session_context_initialization(self):
        """Test SessionContext initialization with all required components."""
        # Create mock objects
        mock_agent = MagicMock()
        mock_runtime = MagicMock()
        mock_controller = MagicMock()
        mock_event_stream = MagicMock()
        mock_usage_metrics = MagicMock()
        mock_config = MagicMock()
        
        # Create session context
        context = SessionContext(
            sid="test-sid",
            agent=mock_agent,
            runtime=mock_runtime,
            controller=mock_controller,
            event_stream=mock_event_stream,
            usage_metrics=mock_usage_metrics,
            config=mock_config,
        )
        
        # Verify all attributes are set correctly
        assert context.sid == "test-sid"
        assert context.agent == mock_agent
        assert context.runtime == mock_runtime
        assert context.controller == mock_controller
        assert context.event_stream == mock_event_stream
        assert context.usage_metrics == mock_usage_metrics
        assert context.config == mock_config


class TestCreateSessionContext:
    """Test create_session_context function."""

    @pytest.mark.asyncio
    @patch('openhands.tui.utils.cli_integration.generate_sid')
    @patch('openhands.tui.utils.cli_integration.create_agent')
    @patch('openhands.tui.utils.cli_integration.create_runtime')
    @patch('openhands.tui.utils.cli_integration.create_controller')
    @patch('openhands.tui.utils.cli_integration.UsageMetrics')
    async def test_create_session_context_success(
        self, mock_usage_metrics, mock_create_controller, mock_create_runtime,
        mock_create_agent, mock_generate_sid
    ):
        """Test successful session context creation."""
        # Setup mocks
        mock_generate_sid.return_value = "test-sid"
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent
        
        mock_runtime = MagicMock()
        mock_event_stream = MagicMock()
        mock_runtime.event_stream = mock_event_stream
        mock_create_runtime.return_value = mock_runtime
        
        mock_controller = MagicMock()
        mock_initial_state = MagicMock()
        mock_create_controller.return_value = (mock_controller, mock_initial_state)
        
        mock_metrics = MagicMock()
        mock_usage_metrics.return_value = mock_metrics
        
        mock_config = MagicMock()
        mock_settings_store = MagicMock()
        
        # Call function
        context = await create_session_context(
            config=mock_config,
            settings_store=mock_settings_store,
            current_dir="/test/dir",
            session_name="test-session"
        )
        
        # Verify function calls
        mock_generate_sid.assert_called_once_with(mock_config, "test-session")
        mock_create_agent.assert_called_once_with(mock_config)
        mock_create_runtime.assert_called_once_with(
            mock_config,
            sid="test-sid",
            headless_mode=True,
            agent=mock_agent,
        )
        mock_create_controller.assert_called_once_with(mock_agent, mock_runtime, mock_config)
        
        # Verify context
        assert isinstance(context, SessionContext)
        assert context.sid == "test-sid"
        assert context.agent == mock_agent
        assert context.runtime == mock_runtime
        assert context.controller == mock_controller
        assert context.event_stream == mock_event_stream
        assert context.usage_metrics == mock_metrics
        assert context.config == mock_config

    @pytest.mark.asyncio
    @patch('openhands.tui.utils.cli_integration.generate_sid')
    async def test_create_session_context_failure(self, mock_generate_sid):
        """Test session context creation failure handling."""
        # Setup mock to raise exception
        mock_generate_sid.side_effect = Exception("Test error")
        
        mock_config = MagicMock()
        mock_settings_store = MagicMock()
        
        # Verify exception is raised
        with pytest.raises(Exception, match="Test error"):
            await create_session_context(
                config=mock_config,
                settings_store=mock_settings_store,
                current_dir="/test/dir"
            )


class TestAdaptCliEventHandler:
    """Test adapt_cli_event_handler function."""

    def test_adapt_cli_event_handler_success(self):
        """Test successful event handler adaptation."""
        # Create mock session context and callback
        mock_context = MagicMock()
        mock_callback = MagicMock()
        
        # Create event handler
        handler = adapt_cli_event_handler(mock_context, mock_callback)
        
        # Create mock event and call handler
        mock_event = MagicMock()
        mock_event.event_type = "test_event"
        
        handler(mock_event)
        
        # Verify callback was called
        mock_callback.assert_called_once_with(mock_event)

    def test_adapt_cli_event_handler_exception(self):
        """Test event handler with callback exception."""
        # Create mock session context and callback that raises exception
        mock_context = MagicMock()
        mock_callback = MagicMock(side_effect=Exception("Callback error"))
        
        # Create event handler
        handler = adapt_cli_event_handler(mock_context, mock_callback)
        
        # Create mock event and call handler (should not raise)
        mock_event = MagicMock()
        handler(mock_event)
        
        # Verify callback was called despite exception
        mock_callback.assert_called_once_with(mock_event)


class TestExtractCliConfigSetup:
    """Test extract_cli_config_setup function."""

    @patch('openhands.tui.utils.cli_integration.setup_config_from_args')
    def test_extract_cli_config_setup_success(self, mock_setup_config):
        """Test successful config setup extraction."""
        # Setup mock
        mock_config = MagicMock()
        mock_setup_config.return_value = mock_config
        mock_args = MagicMock()
        
        # Call function
        result = extract_cli_config_setup(mock_args)
        
        # Verify function call and result
        mock_setup_config.assert_called_once_with(mock_args)
        assert result == mock_config

    @patch('openhands.tui.utils.cli_integration.setup_config_from_args')
    def test_extract_cli_config_setup_failure(self, mock_setup_config):
        """Test config setup extraction failure handling."""
        # Setup mock to raise exception
        mock_setup_config.side_effect = Exception("Config error")
        mock_args = MagicMock()
        
        # Verify exception is raised
        with pytest.raises(Exception, match="Config error"):
            extract_cli_config_setup(mock_args)


class TestReuseCliSecurityCheck:
    """Test reuse_cli_security_check function."""

    @patch('openhands.tui.utils.cli_integration.check_folder_security_agreement')
    def test_reuse_cli_security_check_success(self, mock_security_check):
        """Test successful security check reuse."""
        # Setup mock
        mock_security_check.return_value = True
        mock_config = MagicMock()
        
        # Call function
        result = reuse_cli_security_check(mock_config, "/test/dir")
        
        # Verify function call and result
        mock_security_check.assert_called_once_with(mock_config, "/test/dir")
        assert result is True

    @patch('openhands.tui.utils.cli_integration.check_folder_security_agreement')
    def test_reuse_cli_security_check_failure(self, mock_security_check):
        """Test security check failure handling."""
        # Setup mock to raise exception
        mock_security_check.side_effect = Exception("Security error")
        mock_config = MagicMock()
        
        # Call function (should not raise, returns False)
        result = reuse_cli_security_check(mock_config, "/test/dir")
        
        # Verify result is False on exception
        assert result is False


class TestHandleCliCommand:
    """Test handle_cli_command function."""

    @pytest.mark.asyncio
    @patch('openhands.tui.utils.cli_integration.handle_commands')
    async def test_handle_cli_command_success(self, mock_handle_commands):
        """Test successful CLI command handling."""
        # Setup mock
        mock_handle_commands.return_value = (True, False, True)
        
        # Create mock session context
        mock_context = MagicMock()
        mock_context.event_stream = MagicMock()
        mock_context.usage_metrics = MagicMock()
        mock_context.sid = "test-sid"
        mock_context.config = MagicMock()
        
        mock_settings_store = MagicMock()
        
        # Call function
        result = await handle_cli_command(
            command="test command",
            session_context=mock_context,
            current_dir="/test/dir",
            settings_store=mock_settings_store
        )
        
        # Verify function call and result
        mock_handle_commands.assert_called_once_with(
            command="test command",
            event_stream=mock_context.event_stream,
            usage_metrics=mock_context.usage_metrics,
            sid=mock_context.sid,
            config=mock_context.config,
            current_dir="/test/dir",
            settings_store=mock_settings_store,
        )
        assert result == (True, False, True)

    @pytest.mark.asyncio
    @patch('openhands.tui.utils.cli_integration.handle_commands')
    async def test_handle_cli_command_failure(self, mock_handle_commands):
        """Test CLI command handling failure."""
        # Setup mock to raise exception
        mock_handle_commands.side_effect = Exception("Command error")
        
        # Create mock session context
        mock_context = MagicMock()
        mock_settings_store = MagicMock()
        
        # Call function (should not raise, returns safe defaults)
        result = await handle_cli_command(
            command="test command",
            session_context=mock_context,
            current_dir="/test/dir",
            settings_store=mock_settings_store
        )
        
        # Verify safe defaults are returned
        assert result == (False, False, False)


class TestDisplayCliSettings:
    """Test display_cli_settings function."""

    @patch('openhands.tui.utils.cli_integration.display_settings')
    def test_display_cli_settings_success(self, mock_display_settings):
        """Test successful settings display."""
        mock_config = MagicMock()
        
        # Call function (should not raise)
        display_cli_settings(mock_config)
        
        # Verify function call
        mock_display_settings.assert_called_once_with(mock_config)

    @patch('openhands.tui.utils.cli_integration.display_settings')
    def test_display_cli_settings_failure(self, mock_display_settings):
        """Test settings display failure handling."""
        # Setup mock to raise exception
        mock_display_settings.side_effect = Exception("Display error")
        mock_config = MagicMock()
        
        # Call function (should not raise)
        display_cli_settings(mock_config)
        
        # Verify function was called despite exception
        mock_display_settings.assert_called_once_with(mock_config)


class TestCleanupSessionContext:
    """Test cleanup_session_context function."""

    @pytest.mark.asyncio
    async def test_cleanup_session_context_success(self):
        """Test successful session context cleanup."""
        # Create mock session context
        mock_context = MagicMock()
        mock_context.controller.get_state.return_value = MagicMock()
        mock_context.controller.close = AsyncMock()
        mock_context.event_stream.sid = "test-sid"
        mock_context.event_stream.file_store = MagicMock()
        mock_context.event_stream.user_id = "test-user"
        
        # Call function (should not raise)
        await cleanup_session_context(mock_context)
        
        # Verify cleanup calls
        mock_context.controller.get_state.assert_called_once()
        mock_context.agent.reset.assert_called_once()
        mock_context.runtime.close.assert_called_once()
        mock_context.controller.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_session_context_failure(self):
        """Test session context cleanup failure handling."""
        # Create mock session context that raises exception
        mock_context = MagicMock()
        mock_context.controller.get_state.side_effect = Exception("Cleanup error")
        
        # Call function (should not raise)
        await cleanup_session_context(mock_context)
        
        # Verify function was called despite exception
        mock_context.controller.get_state.assert_called_once()


class TestCreateStreamCallback:
    """Test create_stream_callback function."""

    def test_create_stream_callback_success(self):
        """Test successful stream callback creation."""
        # Create mock TUI output handler
        mock_handler = MagicMock()
        
        # Create callback
        callback = create_stream_callback(mock_handler)
        
        # Call callback with test output
        test_output = "test output"
        callback(test_output)
        
        # Verify handler was called
        mock_handler.assert_called_once_with(test_output)

    def test_create_stream_callback_exception(self):
        """Test stream callback with handler exception."""
        # Create mock handler that raises exception
        mock_handler = MagicMock(side_effect=Exception("Handler error"))
        
        # Create callback
        callback = create_stream_callback(mock_handler)
        
        # Call callback (should not raise)
        callback("test output")
        
        # Verify handler was called despite exception
        mock_handler.assert_called_once_with("test output")