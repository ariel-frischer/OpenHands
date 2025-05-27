"""Debug Panel.

Panel for displaying TUI performance monitoring and debug information.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger
from openhands.runtime.utils.system_stats import get_system_stats

from .base_panel import BasePanel

if TYPE_CHECKING:
    from ..managers import SessionManager, TUIPanelFileManager


class PerformanceMonitor:
    """Monitor for TUI performance metrics."""

    def __init__(self, max_history: int = 60):
        """Initialize the performance monitor.

        Args:
            max_history: Maximum number of performance samples to keep
        """
        self.max_history = max_history
        self.performance_history: List[Dict] = []
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 1.0  # Update every second

    def update_metrics(self) -> Dict:
        """Update and return current performance metrics.

        Returns:
            Dictionary containing current performance metrics
        """
        current_time = time.time()

        # Only update if enough time has passed
        if current_time - self.last_update < self.update_interval:
            return self.get_latest_metrics()

        try:
            # Get system stats using existing OpenHands utility
            system_stats = get_system_stats()

            # Calculate TUI-specific metrics
            uptime = current_time - self.start_time
            memory_mb = system_stats["memory"]["rss"] / (1024 * 1024)

            metrics = {
                "timestamp": datetime.now(),
                "uptime": uptime,
                "cpu_percent": system_stats["cpu_percent"],
                "memory_mb": memory_mb,
                "memory_percent": system_stats["memory"]["percent"],
                "disk_used_gb": system_stats["disk"]["used"] / (1024**3),
                "disk_free_gb": system_stats["disk"]["free"] / (1024**3),
                "disk_percent": system_stats["disk"]["percent"],
                "io_read_mb": system_stats["io"]["read_bytes"] / (1024 * 1024),
                "io_write_mb": system_stats["io"]["write_bytes"] / (1024 * 1024),
            }

            # Add to history
            self.performance_history.append(metrics)

            # Limit history size
            if len(self.performance_history) > self.max_history:
                self.performance_history.pop(0)

            self.last_update = current_time
            return metrics

        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
            return self.get_latest_metrics() or {}

    def get_latest_metrics(self) -> Optional[Dict]:
        """Get the latest performance metrics.

        Returns:
            Latest metrics dictionary or None if no metrics available
        """
        return self.performance_history[-1] if self.performance_history else None

    def get_average_metrics(self, duration_minutes: int = 5) -> Dict:
        """Get average metrics over a specified duration.

        Args:
            duration_minutes: Duration in minutes to calculate averages

        Returns:
            Dictionary containing average metrics
        """
        if not self.performance_history:
            return {}

        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        recent_metrics = [
            m for m in self.performance_history if m["timestamp"] >= cutoff_time
        ]

        if not recent_metrics:
            return {}

        # Calculate averages
        avg_metrics = {
            "cpu_percent": sum(m["cpu_percent"] for m in recent_metrics)
            / len(recent_metrics),
            "memory_mb": sum(m["memory_mb"] for m in recent_metrics)
            / len(recent_metrics),
            "memory_percent": sum(m["memory_percent"] for m in recent_metrics)
            / len(recent_metrics),
            "disk_percent": sum(m["disk_percent"] for m in recent_metrics)
            / len(recent_metrics),
        }

        return avg_metrics


class AsyncOperationTracker:
    """Tracker for async operations in the TUI."""

    def __init__(self):
        """Initialize the async operation tracker."""
        self.active_operations: Dict[str, Dict] = {}
        self.completed_operations: List[Dict] = []
        self.max_completed = 50

    def start_operation(self, operation_id: str, description: str) -> None:
        """Start tracking an async operation.

        Args:
            operation_id: Unique identifier for the operation
            description: Human-readable description of the operation
        """
        self.active_operations[operation_id] = {
            "id": operation_id,
            "description": description,
            "start_time": datetime.now(),
            "status": "running",
        }

    def complete_operation(
        self, operation_id: str, success: bool = True, error: str = ""
    ) -> None:
        """Complete an async operation.

        Args:
            operation_id: Unique identifier for the operation
            success: Whether the operation completed successfully
            error: Error message if operation failed
        """
        if operation_id in self.active_operations:
            operation = self.active_operations.pop(operation_id)
            operation["end_time"] = datetime.now()
            operation["duration"] = (
                operation["end_time"] - operation["start_time"]
            ).total_seconds()
            operation["success"] = success
            operation["error"] = error
            operation["status"] = "completed" if success else "failed"

            self.completed_operations.append(operation)

            # Limit completed operations history
            if len(self.completed_operations) > self.max_completed:
                self.completed_operations.pop(0)

    def get_active_operations(self) -> List[Dict]:
        """Get list of currently active operations.

        Returns:
            List of active operation dictionaries
        """
        return list(self.active_operations.values())

    def get_recent_operations(self, count: int = 10) -> List[Dict]:
        """Get recent completed operations.

        Args:
            count: Number of recent operations to return

        Returns:
            List of recent operation dictionaries
        """
        return self.completed_operations[-count:]


class DebugPanel(BasePanel):
    """Panel for displaying TUI performance monitoring and debug information."""

    def __init__(
        self, session_manager: "SessionManager", file_manager: "TUIPanelFileManager"
    ):
        """Initialize the debug panel.

        Args:
            session_manager: Session manager instance
            file_manager: File manager instance
        """
        super().__init__(session_manager, file_manager, "Debug & Performance")

        # Performance monitoring
        self.performance_monitor = PerformanceMonitor()
        self.async_tracker = AsyncOperationTracker()

        # Display containers
        self.performance_display = ptg.Container()
        self.async_display = ptg.Container()
        self.session_display = ptg.Container()

        # Add sections to panel
        self.add_content(ptg.Label("[bold cyan]Performance Metrics[/bold cyan]"))
        self.add_content(self.performance_display)
        self.add_content(ptg.Label(""))  # Spacer

        self.add_content(ptg.Label("[bold yellow]Async Operations[/bold yellow]"))
        self.add_content(self.async_display)
        self.add_content(ptg.Label(""))  # Spacer

        self.add_content(ptg.Label("[bold green]Session Debug Info[/bold green]"))
        self.add_content(self.session_display)

        # Update interval for display refresh
        self.last_display_update = 0
        self.display_update_interval = 2.0  # Update display every 2 seconds

        # Initialize display (but don't set last_display_update yet)
        try:
            self._update_performance_display()
            self._update_async_display()
            self._update_session_display()
        except Exception as e:
            logger.error(f"Error during initial display setup: {e}")

    def get_panel_name(self) -> str:
        """Get the panel name for file operations.

        Returns:
            Panel name string
        """
        return "debug"

    def update_display(self, session_id: str = "") -> None:
        """Update the debug panel display.

        Args:
            session_id: Session ID to update for (if applicable)
        """
        current_time = time.time()

        # Throttle display updates
        if current_time - self.last_display_update < self.display_update_interval:
            return

        try:
            self._update_performance_display()
            self._update_async_display()
            self._update_session_display(session_id)
            self.last_display_update = current_time

        except Exception as e:
            logger.error(f"Error updating debug panel display: {e}")

    def _update_performance_display(self) -> None:
        """Update the performance metrics display."""
        self.performance_display._widgets.clear()

        # Get current metrics
        current_metrics = self.performance_monitor.update_metrics()
        if not current_metrics:
            self.performance_display += ptg.Label(
                "[dim]No performance data available[/dim]"
            )
            return

        # Get averages
        avg_metrics = self.performance_monitor.get_average_metrics(5)

        # Display current metrics
        uptime_str = self._format_duration(current_metrics["uptime"])
        self.performance_display += ptg.Label(f"Uptime: {uptime_str}")

        # CPU usage with color coding
        cpu_percent = current_metrics["cpu_percent"]
        cpu_color = self._get_usage_color(cpu_percent)
        self.performance_display += ptg.Label(
            f"CPU: [{cpu_color}]{cpu_percent:.1f}%[/{cpu_color}]"
        )

        # Memory usage with color coding
        memory_mb = current_metrics["memory_mb"]
        memory_percent = current_metrics["memory_percent"]
        memory_color = self._get_usage_color(memory_percent)
        self.performance_display += ptg.Label(
            f"Memory: [{memory_color}]{memory_mb:.1f}MB ({memory_percent:.1f}%)[/{memory_color}]"
        )

        # Disk usage
        disk_used = current_metrics["disk_used_gb"]
        disk_free = current_metrics["disk_free_gb"]
        disk_percent = current_metrics["disk_percent"]
        disk_color = self._get_usage_color(disk_percent)
        self.performance_display += ptg.Label(
            f"Disk: [{disk_color}]{disk_used:.1f}GB used, {disk_free:.1f}GB free ({disk_percent:.1f}%)[/{disk_color}]"
        )

        # I/O statistics
        io_read = current_metrics["io_read_mb"]
        io_write = current_metrics["io_write_mb"]
        self.performance_display += ptg.Label(
            f"I/O: {io_read:.1f}MB read, {io_write:.1f}MB write"
        )

        # Show averages if available
        if avg_metrics:
            self.performance_display += ptg.Label("")  # Spacer
            self.performance_display += ptg.Label("[dim]5-minute averages:[/dim]")
            self.performance_display += ptg.Label(
                f"[dim]CPU: {avg_metrics['cpu_percent']:.1f}%, "
                f"Memory: {avg_metrics['memory_mb']:.1f}MB ({avg_metrics['memory_percent']:.1f}%)[/dim]"
            )

    def _update_async_display(self) -> None:
        """Update the async operations display."""
        self.async_display._widgets.clear()

        # Show active operations
        active_ops = self.async_tracker.get_active_operations()
        if active_ops:
            self.async_display += ptg.Label(
                f"[yellow]Active: {len(active_ops)} operations[/yellow]"
            )
            for op in active_ops[:3]:  # Show max 3 active operations
                duration = (datetime.now() - op["start_time"]).total_seconds()
                self.async_display += ptg.Label(
                    f"  • {op['description']} ({duration:.1f}s)"
                )
            if len(active_ops) > 3:
                self.async_display += ptg.Label(f"  ... and {len(active_ops) - 3} more")
        else:
            self.async_display += ptg.Label("[green]No active operations[/green]")

        # Show recent completed operations
        recent_ops = self.async_tracker.get_recent_operations(3)
        if recent_ops:
            self.async_display += ptg.Label("")  # Spacer
            self.async_display += ptg.Label("[dim]Recent completed:[/dim]")
            for op in recent_ops:
                status_color = "green" if op["success"] else "red"
                status_icon = "✅" if op["success"] else "❌"
                self.async_display += ptg.Label(
                    f"  [{status_color}]{status_icon} {op['description']} ({op['duration']:.1f}s)[/{status_color}]"
                )

    def _update_session_display(self, session_id: str = "") -> None:
        """Update the session debug information display.

        Args:
            session_id: Session ID to display info for
        """
        self.session_display._widgets.clear()

        try:
            # Get session summary
            summary = self.session_manager.get_session_summary()
            self.session_display += ptg.Label(
                f"Total Sessions: {summary['total_sessions']}"
            )
            self.session_display += ptg.Label(
                f"Active: {summary['active_sessions']}, "
                f"Waiting: {summary['waiting_sessions']}, "
                f"Errors: {summary['error_sessions']}"
            )

            # Show active session details if available
            active_session = self.session_manager.get_active_session()
            if active_session:
                self.session_display += ptg.Label("")  # Spacer
                self.session_display += ptg.Label("[bold]Active Session:[/bold]")

                # Session ID (shortened)
                short_id = (
                    active_session.sid[:8] + "..."
                    if len(active_session.sid) > 12
                    else active_session.sid
                )
                self.session_display += ptg.Label(f"ID: {short_id}")

                # Agent state
                if (
                    hasattr(active_session, "agent_state")
                    and active_session.agent_state
                ):
                    state_color = self._get_state_color(
                        active_session.agent_state.value
                    )
                    self.session_display += ptg.Label(
                        f"State: [{state_color}]{active_session.agent_state.value}[/{state_color}]"
                    )

                # Connection status
                if hasattr(active_session, "is_connected"):
                    conn_status = (
                        "🟢 Connected"
                        if active_session.is_connected
                        else "🔴 Disconnected"
                    )
                    self.session_display += ptg.Label(f"Connection: {conn_status}")

                # Error count if available
                if hasattr(active_session, "error_count"):
                    try:
                        error_count = active_session.error_count
                        if error_count > 0:
                            self.session_display += ptg.Label(
                                f"[red]Errors: {error_count}[/red]"
                            )
                    except (TypeError, AttributeError):
                        # Handle mock objects or invalid error_count values
                        pass

            else:
                self.session_display += ptg.Label("[dim]No active session[/dim]")

        except Exception as e:
            logger.error(f"Error updating session display: {e}")
            self.session_display += ptg.Label(f"[red]Error: {str(e)}[/red]")

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def _get_usage_color(self, percentage: float) -> str:
        """Get color for usage percentage.

        Args:
            percentage: Usage percentage (0-100)

        Returns:
            Color name for the percentage
        """
        if percentage < 50:
            return "green"
        elif percentage < 80:
            return "yellow"
        else:
            return "red"

    def _get_state_color(self, state: str) -> str:
        """Get color for agent state.

        Args:
            state: Agent state string

        Returns:
            Color name for the state
        """
        state_colors = {
            "LOADING": "yellow",
            "AWAITING_USER_INPUT": "green",
            "RUNNING": "blue",
            "STOPPED": "dim",
            "ERROR": "red",
            "PAUSED": "orange",
            "FINISHED": "cyan",
        }
        return state_colors.get(state.upper(), "white")

    def track_async_operation(self, operation_id: str, description: str) -> None:
        """Start tracking an async operation.

        Args:
            operation_id: Unique identifier for the operation
            description: Human-readable description of the operation
        """
        self.async_tracker.start_operation(operation_id, description)

    def complete_async_operation(
        self, operation_id: str, success: bool = True, error: str = ""
    ) -> None:
        """Complete tracking an async operation.

        Args:
            operation_id: Unique identifier for the operation
            success: Whether the operation completed successfully
            error: Error message if operation failed
        """
        self.async_tracker.complete_operation(operation_id, success, error)

    def handle_key_event(self, key: str) -> bool:
        """Handle key events for the debug panel.

        Args:
            key: Key that was pressed

        Returns:
            True if the key was handled, False otherwise
        """
        if key == "r":
            # Refresh display immediately
            self.last_display_update = 0
            self.update_display()
            return True
        elif key == "c":
            # Clear performance history
            self.performance_monitor.performance_history.clear()
            self.async_tracker.completed_operations.clear()
            return True

        return False
