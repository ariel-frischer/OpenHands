"""Tests for Session Status Widget.

Unit tests for the TUI session status widget with mocked session data.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytermgui as ptg

from openhands.core.schema import AgentState
from openhands.tui.widgets.session_status import SessionStatusWidget, SessionRecoveryWidget


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager for testing."""
    manager = MagicMock()
    manager.sessions = {}
    manager.active_session_id = None
    return manager


@pytest.fixture
def mock_session_context():
    """Create a mock session context for testing."""
    session = MagicMock()
    session.sid = "test-session-123"
    session.agent_state = AgentState.AWAITING_USER_INPUT
    session.task_description = "Test task description"
    session.created_at = datetime.now() - timedelta(minutes=30)
    session.last_activity = datetime.now() - timedelta(minutes=5)
    session.error_count = 0
    session.last_error = None
    session.is_connected = True
    session.startup_time = 2.5
    session.message_count = 10
    session.repo_directory = "/test/repo"
    session.reload_microagents = False
    return session


@pytest.fixture
def session_status_widget(mock_session_manager):
    """Create a session status widget for testing."""
    return SessionStatusWidget(mock_session_manager)


@pytest.fixture
def session_recovery_widget(mock_session_manager):
    """Create a session recovery widget for testing."""
    return SessionRecoveryWidget(mock_session_manager)


class TestSessionStatusWidget:
    """Test cases for SessionStatusWidget."""

    def test_initialization(self, session_status_widget, mock_session_manager):
        """Test widget initialization."""
        assert session_status_widget.session_manager == mock_session_manager
        assert session_status_widget.update_interval == 1.0
        assert session_status_widget.last_update == 0.0
        
        # Check that layout components are created
        assert hasattr(session_status_widget, 'status_header')
        assert hasattr(session_status_widget, 'session_info')
        assert hasattr(session_status_widget, 'recovery_info')
        assert hasattr(session_status_widget, 'cleanup_info')

    def test_update_display_throttling(self, session_status_widget):
        """Test that display updates are throttled."""
        # Mock the update methods to track calls
        with patch.object(session_status_widget, '_update_session_info') as mock_session_info, \
             patch.object(session_status_widget, '_update_recovery_info') as mock_recovery_info, \
             patch.object(session_status_widget, '_update_cleanup_info') as mock_cleanup_info:
            
            # First update should work
            session_status_widget.update_display()
            assert mock_session_info.called
            assert mock_recovery_info.called
            assert mock_cleanup_info.called
            
            # Reset mocks
            mock_session_info.reset_mock()
            mock_recovery_info.reset_mock()
            mock_cleanup_info.reset_mock()
            
            # Immediate second update should be throttled
            session_status_widget.update_display()
            assert not mock_session_info.called
            assert not mock_recovery_info.called
            assert not mock_cleanup_info.called

    def test_update_session_info_no_active_session(self, session_status_widget, mock_session_manager):
        """Test session info update when no active session."""
        mock_session_manager.get_session_summary.return_value = {
            'total_sessions': 0,
            'active_sessions': 0,
            'waiting_sessions': 0,
            'error_sessions': 0
        }
        mock_session_manager.get_active_session.return_value = None
        
        session_status_widget._update_session_info()
        
        # Check that "No active session" message is displayed
        labels = [widget for widget in session_status_widget.session_info._widgets if isinstance(widget, ptg.Label)]
        assert any("No active session" in label.value for label in labels)

    def test_update_session_info_with_active_session(self, session_status_widget, mock_session_manager, mock_session_context):
        """Test session info update with active session."""
        mock_session_manager.get_session_summary.return_value = {
            'total_sessions': 1,
            'active_sessions': 1,
            'waiting_sessions': 0,
            'error_sessions': 0
        }
        mock_session_manager.get_active_session.return_value = mock_session_context
        
        session_status_widget._update_session_info()
        
        # Check that session information is displayed
        labels = [widget for widget in session_status_widget.session_info._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        # Should contain session overview
        assert any("Sessions Overview" in text for text in label_texts)
        assert any("Total: 1" in text for text in label_texts)
        
        # Should contain active session details
        assert any("Active Session" in text for text in label_texts)
        # The mock session ID is "test-session-123", which gets shortened to "test-ses..."
        assert any("test-ses" in text for text in label_texts)

    def test_update_session_info_with_errors(self, session_status_widget, mock_session_manager, mock_session_context):
        """Test session info update with session errors."""
        mock_session_context.error_count = 3
        mock_session_context.last_error = "Test error message"
        
        mock_session_manager.get_session_summary.return_value = {
            'total_sessions': 1,
            'active_sessions': 0,
            'waiting_sessions': 0,
            'error_sessions': 1
        }
        mock_session_manager.get_active_session.return_value = mock_session_context
        
        session_status_widget._update_session_info()
        
        # Check that error information is displayed
        labels = [widget for widget in session_status_widget.session_info._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        assert any("Errors: 3" in text for text in label_texts)
        assert any("Test error" in text for text in label_texts)

    def test_format_agent_state(self, session_status_widget):
        """Test agent state formatting."""
        # Test all agent states
        assert "Loading" in session_status_widget._format_agent_state(AgentState.LOADING)
        assert "Ready" in session_status_widget._format_agent_state(AgentState.AWAITING_USER_INPUT)
        assert "Running" in session_status_widget._format_agent_state(AgentState.RUNNING)
        assert "Stopped" in session_status_widget._format_agent_state(AgentState.STOPPED)
        assert "Error" in session_status_widget._format_agent_state(AgentState.ERROR)
        assert "Paused" in session_status_widget._format_agent_state(AgentState.PAUSED)
        assert "Finished" in session_status_widget._format_agent_state(AgentState.FINISHED)
        
        # Test None state
        assert "Unknown" in session_status_widget._format_agent_state(None)

    def test_format_duration(self, session_status_widget):
        """Test duration formatting."""
        # Test seconds
        duration = timedelta(seconds=30)
        assert session_status_widget._format_duration(duration) == "30s"
        
        # Test minutes and seconds
        duration = timedelta(minutes=5, seconds=30)
        assert session_status_widget._format_duration(duration) == "5m 30s"
        
        # Test hours and minutes
        duration = timedelta(hours=2, minutes=30)
        assert session_status_widget._format_duration(duration) == "2h 30m"

    def test_get_sessions_needing_recovery(self, session_status_widget, mock_session_manager):
        """Test identification of sessions needing recovery."""
        # Create sessions with different states
        error_session = MagicMock()
        error_session.agent_state = AgentState.ERROR
        error_session.is_connected = True
        error_session.error_count = 0
        
        disconnected_session = MagicMock()
        disconnected_session.agent_state = AgentState.RUNNING
        disconnected_session.is_connected = False
        disconnected_session.error_count = 0
        
        high_error_session = MagicMock()
        high_error_session.agent_state = AgentState.AWAITING_USER_INPUT
        high_error_session.is_connected = True
        high_error_session.error_count = 10
        
        healthy_session = MagicMock()
        healthy_session.agent_state = AgentState.AWAITING_USER_INPUT
        healthy_session.is_connected = True
        healthy_session.error_count = 0
        
        mock_session_manager.list_sessions.return_value = [
            error_session, disconnected_session, high_error_session, healthy_session
        ]
        
        recovery_sessions = session_status_widget._get_sessions_needing_recovery()
        
        # Should identify 3 sessions needing recovery
        assert len(recovery_sessions) == 3
        assert error_session in recovery_sessions
        assert disconnected_session in recovery_sessions
        assert high_error_session in recovery_sessions
        assert healthy_session not in recovery_sessions

    def test_get_orphaned_sessions(self, session_status_widget, mock_session_manager):
        """Test identification of orphaned sessions."""
        # Create sessions with different activity times
        old_stopped_session = MagicMock()
        old_stopped_session.agent_state = AgentState.STOPPED
        old_stopped_session.last_activity = datetime.now() - timedelta(hours=2)
        
        old_error_session = MagicMock()
        old_error_session.agent_state = AgentState.ERROR
        old_error_session.last_activity = datetime.now() - timedelta(hours=3)
        
        old_running_session = MagicMock()
        old_running_session.agent_state = AgentState.RUNNING
        old_running_session.last_activity = datetime.now() - timedelta(hours=2)
        
        recent_session = MagicMock()
        recent_session.agent_state = AgentState.STOPPED
        recent_session.last_activity = datetime.now() - timedelta(minutes=30)
        
        mock_session_manager.list_sessions.return_value = [
            old_stopped_session, old_error_session, old_running_session, recent_session
        ]
        
        orphaned_sessions = session_status_widget._get_orphaned_sessions()
        
        # Should identify 2 orphaned sessions (old stopped and error sessions)
        assert len(orphaned_sessions) == 2
        assert old_stopped_session in orphaned_sessions
        assert old_error_session in orphaned_sessions
        assert old_running_session not in orphaned_sessions  # Running sessions aren't orphaned
        assert recent_session not in orphaned_sessions  # Recent activity

    def test_get_backup_status(self, session_status_widget, mock_session_manager):
        """Test backup status determination."""
        # Test no sessions
        mock_session_manager.sessions = {}
        status = session_status_widget._get_backup_status()
        assert "No sessions to backup" in status
        
        # Test few sessions
        mock_session_manager.sessions = {"1": None, "2": None}
        status = session_status_widget._get_backup_status()
        assert "Up to date" in status
        
        # Test many sessions
        mock_session_manager.sessions = {str(i): None for i in range(10)}
        status = session_status_widget._get_backup_status()
        assert "Many sessions" in status

    def test_get_status_summary(self, session_status_widget, mock_session_manager, mock_session_context):
        """Test status summary generation."""
        mock_session_manager.get_session_summary.return_value = {
            'total_sessions': 2,
            'active_sessions': 1,
            'error_sessions': 0
        }
        mock_session_manager.get_active_session.return_value = mock_session_context
        
        with patch.object(session_status_widget, '_get_sessions_needing_recovery', return_value=[]), \
             patch.object(session_status_widget, '_get_orphaned_sessions', return_value=[]):
            
            summary = session_status_widget.get_status_summary()
            
            assert summary['total_sessions'] == 2
            assert summary['active_sessions'] == 1
            assert summary['error_sessions'] == 0
            assert summary['has_active_session'] is True
            assert summary['active_session_state'] == AgentState.AWAITING_USER_INPUT.value
            assert summary['active_session_connected'] is True
            assert summary['sessions_needing_recovery'] == 0
            assert summary['orphaned_sessions'] == 0

    def test_update_recovery_info_healthy_sessions(self, session_status_widget, mock_session_manager):
        """Test recovery info update with healthy sessions."""
        mock_session_manager.list_sessions.return_value = []
        
        with patch.object(session_status_widget, '_get_sessions_needing_recovery', return_value=[]):
            session_status_widget._update_recovery_info()
            
            labels = [widget for widget in session_status_widget.recovery_info._widgets if isinstance(widget, ptg.Label)]
            label_texts = [label.value for label in labels]
            
            assert any("All sessions healthy" in text for text in label_texts)

    def test_update_recovery_info_with_issues(self, session_status_widget, mock_session_manager, mock_session_context):
        """Test recovery info update with session issues."""
        mock_session_context.agent_state = AgentState.ERROR
        mock_session_context.is_connected = False
        
        mock_session_manager.list_sessions.return_value = [mock_session_context]
        
        with patch.object(session_status_widget, '_get_sessions_needing_recovery', return_value=[mock_session_context]):
            session_status_widget._update_recovery_info()
            
            labels = [widget for widget in session_status_widget.recovery_info._widgets if isinstance(widget, ptg.Label)]
            label_texts = [label.value for label in labels]
            
            assert any("need recovery" in text for text in label_texts)
            assert any("disconnected session" in text for text in label_texts)

    def test_update_cleanup_info_no_orphans(self, session_status_widget, mock_session_manager):
        """Test cleanup info update with no orphaned sessions."""
        with patch.object(session_status_widget, '_get_orphaned_sessions', return_value=[]), \
             patch.object(session_status_widget, '_get_backup_status', return_value="Up to date"):
            
            session_status_widget._update_cleanup_info()
            
            labels = [widget for widget in session_status_widget.cleanup_info._widgets if isinstance(widget, ptg.Label)]
            label_texts = [label.value for label in labels]
            
            assert any("No cleanup needed" in text for text in label_texts)
            assert any("Up to date" in text for text in label_texts)

    def test_update_cleanup_info_with_orphans(self, session_status_widget, mock_session_manager, mock_session_context):
        """Test cleanup info update with orphaned sessions."""
        mock_session_context.last_activity = datetime.now() - timedelta(hours=2)
        
        with patch.object(session_status_widget, '_get_orphaned_sessions', return_value=[mock_session_context]), \
             patch.object(session_status_widget, '_get_backup_status', return_value="Up to date"):
            
            session_status_widget._update_cleanup_info()
            
            labels = [widget for widget in session_status_widget.cleanup_info._widgets if isinstance(widget, ptg.Label)]
            label_texts = [label.value for label in labels]
            
            assert any("orphaned session" in text for text in label_texts)
            # The mock session ID is "test-session-123", which gets shortened to "test-ses..."
            assert any("test-ses" in text for text in label_texts)


class TestSessionRecoveryWidget:
    """Test cases for SessionRecoveryWidget."""

    def test_initialization(self, session_recovery_widget, mock_session_manager):
        """Test recovery widget initialization."""
        assert session_recovery_widget.session_manager == mock_session_manager
        
        # Check that layout components are created
        assert hasattr(session_recovery_widget, 'recovery_header')
        assert hasattr(session_recovery_widget, 'recovery_controls')
        
        # Check that buttons are created
        buttons = [widget for widget in session_recovery_widget.recovery_controls._widgets if isinstance(widget, ptg.Button)]
        assert len(buttons) == 3
        
        button_labels = [button.label for button in buttons]
        assert any("Reconnect All" in label for label in button_labels)
        assert any("Cleanup Orphaned" in label for label in button_labels)
        assert any("Backup Sessions" in label for label in button_labels)

    def test_reconnect_all_sessions(self, session_recovery_widget, mock_session_manager):
        """Test reconnecting all disconnected sessions."""
        # Create disconnected sessions
        disconnected_session1 = MagicMock()
        disconnected_session1.sid = "session1"
        disconnected_session1.is_connected = False
        
        disconnected_session2 = MagicMock()
        disconnected_session2.sid = "session2"
        disconnected_session2.is_connected = False
        
        connected_session = MagicMock()
        connected_session.sid = "session3"
        connected_session.is_connected = True
        
        mock_session_manager.list_sessions.return_value = [
            disconnected_session1, disconnected_session2, connected_session
        ]
        
        session_recovery_widget._reconnect_all_sessions()
        
        # Should attempt to reconnect only disconnected sessions
        assert mock_session_manager.set_session_connected.call_count == 2
        mock_session_manager.set_session_connected.assert_any_call("session1", True)
        mock_session_manager.set_session_connected.assert_any_call("session2", True)

    def test_reconnect_all_sessions_with_errors(self, session_recovery_widget, mock_session_manager):
        """Test reconnecting sessions with some failures."""
        disconnected_session = MagicMock()
        disconnected_session.sid = "session1"
        disconnected_session.is_connected = False
        
        mock_session_manager.list_sessions.return_value = [disconnected_session]
        mock_session_manager.set_session_connected.side_effect = Exception("Connection failed")
        
        # Should not raise exception even if reconnection fails
        session_recovery_widget._reconnect_all_sessions()
        
        assert mock_session_manager.set_session_connected.called

    def test_cleanup_orphaned_sessions(self, session_recovery_widget, mock_session_manager):
        """Test cleanup of orphaned sessions."""
        # Create orphaned sessions
        orphaned_session1 = MagicMock()
        orphaned_session1.agent_state = AgentState.STOPPED
        orphaned_session1.last_activity = datetime.now() - timedelta(hours=2)
        
        orphaned_session2 = MagicMock()
        orphaned_session2.agent_state = AgentState.ERROR
        orphaned_session2.last_activity = datetime.now() - timedelta(hours=3)
        
        active_session = MagicMock()
        active_session.agent_state = AgentState.RUNNING
        active_session.last_activity = datetime.now() - timedelta(minutes=5)
        
        mock_session_manager.list_sessions.return_value = [
            orphaned_session1, orphaned_session2, active_session
        ]
        
        # Should log cleanup action without raising exceptions
        session_recovery_widget._cleanup_orphaned_sessions()

    def test_backup_sessions(self, session_recovery_widget, mock_session_manager):
        """Test session backup functionality."""
        mock_session_manager.sessions = {"session1": None, "session2": None}
        
        # Should log backup action without raising exceptions
        session_recovery_widget._backup_sessions()


class TestSessionStatusIntegration:
    """Integration tests for session status widgets."""

    def test_status_widget_with_real_session_data(self, mock_session_manager):
        """Test status widget with realistic session data."""
        # Create realistic session contexts
        active_session = MagicMock()
        active_session.sid = "active-session-12345"
        active_session.agent_state = AgentState.RUNNING
        active_session.task_description = "Implement user authentication system"
        active_session.created_at = datetime.now() - timedelta(hours=1)
        active_session.last_activity = datetime.now() - timedelta(minutes=2)
        active_session.error_count = 1
        active_session.last_error = "Connection timeout"
        active_session.is_connected = True
        
        error_session = MagicMock()
        error_session.sid = "error-session-67890"
        error_session.agent_state = AgentState.ERROR
        error_session.task_description = "Debug database connection"
        error_session.created_at = datetime.now() - timedelta(hours=2)
        error_session.last_activity = datetime.now() - timedelta(hours=1)
        error_session.error_count = 5
        error_session.last_error = "Database connection failed"
        error_session.is_connected = False
        
        mock_session_manager.list_sessions.return_value = [active_session, error_session]
        mock_session_manager.get_active_session.return_value = active_session
        mock_session_manager.active_session_id = active_session.sid
        mock_session_manager.get_session_summary.return_value = {
            'total_sessions': 2,
            'active_sessions': 1,
            'waiting_sessions': 0,
            'error_sessions': 1
        }
        
        widget = SessionStatusWidget(mock_session_manager)
        
        # Force update
        widget.last_update = 0
        widget.update_display()
        
        # Verify status summary
        summary = widget.get_status_summary()
        assert summary['total_sessions'] == 2
        assert summary['has_active_session'] is True
        assert summary['sessions_needing_recovery'] == 1  # error_session
        
        # Verify recovery widget functionality
        recovery_widget = SessionRecoveryWidget(mock_session_manager)
        recovery_widget._reconnect_all_sessions()
        
        # Should attempt to reconnect the disconnected session
        mock_session_manager.set_session_connected.assert_called_with(error_session.sid, True)

    def test_widget_error_handling(self, session_status_widget, mock_session_manager):
        """Test widget behavior when session manager methods fail."""
        # Make session manager methods raise exceptions
        mock_session_manager.get_session_summary.side_effect = Exception("Manager error")
        mock_session_manager.get_active_session.side_effect = Exception("Manager error")
        mock_session_manager.list_sessions.side_effect = Exception("Manager error")
        
        # Widget should handle errors gracefully
        session_status_widget.update_display()
        
        # Should not raise exceptions
        summary = session_status_widget.get_status_summary()
        assert isinstance(summary, dict)

    def test_widget_performance_with_many_sessions(self, mock_session_manager):
        """Test widget performance with many sessions."""
        # Create many sessions
        sessions = []
        for i in range(50):
            session = MagicMock()
            session.sid = f"session-{i}"
            session.agent_state = AgentState.AWAITING_USER_INPUT if i % 2 == 0 else AgentState.RUNNING
            session.task_description = f"Task {i}"
            session.created_at = datetime.now() - timedelta(hours=i)
            session.last_activity = datetime.now() - timedelta(minutes=i)
            session.error_count = i % 3
            session.last_error = f"Error {i}" if i % 3 > 0 else None
            session.is_connected = i % 4 != 0
            sessions.append(session)
        
        mock_session_manager.list_sessions.return_value = sessions
        mock_session_manager.get_active_session.return_value = sessions[0]
        mock_session_manager.get_session_summary.return_value = {
            'total_sessions': 50,
            'active_sessions': 25,
            'waiting_sessions': 25,
            'error_sessions': 0
        }
        
        widget = SessionStatusWidget(mock_session_manager)
        
        # Measure update time
        start_time = time.time()
        widget.last_update = 0
        widget.update_display()
        end_time = time.time()
        
        # Should complete quickly even with many sessions
        assert end_time - start_time < 1.0  # Less than 1 second
        
        # Should still provide accurate summary
        summary = widget.get_status_summary()
        assert summary['total_sessions'] == 50 