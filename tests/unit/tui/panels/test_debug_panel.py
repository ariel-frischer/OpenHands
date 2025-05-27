"""Tests for Debug Panel.

Unit tests for the TUI debug panel with mocked performance data and session management.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytermgui as ptg

from openhands.core.schema import AgentState
from openhands.tui.panels.debug_panel import (
    AsyncOperationTracker,
    DebugPanel,
    PerformanceMonitor,
)


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager for testing."""
    manager = MagicMock()
    manager.sessions = {}
    manager.active_session_id = None
    return manager


@pytest.fixture
def mock_file_manager():
    """Create a mock file manager for testing."""
    return MagicMock()


@pytest.fixture
def mock_session_context():
    """Create a mock session context for testing."""
    session = MagicMock()
    session.sid = "test-debug-session-456"
    session.agent_state = AgentState.RUNNING
    session.task_description = "Debug test task"
    session.created_at = datetime.now() - timedelta(minutes=15)
    session.last_activity = datetime.now() - timedelta(minutes=2)
    session.error_count = 2
    session.last_error = "Test debug error"
    session.is_connected = True
    return session


@pytest.fixture
def mock_system_stats():
    """Create mock system stats data."""
    return {
        "cpu_percent": 25.5,
        "memory": {
            "rss": 512 * 1024 * 1024,  # 512 MB in bytes
            "vms": 1024 * 1024 * 1024,  # 1 GB in bytes
            "percent": 15.2,
        },
        "disk": {
            "total": 100 * 1024**3,  # 100 GB
            "used": 60 * 1024**3,    # 60 GB
            "free": 40 * 1024**3,    # 40 GB
            "percent": 60.0,
        },
        "io": {
            "read_bytes": 1024 * 1024 * 100,   # 100 MB
            "write_bytes": 1024 * 1024 * 50,   # 50 MB
        },
    }


@pytest.fixture
def performance_monitor():
    """Create a performance monitor for testing."""
    return PerformanceMonitor(max_history=10)


@pytest.fixture
def async_tracker():
    """Create an async operation tracker for testing."""
    return AsyncOperationTracker()


@pytest.fixture
def debug_panel(mock_session_manager, mock_file_manager):
    """Create a debug panel for testing."""
    return DebugPanel(mock_session_manager, mock_file_manager)


class TestPerformanceMonitor:
    """Test cases for PerformanceMonitor."""

    def test_initialization(self, performance_monitor):
        """Test performance monitor initialization."""
        assert performance_monitor.max_history == 10
        assert performance_monitor.performance_history == []
        assert performance_monitor.update_interval == 1.0
        assert performance_monitor.last_update == 0
        assert performance_monitor.start_time > 0

    @patch('openhands.tui.panels.debug_panel.get_system_stats')
    def test_update_metrics(self, mock_get_stats, performance_monitor, mock_system_stats):
        """Test metrics update functionality."""
        mock_get_stats.return_value = mock_system_stats
        
        metrics = performance_monitor.update_metrics()
        
        assert metrics is not None
        assert "timestamp" in metrics
        assert "uptime" in metrics
        assert "cpu_percent" in metrics
        assert "memory_mb" in metrics
        assert "memory_percent" in metrics
        assert "disk_used_gb" in metrics
        assert "disk_free_gb" in metrics
        assert "disk_percent" in metrics
        assert "io_read_mb" in metrics
        assert "io_write_mb" in metrics
        
        # Check calculated values
        assert metrics["cpu_percent"] == 25.5
        assert metrics["memory_mb"] == 512.0  # 512 MB
        assert metrics["memory_percent"] == 15.2
        assert metrics["disk_used_gb"] == 60.0  # 60 GB
        assert metrics["disk_free_gb"] == 40.0  # 40 GB
        assert metrics["disk_percent"] == 60.0
        assert metrics["io_read_mb"] == 100.0  # 100 MB
        assert metrics["io_write_mb"] == 50.0   # 50 MB
        
        # Check that metrics are added to history
        assert len(performance_monitor.performance_history) == 1

    def test_update_metrics_throttling(self, performance_monitor):
        """Test that metrics updates are throttled."""
        with patch('openhands.tui.panels.debug_panel.get_system_stats') as mock_get_stats:
            mock_get_stats.return_value = {"cpu_percent": 10, "memory": {"rss": 100, "percent": 5}, 
                                         "disk": {"used": 1, "free": 1, "percent": 1}, 
                                         "io": {"read_bytes": 1, "write_bytes": 1}}
            
            # First call should update
            metrics1 = performance_monitor.update_metrics()
            assert mock_get_stats.called
            
            # Reset mock
            mock_get_stats.reset_mock()
            
            # Immediate second call should be throttled
            metrics2 = performance_monitor.update_metrics()
            assert not mock_get_stats.called
            assert metrics1 == metrics2

    @patch('openhands.tui.panels.debug_panel.get_system_stats')
    def test_update_metrics_error_handling(self, mock_get_stats, performance_monitor):
        """Test error handling in metrics update."""
        mock_get_stats.side_effect = Exception("System stats error")
        
        metrics = performance_monitor.update_metrics()
        
        # Should return empty dict or latest metrics on error
        assert metrics == {} or metrics is None

    def test_get_latest_metrics(self, performance_monitor):
        """Test getting latest metrics."""
        # No metrics initially
        assert performance_monitor.get_latest_metrics() is None
        
        # Add a metric
        test_metric = {"timestamp": datetime.now(), "cpu_percent": 50}
        performance_monitor.performance_history.append(test_metric)
        
        latest = performance_monitor.get_latest_metrics()
        assert latest == test_metric

    def test_get_average_metrics(self, performance_monitor):
        """Test calculating average metrics."""
        # No metrics initially
        assert performance_monitor.get_average_metrics() == {}
        
        # Add test metrics
        now = datetime.now()
        for i in range(5):
            metric = {
                "timestamp": now - timedelta(minutes=i),
                "cpu_percent": 10 + i * 10,
                "memory_mb": 100 + i * 50,
                "memory_percent": 5 + i * 5,
                "disk_percent": 20 + i * 10,
            }
            performance_monitor.performance_history.append(metric)
        
        averages = performance_monitor.get_average_metrics(10)  # 10 minutes
        
        assert "cpu_percent" in averages
        assert "memory_mb" in averages
        assert "memory_percent" in averages
        assert "disk_percent" in averages
        
        # Check that averages are calculated correctly
        assert averages["cpu_percent"] == 30.0  # (10+20+30+40+50)/5
        assert averages["memory_mb"] == 200.0   # (100+150+200+250+300)/5

    @patch('openhands.tui.panels.debug_panel.get_system_stats')
    def test_history_limit(self, mock_get_stats, performance_monitor):
        """Test that performance history is limited."""
        mock_get_stats.return_value = {
            "cpu_percent": 10, 
            "memory": {"rss": 100, "percent": 5}, 
            "disk": {"used": 1, "free": 1, "percent": 1}, 
            "io": {"read_bytes": 1, "write_bytes": 1}
        }
        
        # Add more metrics than max_history using update_metrics
        for i in range(15):
            # Reset last_update to force update
            performance_monitor.last_update = 0
            performance_monitor.update_metrics()
        
        # Should be limited to max_history
        assert len(performance_monitor.performance_history) == 10


class TestAsyncOperationTracker:
    """Test cases for AsyncOperationTracker."""

    def test_initialization(self, async_tracker):
        """Test async tracker initialization."""
        assert async_tracker.active_operations == {}
        assert async_tracker.completed_operations == []
        assert async_tracker.max_completed == 50

    def test_start_operation(self, async_tracker):
        """Test starting an async operation."""
        async_tracker.start_operation("test-op-1", "Test operation")
        
        assert "test-op-1" in async_tracker.active_operations
        operation = async_tracker.active_operations["test-op-1"]
        assert operation["id"] == "test-op-1"
        assert operation["description"] == "Test operation"
        assert operation["status"] == "running"
        assert "start_time" in operation

    def test_complete_operation_success(self, async_tracker):
        """Test completing an operation successfully."""
        async_tracker.start_operation("test-op-2", "Test operation 2")
        
        # Wait a bit to ensure duration > 0
        time.sleep(0.01)
        
        async_tracker.complete_operation("test-op-2", success=True)
        
        # Should be removed from active operations
        assert "test-op-2" not in async_tracker.active_operations
        
        # Should be added to completed operations
        assert len(async_tracker.completed_operations) == 1
        completed = async_tracker.completed_operations[0]
        assert completed["id"] == "test-op-2"
        assert completed["success"] is True
        assert completed["status"] == "completed"
        assert completed["duration"] > 0

    def test_complete_operation_failure(self, async_tracker):
        """Test completing an operation with failure."""
        async_tracker.start_operation("test-op-3", "Test operation 3")
        
        async_tracker.complete_operation("test-op-3", success=False, error="Test error")
        
        # Should be removed from active operations
        assert "test-op-3" not in async_tracker.active_operations
        
        # Should be added to completed operations with error
        assert len(async_tracker.completed_operations) == 1
        completed = async_tracker.completed_operations[0]
        assert completed["success"] is False
        assert completed["status"] == "failed"
        assert completed["error"] == "Test error"

    def test_complete_nonexistent_operation(self, async_tracker):
        """Test completing an operation that doesn't exist."""
        # Should not raise an error
        async_tracker.complete_operation("nonexistent", success=True)
        assert len(async_tracker.completed_operations) == 0

    def test_get_active_operations(self, async_tracker):
        """Test getting active operations."""
        async_tracker.start_operation("op1", "Operation 1")
        async_tracker.start_operation("op2", "Operation 2")
        
        active = async_tracker.get_active_operations()
        assert len(active) == 2
        assert any(op["id"] == "op1" for op in active)
        assert any(op["id"] == "op2" for op in active)

    def test_get_recent_operations(self, async_tracker):
        """Test getting recent completed operations."""
        # Add some completed operations
        for i in range(5):
            async_tracker.start_operation(f"op{i}", f"Operation {i}")
            async_tracker.complete_operation(f"op{i}", success=True)
        
        recent = async_tracker.get_recent_operations(3)
        assert len(recent) == 3
        
        # Should return the most recent ones
        assert recent[-1]["id"] == "op4"  # Most recent
        assert recent[0]["id"] == "op2"   # Third most recent

    def test_completed_operations_limit(self, async_tracker):
        """Test that completed operations are limited."""
        # Set a smaller limit for testing
        async_tracker.max_completed = 3
        
        # Add more operations than the limit
        for i in range(5):
            async_tracker.start_operation(f"op{i}", f"Operation {i}")
            async_tracker.complete_operation(f"op{i}", success=True)
        
        # Should be limited to max_completed
        assert len(async_tracker.completed_operations) == 3
        
        # Should keep the most recent ones
        assert async_tracker.completed_operations[-1]["id"] == "op4"


class TestDebugPanel:
    """Test cases for DebugPanel."""

    def test_initialization(self, debug_panel, mock_session_manager, mock_file_manager):
        """Test debug panel initialization."""
        assert debug_panel.session_manager == mock_session_manager
        assert debug_panel.file_manager == mock_file_manager
        assert debug_panel.title == "Debug & Performance"
        
        # Check that components are created
        assert hasattr(debug_panel, 'performance_monitor')
        assert hasattr(debug_panel, 'async_tracker')
        assert hasattr(debug_panel, 'performance_display')
        assert hasattr(debug_panel, 'async_display')
        assert hasattr(debug_panel, 'session_display')
        
        # Check update intervals
        assert debug_panel.display_update_interval == 2.0
        # last_display_update is initialized to 0 but may be set during initial display setup
        assert debug_panel.last_display_update >= 0

    def test_get_panel_name(self, debug_panel):
        """Test getting panel name."""
        assert debug_panel.get_panel_name() == "debug"

    def test_update_display_throttling(self, debug_panel):
        """Test that display updates are throttled."""
        with patch.object(debug_panel, '_update_performance_display') as mock_perf, \
             patch.object(debug_panel, '_update_async_display') as mock_async, \
             patch.object(debug_panel, '_update_session_display') as mock_session:
            
            # Reset last update time to ensure first update works
            debug_panel.last_display_update = 0
            
            # First update should work
            debug_panel.update_display()
            assert mock_perf.called
            assert mock_async.called
            assert mock_session.called
            
            # Reset mocks
            mock_perf.reset_mock()
            mock_async.reset_mock()
            mock_session.reset_mock()
            
            # Immediate second update should be throttled
            debug_panel.update_display()
            assert not mock_perf.called
            assert not mock_async.called
            assert not mock_session.called

    @patch('openhands.tui.panels.debug_panel.get_system_stats')
    def test_update_performance_display(self, mock_get_stats, debug_panel, mock_system_stats):
        """Test performance display update."""
        mock_get_stats.return_value = mock_system_stats
        
        debug_panel._update_performance_display()
        
        # Check that performance widgets are created
        labels = [widget for widget in debug_panel.performance_display._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        # Should contain performance information
        assert any("Uptime:" in text for text in label_texts)
        assert any("CPU:" in text for text in label_texts)
        assert any("Memory:" in text for text in label_texts)
        assert any("Disk:" in text for text in label_texts)
        assert any("I/O:" in text for text in label_texts)

    def test_update_performance_display_no_data(self, debug_panel):
        """Test performance display with no data."""
        # Clear any existing metrics
        debug_panel.performance_monitor.performance_history.clear()
        
        debug_panel._update_performance_display()
        
        labels = [widget for widget in debug_panel.performance_display._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        assert any("No performance data available" in text for text in label_texts)

    def test_update_async_display_no_operations(self, debug_panel):
        """Test async display with no operations."""
        debug_panel._update_async_display()
        
        labels = [widget for widget in debug_panel.async_display._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        assert any("No active operations" in text for text in label_texts)

    def test_update_async_display_with_operations(self, debug_panel):
        """Test async display with active and completed operations."""
        # Add active operations
        debug_panel.async_tracker.start_operation("active1", "Active operation 1")
        debug_panel.async_tracker.start_operation("active2", "Active operation 2")
        
        # Add completed operations
        debug_panel.async_tracker.start_operation("completed1", "Completed operation 1")
        debug_panel.async_tracker.complete_operation("completed1", success=True)
        
        debug_panel._update_async_display()
        
        labels = [widget for widget in debug_panel.async_display._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        # Should show active operations
        assert any("Active: 2 operations" in text for text in label_texts)
        assert any("Active operation 1" in text for text in label_texts)
        
        # Should show completed operations
        assert any("Recent completed:" in text for text in label_texts)
        assert any("Completed operation 1" in text for text in label_texts)

    def test_update_session_display_no_active_session(self, debug_panel, mock_session_manager):
        """Test session display with no active session."""
        mock_session_manager.get_session_summary.return_value = {
            'total_sessions': 0,
            'active_sessions': 0,
            'waiting_sessions': 0,
            'error_sessions': 0
        }
        mock_session_manager.get_active_session.return_value = None
        
        debug_panel._update_session_display()
        
        labels = [widget for widget in debug_panel.session_display._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        assert any("Total Sessions: 0" in text for text in label_texts)
        assert any("No active session" in text for text in label_texts)

    def test_update_session_display_with_active_session(self, debug_panel, mock_session_manager, mock_session_context):
        """Test session display with active session."""
        # Set up the mock session manager
        mock_session_manager.get_session_summary.return_value = {
            'total_sessions': 1,
            'active_sessions': 1,
            'waiting_sessions': 0,
            'error_sessions': 0
        }
        
        # Ensure the mock session context has proper attributes
        # Create a proper mock for agent_state that behaves like an enum
        mock_agent_state = MagicMock()
        mock_agent_state.value = "RUNNING"
        mock_session_context.agent_state = mock_agent_state
        mock_session_context.is_connected = True
        mock_session_context.error_count = 2
        
        mock_session_manager.get_active_session.return_value = mock_session_context
        
        debug_panel._update_session_display()
        
        labels = [widget for widget in debug_panel.session_display._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        assert any("Total Sessions: 1" in text for text in label_texts)
        assert any("Active Session:" in text for text in label_texts)
        # Session ID gets shortened: "test-debug-session-456" -> "test-deb..."
        assert any("test-deb" in text for text in label_texts)
        assert any("RUNNING" in text for text in label_texts)
        assert any("Connected" in text for text in label_texts)
        assert any("Errors: 2" in text for text in label_texts)

    def test_update_session_display_error_handling(self, debug_panel, mock_session_manager):
        """Test session display error handling."""
        mock_session_manager.get_session_summary.side_effect = Exception("Session manager error")
        
        debug_panel._update_session_display()
        
        labels = [widget for widget in debug_panel.session_display._widgets if isinstance(widget, ptg.Label)]
        label_texts = [label.value for label in labels]
        
        assert any("Error:" in text for text in label_texts)

    def test_format_duration(self, debug_panel):
        """Test duration formatting."""
        assert debug_panel._format_duration(30) == "30s"
        assert debug_panel._format_duration(90) == "1m 30s"
        assert debug_panel._format_duration(3661) == "1h 1m"

    def test_get_usage_color(self, debug_panel):
        """Test usage color determination."""
        assert debug_panel._get_usage_color(30) == "green"
        assert debug_panel._get_usage_color(60) == "yellow"
        assert debug_panel._get_usage_color(90) == "red"

    def test_get_state_color(self, debug_panel):
        """Test agent state color determination."""
        assert debug_panel._get_state_color("LOADING") == "yellow"
        assert debug_panel._get_state_color("AWAITING_USER_INPUT") == "green"
        assert debug_panel._get_state_color("RUNNING") == "blue"
        assert debug_panel._get_state_color("ERROR") == "red"
        assert debug_panel._get_state_color("UNKNOWN") == "white"

    def test_track_async_operation(self, debug_panel):
        """Test tracking async operations."""
        debug_panel.track_async_operation("test-track", "Test tracking operation")
        
        active_ops = debug_panel.async_tracker.get_active_operations()
        assert len(active_ops) == 1
        assert active_ops[0]["id"] == "test-track"
        assert active_ops[0]["description"] == "Test tracking operation"

    def test_complete_async_operation(self, debug_panel):
        """Test completing async operations."""
        debug_panel.track_async_operation("test-complete", "Test completion operation")
        debug_panel.complete_async_operation("test-complete", success=True)
        
        active_ops = debug_panel.async_tracker.get_active_operations()
        assert len(active_ops) == 0
        
        recent_ops = debug_panel.async_tracker.get_recent_operations(1)
        assert len(recent_ops) == 1
        assert recent_ops[0]["id"] == "test-complete"
        assert recent_ops[0]["success"] is True

    def test_handle_key_event_refresh(self, debug_panel):
        """Test refresh key event handling."""
        # Set last update time to simulate throttling
        debug_panel.last_display_update = time.time()
        
        with patch.object(debug_panel, 'update_display') as mock_update:
            result = debug_panel.handle_key_event("r")
            
            assert result is True
            assert debug_panel.last_display_update == 0  # Should reset throttling
            mock_update.assert_called_once()

    def test_handle_key_event_clear(self, debug_panel):
        """Test clear key event handling."""
        # Add some data to clear
        debug_panel.performance_monitor.performance_history.append({"test": "data"})
        debug_panel.async_tracker.completed_operations.append({"test": "operation"})
        
        result = debug_panel.handle_key_event("c")
        
        assert result is True
        assert len(debug_panel.performance_monitor.performance_history) == 0
        assert len(debug_panel.async_tracker.completed_operations) == 0

    def test_handle_key_event_unknown(self, debug_panel):
        """Test unknown key event handling."""
        result = debug_panel.handle_key_event("x")
        assert result is False


class TestDebugPanelIntegration:
    """Integration tests for debug panel."""

    @patch('openhands.tui.panels.debug_panel.get_system_stats')
    def test_full_display_update_cycle(self, mock_get_stats, mock_session_manager, mock_file_manager, mock_system_stats, mock_session_context):
        """Test a full display update cycle with realistic data."""
        mock_get_stats.return_value = mock_system_stats
        mock_session_manager.get_session_summary.return_value = {
            'total_sessions': 2,
            'active_sessions': 1,
            'waiting_sessions': 0,
            'error_sessions': 1
        }
        mock_session_manager.get_active_session.return_value = mock_session_context
        
        debug_panel = DebugPanel(mock_session_manager, mock_file_manager)
        
        # Add some async operations
        debug_panel.track_async_operation("integration-test", "Integration test operation")
        debug_panel.complete_async_operation("integration-test", success=True)
        
        # Force a full update
        debug_panel.last_display_update = 0
        debug_panel.update_display()
        
        # Verify all sections have content
        perf_labels = [w for w in debug_panel.performance_display._widgets if isinstance(w, ptg.Label)]
        async_labels = [w for w in debug_panel.async_display._widgets if isinstance(w, ptg.Label)]
        session_labels = [w for w in debug_panel.session_display._widgets if isinstance(w, ptg.Label)]
        
        assert len(perf_labels) > 0
        assert len(async_labels) > 0
        assert len(session_labels) > 0

    def test_error_resilience(self, mock_session_manager, mock_file_manager):
        """Test that the debug panel handles various errors gracefully."""
        # Make session manager methods fail
        mock_session_manager.get_session_summary.side_effect = Exception("Session error")
        mock_session_manager.get_active_session.side_effect = Exception("Active session error")
        
        debug_panel = DebugPanel(mock_session_manager, mock_file_manager)
        
        # Should not raise exceptions
        debug_panel.update_display()
        
        # Should still have some content
        session_labels = [w for w in debug_panel.session_display._widgets if isinstance(w, ptg.Label)]
        assert len(session_labels) > 0

    def test_performance_with_many_operations(self, mock_session_manager, mock_file_manager):
        """Test debug panel performance with many async operations."""
        debug_panel = DebugPanel(mock_session_manager, mock_file_manager)
        
        # Add many operations
        for i in range(100):
            debug_panel.track_async_operation(f"op-{i}", f"Operation {i}")
            if i % 2 == 0:  # Complete half of them
                debug_panel.complete_async_operation(f"op-{i}", success=i % 4 == 0)
        
        # Measure update time
        start_time = time.time()
        debug_panel.last_display_update = 0
        debug_panel.update_display()
        end_time = time.time()
        
        # Should complete quickly even with many operations
        assert end_time - start_time < 1.0  # Less than 1 second
        
        # Should display limited number of operations for readability
        async_labels = [w for w in debug_panel.async_display._widgets if isinstance(w, ptg.Label)]
        async_texts = [label.value for label in async_labels]
        
        # Should show active operations count
        assert any("Active: 50 operations" in text for text in async_texts) 