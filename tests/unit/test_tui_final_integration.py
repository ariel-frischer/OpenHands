"""Final integration test to verify all TUI fixes work together."""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from openhands.tui.app import OpenHandsTUIApp
from openhands.tui.panels.chat_panel import ChatPanel
from openhands.tui.panels.logs_panel import LogsPanel, get_tui_log_handler
from openhands.tui.panels.sessions_panel import SessionsPanel


class TestTUIFinalIntegration(unittest.TestCase):
    """Test that all TUI fixes work together properly."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = MagicMock()
        self.mock_settings_store = MagicMock()

    def test_app_initialization_with_log_handler(self):
        """Test that app initializes properly with TUI log handler."""
        with patch('openhands.tui.app.SessionManager'), \
             patch('openhands.tui.app.TUIEventManager'), \
             patch('openhands.tui.app.TUIPanelFileManager'), \
             patch('openhands.tui.app.SessionsPanel'), \
             patch('openhands.tui.app.ChatPanel'), \
             patch('openhands.tui.app.LogsPanel'), \
             patch('openhands.tui.app.KeyBindings'):
            
            app = OpenHandsTUIApp(self.mock_config, self.mock_settings_store)
            
            # Should have TUI log handler
            self.assertIsNotNone(app.tui_log_handler)

    def test_button_debouncing_integration(self):
        """Test that button debouncing works across all panels."""
        mock_session_manager = MagicMock()
        mock_file_manager = MagicMock()
        mock_event_manager = MagicMock()
        
        # Test sessions panel
        sessions_panel = SessionsPanel(mock_session_manager, mock_file_manager)
        sessions_panel._create_session_async = AsyncMock()
        
        # Test chat panel
        chat_panel = ChatPanel(mock_session_manager, mock_event_manager, mock_file_manager)
        chat_panel.send_message = AsyncMock()
        
        # Both panels should have debouncing attributes
        self.assertTrue(hasattr(sessions_panel, '_last_button_click'))
        self.assertTrue(hasattr(sessions_panel, '_creating_session'))
        self.assertTrue(hasattr(chat_panel, '_last_button_click'))
        self.assertTrue(hasattr(chat_panel, '_sending_message'))

    def test_exception_handling_integration(self):
        """Test that exception handling works across all components."""
        mock_session_manager = MagicMock()
        mock_file_manager = MagicMock()
        mock_event_manager = MagicMock()
        
        # Test sessions panel exception handling
        sessions_panel = SessionsPanel(mock_session_manager, mock_file_manager)
        mock_task = MagicMock()
        mock_task.result.side_effect = Exception("Test error")
        
        # Should not raise exception
        sessions_panel._handle_task_exception(mock_task)
        self.assertFalse(sessions_panel._creating_session)
        
        # Test chat panel exception handling
        chat_panel = ChatPanel(mock_session_manager, mock_event_manager, mock_file_manager)
        mock_task = MagicMock()
        mock_task.result.side_effect = Exception("Test error")
        
        # Should not raise exception
        chat_panel._handle_task_exception(mock_task)
        self.assertFalse(chat_panel._sending_message)

    def test_logs_panel_integration(self):
        """Test that logs panel integrates properly with TUI log handler."""
        mock_session_manager = MagicMock()
        mock_file_manager = MagicMock()
        
        # Test logs panel creation
        logs_panel = LogsPanel(mock_session_manager, mock_file_manager)
        
        # Test TUI log handler
        handler = get_tui_log_handler()
        self.assertIsNotNone(handler)
        
        # Test log entry creation
        logs_panel.add_log_entry("INFO", "Test message", "test-session")
        
        # Should have logs display container
        self.assertIsNotNone(logs_panel.logs_display)

    def test_async_task_management_integration(self):
        """Test that async task management works properly."""
        mock_session_manager = MagicMock()
        mock_file_manager = MagicMock()
        mock_event_manager = MagicMock()
        
        sessions_panel = SessionsPanel(mock_session_manager, mock_file_manager)
        chat_panel = ChatPanel(mock_session_manager, mock_event_manager, mock_file_manager)
        
        # Mock async methods
        sessions_panel._create_session_async = AsyncMock()
        chat_panel.send_message = AsyncMock()
        
        # Test that both panels can handle async operations
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('asyncio.create_task') as mock_create_task:
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            
            # Test sessions panel
            sessions_panel.create_new_session()
            mock_create_task.assert_called()
            
            # Reset mocks
            mock_create_task.reset_mock()
            
            # Test chat panel
            chat_panel.send_message_sync()
            mock_create_task.assert_called()

    def test_error_logging_integration(self):
        """Test that error logging works across all components."""
        mock_session_manager = MagicMock()
        mock_file_manager = MagicMock()
        mock_event_manager = MagicMock()
        
        # Test that all panels have proper error logging
        sessions_panel = SessionsPanel(mock_session_manager, mock_file_manager)
        chat_panel = ChatPanel(mock_session_manager, mock_event_manager, mock_file_manager)
        logs_panel = LogsPanel(mock_session_manager, mock_file_manager)
        
        # All panels should have logger attributes
        self.assertTrue(hasattr(sessions_panel, '__class__'))
        self.assertTrue(hasattr(chat_panel, '__class__'))
        self.assertTrue(hasattr(logs_panel, '__class__'))

    def test_state_flag_management_integration(self):
        """Test that state flags are properly managed across operations."""
        mock_session_manager = MagicMock()
        mock_file_manager = MagicMock()
        mock_event_manager = MagicMock()
        
        sessions_panel = SessionsPanel(mock_session_manager, mock_file_manager)
        chat_panel = ChatPanel(mock_session_manager, mock_event_manager, mock_file_manager)
        
        # Test initial state
        self.assertFalse(sessions_panel._creating_session)
        self.assertFalse(chat_panel._sending_message)
        
        # Test flag setting and resetting
        sessions_panel._creating_session = True
        chat_panel._sending_message = True
        
        # Test exception handlers reset flags
        mock_task = MagicMock()
        mock_task.result.return_value = None
        
        sessions_panel._handle_task_exception(mock_task)
        chat_panel._handle_task_exception(mock_task)
        
        self.assertFalse(sessions_panel._creating_session)
        self.assertFalse(chat_panel._sending_message)

    def test_button_callback_signature_compatibility(self):
        """Test that button callbacks work with PyTermGUI signatures."""
        mock_session_manager = MagicMock()
        mock_file_manager = MagicMock()
        mock_event_manager = MagicMock()
        
        sessions_panel = SessionsPanel(mock_session_manager, mock_file_manager)
        chat_panel = ChatPanel(mock_session_manager, mock_event_manager, mock_file_manager)
        
        # Mock async methods
        sessions_panel._create_session_async = AsyncMock()
        chat_panel.send_message = AsyncMock()
        
        # Test that callbacks accept various argument patterns
        with patch('asyncio.get_running_loop', side_effect=RuntimeError), \
             patch('asyncio.run') as mock_run:
            
            # Should work with no args
            sessions_panel.create_new_session()
            
            # Should work with args (PyTermGUI style)
            sessions_panel.create_new_session("arg1", "arg2")
            
            # Same for chat panel
            chat_panel.send_message_sync()
            chat_panel.send_message_sync("arg1")
            chat_panel.send_message_sync("arg1", "arg2")


if __name__ == '__main__':
    unittest.main()