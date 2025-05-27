"""Test TUI button debouncing functionality."""

import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from openhands.tui.panels.chat_panel import ChatPanel
from openhands.tui.panels.sessions_panel import SessionsPanel


class TestTUIButtonDebouncing(unittest.TestCase):
    """Test button debouncing functionality in TUI panels."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session_manager = MagicMock()
        self.mock_file_manager = MagicMock()
        self.mock_event_manager = MagicMock()

    def test_sessions_panel_button_debouncing(self):
        """Test that sessions panel new session button has debouncing."""
        panel = SessionsPanel(self.mock_session_manager, self.mock_file_manager)
        
        # Mock the async session creation
        panel._create_session_async = AsyncMock()
        
        # First click should work
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('asyncio.create_task') as mock_create_task:
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            
            panel.create_new_session()
            
            # Should have created a task
            mock_create_task.assert_called_once()
            mock_task.add_done_callback.assert_called_once()
        
        # Immediate second click should be ignored due to debouncing
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('asyncio.create_task') as mock_create_task:
            
            mock_create_task.reset_mock()
            panel.create_new_session()
            
            # Should not have created another task
            mock_create_task.assert_not_called()
    
    def test_sessions_panel_debouncing_after_delay(self):
        """Test that sessions panel allows clicks after debounce period."""
        panel = SessionsPanel(self.mock_session_manager, self.mock_file_manager)
        
        # Mock the async session creation
        panel._create_session_async = AsyncMock()
        
        # First click
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('asyncio.create_task') as mock_create_task:
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            
            panel.create_new_session()
            mock_create_task.assert_called_once()
        
        # Simulate time passing (more than 1 second debounce)
        panel._last_button_click = time.time() - 2.0
        # Reset the creating flag
        panel._creating_session = False
        
        # Second click after delay should work
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('asyncio.create_task') as mock_create_task:
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            
            panel.create_new_session()
            mock_create_task.assert_called_once()

    def test_chat_panel_button_debouncing(self):
        """Test that chat panel send message button has debouncing."""
        panel = ChatPanel(self.mock_session_manager, self.mock_event_manager, self.mock_file_manager)
        
        # Mock the async message sending
        panel.send_message = AsyncMock()
        
        # First click should work
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('asyncio.create_task') as mock_create_task:
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            
            panel.send_message_sync()
            
            # Should have created a task
            mock_create_task.assert_called_once()
            mock_task.add_done_callback.assert_called_once()
        
        # Immediate second click should be ignored due to debouncing
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('asyncio.create_task') as mock_create_task:
            
            mock_create_task.reset_mock()
            panel.send_message_sync()
            
            # Should not have created another task
            mock_create_task.assert_not_called()

    def test_chat_panel_debouncing_after_delay(self):
        """Test that chat panel allows clicks after debounce period."""
        panel = ChatPanel(self.mock_session_manager, self.mock_event_manager, self.mock_file_manager)
        
        # Mock the async message sending
        panel.send_message = AsyncMock()
        
        # First click
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('asyncio.create_task') as mock_create_task:
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            
            panel.send_message_sync()
            mock_create_task.assert_called_once()
        
        # Simulate time passing (more than 0.5 second debounce)
        panel._last_button_click = time.time() - 1.0
        # Reset the sending flag
        panel._sending_message = False
        
        # Second click after delay should work
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('asyncio.create_task') as mock_create_task:
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            
            panel.send_message_sync()
            mock_create_task.assert_called_once()

    def test_sessions_panel_multiple_session_creation_prevention(self):
        """Test that multiple simultaneous session creation is prevented."""
        panel = SessionsPanel(self.mock_session_manager, self.mock_file_manager)
        
        # Mock the async session creation
        panel._create_session_async = AsyncMock()
        
        # Set the creating session flag to simulate ongoing creation
        panel._creating_session = True
        
        # Click should be ignored
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('asyncio.create_task') as mock_create_task:
            
            panel.create_new_session()
            
            # Should not have created a task
            mock_create_task.assert_not_called()

    def test_chat_panel_multiple_message_sending_prevention(self):
        """Test that multiple simultaneous message sending is prevented."""
        panel = ChatPanel(self.mock_session_manager, self.mock_event_manager, self.mock_file_manager)
        
        # Mock the async message sending
        panel.send_message = AsyncMock()
        
        # Set the sending message flag to simulate ongoing sending
        panel._sending_message = True
        
        # Click should be ignored
        with patch('asyncio.get_running_loop') as mock_get_loop, \
             patch('asyncio.create_task') as mock_create_task:
            
            panel.send_message_sync()
            
            # Should not have created a task
            mock_create_task.assert_not_called()

    def test_sessions_panel_flag_reset_on_completion(self):
        """Test that creating session flag is reset when task completes."""
        panel = SessionsPanel(self.mock_session_manager, self.mock_file_manager)
        
        # Create a mock task that succeeds
        mock_task = MagicMock()
        mock_task.result.return_value = None  # No exception
        
        # Set the flag to simulate ongoing creation
        panel._creating_session = True
        
        # Call the exception handler
        panel._handle_task_exception(mock_task)
        
        # Flag should be reset
        self.assertFalse(panel._creating_session)

    def test_chat_panel_flag_reset_on_completion(self):
        """Test that sending message flag is reset when task completes."""
        panel = ChatPanel(self.mock_session_manager, self.mock_event_manager, self.mock_file_manager)
        
        # Create a mock task that succeeds
        mock_task = MagicMock()
        mock_task.result.return_value = None  # No exception
        
        # Set the flag to simulate ongoing sending
        panel._sending_message = True
        
        # Call the exception handler
        panel._handle_task_exception(mock_task)
        
        # Flag should be reset
        self.assertFalse(panel._sending_message)

    def test_sessions_panel_flag_reset_on_exception(self):
        """Test that creating session flag is reset when task fails."""
        panel = SessionsPanel(self.mock_session_manager, self.mock_file_manager)
        
        # Create a mock task that fails
        mock_task = MagicMock()
        mock_task.result.side_effect = Exception("Task failed")
        
        # Set the flag to simulate ongoing creation
        panel._creating_session = True
        
        # Call the exception handler
        panel._handle_task_exception(mock_task)
        
        # Flag should be reset
        self.assertFalse(panel._creating_session)

    def test_chat_panel_flag_reset_on_exception(self):
        """Test that sending message flag is reset when task fails."""
        panel = ChatPanel(self.mock_session_manager, self.mock_event_manager, self.mock_file_manager)
        
        # Create a mock task that fails
        mock_task = MagicMock()
        mock_task.result.side_effect = Exception("Task failed")
        
        # Set the flag to simulate ongoing sending
        panel._sending_message = True
        
        # Call the exception handler
        panel._handle_task_exception(mock_task)
        
        # Flag should be reset
        self.assertFalse(panel._sending_message)


if __name__ == '__main__':
    unittest.main()