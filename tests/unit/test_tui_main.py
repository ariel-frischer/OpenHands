"""Tests for TUI main entry point."""

import argparse
import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands.core.config import AppConfig
from openhands.tui.main import (
    get_tui_parser,
    main,
    main_sync,
    parse_tui_arguments,
)


class TestGetTuiParser:
    """Test get_tui_parser function."""

    @patch('openhands.tui.main.get_parser')
    def test_get_tui_parser_extends_cli_parser(self, mock_get_parser):
        """Test that TUI parser extends CLI parser with TUI-specific options."""
        # Create mock CLI parser
        mock_cli_parser = MagicMock()
        mock_get_parser.return_value = mock_cli_parser
        
        # Call function
        parser = get_tui_parser()
        
        # Verify CLI parser was used as base
        mock_get_parser.assert_called_once()
        assert parser == mock_cli_parser
        
        # Verify description was updated
        assert parser.description == 'Run OpenHands with Terminal User Interface (TUI)'
        
        # Verify TUI-specific arguments were added
        expected_calls = [
            ('--tui-theme',),
            ('--tui-log-level',),
            ('--tui-refresh-rate',),
            ('--tui-max-history',),
        ]
        
        # Check that add_argument was called for TUI-specific options
        add_argument_calls = [call[0][0] for call in parser.add_argument.call_args_list]
        for expected_arg in [arg[0] for arg in expected_calls]:
            assert expected_arg in add_argument_calls

    def test_tui_parser_argument_defaults(self):
        """Test TUI parser argument defaults and choices."""
        with patch('openhands.tui.main.get_parser') as mock_get_parser:
            mock_parser = MagicMock()
            mock_get_parser.return_value = mock_parser
            
            get_tui_parser()
            
            # Find the calls for TUI-specific arguments
            calls = mock_parser.add_argument.call_args_list
            
            # Check theme argument
            theme_call = next(call for call in calls if call[0][0] == '--tui-theme')
            assert theme_call[1]['default'] == 'default'
            assert theme_call[1]['choices'] == ['default', 'dark', 'light']
            
            # Check log level argument
            log_level_call = next(call for call in calls if call[0][0] == '--tui-log-level')
            assert log_level_call[1]['default'] == 'INFO'
            assert log_level_call[1]['choices'] == ['DEBUG', 'INFO', 'WARNING', 'ERROR']
            
            # Check refresh rate argument
            refresh_call = next(call for call in calls if call[0][0] == '--tui-refresh-rate')
            assert refresh_call[1]['default'] == 0.1
            assert refresh_call[1]['type'] == float
            
            # Check max history argument
            history_call = next(call for call in calls if call[0][0] == '--tui-max-history')
            assert history_call[1]['default'] == 1000
            assert history_call[1]['type'] == int


class TestParseTuiArguments:
    """Test parse_tui_arguments function."""

    @patch('openhands.tui.main.get_tui_parser')
    def test_parse_tui_arguments_normal_flow(self, mock_get_tui_parser):
        """Test normal argument parsing flow."""
        # Create mock parser and args
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.version = False
        mock_parser.parse_args.return_value = mock_args
        mock_get_tui_parser.return_value = mock_parser
        
        # Call function
        result = parse_tui_arguments()
        
        # Verify parser was created and used
        mock_get_tui_parser.assert_called_once()
        mock_parser.parse_args.assert_called_once()
        assert result == mock_args

    @patch('openhands.tui.main.get_tui_parser')
    @patch('sys.exit')
    def test_parse_tui_arguments_version_flag(self, mock_exit, mock_get_tui_parser):
        """Test version flag handling."""
        # Create mock parser and args with version=True
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.version = True
        mock_parser.parse_args.return_value = mock_args
        mock_get_tui_parser.return_value = mock_parser
        
        # Call function
        with patch('builtins.print') as mock_print:
            parse_tui_arguments()
        
        # Verify version was printed and exit was called
        mock_print.assert_called_once()
        assert 'OpenHands TUI version:' in mock_print.call_args[0][0]
        mock_exit.assert_called_once_with(0)


class TestMain:
    """Test main function."""

    @pytest.mark.asyncio
    @patch('openhands.tui.main.parse_tui_arguments')
    @patch('openhands.tui.main.extract_cli_config_setup')
    @patch('openhands.tui.main.reuse_cli_security_check')
    @patch('openhands.tui.main.FileSettingsStore.get_instance')
    @patch('openhands.tui.main.OpenHandsTUIApp')
    async def test_main_success_flow(
        self, mock_app_class, mock_settings_store_get_instance, mock_security_check,
        mock_config_setup, mock_parse_args
    ):
        """Test successful main function execution."""
        # Setup mocks
        mock_args = MagicMock()
        mock_args.name = 'test-session'
        mock_args.tui_theme = 'dark'
        mock_args.tui_log_level = 'DEBUG'
        mock_args.tui_refresh_rate = 0.2
        mock_args.tui_max_history = 500
        mock_parse_args.return_value = mock_args
        
        mock_config = MagicMock()
        mock_config.workspace_base = '/test/workspace'
        mock_config_setup.return_value = mock_config
        
        mock_security_check.return_value = True
        
        mock_settings_store = MagicMock()
        mock_settings_store_get_instance.return_value = mock_settings_store
        
        mock_app = MagicMock()
        mock_app.run = AsyncMock()
        mock_app_class.return_value = mock_app
        
        # Call function
        await main()
        
        # Verify function calls
        mock_parse_args.assert_called_once()
        mock_config_setup.assert_called_once_with(mock_args)
        mock_security_check.assert_called_once_with(mock_config, '/test/workspace')
        mock_settings_store_get_instance.assert_called_once_with(mock_config, None)
        mock_app_class.assert_called_once_with(mock_config, mock_settings_store, mock_args)
        mock_app.run.assert_called_once()

    @pytest.mark.asyncio
    @patch('openhands.tui.main.parse_tui_arguments')
    @patch('openhands.tui.main.extract_cli_config_setup')
    @patch('openhands.tui.main.reuse_cli_security_check')
    @patch('sys.exit')
    async def test_main_security_check_failure(
        self, mock_exit, mock_security_check, mock_config_setup, mock_parse_args
    ):
        """Test main function with security check failure."""
        # Setup mocks
        mock_args = MagicMock()
        mock_parse_args.return_value = mock_args
        
        mock_config = MagicMock()
        mock_config.workspace_base = '/test/workspace'
        mock_config_setup.return_value = mock_config
        
        mock_security_check.return_value = False
        
        # Call function
        await main()
        
        # Verify exit was called
        mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    @patch('openhands.tui.main.parse_tui_arguments')
    @patch('sys.exit')
    async def test_main_keyboard_interrupt(self, mock_exit, mock_parse_args):
        """Test main function with keyboard interrupt."""
        # Setup mock to raise KeyboardInterrupt
        mock_parse_args.side_effect = KeyboardInterrupt()
        
        # Call function
        await main()
        
        # Verify exit was called with 0
        mock_exit.assert_called_once_with(0)

    @pytest.mark.asyncio
    @patch('openhands.tui.main.parse_tui_arguments')
    @patch('sys.exit')
    async def test_main_exception_handling(self, mock_exit, mock_parse_args):
        """Test main function with general exception."""
        # Setup mock to raise exception
        mock_parse_args.side_effect = Exception("Test error")
        
        # Call function
        await main()
        
        # Verify exit was called with 1
        mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    @patch('openhands.tui.main.parse_tui_arguments')
    @patch('openhands.tui.main.extract_cli_config_setup')
    @patch('openhands.tui.main.reuse_cli_security_check')
    @patch('openhands.tui.main.FileSettingsStore.get_instance')
    @patch('openhands.tui.main.OpenHandsTUIApp')
    async def test_main_config_without_workspace_base(
        self, mock_app_class, mock_settings_store_get_instance, mock_security_check,
        mock_config_setup, mock_parse_args
    ):
        """Test main function with config that has no workspace_base."""
        # Setup mocks
        mock_args = MagicMock()
        mock_parse_args.return_value = mock_args
        
        mock_config = MagicMock()
        mock_config.workspace_base = None
        mock_config_setup.return_value = mock_config
        
        mock_security_check.return_value = True
        
        mock_settings_store = MagicMock()
        mock_settings_store_get_instance.return_value = mock_settings_store
        
        mock_app = MagicMock()
        mock_app.run = AsyncMock()
        mock_app_class.return_value = mock_app
        
        # Call function
        with patch('os.getcwd', return_value='/current/dir'):
            await main()
        
        # Verify security check was called with current directory
        mock_security_check.assert_called_once_with(mock_config, '/current/dir')


class TestMainSync:
    """Test main_sync function."""

    @patch('openhands.tui.main.FileSettingsStore.get_instance')
    @patch('openhands.tui.main.OpenHandsTUIApp')
    @patch('asyncio.run')
    def test_main_sync_with_config(self, mock_asyncio_run, mock_app_class, mock_settings_store_get_instance):
        """Test main_sync with provided config."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.workspace_base = '/test/workspace'
        
        mock_settings_store = MagicMock()
        mock_settings_store_get_instance.return_value = mock_settings_store
        
        mock_app = MagicMock()
        mock_app_class.return_value = mock_app
        
        # Call function
        main_sync(mock_config)
        
        # Verify app was created and run
        # Note: asyncio.run is called twice - once for settings store, once for app.run()
        assert mock_asyncio_run.call_count == 2
        mock_app_class.assert_called_once()
        
        # Verify args were created properly
        args = mock_app_class.call_args[0][2]  # Third argument is args
        assert args.name == ''
        assert args.directory == '/test/workspace'

    @patch('asyncio.run')
    def test_main_sync_without_config(self, mock_asyncio_run):
        """Test main_sync without provided config."""
        # Call function
        main_sync(None)
        
        # Verify asyncio.run was called with main()
        mock_asyncio_run.assert_called_once()

    @patch('openhands.tui.main.FileSettingsStore.get_instance')
    @patch('openhands.tui.main.OpenHandsTUIApp')
    @patch('sys.exit')
    def test_main_sync_keyboard_interrupt(self, mock_exit, mock_app_class, mock_settings_store_get_instance):
        """Test main_sync with keyboard interrupt."""
        # Setup mocks
        mock_config = MagicMock()
        mock_app_class.side_effect = KeyboardInterrupt()
        
        # Call function
        main_sync(mock_config)
        
        # Verify exit was called with 0
        mock_exit.assert_called_once_with(0)

    @patch('openhands.tui.main.FileSettingsStore.get_instance')
    @patch('openhands.tui.main.OpenHandsTUIApp')
    @patch('sys.exit')
    def test_main_sync_exception_handling(self, mock_exit, mock_app_class, mock_settings_store_get_instance):
        """Test main_sync with general exception."""
        # Setup mocks
        mock_config = MagicMock()
        mock_app_class.side_effect = Exception("Test error")
        
        # Call function
        main_sync(mock_config)
        
        # Verify exit was called with 1
        mock_exit.assert_called_once_with(1)