"""Unit tests for TUI Session Manager."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from openhands.core.config import AppConfig
from openhands.core.schema import AgentState
from openhands.storage.settings.file_settings_store import FileSettingsStore
from openhands.tui.managers.session_manager import SessionContext, SessionManager


class TestSessionManager:
    """Test cases for SessionManager."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock AppConfig."""
        config = MagicMock()
        config.sandbox.selected_repo = None
        config.jwt_secret = "test-secret"
        return config

    @pytest.fixture
    def mock_settings_store(self):
        """Create a mock FileSettingsStore."""
        return MagicMock(spec=FileSettingsStore)

    @pytest.fixture
    def session_manager(self, mock_config, mock_settings_store):
        """Create a SessionManager instance."""
        return SessionManager(mock_config, mock_settings_store)

    @pytest.fixture
    def mock_session_context(self):
        """Create a mock SessionContext."""
        mock_runtime = MagicMock()
        mock_controller = MagicMock()
        mock_event_stream = MagicMock()
        mock_memory = MagicMock()
        mock_agent = MagicMock()
        
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

    def test_initialization(self, mock_config, mock_settings_store):
        """Test SessionManager initialization."""
        manager = SessionManager(mock_config, mock_settings_store)
        
        assert manager.config == mock_config
        assert manager.settings_store == mock_settings_store
        assert manager.sessions == {}
        assert manager.active_session_id is None
        assert manager._cleanup_tasks == {}

    @pytest.mark.asyncio
    @patch('openhands.tui.managers.session_manager.generate_sid')
    @patch('openhands.tui.managers.session_manager.create_agent')
    @patch('openhands.tui.managers.session_manager.create_runtime')
    @patch('openhands.tui.managers.session_manager.create_controller')
    @patch('openhands.tui.managers.session_manager.create_memory')
    @patch('openhands.tui.managers.session_manager.initialize_repository_for_runtime')
    async def test_create_session_success(
        self, mock_initialize_repo, mock_create_memory, mock_create_controller, 
        mock_create_runtime, mock_create_agent, mock_generate_sid, session_manager
    ):
        """Test successful session creation."""
        # Setup mocks
        mock_generate_sid.return_value = "test-session-123"
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent
        
        mock_runtime = MagicMock()
        mock_runtime.connect = AsyncMock()
        mock_runtime.event_stream = MagicMock()
        mock_create_runtime.return_value = mock_runtime
        
        mock_controller = MagicMock()
        mock_initial_state = MagicMock()
        mock_create_controller.return_value = (mock_controller, mock_initial_state)
        
        mock_memory = MagicMock()
        mock_create_memory.return_value = mock_memory
        
        mock_initialize_repo.return_value = "/test/repo/path"
        
        # Set up config to have a selected repo
        session_manager.config.sandbox.selected_repo = "test-repo"
        
        # Create session
        session_id = await session_manager.create_session("Test task", "test-name")
        
        # Verify session creation
        assert session_id == "test-session-123"
        assert session_id in session_manager.sessions
        assert session_manager.active_session_id == session_id
        
        session = session_manager.sessions[session_id]
        assert session.sid == session_id
        assert session.task_description == "Test task"
        assert session.agent == mock_agent
        assert session.runtime == mock_runtime
        assert session.controller == mock_controller
        assert session.memory == mock_memory
        assert session.repo_directory == "/test/repo/path"
        assert session.reload_microagents == False
        
        # Verify mocks were called correctly
        mock_generate_sid.assert_called_once_with(session_manager.config, "test-name")
        mock_create_agent.assert_called_once_with(session_manager.config)
        mock_runtime.connect.assert_called_once()

    @pytest.mark.asyncio
    @patch('openhands.tui.managers.session_manager.generate_sid')
    @patch('openhands.tui.managers.session_manager.create_agent')
    async def test_create_session_failure(
        self, mock_create_agent, mock_generate_sid, session_manager
    ):
        """Test session creation failure."""
        mock_generate_sid.return_value = "test-session-123"
        mock_create_agent.side_effect = Exception("Agent creation failed")
        
        with pytest.raises(Exception, match="Agent creation failed"):
            await session_manager.create_session("Test task")
        
        # Verify no session was created
        assert len(session_manager.sessions) == 0
        assert session_manager.active_session_id is None

    @pytest.mark.asyncio
    @patch('openhands.tui.managers.session_manager.generate_sid')
    @patch('openhands.tui.managers.session_manager.create_agent')
    @patch('openhands.tui.managers.session_manager.create_runtime')
    @patch('openhands.tui.managers.session_manager.create_controller')
    @patch('openhands.tui.managers.session_manager.create_memory')
    @patch('openhands.tui.managers.session_manager.initialize_repository_for_runtime')
    async def test_create_session_without_repo(
        self, mock_initialize_repo, mock_create_memory, mock_create_controller, 
        mock_create_runtime, mock_create_agent, mock_generate_sid, session_manager
    ):
        """Test successful session creation without selected repository."""
        # Setup mocks
        mock_generate_sid.return_value = "test-session-456"
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent
        
        mock_runtime = MagicMock()
        mock_runtime.connect = AsyncMock()
        mock_runtime.event_stream = MagicMock()
        mock_create_runtime.return_value = mock_runtime
        
        mock_controller = MagicMock()
        mock_initial_state = MagicMock()
        mock_create_controller.return_value = (mock_controller, mock_initial_state)
        
        mock_memory = MagicMock()
        mock_create_memory.return_value = mock_memory
        
        # Ensure no selected repo
        session_manager.config.sandbox.selected_repo = None
        
        # Create session
        session_id = await session_manager.create_session("Test task without repo")
        
        # Verify session creation
        assert session_id == "test-session-456"
        assert session_id in session_manager.sessions
        
        session = session_manager.sessions[session_id]
        assert session.repo_directory is None
        assert session.reload_microagents == False
        
        # Verify repository initialization was not called
        mock_initialize_repo.assert_not_called()

    @pytest.mark.asyncio
    async def test_switch_session_success(self, session_manager, mock_session_context):
        """Test successful session switching."""
        # Add session to manager
        session_manager.sessions["test-session-123"] = mock_session_context
        
        # Switch to session
        await session_manager.switch_session("test-session-123")
        
        assert session_manager.active_session_id == "test-session-123"
        # Verify last activity was updated (within last second)
        time_diff = datetime.now() - mock_session_context.last_activity
        assert time_diff.total_seconds() < 1

    @pytest.mark.asyncio
    async def test_switch_session_not_found(self, session_manager):
        """Test switching to non-existent session."""
        with pytest.raises(ValueError, match="Session nonexistent not found"):
            await session_manager.switch_session("nonexistent")

    @pytest.mark.asyncio
    async def test_close_session_success(self, session_manager, mock_session_context):
        """Test successful session closure."""
        # Setup mocks
        mock_session_context.controller.get_state.return_value = MagicMock()
        mock_session_context.controller.close = AsyncMock()
        mock_session_context.runtime.close = MagicMock()
        mock_session_context.agent.reset = MagicMock()
        
        # Add session to manager
        session_manager.sessions["test-session-123"] = mock_session_context
        session_manager.active_session_id = "test-session-123"
        
        # Close session
        await session_manager.close_session("test-session-123")
        
        # Verify session was removed
        assert "test-session-123" not in session_manager.sessions
        assert session_manager.active_session_id is None
        
        # Verify cleanup was called
        mock_session_context.agent.reset.assert_called_once()
        mock_session_context.runtime.close.assert_called_once()
        mock_session_context.controller.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session_not_found(self, session_manager):
        """Test closing non-existent session."""
        with pytest.raises(ValueError, match="Session nonexistent not found"):
            await session_manager.close_session("nonexistent")

    @pytest.mark.asyncio
    async def test_close_session_with_multiple_sessions(self, session_manager):
        """Test closing session when multiple sessions exist."""
        # Create mock sessions
        session1 = MagicMock()
        session1.last_activity = datetime(2023, 1, 1, 10, 0, 0)
        session1.controller.get_state.return_value = MagicMock()
        session1.controller.close = AsyncMock()
        session1.runtime.close = MagicMock()
        session1.agent.reset = MagicMock()
        
        session2 = MagicMock()
        session2.last_activity = datetime(2023, 1, 1, 11, 0, 0)  # More recent
        
        session_manager.sessions = {
            "session1": session1,
            "session2": session2,
        }
        session_manager.active_session_id = "session1"
        
        # Close active session
        await session_manager.close_session("session1")
        
        # Verify active session switched to most recent
        assert session_manager.active_session_id == "session2"
        assert "session1" not in session_manager.sessions
        assert "session2" in session_manager.sessions

    def test_get_active_session(self, session_manager, mock_session_context):
        """Test getting active session."""
        # No active session
        assert session_manager.get_active_session() is None
        
        # Add session and set as active
        session_manager.sessions["test-session-123"] = mock_session_context
        session_manager.active_session_id = "test-session-123"
        
        active_session = session_manager.get_active_session()
        assert active_session == mock_session_context

    def test_get_session(self, session_manager, mock_session_context):
        """Test getting session by ID."""
        # Session not found
        assert session_manager.get_session("nonexistent") is None
        
        # Add session
        session_manager.sessions["test-session-123"] = mock_session_context
        
        session = session_manager.get_session("test-session-123")
        assert session == mock_session_context

    def test_list_sessions(self, session_manager):
        """Test listing sessions sorted by activity."""
        # Create mock sessions with different activity times
        session1 = MagicMock()
        session1.last_activity = datetime(2023, 1, 1, 10, 0, 0)
        
        session2 = MagicMock()
        session2.last_activity = datetime(2023, 1, 1, 11, 0, 0)  # More recent
        
        session3 = MagicMock()
        session3.last_activity = datetime(2023, 1, 1, 9, 0, 0)   # Oldest
        
        session_manager.sessions = {
            "session1": session1,
            "session2": session2,
            "session3": session3,
        }
        
        sessions = session_manager.list_sessions()
        
        # Should be sorted by last_activity (most recent first)
        assert len(sessions) == 3
        assert sessions[0] == session2  # Most recent
        assert sessions[1] == session1
        assert sessions[2] == session3  # Oldest

    def test_update_session_activity(self, session_manager, mock_session_context):
        """Test updating session activity."""
        session_manager.sessions["test-session-123"] = mock_session_context
        session_manager.active_session_id = "test-session-123"
        
        original_time = mock_session_context.last_activity
        
        # Update activity for active session
        session_manager.update_session_activity()
        
        # Verify time was updated
        assert mock_session_context.last_activity > original_time
        
        # Update activity for specific session
        session_manager.update_session_activity("test-session-123")
        
        # Verify time was updated again
        assert mock_session_context.last_activity > original_time

    def test_update_session_task(self, session_manager, mock_session_context):
        """Test updating session task description."""
        session_manager.sessions["test-session-123"] = mock_session_context
        session_manager.active_session_id = "test-session-123"
        
        original_time = mock_session_context.last_activity
        
        # Update task for active session
        session_manager.update_session_task("New task description")
        
        assert mock_session_context.task_description == "New task description"
        assert mock_session_context.last_activity > original_time

    @pytest.mark.asyncio
    async def test_cleanup_all_sessions(self, session_manager):
        """Test cleaning up all sessions."""
        # Create mock sessions
        session1 = MagicMock()
        session1.controller.get_state.return_value = MagicMock()
        session1.controller.close = AsyncMock()
        session1.runtime.close = MagicMock()
        session1.agent.reset = MagicMock()
        
        session2 = MagicMock()
        session2.controller.get_state.return_value = MagicMock()
        session2.controller.close = AsyncMock()
        session2.runtime.close = MagicMock()
        session2.agent.reset = MagicMock()
        
        session_manager.sessions = {
            "session1": session1,
            "session2": session2,
        }
        
        # Add mock cleanup tasks
        task1 = MagicMock()
        task2 = MagicMock()
        session_manager._cleanup_tasks = {
            "task1": task1,
            "task2": task2,
        }
        
        # Cleanup all sessions
        await session_manager.cleanup_all_sessions()
        
        # Verify all sessions were removed
        assert len(session_manager.sessions) == 0
        assert session_manager.active_session_id is None
        
        # Verify cleanup tasks were cancelled
        task1.cancel.assert_called_once()
        task2.cancel.assert_called_once()
        assert len(session_manager._cleanup_tasks) == 0

    def test_get_session_count(self, session_manager, mock_session_context):
        """Test getting session count."""
        assert session_manager.get_session_count() == 0
        
        session_manager.sessions["test-session-123"] = mock_session_context
        assert session_manager.get_session_count() == 1

    def test_has_sessions(self, session_manager, mock_session_context):
        """Test checking if sessions exist."""
        assert not session_manager.has_sessions()
        
        session_manager.sessions["test-session-123"] = mock_session_context
        assert session_manager.has_sessions()

    def test_reload_session_microagents(self, session_manager, mock_session_context):
        """Test reloading microagents for a session."""
        # Setup mock microagents
        mock_microagents = [MagicMock(), MagicMock()]
        mock_session_context.runtime.get_microagents_from_selected_repo.return_value = mock_microagents
        mock_session_context.memory.load_user_workspace_microagents = MagicMock()
        mock_session_context.reload_microagents = True
        
        # Add session to manager
        session_manager.sessions["test-session-123"] = mock_session_context
        session_manager.active_session_id = "test-session-123"
        
        # Reload microagents
        session_manager.reload_session_microagents()
        
        # Verify microagents were reloaded
        mock_session_context.runtime.get_microagents_from_selected_repo.assert_called_once_with(None)
        mock_session_context.memory.load_user_workspace_microagents.assert_called_once_with(mock_microagents)
        assert mock_session_context.reload_microagents == False

    def test_reload_session_microagents_specific_session(self, session_manager, mock_session_context):
        """Test reloading microagents for a specific session."""
        # Setup mock microagents
        mock_microagents = [MagicMock(), MagicMock()]
        mock_session_context.runtime.get_microagents_from_selected_repo.return_value = mock_microagents
        mock_session_context.memory.load_user_workspace_microagents = MagicMock()
        mock_session_context.reload_microagents = True
        
        # Add session to manager
        session_manager.sessions["test-session-123"] = mock_session_context
        
        # Reload microagents for specific session
        session_manager.reload_session_microagents("test-session-123")
        
        # Verify microagents were reloaded
        mock_session_context.runtime.get_microagents_from_selected_repo.assert_called_once_with(None)
        mock_session_context.memory.load_user_workspace_microagents.assert_called_once_with(mock_microagents)
        assert mock_session_context.reload_microagents == False

    def test_reload_session_microagents_error(self, session_manager, mock_session_context):
        """Test error handling during microagent reload."""
        # Setup mock to raise exception
        mock_session_context.runtime.get_microagents_from_selected_repo.side_effect = Exception("Microagent error")
        mock_session_context.reload_microagents = True
        
        # Add session to manager
        session_manager.sessions["test-session-123"] = mock_session_context
        session_manager.active_session_id = "test-session-123"
        
        # Reload microagents (should not raise exception)
        session_manager.reload_session_microagents()
        
        # Verify error was handled gracefully
        mock_session_context.runtime.get_microagents_from_selected_repo.assert_called_once_with(None)
        # reload_microagents flag should still be True since reload failed
        assert mock_session_context.reload_microagents == True

    def test_mark_session_for_microagent_reload(self, session_manager, mock_session_context):
        """Test marking session for microagent reload."""
        mock_session_context.reload_microagents = False
        
        # Add session to manager
        session_manager.sessions["test-session-123"] = mock_session_context
        session_manager.active_session_id = "test-session-123"
        
        # Mark for reload
        session_manager.mark_session_for_microagent_reload()
        
        assert mock_session_context.reload_microagents == True

    def test_mark_session_for_microagent_reload_specific_session(self, session_manager, mock_session_context):
        """Test marking specific session for microagent reload."""
        mock_session_context.reload_microagents = False
        
        # Add session to manager
        session_manager.sessions["test-session-123"] = mock_session_context
        
        # Mark specific session for reload
        session_manager.mark_session_for_microagent_reload("test-session-123")
        
        assert mock_session_context.reload_microagents == True