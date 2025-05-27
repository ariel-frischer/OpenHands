"""TUI Error Handling Framework.

This module provides comprehensive error handling for the OpenHands TUI,
including custom exception classes, error boundaries, user-friendly error
messages, and recovery mechanisms.
"""

import logging
import traceback
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

import pytermgui as ptg

logger = logging.getLogger(__name__)


class TUIErrorSeverity(Enum):
    """Error severity levels for TUI display."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TUIErrorCategory(Enum):
    """Categories of TUI errors for better handling."""

    SESSION = "session"
    NETWORK = "network"
    FILE_OPERATION = "file_operation"
    DISPLAY = "display"
    USER_INPUT = "user_input"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class TUIError(Exception):
    """Base exception class for TUI-specific errors."""

    def __init__(
        self,
        message: str,
        category: TUIErrorCategory = TUIErrorCategory.UNKNOWN,
        severity: TUIErrorSeverity = TUIErrorSeverity.ERROR,
        recoverable: bool = True,
        recovery_suggestions: Optional[List[str]] = None,
        original_error: Optional[Exception] = None,
    ):
        """Initialize TUI error.

        Args:
            message: Human-readable error message
            category: Error category for handling
            severity: Error severity level
            recoverable: Whether error can be recovered from
            recovery_suggestions: List of suggested recovery actions
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.recoverable = recoverable
        self.recovery_suggestions = recovery_suggestions or []
        self.original_error = original_error


class TUISessionError(TUIError):
    """Session-related TUI errors."""

    def __init__(self, message: str, session_id: Optional[str] = None, **kwargs):
        """Initialize session error.

        Args:
            message: Error message
            session_id: ID of the affected session
            **kwargs: Additional TUIError arguments
        """
        super().__init__(
            message,
            category=TUIErrorCategory.SESSION,
            **kwargs,
        )
        self.session_id = session_id


class TUINetworkError(TUIError):
    """Network-related TUI errors."""

    def __init__(self, message: str, **kwargs):
        """Initialize network error."""
        super().__init__(
            message,
            category=TUIErrorCategory.NETWORK,
            recovery_suggestions=[
                "Check your internet connection",
                "Verify server is running",
                "Try again in a few moments",
            ],
            **kwargs,
        )


class TUIFileOperationError(TUIError):
    """File operation TUI errors."""

    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        """Initialize file operation error.

        Args:
            message: Error message
            file_path: Path of the affected file
            **kwargs: Additional TUIError arguments
        """
        super().__init__(
            message,
            category=TUIErrorCategory.FILE_OPERATION,
            recovery_suggestions=[
                "Check file permissions",
                "Verify file path exists",
                "Ensure sufficient disk space",
            ],
            **kwargs,
        )
        self.file_path = file_path


class TUIDisplayError(TUIError):
    """Display-related TUI errors."""

    def __init__(self, message: str, **kwargs):
        """Initialize display error."""
        super().__init__(
            message,
            category=TUIErrorCategory.DISPLAY,
            recovery_suggestions=[
                "Resize terminal window",
                "Check terminal compatibility",
                "Restart TUI application",
            ],
            **kwargs,
        )


class TUIUserInputError(TUIError):
    """User input validation TUI errors."""

    def __init__(self, message: str, input_value: Optional[str] = None, **kwargs):
        """Initialize user input error.

        Args:
            message: Error message
            input_value: The invalid input value
            **kwargs: Additional TUIError arguments
        """
        super().__init__(
            message,
            category=TUIErrorCategory.USER_INPUT,
            severity=TUIErrorSeverity.WARNING,
            recovery_suggestions=[
                "Check input format",
                "Refer to help documentation",
                "Try a different value",
            ],
            **kwargs,
        )
        self.input_value = input_value


class TUISystemError(TUIError):
    """System-level TUI errors."""

    def __init__(self, message: str, **kwargs):
        """Initialize system error."""
        super().__init__(
            message,
            category=TUIErrorCategory.SYSTEM,
            severity=TUIErrorSeverity.CRITICAL,
            recoverable=False,
            recovery_suggestions=[
                "Restart the application",
                "Check system resources",
                "Contact support if issue persists",
            ],
            **kwargs,
        )


class TUIErrorHandler:
    """Central error handler for TUI operations."""

    def __init__(self):
        """Initialize error handler."""
        self.error_history: List[TUIError] = []
        self.error_callbacks: Dict[TUIErrorCategory, List[Callable]] = {}
        self.max_history_size = 100

    def register_error_callback(
        self, category: TUIErrorCategory, callback: Callable[[TUIError], None]
    ) -> None:
        """Register callback for specific error category.

        Args:
            category: Error category to handle
            callback: Function to call when error occurs
        """
        if category not in self.error_callbacks:
            self.error_callbacks[category] = []
        self.error_callbacks[category].append(callback)

    def handle_error(
        self,
        error: Union[Exception, TUIError],
        context: Optional[str] = None,
        show_notification: bool = True,
    ) -> TUIError:
        """Handle an error with appropriate TUI response.

        Args:
            error: Exception or TUIError to handle
            context: Additional context about where error occurred
            show_notification: Whether to show notification to user

        Returns:
            TUIError instance (converted if needed)
        """
        # Convert regular exceptions to TUIError
        if not isinstance(error, TUIError):
            tui_error = self._convert_to_tui_error(error, context)
        else:
            tui_error = error

        # Add to error history
        self._add_to_history(tui_error)

        # Log the error
        self._log_error(tui_error, context)

        # Show notification if requested
        if show_notification:
            self._show_error_notification(tui_error)

        # Call registered callbacks
        self._call_error_callbacks(tui_error)

        return tui_error

    def _convert_to_tui_error(
        self, error: Exception, context: Optional[str] = None
    ) -> TUIError:
        """Convert regular exception to TUIError.

        Args:
            error: Original exception
            context: Additional context

        Returns:
            Converted TUIError
        """
        error_message = str(error)
        if context:
            error_message = f"{context}: {error_message}"

        # Determine category based on error type
        category = self._determine_error_category(error)

        # Create appropriate TUIError subclass
        if category == TUIErrorCategory.SESSION:
            return TUISessionError(error_message, original_error=error)
        elif category == TUIErrorCategory.NETWORK:
            return TUINetworkError(error_message, original_error=error)
        elif category == TUIErrorCategory.FILE_OPERATION:
            return TUIFileOperationError(error_message, original_error=error)
        elif category == TUIErrorCategory.DISPLAY:
            return TUIDisplayError(error_message, original_error=error)
        elif category == TUIErrorCategory.USER_INPUT:
            return TUIUserInputError(error_message, original_error=error)
        elif category == TUIErrorCategory.SYSTEM:
            return TUISystemError(error_message, original_error=error)
        else:
            return TUIError(error_message, category=category, original_error=error)

    def _determine_error_category(self, error: Exception) -> TUIErrorCategory:
        """Determine error category from exception type.

        Args:
            error: Exception to categorize

        Returns:
            Appropriate error category
        """
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()

        # Network-related errors
        if any(
            keyword in error_type or keyword in error_message
            for keyword in [
                "connection",
                "network",
                "timeout",
                "socket",
                "http",
                "url",
                "dns",
            ]
        ):
            return TUIErrorCategory.NETWORK

        # Session-related errors (check before file operations)
        if any(
            keyword in error_message
            for keyword in ["session", "agent", "controller", "runtime"]
        ):
            return TUIErrorCategory.SESSION

        # File operation errors
        if any(
            keyword in error_type or keyword in error_message
            for keyword in [
                "file",
                "io",
                "permission",
                "notfound",
                "exists",
                "directory",
                "path",
            ]
        ):
            return TUIErrorCategory.FILE_OPERATION

        # Display errors
        if any(
            keyword in error_type or keyword in error_message
            for keyword in ["display", "terminal", "widget", "layout", "render"]
        ):
            return TUIErrorCategory.DISPLAY

        # User input errors
        if any(
            keyword in error_type or keyword in error_message
            for keyword in ["validation", "input", "format", "parse"]
        ):
            return TUIErrorCategory.USER_INPUT

        # System errors
        if any(
            keyword in error_type
            for keyword in ["system", "memory", "resource", "os", "environment"]
        ):
            return TUIErrorCategory.SYSTEM

        return TUIErrorCategory.UNKNOWN

    def _add_to_history(self, error: TUIError) -> None:
        """Add error to history with size limit.

        Args:
            error: Error to add to history
        """
        self.error_history.append(error)
        if len(self.error_history) > self.max_history_size:
            self.error_history.pop(0)

    def _log_error(self, error: TUIError, context: Optional[str] = None) -> None:
        """Log error with appropriate level.

        Args:
            error: Error to log
            context: Additional context
        """
        log_message = f"TUI Error [{error.category.value}]: {error.message}"
        if context:
            log_message = f"{log_message} (Context: {context})"

        if error.original_error:
            log_message += f" (Original: {error.original_error})"

        # Log with appropriate level
        if error.severity == TUIErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif error.severity == TUIErrorSeverity.ERROR:
            logger.error(log_message)
        elif error.severity == TUIErrorSeverity.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        # Log stack trace for debugging
        if error.original_error and logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Stack trace for {error.category.value} error:",
                exc_info=error.original_error,
            )

    def _show_error_notification(self, error: TUIError) -> None:
        """Show error notification to user.

        Args:
            error: Error to display
        """
        try:
            # Create notification message
            title = f"{error.category.value.title()} Error"
            message = error.message

            # Add recovery suggestions if available
            if error.recovery_suggestions:
                suggestions = "\n".join(
                    f"• {suggestion}" for suggestion in error.recovery_suggestions
                )
                message += f"\n\nSuggestions:\n{suggestions}"

            # Show notification (this would integrate with the TUI notification system)
            # For now, we'll log it as the notification system may not be available
            logger.info(f"TUI Notification: {title} - {message}")

        except Exception as e:
            # Don't let notification errors crash the application
            logger.error(f"Failed to show error notification: {e}")

    def _call_error_callbacks(self, error: TUIError) -> None:
        """Call registered callbacks for error category.

        Args:
            error: Error that occurred
        """
        callbacks = self.error_callbacks.get(error.category, [])
        for callback in callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error callback failed: {e}")

    def get_error_history(
        self, category: Optional[TUIErrorCategory] = None, limit: Optional[int] = None
    ) -> List[TUIError]:
        """Get error history with optional filtering.

        Args:
            category: Filter by error category
            limit: Maximum number of errors to return

        Returns:
            List of errors matching criteria
        """
        errors = self.error_history
        if category:
            errors = [e for e in errors if e.category == category]

        if limit:
            errors = errors[-limit:]

        return errors

    def clear_error_history(self) -> None:
        """Clear error history."""
        self.error_history.clear()

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics.

        Returns:
            Dictionary with error statistics
        """
        total_errors = len(self.error_history)
        if total_errors == 0:
            return {"total": 0}

        # Count by category
        category_counts = {}
        severity_counts = {}
        recoverable_count = 0

        for error in self.error_history:
            # Count by category
            category = error.category.value
            category_counts[category] = category_counts.get(category, 0) + 1

            # Count by severity
            severity = error.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            # Count recoverable errors
            if error.recoverable:
                recoverable_count += 1

        return {
            "total": total_errors,
            "by_category": category_counts,
            "by_severity": severity_counts,
            "recoverable": recoverable_count,
            "non_recoverable": total_errors - recoverable_count,
        }


def error_boundary(
    error_handler: Optional[TUIErrorHandler] = None,
    context: Optional[str] = None,
    show_notification: bool = True,
    reraise: bool = False,
) -> Callable:
    """Decorator to create error boundary for TUI functions.

    Args:
        error_handler: Error handler instance to use
        context: Context description for error
        show_notification: Whether to show notification
        reraise: Whether to reraise the error after handling

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler = error_handler or get_global_error_handler()
                tui_error = handler.handle_error(e, context, show_notification)

                if reraise:
                    raise tui_error
                return None

        return wrapper

    return decorator


def async_error_boundary(
    error_handler: Optional[TUIErrorHandler] = None,
    context: Optional[str] = None,
    show_notification: bool = True,
    reraise: bool = False,
) -> Callable:
    """Async decorator to create error boundary for TUI async functions.

    Args:
        error_handler: Error handler instance to use
        context: Context description for error
        show_notification: Whether to show notification
        reraise: Whether to reraise the error after handling

    Returns:
        Async decorator function
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                handler = error_handler or get_global_error_handler()
                tui_error = handler.handle_error(e, context, show_notification)

                if reraise:
                    raise tui_error
                return None

        return wrapper

    return decorator


# Global error handler instance
_global_error_handler: Optional[TUIErrorHandler] = None


def get_global_error_handler() -> TUIErrorHandler:
    """Get or create global error handler instance.

    Returns:
        Global error handler instance
    """
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = TUIErrorHandler()
    return _global_error_handler


def set_global_error_handler(handler: TUIErrorHandler) -> None:
    """Set global error handler instance.

    Args:
        handler: Error handler to set as global
    """
    global _global_error_handler
    _global_error_handler = handler


def handle_error(
    error: Union[Exception, TUIError],
    context: Optional[str] = None,
    show_notification: bool = True,
) -> TUIError:
    """Convenience function to handle error with global handler.

    Args:
        error: Exception or TUIError to handle
        context: Additional context about where error occurred
        show_notification: Whether to show notification to user

    Returns:
        TUIError instance
    """
    return get_global_error_handler().handle_error(error, context, show_notification)
