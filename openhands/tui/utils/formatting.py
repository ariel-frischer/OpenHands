"""Formatting Utilities.

Text formatting utilities for the TUI system.
"""

import re
from datetime import datetime
from typing import Any, Union


class Formatter:
    """Text formatting utilities for the TUI."""

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate text to a maximum length.

        Args:
            text: Text to truncate
            max_length: Maximum length including suffix
            suffix: Suffix to add when truncating

        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text

        return text[: max_length - len(suffix)] + suffix

    @staticmethod
    def format_timestamp(timestamp: Union[datetime, str, None] = None) -> str:
        """Format a timestamp for display.

        Args:
            timestamp: Timestamp to format (defaults to current time)

        Returns:
            Formatted timestamp string
        """
        if timestamp is None:
            timestamp = datetime.now()
        elif isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                return timestamp  # Return as-is if parsing fails

        return timestamp.strftime("%H:%M:%S")

    @staticmethod
    def format_duration(
        start_time: datetime, end_time: Union[datetime, None] = None
    ) -> str:
        """Format a duration between two timestamps.

        Args:
            start_time: Start timestamp
            end_time: End timestamp (defaults to current time)

        Returns:
            Formatted duration string
        """
        if end_time is None:
            end_time = datetime.now()

        duration = end_time - start_time

        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        elif minutes > 0:
            return f"{int(minutes)}m {int(seconds)}s"
        else:
            return f"{int(seconds)}s"

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string
        """
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1

        return f"{size:.1f} {size_names[i]}"

    @staticmethod
    def colorize_log_level(level: str) -> str:
        """Add color markup to log level.

        Args:
            level: Log level string

        Returns:
            Colorized log level string
        """
        level_colors = {
            "DEBUG": "dim",
            "INFO": "blue",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }

        color = level_colors.get(level.upper(), "white")
        return f"[{color}]{level}[/{color}]"

    @staticmethod
    def format_session_status(status: str) -> str:
        """Format session status with appropriate styling.

        Args:
            status: Session status string

        Returns:
            Formatted status string
        """
        status_colors = {
            "INIT": "yellow",
            "RUNNING": "green",
            "PAUSED": "orange",
            "FINISHED": "blue",
            "ERROR": "red",
            "STOPPED": "dim",
        }

        color = status_colors.get(status.upper(), "white")
        return f"[{color}]{status}[/{color}]"

    @staticmethod
    def clean_ansi_codes(text: str) -> str:
        """Remove ANSI escape codes from text.

        Args:
            text: Text that may contain ANSI codes

        Returns:
            Text with ANSI codes removed
        """
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    @staticmethod
    def wrap_text(text: str, width: int, indent: str = "") -> list[str]:
        """Wrap text to a specific width.

        Args:
            text: Text to wrap
            width: Maximum width per line
            indent: Indentation for wrapped lines

        Returns:
            List of wrapped lines
        """
        if not text:
            return [""]

        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            if not current_line:
                current_line = word
            elif len(current_line) + len(word) + 1 <= width:
                current_line += " " + word
            else:
                lines.append(current_line)
                current_line = indent + word

        if current_line:
            lines.append(current_line)

        return lines

    @staticmethod
    def format_command_output(output: str, max_lines: int = 10) -> str:
        """Format command output for display.

        Args:
            output: Raw command output
            max_lines: Maximum number of lines to show

        Returns:
            Formatted output string
        """
        if not output:
            return "[dim]No output[/dim]"

        # Clean ANSI codes
        clean_output = Formatter.clean_ansi_codes(output)

        # Split into lines
        lines = clean_output.split("\n")

        # Truncate if too many lines
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines.append(f"[dim]... ({len(lines) - max_lines} more lines)[/dim]")

        return "\n".join(lines)

    @staticmethod
    def format_error_message(error: Union[str, Exception]) -> str:
        """Format error message for display.

        Args:
            error: Error message or exception

        Returns:
            Formatted error string
        """
        if isinstance(error, Exception):
            error_text = str(error)
            error_type = type(error).__name__
            return f"[red]{error_type}:[/red] {error_text}"
        else:
            return f"[red]Error:[/red] {error}"

    @staticmethod
    def format_json(data: Any, indent: int = 2) -> str:
        """Format JSON data for display.

        Args:
            data: Data to format as JSON
            indent: Indentation level

        Returns:
            Formatted JSON string
        """
        import json

        try:
            return json.dumps(data, indent=indent, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            return f"[red]JSON formatting error:[/red] {e}"

    @staticmethod
    def highlight_search_term(text: str, search_term: str) -> str:
        """Highlight search term in text.

        Args:
            text: Text to search in
            search_term: Term to highlight

        Returns:
            Text with highlighted search terms
        """
        if not search_term:
            return text

        # Case-insensitive highlighting
        pattern = re.compile(re.escape(search_term), re.IGNORECASE)
        return pattern.sub(f"[bold yellow]{search_term}[/bold yellow]", text)
