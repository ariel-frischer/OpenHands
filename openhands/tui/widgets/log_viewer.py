"""Log Viewer Widget.

Specialized widget for displaying and filtering log entries.
"""

import logging
from datetime import datetime
from typing import Any, Union

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger


class LogViewer(ptg.Container):
    """Specialized widget for log viewing and filtering."""

    def __init__(self, max_entries: int = 50):
        """Initialize the log viewer widget.

        Args:
            max_entries: Maximum number of log entries to keep in memory
        """
        super().__init__()
        self.max_entries = max_entries
        self.log_entries: list[dict[str, Any]] = []
        self.min_level = logging.INFO
        self.auto_scroll = True
        self.show_timestamps = True

    def add_log_entry(
        self,
        message: str,
        level: int = logging.INFO,
        timestamp: Union[datetime, None] = None,
        source: str = "system",
    ) -> None:
        """Add a log entry to the viewer.

        Args:
            message: Log message
            level: Log level (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
            timestamp: Log timestamp (defaults to current time)
            source: Source of the log entry
        """
        if timestamp is None:
            timestamp = datetime.now()

        entry = {
            "message": message,
            "level": level,
            "level_name": logging.getLevelName(level),
            "timestamp": timestamp,
            "source": source,
        }

        self.log_entries.append(entry)

        # Limit log history
        if len(self.log_entries) > self.max_entries:
            self.log_entries.pop(0)

        # Add entry widget if it meets the level filter
        if level >= self.min_level:
            widget = self.create_log_widget(entry)
            self += widget

            # Remove old widgets if we exceed the limit
            if len(self._widgets) > self.max_entries:
                self._widgets.pop(0)

        logger.debug(
            f"Added log entry: {logging.getLevelName(level)} - {message[:50]}..."
        )

    def create_log_widget(self, entry: dict[str, Any]) -> ptg.Widget:
        """Create a widget for a single log entry.

        Args:
            entry: Log entry dictionary

        Returns:
            Widget representing the log entry
        """
        message = entry["message"]
        level = entry["level"]
        level_name = entry["level_name"]
        timestamp = entry["timestamp"]
        source = entry["source"]

        # Format timestamp
        if self.show_timestamps:
            time_str = (
                timestamp.strftime("%H:%M:%S")
                if isinstance(timestamp, datetime)
                else str(timestamp)
            )
            time_part = f"[{time_str}] "
        else:
            time_part = ""

        # Color code by log level
        level_colors = {
            logging.DEBUG: "dim",
            logging.INFO: "blue",
            logging.WARNING: "yellow",
            logging.ERROR: "red",
            logging.CRITICAL: "bold red",
        }

        color = level_colors.get(level, "white")

        # Format log entry
        if source != "system":
            log_text = (
                f"[{color}]{time_part}{level_name}[/{color}] [{source}] {message}"
            )
        else:
            log_text = f"[{color}]{time_part}{level_name}[/{color}] {message}"

        return ptg.Label(log_text)

    def set_log_level(self, level: int) -> None:
        """Set the minimum log level to display.

        Args:
            level: Minimum log level (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.min_level = level
        self.refresh_display()
        logger.debug(f"Set log level filter to: {logging.getLevelName(level)}")

    def refresh_display(self) -> None:
        """Refresh the log display with current filters."""
        self.clear()

        # Re-add entries that meet the current filter
        for entry in self.log_entries:
            if entry["level"] >= self.min_level:
                widget = self.create_log_widget(entry)
                self += widget

    def clear_logs(self) -> None:
        """Clear all log entries from the viewer."""
        self.clear()
        self.log_entries.clear()
        logger.debug("Cleared log entries")

    def get_log_entries(self) -> list[dict[str, Any]]:
        """Get all log entries.

        Returns:
            List of log entry dictionaries
        """
        return self.log_entries.copy()

    def get_entry_count(self) -> int:
        """Get the number of log entries.

        Returns:
            Number of log entries
        """
        return len(self.log_entries)

    def search_logs(self, query: str) -> list[dict[str, Any]]:
        """Search for log entries containing a query.

        Args:
            query: Search query

        Returns:
            List of matching log entries
        """
        query_lower = query.lower()
        matches = []

        for entry in self.log_entries:
            if (
                query_lower in entry["message"].lower()
                or query_lower in entry["source"].lower()
            ):
                matches.append(entry)

        return matches

    def filter_by_level(self, level: int) -> list[dict[str, Any]]:
        """Filter log entries by level.

        Args:
            level: Log level to filter by

        Returns:
            List of log entries at the specified level
        """
        return [entry for entry in self.log_entries if entry["level"] == level]

    def filter_by_source(self, source: str) -> list[dict[str, Any]]:
        """Filter log entries by source.

        Args:
            source: Source to filter by

        Returns:
            List of log entries from the specified source
        """
        return [entry for entry in self.log_entries if entry["source"] == source]

    def export_logs(self) -> str:
        """Export log entries as formatted text.

        Returns:
            Formatted text representation of all log entries
        """
        lines = []

        for entry in self.log_entries:
            timestamp = entry["timestamp"]
            if isinstance(timestamp, datetime):
                time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_str = str(timestamp)

            level_name = entry["level_name"]
            source = entry["source"]
            message = entry["message"]

            if source != "system":
                lines.append(f"[{time_str}] {level_name} [{source}] {message}")
            else:
                lines.append(f"[{time_str}] {level_name} {message}")

        return "\n".join(lines)

    def set_show_timestamps(self, show: bool) -> None:
        """Enable or disable timestamp display.

        Args:
            show: Whether to show timestamps
        """
        self.show_timestamps = show
        self.refresh_display()

    def set_auto_scroll(self, enabled: bool) -> None:
        """Enable or disable auto-scrolling to new entries.

        Args:
            enabled: Whether to enable auto-scrolling
        """
        self.auto_scroll = enabled

    def get_level_counts(self) -> dict[str, int]:
        """Get counts of log entries by level.

        Returns:
            Dictionary mapping level names to counts
        """
        counts = {}

        for entry in self.log_entries:
            level_name = entry["level_name"]
            counts[level_name] = counts.get(level_name, 0) + 1

        return counts

    def get_recent_errors(self, count: int = 5) -> list[dict[str, Any]]:
        """Get recent error log entries.

        Args:
            count: Number of recent errors to return

        Returns:
            List of recent error log entries
        """
        errors = [
            entry for entry in self.log_entries if entry["level"] >= logging.ERROR
        ]

        return errors[-count:] if errors else []

    def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the log viewer."""
        # TODO: Implement scrolling functionality
        # This will depend on PyTermGUI's scrolling capabilities
        pass

    def scroll_to_top(self) -> None:
        """Scroll to the top of the log viewer."""
        # TODO: Implement scrolling functionality
        # This will depend on PyTermGUI's scrolling capabilities
        pass
