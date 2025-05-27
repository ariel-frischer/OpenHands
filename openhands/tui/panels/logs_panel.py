"""Logs Panel.

Bottom left panel showing logs with responsive layout and session filtering.
"""

import logging
import textwrap
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger

from .base_panel import BasePanel

if TYPE_CHECKING:
    from ..managers import SessionManager, TUIPanelFileManager


class TUILogHandler(logging.Handler):
    """Custom log handler to capture logs for TUI display."""
    
    def __init__(self, max_logs: int = 1000):
        """Initialize the TUI log handler.
        
        Args:
            max_logs: Maximum number of logs to keep in memory
        """
        super().__init__()
        self.max_logs = max_logs
        self.logs_by_session: Dict[str, deque] = {}
        self.global_logs: deque = deque(maxlen=max_logs)
        
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record.
        
        Args:
            record: Log record to emit
        """
        try:
            # Format the log entry
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created),
                'level': record.levelname,
                'message': self.format(record),
                'logger_name': record.name,
                'session_id': getattr(record, 'session_id', None)
            }
            
            # Add to global logs
            self.global_logs.append(log_entry)
            
            # Debug: Print to console to verify logs are being captured
            if record.name.startswith('openhands') and 'session' in record.getMessage().lower():
                print(f"[TUI LOG CAPTURE] {record.levelname}: {record.getMessage()}", flush=True)
            
            # Add to session-specific logs if session_id is available
            session_id = log_entry.get('session_id')
            if session_id:
                if session_id not in self.logs_by_session:
                    self.logs_by_session[session_id] = deque(maxlen=self.max_logs)
                self.logs_by_session[session_id].append(log_entry)
                
        except Exception:
            self.handleError(record)
    
    def get_session_logs(self, session_id: str) -> List[dict]:
        """Get logs for a specific session.
        
        Args:
            session_id: Session ID to get logs for
            
        Returns:
            List of log entries for the session
        """
        if session_id in self.logs_by_session:
            return list(self.logs_by_session[session_id])
        
        # If no session-specific logs, filter global logs
        return [
            log for log in self.global_logs 
            if log.get('session_id') == session_id or log.get('session_id') is None
        ]
    
    def get_all_logs(self) -> List[dict]:
        """Get all logs.
        
        Returns:
            List of all log entries
        """
        return list(self.global_logs)
    
    def clear_session_logs(self, session_id: str) -> None:
        """Clear logs for a specific session.
        
        Args:
            session_id: Session ID to clear logs for
        """
        if session_id in self.logs_by_session:
            self.logs_by_session[session_id].clear()


# Global TUI log handler instance
_tui_log_handler = None


def get_tui_log_handler() -> TUILogHandler:
    """Get or create the global TUI log handler.
    
    Returns:
        TUI log handler instance
    """
    global _tui_log_handler
    if _tui_log_handler is None:
        _tui_log_handler = TUILogHandler()
        
        # Add to the OpenHands logger specifically
        from openhands.core.logger import openhands_logger
        openhands_logger.addHandler(_tui_log_handler)
        _tui_log_handler.setLevel(logging.DEBUG)
        
        # Also add to root logger to capture other logs
        root_logger = logging.getLogger()
        root_logger.addHandler(_tui_log_handler)
        
        # Set a simple formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s:%(levelname)s - %(message)s')
        _tui_log_handler.setFormatter(formatter)
        
        # Set up file logging to logs/ directory
        import os
        from pathlib import Path
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Create file handler for TUI logs
        file_handler = logging.FileHandler(logs_dir / "tui_debug.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Add file handler to both loggers
        openhands_logger.addHandler(file_handler)
        root_logger.addHandler(file_handler)
        
        # Test that the handler is working
        openhands_logger.info("TUI log handler successfully initialized")
        
    return _tui_log_handler


class LogsPanel(BasePanel):
    """Bottom left panel showing logs."""
    
    def __init__(self, session_manager: "SessionManager", file_manager: "TUIPanelFileManager"):
        """Initialize the logs panel.
        
        Args:
            session_manager: Session manager instance
            file_manager: File manager instance
        """
        super().__init__(session_manager, file_manager, "Logs")
        
        # Logs display container with responsive sizing
        self.logs_display = ptg.Container()
        self.add_content(self.logs_display)
        
        # Log level filter (for future enhancement)
        self.log_level = logging.INFO
        
        # Maximum number of log entries to display
        self.max_log_entries = 20
        
        # Get the TUI log handler
        self.log_handler = get_tui_log_handler()
        
        # Initialize with current logs
        self.update_logs_display()
    
    def get_panel_name(self) -> str:
        """Get the panel name for file operations.
        
        Returns:
            Panel name string
        """
        return "logs"
    
    def update_display(self, session_id: str = "") -> None:
        """Update the logs display.
        
        Args:
            session_id: Session ID to update logs for
        """
        if not session_id:
            active_session = self.session_manager.get_active_session()
            if active_session:
                session_id = active_session.sid
            # If no active session, show all logs (session_id will be empty)
        
        self.update_logs_display(session_id)
    
    def update_logs_display(self, session_id: str = "") -> None:
        """Update logs for active session with responsive layout.
        
        Args:
            session_id: Session ID to update logs for, or empty for all logs
        """
        logger.debug(f"Updating logs display for session: {session_id or 'all'}")
        
        # Clear existing logs
        self.logs_display._widgets.clear()
        
        # Calculate how many log entries can fit in current terminal height
        # Panel height - title(1) - spacer(1) - bottom_margin(1) = self.height - 3
        logs_display_container_height = max(1, self.height - 2) # Height of the logs_display container itself
        # max_entries is a rough estimate if logs are single line. Wrapping makes this complex.
        # We use self.max_log_entries (default 20) as a hard cap on entries processed.
        # The display will show what fits from these recent_logs.
        
        # Get log entries for the session or all logs
        if session_id:
            log_entries = self.get_session_logs(session_id)
        else:
            log_entries = self.log_handler.get_all_logs()
        
        if not log_entries:
            self.logs_display += ptg.Label("[dim]No logs available[/dim]")
        else:
            # Show recent log entries, capped by self.max_log_entries
            recent_logs = log_entries[-self.max_log_entries:]
            for entry in recent_logs:
                widget = self.create_log_widget(entry)
                self.logs_display += widget
        
        # Update logs file for Ctrl+E
        self.file_manager.update_logs_file(session_id or "all", log_entries)
    
    def get_session_logs(self, session_id: str) -> list[dict]:
        """Get logs for specific session.
        
        Args:
            session_id: Session ID to get logs for
            
        Returns:
            List of log entry dictionaries
        """
        # Get logs from the TUI log handler
        logs = self.log_handler.get_session_logs(session_id)
        
        # Filter by log level if needed
        filtered_logs = []
        for log_entry in logs:
            log_level_num = getattr(logging, log_entry.get('level', 'INFO'), logging.INFO)
            if log_level_num >= self.log_level:
                filtered_logs.append(log_entry)
        
        return filtered_logs
    
    def wrap_log_message(self, message: str, max_width: int) -> str:
        """Wrap long log messages to fit terminal width.
        
        Args:
            message: Log message to wrap
            max_width: Maximum width for wrapping
            
        Returns:
            Wrapped message string
        """
        if not message:
            return ""
        
        # Use textwrap to wrap long messages
        wrapped_lines = textwrap.wrap(message, width=max_width)
        return '\n'.join(wrapped_lines)
    
    def create_log_widget(self, log_entry: dict) -> ptg.Widget:
        """Create widget for a log entry with responsive text wrapping.
        
        Args:
            log_entry: Log entry dictionary
            
        Returns:
            Widget representing the log entry
        """
        timestamp = log_entry.get('timestamp', datetime.now())
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.strftime('%H:%M:%S')
        else:
            timestamp_str = str(timestamp)
            
        level = log_entry.get('level', 'INFO')
        message = log_entry.get('message', '')
        
        # Color code by log level
        level_colors = {
            'DEBUG': 'dim',
            'INFO': 'blue',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold red'
        }
        
        color = level_colors.get(level, 'white')
        
        # Wrap long log messages to fit terminal width
        # self.width is panel width. Subtract ~2 for internal padding/borders of the label.
        label_content_area_width = max(10, self.width - 2)
        
        # Construct prefix for length calculation
        prefix_text_raw = f"{timestamp_str} {level} " # Raw text for length
        prefix_markup = f"[{color}]{timestamp_str} {level}[/{color}] " # Markup for display
        
        prefix_visual_len = len(ptg.strip_markup(prefix_markup)) # Actually, just len(prefix_text_raw) is fine here
                                                                    # as markup doesn't change length of this specific prefix.
                                                                    # Using strip_markup for consistency if prefix becomes complex.
        
        content_wrap_width = max(10, label_content_area_width - prefix_visual_len)
        wrapped_message = self.wrap_log_message(message, content_wrap_width)
        
        # Format log entry
        log_text = f"{prefix_markup}{wrapped_message}"
        
        return ptg.Label(log_text)
    
    def add_log_entry(self, level: str, message: str, session_id: str = "") -> None:
        """Add a new log entry.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            session_id: Session ID (if applicable)
        """
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message
        }
        
        # Add to display if it's for the active session
        active_session = self.session_manager.get_active_session()
        if not session_id or (active_session and session_id == active_session.sid):
            widget = self.create_log_widget(log_entry)
            self.logs_display += widget
            
            # Remove old entries if we exceed the limit
            if len(self.logs_display._widgets) > self.max_log_entries:
                self.logs_display._widgets.pop(0)
    
    def clear_logs(self) -> None:
        """Clear the logs display."""
        self.logs_display._widgets.clear()
        self.logs_display += ptg.Label("[dim]Logs cleared[/dim]")
    
    def set_log_level(self, level: int) -> None:
        """Set the minimum log level to display.
        
        Args:
            level: Minimum log level (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.log_level = level
        
        # Refresh display with new filter
        active_session = self.session_manager.get_active_session()
        if active_session:
            self.update_logs_display(active_session.sid)
    
    def handle_terminal_resize(self) -> None:
        """Handle terminal resize events by refreshing logs display for new terminal size.
        
        This method should be called when the terminal is resized to ensure
        the logs display adapts to the new dimensions.
        """
        # Refresh logs display for new terminal size
        if self.session_manager.active_session_id:
            self.update_logs_display(self.session_manager.active_session_id)
    
    def handle_key_event(self, key: str) -> bool:
        """Handle key events for the logs panel.
        
        Args:
            key: Key that was pressed
            
        Returns:
            True if the key was handled, False otherwise
        """
        if key == "c":
            # Clear logs
            self.clear_logs()
            return True
        elif key == "r":
            # Refresh logs
            active_session = self.session_manager.get_active_session()
            if active_session:
                self.update_logs_display(active_session.sid)
            return True
        
        return False
