"""Unit tests for TUI Sessions Panel."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import pytermgui as ptg

from openhands.tui.panels.sessions_panel import SessionsPanel
from openhands.tui.managers.session_manager import SessionContext
from openhands.core.schema import AgentState
from datetime import datetime


class TestSessionsPanel:
    """Test cases for SessionsPanel class."""
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create mock session manager."""
        manager = MagicMock()
        manager.list_sessions.return_value = []
        manager.active_session_id = None
        manager.get_active_session.return_value = None
        manager.create_session = AsyncMock()
        manager.switch_session = AsyncMock()
        manager.close_session = AsyncMock()
        return manager
    
    @pytest.fixture
    def mock_file_manager(self):
        """Create mock file manager."""
        manager = MagicMock()
        manager.update_sessions_file = MagicMock()
        return manager
    
    @pytest.fixture
    def sessions_panel(self, mock_session_manager, mock_file_manager):
        """Create sessions panel instance."""
        return SessionsPanel(mock_session_manager, mock_file_manager)
    
    @pytest.fixture
    def sample_sessions(self):
        """Create sample session contexts."""
        mock_config = MagicMock()
        mock_runtime = MagicMock()
        mock_controller = MagicMock()
        mock_event_stream = MagicMock()
        mock_memory = MagicMock()
        
        return [
            SessionContext(
                sid="session1",
                config=mock_config,
                runtime=mock_runtime,
                controller=mock_controller,
                event_stream=mock_event_stream,
                memory=mock_memory,
                agent_state=AgentState.STOPPED,
                created_at=datetime(2024, 1, 1, 10, 0, 0),
                last_activity=datetime(2024, 1, 1, 10, 0, 0),
                task_description="Test task 1"
            ),
            SessionContext(
                sid="session2",
                config=mock_config,
                runtime=mock_runtime,
                controller=mock_controller,
                event_stream=mock_event_stream,
                memory=mock_memory,
                agent_state=AgentState.RUNNING,
                created_at=datetime(2024, 1, 1, 11, 0, 0),
                last_activity=datetime(2024, 1, 1, 11, 0, 0),
                task_description="Test task 2 with a very long description that should be truncated"
            )
        ]
    
    def test_initialization(self, sessions_panel, mock_session_manager, mock_file_manager):
        """Test sessions panel initialization."""
        assert sessions_panel.session_manager == mock_session_manager
        assert sessions_panel.file_manager == mock_file_manager
        assert sessions_panel.title == "Sessions"
        assert sessions_panel.get_panel_name() == "sessions"
        
        # Check that session list and button were added
        assert hasattr(sessions_panel, 'session_list')
        assert hasattr(sessions_panel, 'session_widgets')
        assert isinstance(sessions_panel.session_widgets, dict)
        
        # Check for New Session button
        widgets = sessions_panel._widgets
        button_found = any(
            isinstance(widget, ptg.Button) and "New Session" in str(widget)
            for widget in widgets
        )
        assert button_found
    
    def test_update_display(self, sessions_panel):
        """Test update display method."""
        with patch.object(sessions_panel, 'update_sessions') as mock_update:
            sessions_panel.update_display("test_session")
            mock_update.assert_called_once()
    
    def test_update_sessions_empty(self, sessions_panel, mock_session_manager, mock_file_manager):
        """Test updating sessions display with no sessions."""
        mock_session_manager.list_sessions.return_value = []
        
        sessions_panel.update_sessions()
        
        # Should update file manager
        mock_file_manager.update_sessions_file.assert_called_once_with([])
        
        # Should show "No active sessions" message
        session_list_widgets = sessions_panel.session_list._widgets
        assert any(
            isinstance(widget, ptg.Label) and "No active sessions" in str(widget)
            for widget in session_list_widgets
        )
    
    def test_update_sessions_with_data(self, sessions_panel, mock_session_manager, mock_file_manager, sample_sessions):
        """Test updating sessions display with session data."""
        mock_session_manager.list_sessions.return_value = sample_sessions
        mock_session_manager.active_session_id = "session1"
        
        sessions_panel.update_sessions()
        
        # Should update file manager
        mock_file_manager.update_sessions_file.assert_called_once_with(sample_sessions)
        
        # Should create widgets for each session
        assert len(sessions_panel.session_widgets) == 2
        assert "session1" in sessions_panel.session_widgets
        assert "session2" in sessions_panel.session_widgets
        
        # Should have buttons in session list
        session_list_widgets = sessions_panel.session_list._widgets
        button_count = sum(1 for widget in session_list_widgets if isinstance(widget, ptg.Button))
        assert button_count == 2
    
    def test_create_session_widget_active(self, sessions_panel, mock_session_manager, sample_sessions):
        """Test creating widget for active session."""
        mock_session_manager.active_session_id = "session1"
        session = sample_sessions[0]
        
        widget = sessions_panel.create_session_widget(session)
        
        assert isinstance(widget, ptg.Button)
        # Active session should have indicator
        assert "●" in str(widget)
        assert "Test task 1" in str(widget)
        # Active session should have green styling
        assert "bold green" in str(widget.styles.label)
    
    def test_create_session_widget_inactive(self, sessions_panel, mock_session_manager, sample_sessions):
        """Test creating widget for inactive session."""
        mock_session_manager.active_session_id = "other_session"
        session = sample_sessions[0]
        
        widget = sessions_panel.create_session_widget(session)
        
        assert isinstance(widget, ptg.Button)
        # Inactive session should not have indicator
        assert "●" not in str(widget)
        assert "Test task 1" in str(widget)
        # Should not have special styling
        assert "bold green" not in str(widget.styles.label)
    
    def test_create_session_widget_long_description(self, sessions_panel, mock_session_manager, sample_sessions):
        """Test creating widget with long task description."""
        mock_session_manager.active_session_id = None
        session = sample_sessions[1]  # Has long description
        
        widget = sessions_panel.create_session_widget(session)
        
        assert isinstance(widget, ptg.Button)
        widget_label = widget.label
        # Should be truncated with ellipsis
        assert "..." in widget_label
        assert len(widget_label) < len(session.task_description)  # Should be shorter than original
    
    @pytest.mark.asyncio
    async def test_create_new_session_success(self, sessions_panel, mock_session_manager):
        """Test creating new session successfully."""
        mock_session_manager.create_session.return_value = "new_session_id"
        
        with patch.object(sessions_panel, 'update_sessions') as mock_update:
            await sessions_panel._create_session_async("New session - ready for your first message")
        
        mock_session_manager.create_session.assert_called_once_with("New session - ready for your first message")
        mock_update.assert_called_once()
    
    def test_create_new_session_sync(self, sessions_panel):
        """Test synchronous create_new_session method."""
        with patch('asyncio.create_task') as mock_create_task:
            with patch('asyncio.get_running_loop') as mock_get_loop:
                mock_loop = MagicMock()
                mock_get_loop.return_value = mock_loop
                
                sessions_panel.create_new_session()
                
                # Should create async task
                mock_create_task.assert_called_once()
                # Should get event loop
                mock_get_loop.assert_called_once()

    def test_create_new_session_sync_no_loop(self, sessions_panel):
        """Test synchronous create_new_session method when no event loop exists."""
        with patch('asyncio.run') as mock_run:
            with patch('asyncio.get_running_loop', side_effect=RuntimeError("No event loop")):
                sessions_panel.create_new_session()
                
                # Should run in new loop
                mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_async_success(self, sessions_panel, mock_session_manager):
        """Test async session creation successfully."""
        mock_session_manager.create_session.return_value = "new_session_id"
        mock_session_manager.event_manager = MagicMock()
        mock_session_manager.event_manager.subscribe_to_session = MagicMock()
        
        with patch.object(sessions_panel, 'update_sessions') as mock_update:
            await sessions_panel._create_session_async("Test task")
        
        mock_session_manager.create_session.assert_called_once_with("Test task")
        mock_session_manager.event_manager.subscribe_to_session.assert_called_once_with("new_session_id")
        mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_async_no_event_manager(self, sessions_panel, mock_session_manager):
        """Test async session creation when no event manager available."""
        mock_session_manager.create_session.return_value = "new_session_id"
        # No event_manager attribute
        
        with patch.object(sessions_panel, 'update_sessions') as mock_update:
            await sessions_panel._create_session_async("Test task")
        
        mock_session_manager.create_session.assert_called_once_with("Test task")
        mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_async_failure(self, sessions_panel, mock_session_manager):
        """Test async session creation with failure."""
        mock_session_manager.create_session.side_effect = Exception("Creation failed")
        
        with patch.object(sessions_panel, 'update_sessions') as mock_update:
            # Should not raise exception
            await sessions_panel._create_session_async("Test task")
        
        mock_session_manager.create_session.assert_called_once()
        mock_update.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_switch_to_session_success(self, sessions_panel, mock_session_manager):
        """Test switching to session successfully."""
        session_id = "test_session"
        
        with patch.object(sessions_panel, 'update_sessions') as mock_update:
            await sessions_panel.switch_to_session(session_id)
        
        mock_session_manager.switch_session.assert_called_once_with(session_id)
        mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_switch_to_session_failure(self, sessions_panel, mock_session_manager):
        """Test switching to session with failure."""
        session_id = "test_session"
        mock_session_manager.switch_session.side_effect = Exception("Switch failed")
        
        with patch.object(sessions_panel, 'update_sessions') as mock_update:
            # Should not raise exception
            await sessions_panel.switch_to_session(session_id)
        
        mock_session_manager.switch_session.assert_called_once_with(session_id)
        mock_update.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_close_session_success(self, sessions_panel, mock_session_manager):
        """Test closing session successfully."""
        session_id = "test_session"
        
        with patch.object(sessions_panel, 'update_sessions') as mock_update:
            await sessions_panel.close_session(session_id)
        
        mock_session_manager.close_session.assert_called_once_with(session_id)
        mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_session_failure(self, sessions_panel, mock_session_manager):
        """Test closing session with failure."""
        session_id = "test_session"
        mock_session_manager.close_session.side_effect = Exception("Close failed")
        
        with patch.object(sessions_panel, 'update_sessions') as mock_update:
            # Should not raise exception
            await sessions_panel.close_session(session_id)
        
        mock_session_manager.close_session.assert_called_once_with(session_id)
        mock_update.assert_not_called()
    
    def test_handle_key_event_new_session(self, sessions_panel):
        """Test handling 'n' key for new session."""
        with patch.object(sessions_panel, 'create_new_session') as mock_create:
            result = sessions_panel.handle_key_event("n")
        
        assert result is True
        mock_create.assert_called_once()
    
    def test_handle_key_event_delete_session(self, sessions_panel, mock_session_manager, sample_sessions):
        """Test handling 'd' key for deleting session."""
        mock_session_manager.get_active_session.return_value = sample_sessions[0]
        
        with patch('asyncio.create_task') as mock_task:
            with patch('asyncio.get_running_loop') as mock_get_loop:
                mock_loop = MagicMock()
                mock_get_loop.return_value = mock_loop
                
                result = sessions_panel.handle_key_event("d")
        
        assert result is True
        mock_task.assert_called_once()
        # Verify the task was created with a coroutine
        args, kwargs = mock_task.call_args
        assert len(args) == 1
        # The argument should be a coroutine
        import inspect
        assert inspect.iscoroutine(args[0])
    
    def test_handle_key_event_delete_no_active_session(self, sessions_panel, mock_session_manager):
        """Test handling 'd' key with no active session."""
        mock_session_manager.get_active_session.return_value = None
        
        with patch('asyncio.create_task') as mock_task:
            result = sessions_panel.handle_key_event("d")
        
        assert result is True
        mock_task.assert_not_called()
    
    def test_handle_key_event_unhandled(self, sessions_panel):
        """Test handling unrecognized key."""
        result = sessions_panel.handle_key_event("x")
        assert result is False
        
        result = sessions_panel.handle_key_event("Enter")
        assert result is False