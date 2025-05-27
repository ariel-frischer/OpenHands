"""Tests for TUI Logs Panel."""

import logging
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import pytermgui as ptg

from openhands.tui.panels.logs_panel import LogsPanel, TUILogHandler, get_tui_log_handler


class TestTUILogHandler:
    """Test cases for TUILogHandler."""

    def test_initialization(self):
        """Test TUILogHandler initialization."""
        handler = TUILogHandler(max_logs=500)
        
        assert handler.max_logs == 500
        assert len(handler.logs_by_session) == 0
        assert len(handler.global_logs) == 0

    def test_emit_log_record(self):
        """Test emitting log records."""
        handler = TUILogHandler()
        
        # Create a log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.session_id = "test-session-123"
        
        # Emit the record
        handler.emit(record)
        
        # Check global logs
        assert len(handler.global_logs) == 1
        log_entry = handler.global_logs[0]
        assert log_entry['level'] == 'INFO'
        assert log_entry['message'] == 'Test message'
        assert log_entry['session_id'] == 'test-session-123'
        
        # Check session-specific logs
        assert 'test-session-123' in handler.logs_by_session
        assert len(handler.logs_by_session['test-session-123']) == 1

    def test_emit_log_record_without_session(self):
        """Test emitting log records without session ID."""
        handler = TUILogHandler()
        
        # Create a log record without session_id
        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=10,
            msg="Warning message",
            args=(),
            exc_info=None
        )
        
        # Emit the record
        handler.emit(record)
        
        # Check global logs
        assert len(handler.global_logs) == 1
        log_entry = handler.global_logs[0]
        assert log_entry['level'] == 'WARNING'
        assert log_entry['session_id'] is None

    def test_get_session_logs(self):
        """Test getting logs for a specific session."""
        handler = TUILogHandler()
        
        # Add logs for different sessions
        record1 = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1,
            msg="Session 1 message", args=(), exc_info=None
        )
        record1.session_id = "session-1"
        
        record2 = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=2,
            msg="Session 2 message", args=(), exc_info=None
        )
        record2.session_id = "session-2"
        
        handler.emit(record1)
        handler.emit(record2)
        
        # Get logs for session-1
        session1_logs = handler.get_session_logs("session-1")
        assert len(session1_logs) == 1
        assert session1_logs[0]['message'] == 'Session 1 message'
        
        # Get logs for session-2
        session2_logs = handler.get_session_logs("session-2")
        assert len(session2_logs) == 1
        assert session2_logs[0]['message'] == 'Session 2 message'

    def test_get_all_logs(self):
        """Test getting all logs."""
        handler = TUILogHandler()
        
        # Add multiple logs
        for i in range(3):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="test.py", lineno=i,
                msg=f"Message {i}", args=(), exc_info=None
            )
            handler.emit(record)
        
        all_logs = handler.get_all_logs()
        assert len(all_logs) == 3

    def test_clear_session_logs(self):
        """Test clearing logs for a specific session."""
        handler = TUILogHandler()
        
        # Add logs for a session
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1,
            msg="Test message", args=(), exc_info=None
        )
        record.session_id = "test-session"
        handler.emit(record)
        
        # Verify logs exist
        assert len(handler.get_session_logs("test-session")) == 1
        
        # Clear session logs
        handler.clear_session_logs("test-session")
        
        # Verify logs are cleared
        assert len(handler.get_session_logs("test-session")) == 0

    def test_max_logs_limit(self):
        """Test that logs are limited to max_logs."""
        handler = TUILogHandler(max_logs=2)
        
        # Add more logs than the limit
        for i in range(5):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="test.py", lineno=i,
                msg=f"Message {i}", args=(), exc_info=None
            )
            handler.emit(record)
        
        # Should only keep the last 2 logs
        all_logs = handler.get_all_logs()
        assert len(all_logs) == 2
        assert all_logs[0]['message'] == 'Message 3'
        assert all_logs[1]['message'] == 'Message 4'


class TestLogsPanel:
    """Test cases for LogsPanel."""

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        manager = MagicMock()
        manager.active_session_id = "test-session-123"
        
        # Mock active session
        mock_session = MagicMock()
        mock_session.sid = "test-session-123"
        manager.get_active_session.return_value = mock_session
        
        return manager

    @pytest.fixture
    def mock_file_manager(self):
        """Create a mock file manager."""
        manager = MagicMock()
        manager.update_logs_file = MagicMock()
        return manager

    @pytest.fixture
    def logs_panel(self, mock_session_manager, mock_file_manager):
        """Create a LogsPanel instance for testing."""
        # Mock the terminal object instead of individual properties
        with patch('openhands.tui.panels.logs_panel.ptg.terminal') as mock_terminal:
            mock_terminal.height = 50
            mock_terminal.width = 100
            return LogsPanel(mock_session_manager, mock_file_manager)

    def test_initialization(self, logs_panel):
        """Test LogsPanel initialization."""
        assert logs_panel.title == "Logs"
        assert logs_panel.log_level == logging.INFO
        assert logs_panel.logs_display is not None
        assert logs_panel.log_handler is not None

    def test_get_panel_name(self, logs_panel):
        """Test getting panel name."""
        assert logs_panel.get_panel_name() == "logs"

    def test_wrap_log_message(self, logs_panel):
        """Test wrapping long log messages."""
        # Test short message (no wrapping needed)
        short_message = "Short message"
        wrapped = logs_panel.wrap_log_message(short_message, 50)
        assert wrapped == short_message
        
        # Test long message (wrapping needed)
        long_message = "This is a very long message that should be wrapped when it exceeds the maximum width"
        wrapped = logs_panel.wrap_log_message(long_message, 30)
        lines = wrapped.split('\n')
        assert len(lines) > 1
        for line in lines:
            assert len(line) <= 30

    def test_wrap_log_message_empty(self, logs_panel):
        """Test wrapping empty message."""
        assert logs_panel.wrap_log_message("", 50) == ""
        assert logs_panel.wrap_log_message(None, 50) == ""

    def test_create_log_widget(self, logs_panel):
        """Test creating log widgets."""
        log_entry = {
            'timestamp': datetime(2023, 1, 1, 12, 30, 45),
            'level': 'INFO',
            'message': 'Test log message'
        }
        
        with patch('openhands.tui.panels.logs_panel.ptg.terminal') as mock_terminal:
            mock_terminal.width = 100
            widget = logs_panel.create_log_widget(log_entry)
            assert isinstance(widget, ptg.Label)

    def test_create_log_widget_with_wrapping(self, logs_panel):
        """Test creating log widgets with message wrapping."""
        long_message = "This is a very long log message that should be wrapped " * 5
        log_entry = {
            'timestamp': datetime(2023, 1, 1, 12, 30, 45),
            'level': 'ERROR',
            'message': long_message
        }
        
        with patch('openhands.tui.panels.logs_panel.ptg.terminal') as mock_terminal:
            mock_terminal.width = 60
            widget = logs_panel.create_log_widget(log_entry)
            assert isinstance(widget, ptg.Label)

    def test_get_session_logs(self, logs_panel):
        """Test getting session logs with filtering."""
        # Mock the log handler
        mock_logs = [
            {'level': 'DEBUG', 'message': 'Debug message'},
            {'level': 'INFO', 'message': 'Info message'},
            {'level': 'WARNING', 'message': 'Warning message'},
            {'level': 'ERROR', 'message': 'Error message'},
        ]
        logs_panel.log_handler.get_session_logs = MagicMock(return_value=mock_logs)
        
        # Test with INFO level filter
        logs_panel.log_level = logging.INFO
        filtered_logs = logs_panel.get_session_logs("test-session")
        
        # Should filter out DEBUG messages
        assert len(filtered_logs) == 3
        levels = [log['level'] for log in filtered_logs]
        assert 'DEBUG' not in levels
        assert 'INFO' in levels
        assert 'WARNING' in levels
        assert 'ERROR' in levels

    def test_update_logs_display(self, logs_panel, mock_session_manager, mock_file_manager):
        """Test updating logs display with responsive layout."""
        with patch('openhands.tui.panels.logs_panel.ptg.terminal') as mock_terminal:
            mock_terminal.height = 30
            mock_terminal.width = 100
            
            # Mock session logs
            mock_logs = [
                {
                    'timestamp': datetime(2023, 1, 1, 12, 30, i),
                    'level': 'INFO',
                    'message': f'Log message {i}'
                }
                for i in range(50)  # More logs than can fit
            ]
            logs_panel.log_handler.get_session_logs = MagicMock(return_value=mock_logs)
            
            # Update display
            logs_panel.update_logs_display("test-session")
            
            # Should limit logs based on terminal height
            # available_height = 30 - 4 = 26, max_entries = 26 - 2 = 24
            expected_max_entries = max(10, 26 - 2)
            
            # Verify file manager was called
            mock_file_manager.update_logs_file.assert_called_once_with("test-session", mock_logs)

    def test_update_logs_display_no_logs(self, logs_panel, mock_file_manager):
        """Test updating logs display when no logs are available."""
        logs_panel.log_handler.get_session_logs = MagicMock(return_value=[])
        
        logs_panel.update_logs_display("test-session")
        
        # Should show "No logs available" message
        assert len(logs_panel.logs_display._widgets) == 1
        mock_file_manager.update_logs_file.assert_called_once_with("test-session", [])

    def test_update_display(self, logs_panel, mock_session_manager):
        """Test update_display method."""
        with patch.object(logs_panel, 'update_logs_display') as mock_update:
            # Test with session_id provided
            logs_panel.update_display("specific-session")
            mock_update.assert_called_once_with("specific-session")
            
            # Test without session_id (should use active session)
            mock_update.reset_mock()
            logs_panel.update_display()
            mock_update.assert_called_once_with("test-session-123")

    def test_update_display_no_active_session(self, logs_panel, mock_session_manager):
        """Test update_display when no active session."""
        mock_session_manager.get_active_session.return_value = None
        
        with patch.object(logs_panel, 'update_logs_display') as mock_update:
            logs_panel.update_display()
            mock_update.assert_not_called()

    def test_handle_terminal_resize(self, logs_panel, mock_session_manager):
        """Test handling terminal resize events."""
        with patch.object(logs_panel, 'update_logs_display') as mock_update:
            logs_panel.handle_terminal_resize()
            mock_update.assert_called_once_with("test-session-123")

    def test_handle_terminal_resize_no_active_session(self, logs_panel, mock_session_manager):
        """Test handling terminal resize when no active session."""
        mock_session_manager.active_session_id = None
        
        with patch.object(logs_panel, 'update_logs_display') as mock_update:
            logs_panel.handle_terminal_resize()
            mock_update.assert_not_called()

    def test_handle_key_event_clear(self, logs_panel):
        """Test handling 'c' key to clear logs."""
        with patch.object(logs_panel, 'clear_logs') as mock_clear:
            result = logs_panel.handle_key_event("c")
            assert result is True
            mock_clear.assert_called_once()

    def test_handle_key_event_refresh(self, logs_panel, mock_session_manager):
        """Test handling 'r' key to refresh logs."""
        with patch.object(logs_panel, 'update_logs_display') as mock_update:
            result = logs_panel.handle_key_event("r")
            assert result is True
            mock_update.assert_called_once_with("test-session-123")

    def test_handle_key_event_unhandled(self, logs_panel):
        """Test handling unrecognized keys."""
        result = logs_panel.handle_key_event("x")
        assert result is False

    def test_clear_logs(self, logs_panel):
        """Test clearing logs display."""
        # Add some widgets first
        logs_panel.logs_display += ptg.Label("Test log")
        assert len(logs_panel.logs_display._widgets) == 1
        
        # Clear logs
        logs_panel.clear_logs()
        
        # Should have one widget (the "Logs cleared" message)
        assert len(logs_panel.logs_display._widgets) == 1

    def test_set_log_level(self, logs_panel, mock_session_manager):
        """Test setting log level filter."""
        with patch.object(logs_panel, 'update_logs_display') as mock_update:
            logs_panel.set_log_level(logging.WARNING)
            
            assert logs_panel.log_level == logging.WARNING
            mock_update.assert_called_once_with("test-session-123")

    def test_add_log_entry(self, logs_panel, mock_session_manager):
        """Test adding log entries."""
        # Test adding log for active session
        logs_panel.add_log_entry("INFO", "Test message", "test-session-123")
        
        # Should add widget to display
        assert len(logs_panel.logs_display._widgets) > 0

    def test_add_log_entry_different_session(self, logs_panel, mock_session_manager):
        """Test adding log entries for different session."""
        initial_count = len(logs_panel.logs_display._widgets)
        
        # Test adding log for different session
        logs_panel.add_log_entry("INFO", "Test message", "other-session")
        
        # Should not add widget to display
        assert len(logs_panel.logs_display._widgets) == initial_count


def test_get_tui_log_handler():
    """Test getting the global TUI log handler."""
    # Reset global handler
    import openhands.tui.panels.logs_panel
    openhands.tui.panels.logs_panel._tui_log_handler = None
    
    # Get handler (should create new one)
    handler1 = get_tui_log_handler()
    assert isinstance(handler1, TUILogHandler)
    
    # Get handler again (should return same instance)
    handler2 = get_tui_log_handler()
    assert handler1 is handler2