"""Tests for TUI Error Handling Framework.

This module contains comprehensive tests for the TUI error handling system,
including custom exception classes, error boundaries, and recovery mechanisms.
"""

import logging
import pytest
from unittest.mock import MagicMock, patch, call

from openhands.tui.utils.error_handler import (
    TUIError,
    TUIErrorCategory,
    TUIErrorHandler,
    TUIErrorSeverity,
    TUISessionError,
    TUINetworkError,
    TUIFileOperationError,
    TUIDisplayError,
    TUIUserInputError,
    TUISystemError,
    error_boundary,
    async_error_boundary,
    get_global_error_handler,
    set_global_error_handler,
    handle_error,
)


class TestTUIErrorClasses:
    """Test cases for TUI error classes."""

    def test_tui_error_initialization(self):
        """Test TUIError initialization with all parameters."""
        error = TUIError(
            message="Test error",
            category=TUIErrorCategory.SESSION,
            severity=TUIErrorSeverity.WARNING,
            recoverable=False,
            recovery_suggestions=["Try again", "Check settings"],
            original_error=ValueError("Original error"),
        )

        assert error.message == "Test error"
        assert error.category == TUIErrorCategory.SESSION
        assert error.severity == TUIErrorSeverity.WARNING
        assert error.recoverable is False
        assert error.recovery_suggestions == ["Try again", "Check settings"]
        assert isinstance(error.original_error, ValueError)
        assert str(error) == "Test error"

    def test_tui_error_defaults(self):
        """Test TUIError initialization with default values."""
        error = TUIError("Simple error")

        assert error.message == "Simple error"
        assert error.category == TUIErrorCategory.UNKNOWN
        assert error.severity == TUIErrorSeverity.ERROR
        assert error.recoverable is True
        assert error.recovery_suggestions == []
        assert error.original_error is None

    def test_tui_session_error(self):
        """Test TUISessionError initialization."""
        error = TUISessionError("Session failed", session_id="test-session-123")

        assert error.message == "Session failed"
        assert error.category == TUIErrorCategory.SESSION
        assert error.session_id == "test-session-123"

    def test_tui_network_error(self):
        """Test TUINetworkError initialization."""
        error = TUINetworkError("Connection failed")

        assert error.message == "Connection failed"
        assert error.category == TUIErrorCategory.NETWORK
        assert "Check your internet connection" in error.recovery_suggestions

    def test_tui_file_operation_error(self):
        """Test TUIFileOperationError initialization."""
        error = TUIFileOperationError("File not found", file_path="/test/path")

        assert error.message == "File not found"
        assert error.category == TUIErrorCategory.FILE_OPERATION
        assert error.file_path == "/test/path"
        assert "Check file permissions" in error.recovery_suggestions

    def test_tui_display_error(self):
        """Test TUIDisplayError initialization."""
        error = TUIDisplayError("Display rendering failed")

        assert error.message == "Display rendering failed"
        assert error.category == TUIErrorCategory.DISPLAY
        assert "Resize terminal window" in error.recovery_suggestions

    def test_tui_user_input_error(self):
        """Test TUIUserInputError initialization."""
        error = TUIUserInputError("Invalid input", input_value="bad_value")

        assert error.message == "Invalid input"
        assert error.category == TUIErrorCategory.USER_INPUT
        assert error.severity == TUIErrorSeverity.WARNING
        assert error.input_value == "bad_value"
        assert "Check input format" in error.recovery_suggestions

    def test_tui_system_error(self):
        """Test TUISystemError initialization."""
        error = TUISystemError("System resource exhausted")

        assert error.message == "System resource exhausted"
        assert error.category == TUIErrorCategory.SYSTEM
        assert error.severity == TUIErrorSeverity.CRITICAL
        assert error.recoverable is False
        assert "Restart the application" in error.recovery_suggestions


class TestTUIErrorHandler:
    """Test cases for TUIErrorHandler functionality."""

    @pytest.fixture
    def error_handler(self):
        """Create a TUIErrorHandler instance for testing."""
        return TUIErrorHandler()

    def test_initialization(self, error_handler):
        """Test TUIErrorHandler initialization."""
        assert error_handler.error_history == []
        assert error_handler.error_callbacks == {}
        assert error_handler.max_history_size == 100

    def test_register_error_callback(self, error_handler):
        """Test registering error callbacks."""
        callback1 = MagicMock()
        callback2 = MagicMock()

        error_handler.register_error_callback(TUIErrorCategory.SESSION, callback1)
        error_handler.register_error_callback(TUIErrorCategory.SESSION, callback2)
        error_handler.register_error_callback(TUIErrorCategory.NETWORK, callback1)

        assert len(error_handler.error_callbacks[TUIErrorCategory.SESSION]) == 2
        assert len(error_handler.error_callbacks[TUIErrorCategory.NETWORK]) == 1
        assert callback1 in error_handler.error_callbacks[TUIErrorCategory.SESSION]
        assert callback2 in error_handler.error_callbacks[TUIErrorCategory.SESSION]

    def test_handle_tui_error(self, error_handler):
        """Test handling a TUIError instance."""
        original_error = TUISessionError("Session error", session_id="test-123")

        with patch.object(error_handler, "_log_error") as mock_log, \
             patch.object(error_handler, "_show_error_notification") as mock_notify, \
             patch.object(error_handler, "_call_error_callbacks") as mock_callbacks:

            result = error_handler.handle_error(original_error)

            assert result is original_error
            assert len(error_handler.error_history) == 1
            assert error_handler.error_history[0] is original_error
            mock_log.assert_called_once_with(original_error, None)
            mock_notify.assert_called_once_with(original_error)
            mock_callbacks.assert_called_once_with(original_error)

    def test_handle_regular_exception(self, error_handler):
        """Test handling a regular exception."""
        original_exception = ValueError("Test value error")

        with patch.object(error_handler, "_convert_to_tui_error") as mock_convert, \
             patch.object(error_handler, "_log_error") as mock_log:

            mock_tui_error = TUIError("Converted error")
            mock_convert.return_value = mock_tui_error

            result = error_handler.handle_error(original_exception, context="test context")

            mock_convert.assert_called_once_with(original_exception, "test context")
            assert result is mock_tui_error
            assert len(error_handler.error_history) == 1

    def test_convert_to_tui_error_network(self, error_handler):
        """Test converting network-related exceptions."""
        network_error = ConnectionError("Connection timeout")
        result = error_handler._convert_to_tui_error(network_error, "API call")

        assert isinstance(result, TUINetworkError)
        assert result.message == "API call: Connection timeout"
        assert result.original_error is network_error

    def test_convert_to_tui_error_file_operation(self, error_handler):
        """Test converting file operation exceptions."""
        file_error = FileNotFoundError("File not found")
        result = error_handler._convert_to_tui_error(file_error)

        assert isinstance(result, TUIFileOperationError)
        assert result.message == "File not found"
        assert result.original_error is file_error

    def test_convert_to_tui_error_session(self, error_handler):
        """Test converting session-related exceptions."""
        session_error = RuntimeError("Session controller failed")
        result = error_handler._convert_to_tui_error(session_error)

        assert isinstance(result, TUISessionError)
        assert result.message == "Session controller failed"
        assert result.original_error is session_error

    def test_convert_to_tui_error_display(self, error_handler):
        """Test converting display-related exceptions."""
        display_error = RuntimeError("Widget rendering failed")
        result = error_handler._convert_to_tui_error(display_error)

        assert isinstance(result, TUIDisplayError)
        assert result.message == "Widget rendering failed"
        assert result.original_error is display_error

    def test_convert_to_tui_error_user_input(self, error_handler):
        """Test converting user input exceptions."""
        input_error = ValueError("Invalid input format")
        result = error_handler._convert_to_tui_error(input_error)

        assert isinstance(result, TUIUserInputError)
        assert result.message == "Invalid input format"
        assert result.original_error is input_error

    def test_convert_to_tui_error_system(self, error_handler):
        """Test converting system-related exceptions."""
        system_error = MemoryError("Out of memory")
        result = error_handler._convert_to_tui_error(system_error)

        assert isinstance(result, TUISystemError)
        assert result.message == "Out of memory"
        assert result.original_error is system_error

    def test_convert_to_tui_error_unknown(self, error_handler):
        """Test converting unknown exceptions."""
        unknown_error = RuntimeError("Unknown error")
        result = error_handler._convert_to_tui_error(unknown_error)

        assert isinstance(result, TUIError)
        assert result.category == TUIErrorCategory.UNKNOWN
        assert result.message == "Unknown error"
        assert result.original_error is unknown_error

    def test_determine_error_category_network(self, error_handler):
        """Test determining network error category."""
        network_errors = [
            ConnectionError("Connection failed"),
            TimeoutError("Request timeout"),
            RuntimeError("HTTP error occurred"),
            ValueError("Invalid URL format"),
            Exception("DNS resolution failed"),
        ]

        for error in network_errors:
            category = error_handler._determine_error_category(error)
            assert category == TUIErrorCategory.NETWORK

    def test_determine_error_category_file_operation(self, error_handler):
        """Test determining file operation error category."""
        file_errors = [
            FileNotFoundError("File not found"),
            PermissionError("Permission denied"),
            IOError("I/O operation failed"),
            OSError("Directory does not exist"),
        ]

        for error in file_errors:
            category = error_handler._determine_error_category(error)
            assert category == TUIErrorCategory.FILE_OPERATION

    def test_add_to_history_with_limit(self, error_handler):
        """Test adding errors to history with size limit."""
        error_handler.max_history_size = 3

        # Add 5 errors
        for i in range(5):
            error = TUIError(f"Error {i}")
            error_handler._add_to_history(error)

        # Should only keep the last 3
        assert len(error_handler.error_history) == 3
        assert error_handler.error_history[0].message == "Error 2"
        assert error_handler.error_history[1].message == "Error 3"
        assert error_handler.error_history[2].message == "Error 4"

    def test_log_error_levels(self, error_handler):
        """Test logging errors with different severity levels."""
        with patch("openhands.tui.utils.error_handler.logger") as mock_logger:
            # Test different severity levels
            critical_error = TUIError("Critical", severity=TUIErrorSeverity.CRITICAL)
            error_handler._log_error(critical_error)
            mock_logger.critical.assert_called()

            error_error = TUIError("Error", severity=TUIErrorSeverity.ERROR)
            error_handler._log_error(error_error)
            mock_logger.error.assert_called()

            warning_error = TUIError("Warning", severity=TUIErrorSeverity.WARNING)
            error_handler._log_error(warning_error)
            mock_logger.warning.assert_called()

            info_error = TUIError("Info", severity=TUIErrorSeverity.INFO)
            error_handler._log_error(info_error)
            mock_logger.info.assert_called()

    def test_log_error_with_context_and_original(self, error_handler):
        """Test logging error with context and original exception."""
        with patch("openhands.tui.utils.error_handler.logger") as mock_logger:
            original = ValueError("Original error")
            error = TUIError("Test error", original_error=original)

            error_handler._log_error(error, context="Test context")

            # Check that the log message includes context and original error
            call_args = mock_logger.error.call_args[0][0]
            assert "Test context" in call_args
            assert "Original: Original error" in call_args

    def test_show_error_notification(self, error_handler):
        """Test showing error notifications."""
        with patch("openhands.tui.utils.error_handler.logger") as mock_logger:
            error = TUIError(
                "Test error",
                category=TUIErrorCategory.SESSION,
                recovery_suggestions=["Try again", "Check settings"]
            )

            error_handler._show_error_notification(error)

            # Should log the notification
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args[0][0]
            assert "Session Error" in call_args
            assert "Test error" in call_args
            assert "Try again" in call_args

    def test_show_error_notification_exception(self, error_handler):
        """Test error notification handling when notification fails."""
        with patch("openhands.tui.utils.error_handler.logger") as mock_logger:
            # Mock logger.info to raise an exception
            mock_logger.info.side_effect = Exception("Notification failed")

            error = TUIError("Test error")
            error_handler._show_error_notification(error)

            # Should log the notification failure
            mock_logger.error.assert_called()

    def test_call_error_callbacks(self, error_handler):
        """Test calling registered error callbacks."""
        callback1 = MagicMock()
        callback2 = MagicMock()
        callback3 = MagicMock()

        error_handler.register_error_callback(TUIErrorCategory.SESSION, callback1)
        error_handler.register_error_callback(TUIErrorCategory.SESSION, callback2)
        error_handler.register_error_callback(TUIErrorCategory.NETWORK, callback3)

        session_error = TUISessionError("Session error")
        error_handler._call_error_callbacks(session_error)

        callback1.assert_called_once_with(session_error)
        callback2.assert_called_once_with(session_error)
        callback3.assert_not_called()

    def test_call_error_callbacks_exception(self, error_handler):
        """Test error callback handling when callback fails."""
        failing_callback = MagicMock(side_effect=Exception("Callback failed"))
        error_handler.register_error_callback(TUIErrorCategory.SESSION, failing_callback)

        with patch("openhands.tui.utils.error_handler.logger") as mock_logger:
            session_error = TUISessionError("Session error")
            error_handler._call_error_callbacks(session_error)

            # Should log the callback failure
            mock_logger.error.assert_called()

    def test_get_error_history_no_filter(self, error_handler):
        """Test getting error history without filters."""
        errors = [
            TUISessionError("Session error 1"),
            TUINetworkError("Network error"),
            TUISessionError("Session error 2"),
        ]

        for error in errors:
            error_handler._add_to_history(error)

        history = error_handler.get_error_history()
        assert len(history) == 3
        assert history == errors

    def test_get_error_history_with_category_filter(self, error_handler):
        """Test getting error history with category filter."""
        errors = [
            TUISessionError("Session error 1"),
            TUINetworkError("Network error"),
            TUISessionError("Session error 2"),
        ]

        for error in errors:
            error_handler._add_to_history(error)

        session_history = error_handler.get_error_history(category=TUIErrorCategory.SESSION)
        assert len(session_history) == 2
        assert all(e.category == TUIErrorCategory.SESSION for e in session_history)

    def test_get_error_history_with_limit(self, error_handler):
        """Test getting error history with limit."""
        errors = [TUIError(f"Error {i}") for i in range(5)]

        for error in errors:
            error_handler._add_to_history(error)

        limited_history = error_handler.get_error_history(limit=3)
        assert len(limited_history) == 3
        assert limited_history[0].message == "Error 2"
        assert limited_history[2].message == "Error 4"

    def test_clear_error_history(self, error_handler):
        """Test clearing error history."""
        errors = [TUIError(f"Error {i}") for i in range(3)]
        for error in errors:
            error_handler._add_to_history(error)

        assert len(error_handler.error_history) == 3

        error_handler.clear_error_history()
        assert len(error_handler.error_history) == 0

    def test_get_error_statistics_empty(self, error_handler):
        """Test getting error statistics when no errors."""
        stats = error_handler.get_error_statistics()
        assert stats == {"total": 0}

    def test_get_error_statistics_with_errors(self, error_handler):
        """Test getting error statistics with various errors."""
        errors = [
            TUISessionError("Session error 1"),
            TUISessionError("Session error 2"),
            TUINetworkError("Network error"),
            TUIError("Generic error", severity=TUIErrorSeverity.WARNING),
            TUISystemError("System error"),  # Non-recoverable
        ]

        for error in errors:
            error_handler._add_to_history(error)

        stats = error_handler.get_error_statistics()

        assert stats["total"] == 5
        assert stats["by_category"]["session"] == 2
        assert stats["by_category"]["network"] == 1
        assert stats["by_category"]["unknown"] == 1
        assert stats["by_category"]["system"] == 1
        assert stats["by_severity"]["error"] == 3
        assert stats["by_severity"]["warning"] == 1
        assert stats["by_severity"]["critical"] == 1
        assert stats["recoverable"] == 4
        assert stats["non_recoverable"] == 1


class TestErrorBoundaries:
    """Test cases for error boundary decorators."""

    def test_error_boundary_success(self):
        """Test error boundary with successful function."""
        @error_boundary(context="test function")
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_error_boundary_exception(self):
        """Test error boundary with exception."""
        mock_handler = MagicMock()
        mock_tui_error = TUIError("Handled error")
        mock_handler.handle_error.return_value = mock_tui_error

        @error_boundary(error_handler=mock_handler, context="test function")
        def failing_function():
            raise ValueError("Test error")

        result = failing_function()

        assert result is None
        mock_handler.handle_error.assert_called_once()
        call_args = mock_handler.handle_error.call_args
        assert isinstance(call_args[0][0], ValueError)
        assert call_args[0][1] == "test function"

    def test_error_boundary_reraise(self):
        """Test error boundary with reraise option."""
        mock_handler = MagicMock()
        mock_tui_error = TUIError("Handled error")
        mock_handler.handle_error.return_value = mock_tui_error

        @error_boundary(error_handler=mock_handler, reraise=True)
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(TUIError):
            failing_function()

    @pytest.mark.asyncio
    async def test_async_error_boundary_success(self):
        """Test async error boundary with successful function."""
        @async_error_boundary(context="async test function")
        async def successful_async_function():
            return "async success"

        result = await successful_async_function()
        assert result == "async success"

    @pytest.mark.asyncio
    async def test_async_error_boundary_exception(self):
        """Test async error boundary with exception."""
        mock_handler = MagicMock()
        mock_tui_error = TUIError("Handled async error")
        mock_handler.handle_error.return_value = mock_tui_error

        @async_error_boundary(error_handler=mock_handler, context="async test")
        async def failing_async_function():
            raise ValueError("Async test error")

        result = await failing_async_function()

        assert result is None
        mock_handler.handle_error.assert_called_once()


class TestGlobalErrorHandler:
    """Test cases for global error handler functions."""

    def test_get_global_error_handler(self):
        """Test getting global error handler."""
        # Reset global handler
        set_global_error_handler(None)

        handler1 = get_global_error_handler()
        handler2 = get_global_error_handler()

        assert handler1 is handler2
        assert isinstance(handler1, TUIErrorHandler)

    def test_set_global_error_handler(self):
        """Test setting global error handler."""
        custom_handler = TUIErrorHandler()
        set_global_error_handler(custom_handler)

        retrieved_handler = get_global_error_handler()
        assert retrieved_handler is custom_handler

    def test_handle_error_convenience_function(self):
        """Test convenience handle_error function."""
        custom_handler = MagicMock()
        mock_tui_error = TUIError("Handled error")
        custom_handler.handle_error.return_value = mock_tui_error

        set_global_error_handler(custom_handler)

        test_error = ValueError("Test error")
        result = handle_error(test_error, context="test context")

        assert result is mock_tui_error
        custom_handler.handle_error.assert_called_once_with(
            test_error, "test context", True
        ) 