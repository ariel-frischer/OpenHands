#!/usr/bin/env python3
"""Test script to verify TUI fixes work correctly."""

import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from openhands.tui.panels.chat_panel import ChatPanel
from openhands.core.schema import AgentState


async def test_automatic_session_creation():
    """Test that automatic session creation works when no active session exists."""
    print("Testing automatic session creation...")
    
    # Create mock managers
    mock_session_manager = MagicMock()
    mock_event_manager = MagicMock()
    mock_file_manager = MagicMock()
    
    # Set up mocks for no active session scenario
    mock_session_manager.get_active_session.return_value = None
    mock_session_manager.create_session = AsyncMock(return_value="test-session-id")
    mock_session_manager.start_session = AsyncMock()
    mock_event_manager.route_user_input.return_value = True
    
    # Create chat panel
    with patch('openhands.tui.panels.chat_panel.ptg.terminal') as mock_terminal:
        mock_terminal.height = 50
        mock_terminal.width = 100
        chat_panel = ChatPanel(mock_session_manager, mock_event_manager, mock_file_manager)
    
    # Test the _create_session_and_send_message method directly
    await chat_panel._create_session_and_send_message("Test task", "Hello, create a new session!")
    
    # Verify that session creation was called
    mock_session_manager.create_session.assert_called_once_with("Test task")
    mock_session_manager.start_session.assert_called_once_with("test-session-id")
    mock_event_manager.route_user_input.assert_called_once_with("test-session-id", "Hello, create a new session!")
    
    print("✅ Automatic session creation test passed!")


async def test_send_message_with_no_session():
    """Test that send_message creates a task when no active session exists."""
    print("Testing send_message with no active session...")
    
    # Create mock managers
    mock_session_manager = MagicMock()
    mock_event_manager = MagicMock()
    mock_file_manager = MagicMock()
    
    # Set up mocks for no active session scenario
    mock_session_manager.get_active_session.return_value = None
    
    # Create chat panel
    with patch('openhands.tui.panels.chat_panel.ptg.terminal') as mock_terminal:
        mock_terminal.height = 50
        mock_terminal.width = 100
        chat_panel = ChatPanel(mock_session_manager, mock_event_manager, mock_file_manager)
    
    # Set up input field with a test message
    chat_panel.input_field.insert_text("Hello, create a new session!")
    
    # Mock asyncio.create_task to capture the task creation
    with patch('asyncio.create_task') as mock_create_task:
        # Mock create_task to close the coroutine to avoid warnings
        def mock_create_task_impl(coro):
            # Close the coroutine to avoid "never awaited" warnings
            if hasattr(coro, 'close'):
                coro.close()
            return MagicMock()
        mock_create_task.side_effect = mock_create_task_impl
        
        # Call send_message
        await chat_panel.send_message()
        
        # Verify that create_task was called (indicating session creation was triggered)
        mock_create_task.assert_called_once()
    
    print("✅ Send message with no session test passed!")


async def test_session_ready_check():
    """Test that messages are only sent when session is ready."""
    print("Testing session ready check...")
    
    # Create mock managers
    mock_session_manager = MagicMock()
    mock_event_manager = MagicMock()
    mock_file_manager = MagicMock()
    
    # Set up mock session in LOADING state (not ready)
    mock_session = MagicMock()
    mock_session.sid = "test-session"
    mock_session.agent_state = AgentState.LOADING
    mock_session_manager.get_active_session.return_value = mock_session
    
    # Create chat panel
    with patch('openhands.tui.panels.chat_panel.ptg.terminal') as mock_terminal:
        mock_terminal.height = 50
        mock_terminal.width = 100
        chat_panel = ChatPanel(mock_session_manager, mock_event_manager, mock_file_manager)
    
    # Set up input field with a test message
    chat_panel.input_field.insert_text("This should not be sent yet")
    
    # Call send_message
    await chat_panel.send_message()
    
    # Verify that message was NOT sent (session not ready)
    mock_event_manager.route_user_input.assert_not_called()
    
    # Now test with ready session
    mock_session.agent_state = AgentState.AWAITING_USER_INPUT
    mock_event_manager.route_user_input.return_value = True
    
    # Clear input field first
    if chat_panel.input_field.value:
        chat_panel.input_field.delete_back(len(chat_panel.input_field.value))
    
    # Set up input field again
    chat_panel.input_field.insert_text("This should be sent now")
    
    # Call send_message
    await chat_panel.send_message()
    
    # Verify that message was sent (session ready)
    mock_event_manager.route_user_input.assert_called_once_with("test-session", "This should be sent now")
    
    print("✅ Session ready check test passed!")


def test_logging_setup():
    """Test that logging is properly set up."""
    print("Testing logging setup...")
    
    from openhands.tui.panels.logs_panel import get_tui_log_handler
    from openhands.core.logger import openhands_logger
    import logging
    from pathlib import Path
    
    # Get the TUI log handler
    handler = get_tui_log_handler()
    
    # Check that logs directory exists
    logs_dir = Path("logs")
    assert logs_dir.exists(), "logs/ directory should exist"
    
    # Check that log file exists
    log_file = logs_dir / "tui_debug.log"
    assert log_file.exists(), "tui_debug.log should exist"
    
    # Test logging
    openhands_logger.info("Test log message from test script")
    
    # Check that the log was written
    with open(log_file, 'r') as f:
        content = f.read()
        assert "Test log message from test script" in content, "Log message should be in file"
    
    print("✅ Logging setup test passed!")


async def main():
    """Run all tests."""
    print("Running TUI fixes tests...\n")
    
    try:
        await test_automatic_session_creation()
        await test_send_message_with_no_session()
        await test_session_ready_check()
        test_logging_setup()
        
        print("\n🎉 All tests passed! TUI fixes are working correctly.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 