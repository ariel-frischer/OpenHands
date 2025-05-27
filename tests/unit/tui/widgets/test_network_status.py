"""Tests for Network Status Widget.

Unit tests for the TUI network status widget with mocked network states and session management.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytermgui as ptg

from openhands.core.schema import AgentState
from openhands.tui.widgets.network_status import (
    NetworkReconnectionWidget,
    NetworkStatusWidget,
)


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager for testing."""
    manager = MagicMock()
    manager.list_sessions.return_value = []
    manager.get_active_session.return_value = None
    manager.get_session_health.return_value = {"healthy": True}
    manager.set_session_connected = MagicMock()
    return manager


@pytest.fixture
def mock_event_manager():
    """Create a mock event manager for testing."""
    manager = MagicMock()
    manager.validate_session_connection.return_value = True
    manager.subscribe_to_session = MagicMock()
    return manager


@pytest.fixture
def mock_session_context():
    """Create a mock session context for testing."""
    session = MagicMock()
    session.sid = "test-network-session-789"
    session.agent_state = AgentState.AWAITING_USER_INPUT
    session.is_connected = True
    session.error_count = 0
    session.last_error = None
    return session


@pytest.fixture
def network_status_widget(mock_session_manager, mock_event_manager):
    """Create a network status widget for testing."""
    return NetworkStatusWidget(mock_session_manager, mock_event_manager)


@pytest.fixture
def network_reconnection_widget(mock_session_manager, mock_event_manager):
    """Create a network reconnection widget for testing."""
    return NetworkReconnectionWidget(mock_session_manager, mock_event_manager)


class TestNetworkStatusWidget:
    """Test cases for NetworkStatusWidget."""

    def test_initialization(self, network_status_widget, mock_session_manager, mock_event_manager):
        """Test network status widget initialization."""
        assert network_status_widget.session_manager == mock_session_manager
        assert network_status_widget.event_manager == mock_event_manager
        assert network_status_widget.update_interval == 3.0
        assert network_status_widget.max_history == 20
        # Connection history starts empty (no connectivity checks during init)
        assert len(network_status_widget.connection_history) == 0
        
        # Check that containers are created
        assert hasattr(network_status_widget, 'connection_status')
        assert hasattr(network_status_widget, 'session_connections')
        assert hasattr(network_status_widget, 'reconnection_status')

    def test_update_display_throttling(self, network_status_widget):
        """Test that display updates are throttled."""
        with patch.object(network_status_widget, '_update_connection_status') as mock_conn, \
             patch.object(network_status_widget, '_update_session_connections') as mock_sessions, \
             patch.object(network_status_widget, '_update_reconnection_status') as mock_reconnect:
            
            # First update should work
            network_status_widget.last_update = 0
            network_status_widget.update_display()
            assert mock_conn.called
            assert mock_sessions.called
            assert mock_reconnect.called
            
            # Reset mocks
            mock_conn.reset_mock()
            mock_sessions.reset_mock()
            mock_reconnect.reset_mock()
            
            # Immediate second update should be throttled
            network_status_widget.update_display()
            assert not mock_conn.called
            assert not mock_sessions.called
            assert not mock_reconnect.called

    def test_check_overall_connectivity_with_active_session(self, network_status_widget, mock_session_manager, mock_session_context):
        """Test connectivity check with active session."""
        # Clear any existing history from initialization
        network_status_widget.connection_history.clear()
        
        mock_session_manager.get_active_session.return_value = mock_session_context
        mock_session_manager.get_session_health.return_value = {"healthy": True}
        
        result = network_status_widget._check_overall_connectivity()
        
        assert result["connected"] is True
        assert result["error"] is None
        assert result["check_time"] > 0
        assert len(network_status_widget.connection_history) == 1

    def test_check_overall_connectivity_with_unhealthy_session(self, network_status_widget, mock_session_manager, mock_session_context):
        """Test connectivity check with unhealthy session."""
        mock_session_manager.get_active_session.return_value = mock_session_context
        mock_session_manager.get_session_health.return_value = {"healthy": False, "reason": "Connection timeout"}
        
        result = network_status_widget._check_overall_connectivity()
        
        assert result["connected"] is False
        assert result["error"] == "Connection timeout"
        assert result["check_time"] > 0

    def test_check_overall_connectivity_no_active_session(self, network_status_widget, mock_session_manager):
        """Test connectivity check with no active session."""
        mock_session_manager.get_active_session.return_value = None
        
        result = network_status_widget._check_overall_connectivity()
        
        assert result["connected"] is True
        assert result["error"] is None
        assert result["check_time"] > 0

    def test_check_overall_connectivity_exception(self, network_status_widget, mock_session_manager):
        """Test connectivity check with exception."""
        mock_session_manager.get_active_session.side_effect = Exception("Network error")
        
        result = network_status_widget._check_overall_connectivity()
        
        assert result["connected"] is False
        assert "Network error" in result["error"]
        assert result["check_time"] > 0

    def test_get_connection_quality(self, network_status_widget):
        """Test connection quality determination."""
        assert network_status_widget._get_connection_quality(25) == "Excellent"
        assert network_status_widget._get_connection_quality(75) == "Good"
        assert network_status_widget._get_connection_quality(150) == "Fair"
        assert network_status_widget._get_connection_quality(300) == "Poor"
        assert network_status_widget._get_connection_quality(600) == "Very Poor"

    def test_get_quality_color(self, network_status_widget):
        """Test quality color determination."""
        assert network_status_widget._get_quality_color("Excellent") == "green"
        assert network_status_widget._get_quality_color("Good") == "green"
        assert network_status_widget._get_quality_color("Fair") == "yellow"
        assert network_status_widget._get_quality_color("Poor") == "orange"
        assert network_status_widget._get_quality_color("Very Poor") == "red"
        assert network_status_widget._get_quality_color("Unknown") == "white"

    def test_calculate_success_rate(self, network_status_widget):
        """Test success rate calculation."""
        # Clear any existing history and test with no history
        network_status_widget.connection_history.clear()
        assert network_status_widget._calculate_success_rate() == 0.0
        
        # Add test history
        network_status_widget.connection_history = [
            {"connected": True},
            {"connected": False},
            {"connected": True},
            {"connected": True},
        ]
        
        assert network_status_widget._calculate_success_rate() == 75.0

    def test_calculate_average_latency(self, network_status_widget):
        """Test average latency calculation."""
        # Clear any existing history and test with no history
        network_status_widget.connection_history.clear()
        assert network_status_widget._calculate_average_latency() == 0.0
        
        # Add test history
        network_status_widget.connection_history = [
            {"connected": True, "check_time": 50},
            {"connected": False, "check_time": 200},  # Should be ignored
            {"connected": True, "check_time": 100},
            {"connected": True, "check_time": 150},
        ]
        
        assert network_status_widget._calculate_average_latency() == 100.0

    def test_get_session_status_display(self, network_status_widget, mock_session_context):
        """Test session status display formatting."""
        # Test different states
        mock_session_context.agent_state = AgentState.ERROR
        icon, color = network_status_widget._get_session_status_display(mock_session_context)
        assert icon == "❌"
        assert color == "red"
        
        mock_session_context.agent_state = AgentState.RUNNING
        mock_session_context.is_connected = True
        icon, color = network_status_widget._get_session_status_display(mock_session_context)
        assert icon == "🟢"
        assert color == "blue"
        
        mock_session_context.agent_state = AgentState.AWAITING_USER_INPUT
        icon, color = network_status_widget._get_session_status_display(mock_session_context)
        assert icon == "🟢"
        assert color == "green"
        
        mock_session_context.agent_state = AgentState.LOADING
        icon, color = network_status_widget._get_session_status_display(mock_session_context)
        assert icon == "🟡"
        assert color == "yellow"
        
        mock_session_context.is_connected = False
        icon, color = network_status_widget._get_session_status_display(mock_session_context)
        assert icon == "🔴"
        assert color == "yellow"

    def test_update_connection_status_online(self, network_status_widget):
        """Test connection status update when online."""
        with patch.object(network_status_widget, '_check_overall_connectivity') as mock_check:
            mock_check.return_value = {"connected": True, "check_time": 50, "error": None}
            
            # Add some history for statistics
            network_status_widget.connection_history = [
                {"connected": True, "check_time": 40},
                {"connected": True, "check_time": 60},
            ]
            
            network_status_widget._update_connection_status()
            
            labels = [widget for widget in network_status_widget.connection_status._widgets if isinstance(widget, ptg.Label)]
            label_texts = [label.value for label in labels]
            
            assert any("System Online" in text for text in label_texts)
            assert any("Connection Quality" in text for text in label_texts)
            assert any("Success Rate" in text for text in label_texts)

    def test_update_connection_status_offline(self, network_status_widget):
        """Test connection status update when offline."""
        with patch.object(network_status_widget, '_check_overall_connectivity') as mock_check:
            mock_check.return_value = {"connected": False, "check_time": 1000, "error": "Network unreachable"}
            
            network_status_widget._update_connection_status()
            
            labels = [widget for widget in network_status_widget.connection_status._widgets if isinstance(widget, ptg.Label)]
            label_texts = [label.value for label in labels]
            
            assert any("System Offline" in text for text in label_texts)
            assert any("Network unreachable" in text for text in label_texts)

    def test_update_session_connections_no_sessions(self, network_status_widget, mock_session_manager):
        """Test session connections update with no sessions."""
        mock_session_manager.list_sessions.return_value = []
        
        network_status_widget._update_session_connections()
        
        labels = [widget for widget in network_status_widget.session_connections._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        assert any("No sessions to monitor" in text for text in label_texts)

    def test_update_session_connections_with_sessions(self, network_status_widget, mock_session_manager, mock_event_manager):
        """Test session connections update with sessions."""
        # Create test sessions
        session1 = MagicMock()
        session1.sid = "session-1-connected"
        session1.agent_state = AgentState.RUNNING
        session1.is_connected = True
        
        session2 = MagicMock()
        session2.sid = "session-2-disconnected"
        session2.agent_state = AgentState.AWAITING_USER_INPUT
        session2.is_connected = False
        
        session3 = MagicMock()
        session3.sid = "session-3-error"
        session3.agent_state = AgentState.ERROR
        session3.is_connected = False
        
        mock_session_manager.list_sessions.return_value = [session1, session2, session3]
        mock_event_manager.validate_session_connection.return_value = True
        
        network_status_widget._update_session_connections()
        
        labels = [widget for widget in network_status_widget.session_connections._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        # Should show summary (check for the actual format)
        assert any("Connected:" in text and "1" in text for text in label_texts)
        assert any("Disconnected:" in text and "1" in text for text in label_texts)
        assert any("Errors:" in text and "1" in text for text in label_texts)
        
        # Should show individual sessions (IDs get shortened to 8 chars + "...")
        assert any("session-" in text for text in label_texts)
        # Check that we have at least 3 session entries (one for each session)
        session_entries = [text for text in label_texts if "session-" in text]
        assert len(session_entries) >= 3

    def test_get_sessions_needing_reconnection(self, network_status_widget, mock_session_manager, mock_event_manager):
        """Test getting sessions that need reconnection."""
        # Create test sessions
        healthy_session = MagicMock()
        healthy_session.agent_state = AgentState.AWAITING_USER_INPUT
        healthy_session.is_connected = True
        healthy_session.error_count = 1
        
        disconnected_session = MagicMock()
        disconnected_session.agent_state = AgentState.RUNNING
        disconnected_session.is_connected = False
        disconnected_session.error_count = 0
        
        error_session = MagicMock()
        error_session.agent_state = AgentState.ERROR
        error_session.is_connected = True
        error_session.error_count = 2
        
        high_error_session = MagicMock()
        high_error_session.agent_state = AgentState.AWAITING_USER_INPUT
        high_error_session.is_connected = True
        high_error_session.error_count = 5
        
        mock_session_manager.list_sessions.return_value = [
            healthy_session, disconnected_session, error_session, high_error_session
        ]
        mock_event_manager.validate_session_connection.return_value = True
        
        sessions_needing_reconnection = network_status_widget._get_sessions_needing_reconnection()
        
        # Should include disconnected, error, and high error count sessions
        assert len(sessions_needing_reconnection) == 3
        assert disconnected_session in sessions_needing_reconnection
        assert error_session in sessions_needing_reconnection
        assert high_error_session in sessions_needing_reconnection
        assert healthy_session not in sessions_needing_reconnection

    def test_get_reconnection_reason(self, network_status_widget, mock_session_context, mock_event_manager):
        """Test getting reconnection reason for sessions."""
        # Test different reasons
        mock_session_context.agent_state = AgentState.ERROR
        assert network_status_widget._get_reconnection_reason(mock_session_context) == "Error state"
        
        mock_session_context.agent_state = AgentState.RUNNING
        mock_session_context.is_connected = False
        assert network_status_widget._get_reconnection_reason(mock_session_context) == "Disconnected"
        
        mock_session_context.is_connected = True
        mock_session_context.error_count = 5
        assert "High error count" in network_status_widget._get_reconnection_reason(mock_session_context)
        
        mock_session_context.error_count = 1
        mock_event_manager.validate_session_connection.return_value = False
        assert network_status_widget._get_reconnection_reason(mock_session_context) == "Event stream invalid"

    def test_update_reconnection_status_all_stable(self, network_status_widget):
        """Test reconnection status update when all sessions are stable."""
        with patch.object(network_status_widget, '_get_sessions_needing_reconnection', return_value=[]):
            network_status_widget._update_reconnection_status()
            
            labels = [widget for widget in network_status_widget.reconnection_status._widgets if isinstance(widget, ptg.Label)]
            label_texts = [label.value for label in labels]
            
            assert any("All sessions stable" in text for text in label_texts)

    def test_update_reconnection_status_with_issues(self, network_status_widget):
        """Test reconnection status update with sessions needing attention."""
        mock_session = MagicMock()
        mock_session.sid = "problematic-session-123"
        
        with patch.object(network_status_widget, '_get_sessions_needing_reconnection', return_value=[mock_session]), \
             patch.object(network_status_widget, '_get_reconnection_reason', return_value="Test reason"):
            
            network_status_widget._update_reconnection_status()
            
            labels = [widget for widget in network_status_widget.reconnection_status._widgets if isinstance(widget, ptg.Label)]
            label_texts = [label.value for label in labels]
            
            assert any("need attention" in text for text in label_texts)
            # Session ID gets shortened to 8 chars + "..."
            assert any("problema" in text for text in label_texts)
            assert any("Test reason" in text for text in label_texts)
            assert any("Press 'r'" in text for text in label_texts)

    def test_attempt_reconnect_all_no_sessions(self, network_status_widget):
        """Test reconnect all when no sessions need reconnection."""
        with patch.object(network_status_widget, '_get_sessions_needing_reconnection', return_value=[]):
            network_status_widget.attempt_reconnect_all()
            # Should not raise any errors

    def test_attempt_reconnect_all_with_sessions(self, network_status_widget, mock_session_manager, mock_event_manager):
        """Test reconnect all with sessions needing reconnection."""
        mock_session = MagicMock()
        mock_session.sid = "test-session-reconnect"
        
        with patch.object(network_status_widget, '_get_sessions_needing_reconnection', return_value=[mock_session]):
            network_status_widget.attempt_reconnect_all()
            
            # Should call session manager methods
            mock_session_manager.set_session_connected.assert_called_with("test-session-reconnect", True)
            mock_event_manager.subscribe_to_session.assert_called_with("test-session-reconnect")

    def test_get_network_summary(self, network_status_widget):
        """Test getting network summary."""
        with patch.object(network_status_widget, '_check_overall_connectivity') as mock_check, \
             patch.object(network_status_widget, '_get_sessions_needing_reconnection') as mock_sessions:
            
            mock_check.return_value = {"connected": True, "check_time": 75}
            mock_sessions.return_value = [MagicMock(), MagicMock()]  # 2 sessions
            
            summary = network_status_widget.get_network_summary()
            
            assert summary["system_online"] is True
            assert summary["connection_quality"] == "Good"
            assert summary["sessions_needing_reconnection"] == 2
            assert "last_check" in summary

    def test_get_network_summary_error(self, network_status_widget):
        """Test getting network summary with error."""
        with patch.object(network_status_widget, '_check_overall_connectivity', side_effect=Exception("Test error")):
            summary = network_status_widget.get_network_summary()
            
            assert summary["system_online"] is False
            assert summary["connection_quality"] == "Error"
            assert "error" in summary

    def test_handle_key_event_reconnect(self, network_status_widget):
        """Test handling 'r' key event for reconnection."""
        with patch.object(network_status_widget, 'attempt_reconnect_all') as mock_reconnect:
            result = network_status_widget.handle_key_event("r")
            
            assert result is True
            mock_reconnect.assert_called_once()

    def test_handle_key_event_refresh(self, network_status_widget):
        """Test handling 'n' key event for refresh."""
        network_status_widget.last_update = time.time()
        
        result = network_status_widget.handle_key_event("n")
        
        assert result is True
        assert network_status_widget.last_update == 0

    def test_handle_key_event_unknown(self, network_status_widget):
        """Test handling unknown key event."""
        result = network_status_widget.handle_key_event("x")
        assert result is False

    def test_connection_history_limit(self, network_status_widget):
        """Test that connection history is limited to max_history."""
        # Clear existing history first
        network_status_widget.connection_history.clear()
        
        # Add entries up to the limit
        for i in range(network_status_widget.max_history):
            network_status_widget.connection_history.append({
                "timestamp": datetime.now(),
                "connected": True,
                "check_time": i,
                "error": None,
            })
        
        # Verify we're at the limit
        assert len(network_status_widget.connection_history) == network_status_widget.max_history
        
        # Add one more entry via connectivity check to trigger limit enforcement
        with patch.object(network_status_widget.session_manager, 'get_active_session', return_value=None):
            network_status_widget._check_overall_connectivity()
        
        # Should still be at max_history (oldest entry removed, new one added)
        assert len(network_status_widget.connection_history) == network_status_widget.max_history


class TestNetworkReconnectionWidget:
    """Test cases for NetworkReconnectionWidget."""

    def test_initialization(self, network_reconnection_widget, mock_session_manager, mock_event_manager):
        """Test network reconnection widget initialization."""
        assert network_reconnection_widget.session_manager == mock_session_manager
        assert network_reconnection_widget.event_manager == mock_event_manager
        assert network_reconnection_widget.reconnection_attempts == {}
        assert network_reconnection_widget.last_reconnection_time == 0
        
        # Check that containers are created
        assert hasattr(network_reconnection_widget, 'reconnection_controls')
        assert hasattr(network_reconnection_widget, 'reconnection_log')

    def test_update_reconnection_controls(self, network_reconnection_widget):
        """Test reconnection controls update."""
        network_reconnection_widget._update_reconnection_controls()
        
        labels = [widget for widget in network_reconnection_widget.reconnection_controls._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        assert any("Available Actions" in text for text in label_texts)
        assert any("'r' - Reconnect all sessions" in text for text in label_texts)
        assert any("'c' - Clear reconnection log" in text for text in label_texts)
        assert any("'s' - Show session health details" in text for text in label_texts)

    def test_update_reconnection_controls_with_last_attempt(self, network_reconnection_widget):
        """Test reconnection controls update with last attempt time."""
        network_reconnection_widget.last_reconnection_time = time.time() - 30  # 30 seconds ago
        
        network_reconnection_widget._update_reconnection_controls()
        
        labels = [widget for widget in network_reconnection_widget.reconnection_controls._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        assert any("Last reconnection attempt" in text for text in label_texts)

    def test_update_reconnection_log_empty(self, network_reconnection_widget):
        """Test reconnection log update when empty."""
        network_reconnection_widget._update_reconnection_log()
        
        labels = [widget for widget in network_reconnection_widget.reconnection_log._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        assert any("No reconnection attempts yet" in text for text in label_texts)

    def test_update_reconnection_log_with_attempts(self, network_reconnection_widget):
        """Test reconnection log update with attempts."""
        # Add test attempts
        network_reconnection_widget.reconnection_attempts = {
            "session-1": {
                "timestamp": datetime.now(),
                "success": True,
            },
            "session-2": {
                "timestamp": datetime.now(),
                "success": False,
                "error": "Connection failed",
            },
        }
        
        network_reconnection_widget._update_reconnection_log()
        
        labels = [widget for widget in network_reconnection_widget.reconnection_log._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        # Should show both attempts
        assert any("session-1" in text for text in label_texts)
        assert any("session-2" in text for text in label_texts)
        assert any("Connection failed" in text for text in label_texts)

    def test_attempt_session_reconnection_success(self, network_reconnection_widget, mock_session_manager, mock_event_manager):
        """Test successful session reconnection."""
        mock_event_manager.validate_session_connection.return_value = True
        
        result = network_reconnection_widget.attempt_session_reconnection("test-session")
        
        assert result is True
        assert "test-session" in network_reconnection_widget.reconnection_attempts
        assert network_reconnection_widget.reconnection_attempts["test-session"]["success"] is True
        assert network_reconnection_widget.last_reconnection_time > 0
        
        # Should call session manager methods
        mock_session_manager.set_session_connected.assert_called_with("test-session", True)
        mock_event_manager.subscribe_to_session.assert_called_with("test-session")

    def test_attempt_session_reconnection_failure(self, network_reconnection_widget, mock_session_manager, mock_event_manager):
        """Test failed session reconnection."""
        mock_session_manager.set_session_connected.side_effect = Exception("Reconnection failed")
        
        result = network_reconnection_widget.attempt_session_reconnection("test-session")
        
        assert result is False
        assert "test-session" in network_reconnection_widget.reconnection_attempts
        assert network_reconnection_widget.reconnection_attempts["test-session"]["success"] is False
        assert "Reconnection failed" in network_reconnection_widget.reconnection_attempts["test-session"]["error"]

    def test_attempt_session_reconnection_validation_failure(self, network_reconnection_widget, mock_session_manager, mock_event_manager):
        """Test session reconnection with validation failure."""
        mock_event_manager.validate_session_connection.return_value = False
        
        result = network_reconnection_widget.attempt_session_reconnection("test-session")
        
        assert result is False
        assert "test-session" in network_reconnection_widget.reconnection_attempts
        assert network_reconnection_widget.reconnection_attempts["test-session"]["success"] is False
        assert "Event stream validation failed" in network_reconnection_widget.reconnection_attempts["test-session"]["error"]

    def test_clear_reconnection_log(self, network_reconnection_widget):
        """Test clearing reconnection log."""
        # Add test data
        network_reconnection_widget.reconnection_attempts = {"test": {"data": "value"}}
        
        network_reconnection_widget.clear_reconnection_log()
        
        assert network_reconnection_widget.reconnection_attempts == {}

    def test_handle_key_event_clear_log(self, network_reconnection_widget):
        """Test handling 'c' key event for clearing log."""
        with patch.object(network_reconnection_widget, 'clear_reconnection_log') as mock_clear:
            result = network_reconnection_widget.handle_key_event("c")
            
            assert result is True
            mock_clear.assert_called_once()

    def test_handle_key_event_show_health(self, network_reconnection_widget):
        """Test handling 's' key event for showing health details."""
        with patch.object(network_reconnection_widget, '_log_session_health_details') as mock_log:
            result = network_reconnection_widget.handle_key_event("s")
            
            assert result is True
            mock_log.assert_called_once()

    def test_handle_key_event_unknown(self, network_reconnection_widget):
        """Test handling unknown key event."""
        result = network_reconnection_widget.handle_key_event("x")
        assert result is False

    def test_log_session_health_details(self, network_reconnection_widget, mock_session_manager):
        """Test logging session health details."""
        mock_session = MagicMock()
        mock_session.sid = "test-session-health"
        mock_session_manager.list_sessions.return_value = [mock_session]
        mock_session_manager.get_session_health.return_value = {"healthy": True, "checks": {}}
        
        # Should not raise any errors
        network_reconnection_widget._log_session_health_details()
        
        # Should call session manager methods
        mock_session_manager.list_sessions.assert_called_once()
        mock_session_manager.get_session_health.assert_called_with("test-session-health")

    def test_log_session_health_details_error(self, network_reconnection_widget, mock_session_manager):
        """Test logging session health details with error."""
        mock_session_manager.list_sessions.side_effect = Exception("Health check failed")
        
        # Should not raise any errors
        network_reconnection_widget._log_session_health_details()


class TestNetworkStatusIntegration:
    """Integration tests for network status widgets."""

    def test_network_status_widget_with_real_session_data(self, mock_session_manager, mock_event_manager):
        """Test network status widget with realistic session data."""
        # Create realistic session contexts
        active_session = MagicMock()
        active_session.sid = "active-network-session"
        active_session.agent_state = AgentState.RUNNING
        active_session.is_connected = True
        active_session.error_count = 0
        
        disconnected_session = MagicMock()
        disconnected_session.sid = "disconnected-network-session"
        disconnected_session.agent_state = AgentState.AWAITING_USER_INPUT
        disconnected_session.is_connected = False
        disconnected_session.error_count = 2
        
        mock_session_manager.list_sessions.return_value = [active_session, disconnected_session]
        mock_session_manager.get_active_session.return_value = active_session
        mock_session_manager.get_session_health.return_value = {"healthy": True}
        mock_event_manager.validate_session_connection.return_value = True
        
        widget = NetworkStatusWidget(mock_session_manager, mock_event_manager)
        
        # Force update
        widget.last_update = 0
        widget.update_display()
        
        # Verify network summary
        summary = widget.get_network_summary()
        assert summary['system_online'] is True
        assert summary['sessions_needing_reconnection'] == 1  # disconnected_session

    def test_widget_error_handling(self, mock_session_manager, mock_event_manager):
        """Test widget behavior when session manager methods fail."""
        # Make session manager methods raise exceptions
        mock_session_manager.list_sessions.side_effect = Exception("Manager error")
        mock_session_manager.get_active_session.side_effect = Exception("Manager error")
        
        widget = NetworkStatusWidget(mock_session_manager, mock_event_manager)
        
        # Widget should handle errors gracefully
        widget.update_display()
        
        # Should not raise exceptions
        summary = widget.get_network_summary()
        assert isinstance(summary, dict)
        # When session manager fails, system should be offline but no explicit error field
        assert summary["system_online"] is False

    def test_performance_with_many_sessions(self, mock_session_manager, mock_event_manager):
        """Test network status widget performance with many sessions."""
        # Create many sessions
        sessions = []
        for i in range(50):
            session = MagicMock()
            session.sid = f"session-{i}"
            session.agent_state = AgentState.AWAITING_USER_INPUT if i % 2 == 0 else AgentState.RUNNING
            session.is_connected = i % 3 != 0  # Some disconnected
            session.error_count = i % 5  # Varying error counts
            sessions.append(session)
        
        mock_session_manager.list_sessions.return_value = sessions
        mock_session_manager.get_active_session.return_value = sessions[0]
        mock_session_manager.get_session_health.return_value = {"healthy": True}
        mock_event_manager.validate_session_connection.return_value = True
        
        widget = NetworkStatusWidget(mock_session_manager, mock_event_manager)
        
        # Measure update time
        start_time = time.time()
        widget.last_update = 0
        widget.update_display()
        end_time = time.time()
        
        # Should complete quickly even with many sessions
        assert end_time - start_time < 1.0  # Less than 1 second
        
        # Should display limited number of sessions for readability
        session_labels = [w for w in widget.session_connections._widgets if isinstance(w, ptg.Label)]
        session_texts = [label.value for label in session_labels]
        
        # Should show summary counts
        assert any("Connected:" in text for text in session_texts)
        assert any("Disconnected:" in text for text in session_texts)
        
        # Should limit individual session display
        individual_sessions = [text for text in session_texts if "session-" in text]
        assert len(individual_sessions) <= 6  # Max 5 sessions + "... and X more" 