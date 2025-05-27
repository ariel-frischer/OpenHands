#!/usr/bin/env python3
"""Test for TUI exit issue after session creation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytermgui as ptg

from openhands.core.config import AppConfig
from openhands.core.schema import AgentState
from openhands.tui.app import OpenHandsTUIApp
from openhands.tui.panels.sessions_panel import SessionsPanel
from openhands.tui.managers.session_manager import SessionManager, SessionContext
from datetime import datetime


class TestTUISessionCreationExitIssue:
    """Test cases for TUI exit issue after session creation."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = MagicMock(spec=AppConfig)
        config.workspace_base = "/tmp/test_workspace"
        config.file_store_path = "/tmp/test_file_store"
        config.runtime = "local"
        # Mock sandbox as an object with selected_repo attribute
        config.sandbox = MagicMock()
        config.sandbox.selected_repo = None
        return config

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        manager = MagicMock(spec=SessionManager)
        manager.sessions = {}
        manager.active_session_id = None
        manager.get_active_session = MagicMock(return_value=None)
        manager.list_sessions = MagicMock(return_value=[])
        manager.create_session = AsyncMock(return_value="test-session-123")
        manager.start_session = AsyncMock()
        manager.switch_session = AsyncMock()
        manager.close_session = AsyncMock()
        manager._cleanup_tasks = {}
        return manager

    @pytest.fixture
    def mock_file_manager(self):
        """Create a mock file manager."""
        manager = MagicMock()
        manager.update_sessions_file = MagicMock()
        return manager

    @pytest.fixture
    def mock_event_manager(self):
        """Create a mock event manager."""
        manager = MagicMock()
        manager.subscribe_to_session = MagicMock()
        return manager

    @pytest.fixture
    def sessions_panel(self, mock_session_manager, mock_file_manager):
        """Create sessions panel instance."""
        return SessionsPanel(mock_session_manager, mock_file_manager)

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
            created_at=datetime.now(),
            last_activity=datetime.now(),
            task_description="Test task",
            agent=mock_agent,
            repo_directory=None,
            reload_microagents=False,
        )

    @pytest.mark.asyncio
    async def test_session_creation_with_run_agent_until_done_exception(
        self, sessions_panel, mock_session_manager, mock_session_context
    ):
        """Test that exceptions in run_agent_until_done don't cause TUI exit."""
        # Mock create_session to return a session ID
        mock_session_manager.create_session.return_value = "test-session-123"
        
        # Mock session manager to have the event manager
        mock_session_manager.event_manager = MagicMock()
        mock_session_manager.event_manager.subscribe_to_session = MagicMock()
        
        # Mock start_session to raise an exception that would normally crash the TUI
        mock_session_manager.start_session.side_effect = Exception("run_agent_until_done failed")

        # Test that session creation still completes without crashing
        # This should NOT raise an exception - the error should be caught and handled
        try:
            await sessions_panel._create_session_async("Test task")
            # If we reach here, the exception was properly handled
            session_creation_succeeded = True
        except Exception as e:
            # This should not happen - exceptions should be caught internally
            session_creation_succeeded = False
            pytest.fail(f"Session creation should not raise exception: {e}")

        # Verify that create_session was called
        mock_session_manager.create_session.assert_called_once_with("Test task")
        
        # Verify that start_session was called and failed
        mock_session_manager.start_session.assert_called_once_with("test-session-123")

    @pytest.mark.asyncio 
    async def test_session_creation_background_task_exception_handling(
        self, sessions_panel, mock_session_manager
    ):
        """Test that background task exceptions in session creation are properly handled."""
        # Mock create_session to return a session ID
        mock_session_manager.create_session.return_value = "test-session-123"
        
        # Mock session manager to have the event manager  
        mock_session_manager.event_manager = MagicMock()
        mock_session_manager.event_manager.subscribe_to_session = MagicMock()

        # Mock start_session to succeed but cause background task issues
        mock_session_manager.start_session = AsyncMock()

        # Test that the _handle_task_exception method exists and works
        assert hasattr(sessions_panel, '_handle_task_exception')

        # Create a mock task that failed
        mock_failed_task = MagicMock()
        mock_failed_task.result.side_effect = Exception("Background task failed")

        # Test that exception handler doesn't crash
        try:
            sessions_panel._handle_task_exception(mock_failed_task)
            exception_handler_worked = True
        except Exception as e:
            exception_handler_worked = False
            pytest.fail(f"Exception handler should not raise: {e}")

        assert exception_handler_worked
        # Verify that the creating session flag is reset
        assert not sessions_panel._creating_session

    @pytest.mark.asyncio
    async def test_new_session_button_click_with_background_task_error(
        self, sessions_panel, mock_session_manager
    ):
        """Test new session button with background task errors."""
        # Set up session manager with event manager
        mock_session_manager.event_manager = MagicMock()
        mock_session_manager.event_manager.subscribe_to_session = MagicMock()
        
        # Mock session creation to succeed but start to fail
        mock_session_manager.create_session.return_value = "test-session-123"
        mock_session_manager.start_session.side_effect = Exception("Start session failed")

        # Mock asyncio.create_task to capture the task creation
        with patch('asyncio.create_task') as mock_create_task:
            # Create a mock task that will complete immediately
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_create_task.return_value = mock_task
            
            # Mock _create_session_async to avoid actual async execution
            with patch.object(sessions_panel, '_create_session_async', new_callable=AsyncMock) as mock_create_async:
                mock_create_async.side_effect = Exception("Session creation failed")
                
                # Call create_new_session - this should not crash
                try:
                    sessions_panel.create_new_session()
                    button_click_succeeded = True
                except Exception as e:
                    button_click_succeeded = False
                    pytest.fail(f"New session button should not crash TUI: {e}")

                assert button_click_succeeded
                # Verify task was created with done callback
                mock_create_task.assert_called_once()
                mock_task.add_done_callback.assert_called_once_with(sessions_panel._handle_task_exception)

    @pytest.mark.asyncio
    async def test_run_agent_until_done_task_isolation(self, mock_session_manager, mock_session_context):
        """Test that run_agent_until_done background task doesn't affect TUI event loop."""
        # Mock the actual session manager with start_session that calls run_agent_until_done
        real_session_manager = SessionManager(MagicMock(), None, offline_mode=True)
        real_session_manager.sessions = {"test-session-123": mock_session_context}
        
        # Mock run_agent_until_done to raise an exception
        with patch('openhands.core.loop.run_agent_until_done') as mock_run_agent:
            mock_run_agent.side_effect = Exception("Agent loop failed")
            
            # Mock asyncio.create_task to capture task creation 
            with patch('asyncio.create_task') as mock_create_task:
                mock_task = MagicMock()
                mock_create_task.return_value = mock_task
                
                # Call start_session - this should handle the exception gracefully
                try:
                    await real_session_manager.start_session("test-session-123")
                    start_session_succeeded = True
                except Exception as e:
                    start_session_succeeded = False
                    # start_session should catch and re-raise only critical errors
                    # Background task errors should be isolated
                    if "Agent loop failed" in str(e):
                        pytest.fail("Background task exception should not propagate to start_session")
                    else:
                        # Other exceptions (like setup failures) are expected to propagate
                        pass

                # The task should still be created even if it will fail
                mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_tui_app_with_session_creation_error_handling(self, mock_config):
        """Test that the TUI app properly handles session creation failures."""
        # Create a minimal TUI app instance
        with patch('openhands.tui.app.SessionManager') as MockSessionManager:
            with patch('openhands.tui.app.TUIEventManager') as MockEventManager:
                with patch('openhands.tui.app.TUIPanelFileManager') as MockFileManager:
                    # Mock the managers
                    mock_session_manager = MagicMock()
                    mock_event_manager = MagicMock()  
                    mock_file_manager = MagicMock()
                    
                    MockSessionManager.return_value = mock_session_manager
                    MockEventManager.return_value = mock_event_manager
                    MockFileManager.return_value = mock_file_manager
                    
                    # Create TUI app
                    app = OpenHandsTUIApp(mock_config, None, None)
                    
                    # Verify that app initialized without crashing
                    assert app is not None
                    assert app.session_manager == mock_session_manager
                    assert app.event_manager == mock_event_manager
                    assert app.file_manager == mock_file_manager

    def test_session_creation_debouncing(self, sessions_panel):
        """Test that rapid session creation button clicks are debounced."""
        # Test that rapid clicks are ignored
        initial_time = sessions_panel._last_button_click
        
        # First click should work
        with patch.object(sessions_panel, '_create_session_async', new_callable=AsyncMock):
            with patch('time.time', return_value=initial_time + 2.0):  # 2 seconds later
                with patch('asyncio.create_task'):
                    sessions_panel.create_new_session()
                    first_click_processed = not sessions_panel._creating_session or True  # Reset in _handle_task_exception
        
        # Rapid second click should be ignored due to debouncing
        with patch.object(sessions_panel, '_create_session_async', new_callable=AsyncMock) as mock_create:
            with patch('time.time', return_value=initial_time + 2.5):  # Only 0.5 seconds later
                sessions_panel.create_new_session()
                # Should not create a new async task due to debouncing
                mock_create.assert_not_called()

    def test_session_creation_flag_prevents_concurrent_creation(self, sessions_panel):
        """Test that the _creating_session flag prevents concurrent session creation."""
        # Set the flag to simulate ongoing session creation
        sessions_panel._creating_session = True
        
        # Attempt to create another session - should be ignored
        with patch.object(sessions_panel, '_create_session_async', new_callable=AsyncMock) as mock_create:
            with patch('time.time', return_value=1000.0):  # Mock time to pass debouncing
                sessions_panel.create_new_session()
                # Should not create a new async task due to concurrent creation flag
                mock_create.assert_not_called() 