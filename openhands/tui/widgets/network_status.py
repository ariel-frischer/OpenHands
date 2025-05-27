"""Network Status Widget.

Widget for displaying TUI network connectivity status and reconnection indicators.
"""

import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger
from openhands.core.schema import AgentState

if TYPE_CHECKING:
    from ..managers import SessionManager, TUIEventManager


class NetworkStatusWidget(ptg.Container):
    """Widget for displaying network connectivity status and reconnection indicators."""

    def __init__(
        self,
        session_manager: "SessionManager",
        event_manager: Optional["TUIEventManager"] = None,
    ):
        """Initialize the network status widget.

        Args:
            session_manager: Session manager instance
            event_manager: Event manager instance (optional)
        """
        super().__init__()
        self.session_manager = session_manager
        self.event_manager = event_manager

        # Update throttling
        self.last_update = 0
        self.update_interval = 3.0  # Update every 3 seconds

        # Connection tracking
        self.connection_history: List[Dict] = []
        self.max_history = 20  # Keep last 20 connection checks

        # Network status containers
        self.connection_status = ptg.Container()
        self.session_connections = ptg.Container()
        self.reconnection_status = ptg.Container()

        # Add sections to widget
        self += ptg.Label("[bold cyan]Network Status[/bold cyan]")
        self += self.connection_status
        self += ptg.Label("")  # Spacer

        self += ptg.Label("[bold yellow]Session Connections[/bold yellow]")
        self += self.session_connections
        self += ptg.Label("")  # Spacer

        self += ptg.Label("[bold orange]Reconnection Status[/bold orange]")
        self += self.reconnection_status

        # Initialize display (but don't trigger connectivity checks during init)
        try:
            self._update_session_connections()
            self._update_reconnection_status()
        except Exception as e:
            logger.error(f"Error during initial display setup: {e}")

    def update_display(self) -> None:
        """Update the network status display."""
        current_time = time.time()

        # Throttle updates
        if current_time - self.last_update < self.update_interval:
            return

        try:
            self._update_connection_status()
            self._update_session_connections()
            self._update_reconnection_status()
            self.last_update = current_time

        except Exception as e:
            logger.error(f"Error updating network status display: {e}")

    def _update_connection_status(self) -> None:
        """Update overall connection status display."""
        self.connection_status._widgets.clear()

        try:
            # Check overall system connectivity
            overall_status = self._check_overall_connectivity()

            # Display overall status
            if overall_status["connected"]:
                self.connection_status += ptg.Label(
                    f"[green]🟢 System Online[/green] ({overall_status['check_time']:.1f}ms)"
                )
            else:
                self.connection_status += ptg.Label(
                    f"[red]🔴 System Offline[/red] - {overall_status['error']}"
                )

            # Show connection quality
            if overall_status["connected"]:
                quality = self._get_connection_quality(overall_status["check_time"])
                quality_color = self._get_quality_color(quality)
                self.connection_status += ptg.Label(
                    f"Connection Quality: [{quality_color}]{quality}[/{quality_color}]"
                )

            # Show network statistics
            if self.connection_history:
                success_rate = self._calculate_success_rate()
                avg_latency = self._calculate_average_latency()

                self.connection_status += ptg.Label(
                    f"Success Rate: {success_rate:.1f}% (last {len(self.connection_history)} checks)"
                )
                if avg_latency > 0:
                    self.connection_status += ptg.Label(
                        f"Average Latency: {avg_latency:.1f}ms"
                    )

        except Exception as e:
            logger.error(f"Error updating connection status: {e}")
            self.connection_status += ptg.Label(f"[red]Error: {str(e)}[/red]")

    def _update_session_connections(self) -> None:
        """Update session-specific connection status."""
        self.session_connections._widgets.clear()

        try:
            sessions = self.session_manager.list_sessions()

            if not sessions:
                self.session_connections += ptg.Label(
                    "[dim]No sessions to monitor[/dim]"
                )
                return

            # Count connection states
            connected_count = 0
            disconnected_count = 0
            error_count = 0

            for session in sessions:
                if session.agent_state == AgentState.ERROR:
                    error_count += 1
                elif session.is_connected:
                    connected_count += 1
                else:
                    disconnected_count += 1

            # Display summary
            self.session_connections += ptg.Label(
                f"Connected: [green]{connected_count}[/green] | "
                f"Disconnected: [yellow]{disconnected_count}[/yellow] | "
                f"Errors: [red]{error_count}[/red]"
            )

            # Show individual session status (max 5 for space)
            sessions_to_show = sessions[:5]
            for session in sessions_to_show:
                status_icon, status_color = self._get_session_status_display(session)
                short_id = (
                    session.sid[:8] + "..." if len(session.sid) > 12 else session.sid
                )

                # Add connection validation if event manager is available
                connection_valid = True
                if self.event_manager:
                    connection_valid = self.event_manager.validate_session_connection(
                        session.sid
                    )

                validation_icon = "✅" if connection_valid else "⚠️"

                self.session_connections += ptg.Label(
                    f"  {status_icon} {short_id} [{status_color}]{session.agent_state.value}[/{status_color}] {validation_icon}"
                )

            if len(sessions) > 5:
                self.session_connections += ptg.Label(
                    f"  ... and {len(sessions) - 5} more"
                )

        except Exception as e:
            logger.error(f"Error updating session connections: {e}")
            self.session_connections += ptg.Label(f"[red]Error: {str(e)}[/red]")

    def _update_reconnection_status(self) -> None:
        """Update reconnection status and indicators."""
        self.reconnection_status._widgets.clear()

        try:
            # Check for sessions needing reconnection
            sessions_needing_reconnection = self._get_sessions_needing_reconnection()

            if not sessions_needing_reconnection:
                self.reconnection_status += ptg.Label(
                    "[green]✅ All sessions stable[/green]"
                )
                return

            self.reconnection_status += ptg.Label(
                f"[yellow]⚠️  {len(sessions_needing_reconnection)} session(s) need attention[/yellow]"
            )

            # Show sessions needing reconnection (max 3)
            for session in sessions_needing_reconnection[:3]:
                short_id = (
                    session.sid[:8] + "..." if len(session.sid) > 12 else session.sid
                )
                reason = self._get_reconnection_reason(session)

                self.reconnection_status += ptg.Label(f"  🔄 {short_id}: {reason}")

            if len(sessions_needing_reconnection) > 3:
                self.reconnection_status += ptg.Label(
                    f"  ... and {len(sessions_needing_reconnection) - 3} more"
                )

            # Show reconnection actions available
            self.reconnection_status += ptg.Label("")  # Spacer
            self.reconnection_status += ptg.Label(
                "[dim]Press 'r' to attempt reconnection of all sessions[/dim]"
            )

        except Exception as e:
            logger.error(f"Error updating reconnection status: {e}")
            self.reconnection_status += ptg.Label(f"[red]Error: {str(e)}[/red]")

    def _check_overall_connectivity(self) -> Dict:
        """Check overall system connectivity.

        Returns:
            Dictionary containing connectivity status
        """
        start_time = time.time()

        try:
            # Use session manager's health check capabilities
            active_session = self.session_manager.get_active_session()

            if active_session:
                # Check if we can get session health (indicates connectivity)
                health = self.session_manager.get_session_health(active_session.sid)
                connected = health.get("healthy", False)
                error = None if connected else health.get("reason", "Unknown error")
            else:
                # No active session, assume system is online but no sessions
                connected = True
                error = None

            check_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            # Record in history
            self.connection_history.append(
                {
                    "timestamp": datetime.now(),
                    "connected": connected,
                    "check_time": check_time,
                    "error": error,
                }
            )

            # Limit history
            if len(self.connection_history) > self.max_history:
                self.connection_history.pop(0)

            return {
                "connected": connected,
                "check_time": check_time,
                "error": error,
            }

        except Exception as e:
            check_time = (time.time() - start_time) * 1000
            error_result = {
                "connected": False,
                "check_time": check_time,
                "error": str(e),
            }

            self.connection_history.append(
                {
                    "timestamp": datetime.now(),
                    "connected": False,
                    "check_time": check_time,
                    "error": str(e),
                }
            )

            if len(self.connection_history) > self.max_history:
                self.connection_history.pop(0)

            return error_result

    def _get_connection_quality(self, latency: float) -> str:
        """Get connection quality based on latency.

        Args:
            latency: Latency in milliseconds

        Returns:
            Quality description string
        """
        if latency < 50:
            return "Excellent"
        elif latency < 100:
            return "Good"
        elif latency < 200:
            return "Fair"
        elif latency < 500:
            return "Poor"
        else:
            return "Very Poor"

    def _get_quality_color(self, quality: str) -> str:
        """Get color for connection quality.

        Args:
            quality: Quality description

        Returns:
            Color name
        """
        quality_colors = {
            "Excellent": "green",
            "Good": "green",
            "Fair": "yellow",
            "Poor": "orange",
            "Very Poor": "red",
        }
        return quality_colors.get(quality, "white")

    def _calculate_success_rate(self) -> float:
        """Calculate connection success rate from history.

        Returns:
            Success rate as percentage
        """
        if not self.connection_history:
            return 0.0

        successful = sum(1 for check in self.connection_history if check["connected"])
        return (successful / len(self.connection_history)) * 100

    def _calculate_average_latency(self) -> float:
        """Calculate average latency from successful connections.

        Returns:
            Average latency in milliseconds
        """
        successful_checks = [
            check
            for check in self.connection_history
            if check["connected"] and check["check_time"] > 0
        ]

        if not successful_checks:
            return 0.0

        return sum(check["check_time"] for check in successful_checks) / len(
            successful_checks
        )

    def _get_session_status_display(self, session) -> tuple[str, str]:
        """Get display icon and color for session status.

        Args:
            session: Session context

        Returns:
            Tuple of (icon, color)
        """
        if session.agent_state == AgentState.ERROR:
            return "❌", "red"
        elif not session.is_connected:
            return "🔴", "yellow"
        elif session.agent_state == AgentState.RUNNING:
            return "🟢", "blue"
        elif session.agent_state == AgentState.AWAITING_USER_INPUT:
            return "🟢", "green"
        elif session.agent_state == AgentState.LOADING:
            return "🟡", "yellow"
        else:
            return "⚪", "dim"

    def _get_sessions_needing_reconnection(self) -> List:
        """Get sessions that need reconnection.

        Returns:
            List of sessions needing reconnection
        """
        try:
            sessions_needing_reconnection = []

            for session in self.session_manager.list_sessions():
                # Check for disconnected sessions that should be connected
                if not session.is_connected and session.agent_state in [
                    AgentState.RUNNING,
                    AgentState.AWAITING_USER_INPUT,
                ]:
                    sessions_needing_reconnection.append(session)
                    continue

                # Check for error states
                if session.agent_state == AgentState.ERROR:
                    sessions_needing_reconnection.append(session)
                    continue

                # Check for sessions with high error counts
                if session.error_count > 3:
                    sessions_needing_reconnection.append(session)
                    continue

                # Check event stream validation if event manager available
                if self.event_manager:
                    if not self.event_manager.validate_session_connection(session.sid):
                        sessions_needing_reconnection.append(session)
                        continue

            return sessions_needing_reconnection

        except Exception as e:
            logger.error(f"Error getting sessions needing reconnection: {e}")
            return []

    def _get_reconnection_reason(self, session) -> str:
        """Get reason why session needs reconnection.

        Args:
            session: Session context

        Returns:
            Reason string
        """
        if session.agent_state == AgentState.ERROR:
            return "Error state"
        elif not session.is_connected:
            return "Disconnected"
        elif session.error_count > 3:
            return f"High error count ({session.error_count})"
        elif self.event_manager and not self.event_manager.validate_session_connection(
            session.sid
        ):
            return "Event stream invalid"
        else:
            return "Unknown issue"

    def attempt_reconnect_all(self) -> None:
        """Attempt to reconnect all sessions needing reconnection."""
        try:
            sessions_needing_reconnection = self._get_sessions_needing_reconnection()

            if not sessions_needing_reconnection:
                logger.info("No sessions need reconnection")
                return

            logger.info(
                f"Attempting to reconnect {len(sessions_needing_reconnection)} sessions"
            )

            for session in sessions_needing_reconnection:
                try:
                    # Set session as connected (this will trigger reconnection logic)
                    self.session_manager.set_session_connected(session.sid, True)

                    # Re-subscribe to events if event manager is available
                    if self.event_manager:
                        self.event_manager.subscribe_to_session(session.sid)

                    logger.info(f"Attempted reconnection for session {session.sid}")

                except Exception as e:
                    logger.error(f"Failed to reconnect session {session.sid}: {e}")

            # Force immediate update to show changes
            self.last_update = 0
            self.update_display()

        except Exception as e:
            logger.error(f"Error during reconnection attempt: {e}")

    def get_network_summary(self) -> Dict:
        """Get a summary of network status.

        Returns:
            Dictionary containing network status summary
        """
        try:
            overall_status = self._check_overall_connectivity()
            sessions_needing_reconnection = self._get_sessions_needing_reconnection()

            return {
                "system_online": overall_status["connected"],
                "connection_quality": self._get_connection_quality(
                    overall_status["check_time"]
                )
                if overall_status["connected"]
                else "Offline",
                "success_rate": self._calculate_success_rate(),
                "average_latency": self._calculate_average_latency(),
                "sessions_needing_reconnection": len(sessions_needing_reconnection),
                "last_check": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting network summary: {e}")
            return {
                "system_online": False,
                "connection_quality": "Error",
                "success_rate": 0.0,
                "average_latency": 0.0,
                "sessions_needing_reconnection": 0,
                "last_check": datetime.now().isoformat(),
                "error": str(e),
            }

    def handle_key_event(self, key: str) -> bool:
        """Handle key events for the network status widget.

        Args:
            key: Key that was pressed

        Returns:
            True if the key was handled, False otherwise
        """
        if key == "r":
            # Attempt reconnection
            self.attempt_reconnect_all()
            return True
        elif key == "n":
            # Force network status refresh
            self.last_update = 0
            return True

        return False


class NetworkReconnectionWidget(ptg.Container):
    """Widget for managing network reconnection operations."""

    def __init__(
        self,
        session_manager: "SessionManager",
        event_manager: Optional["TUIEventManager"] = None,
    ):
        """Initialize the network reconnection widget.

        Args:
            session_manager: Session manager instance
            event_manager: Event manager instance (optional)
        """
        super().__init__()
        self.session_manager = session_manager
        self.event_manager = event_manager

        # Reconnection tracking
        self.reconnection_attempts: Dict[str, Dict] = {}
        self.last_reconnection_time = 0

        # Widget sections
        self.reconnection_controls = ptg.Container()
        self.reconnection_log = ptg.Container()

        # Add sections
        self += ptg.Label("[bold green]Reconnection Controls[/bold green]")
        self += self.reconnection_controls
        self += ptg.Label("")  # Spacer

        self += ptg.Label("[bold blue]Reconnection Log[/bold blue]")
        self += self.reconnection_log

        # Initialize display
        self.update_display()

    def update_display(self) -> None:
        """Update the reconnection widget display."""
        try:
            self._update_reconnection_controls()
            self._update_reconnection_log()

        except Exception as e:
            logger.error(f"Error updating reconnection widget: {e}")

    def _update_reconnection_controls(self) -> None:
        """Update reconnection controls display."""
        self.reconnection_controls._widgets.clear()

        try:
            # Show available actions
            self.reconnection_controls += ptg.Label("Available Actions:")
            self.reconnection_controls += ptg.Label(
                "  [dim]'r' - Reconnect all sessions[/dim]"
            )
            self.reconnection_controls += ptg.Label(
                "  [dim]'c' - Clear reconnection log[/dim]"
            )
            self.reconnection_controls += ptg.Label(
                "  [dim]'s' - Show session health details[/dim]"
            )

            # Show last reconnection time
            if self.last_reconnection_time > 0:
                time_since = time.time() - self.last_reconnection_time
                self.reconnection_controls += ptg.Label("")  # Spacer
                self.reconnection_controls += ptg.Label(
                    f"Last reconnection attempt: {time_since:.1f}s ago"
                )

        except Exception as e:
            logger.error(f"Error updating reconnection controls: {e}")
            self.reconnection_controls += ptg.Label(f"[red]Error: {str(e)}[/red]")

    def _update_reconnection_log(self) -> None:
        """Update reconnection log display."""
        self.reconnection_log._widgets.clear()

        try:
            if not self.reconnection_attempts:
                self.reconnection_log += ptg.Label(
                    "[dim]No reconnection attempts yet[/dim]"
                )
                return

            # Show recent reconnection attempts (last 5)
            recent_attempts = list(self.reconnection_attempts.items())[-5:]

            for session_id, attempt_info in recent_attempts:
                short_id = (
                    session_id[:8] + "..." if len(session_id) > 12 else session_id
                )
                timestamp = attempt_info["timestamp"].strftime("%H:%M:%S")
                success = attempt_info["success"]

                status_icon = "✅" if success else "❌"
                status_color = "green" if success else "red"

                self.reconnection_log += ptg.Label(
                    f"  {status_icon} [{status_color}]{timestamp}[/{status_color}] {short_id}"
                )

                if not success and "error" in attempt_info:
                    error_preview = (
                        attempt_info["error"][:40] + "..."
                        if len(attempt_info["error"]) > 40
                        else attempt_info["error"]
                    )
                    self.reconnection_log += ptg.Label(
                        f"    [red]{error_preview}[/red]"
                    )

        except Exception as e:
            logger.error(f"Error updating reconnection log: {e}")
            self.reconnection_log += ptg.Label(f"[red]Error: {str(e)}[/red]")

    def attempt_session_reconnection(self, session_id: str) -> bool:
        """Attempt to reconnect a specific session.

        Args:
            session_id: ID of the session to reconnect

        Returns:
            True if reconnection was successful, False otherwise
        """
        try:
            logger.info(f"Attempting to reconnect session {session_id}")

            # Record attempt start
            attempt_info = {
                "timestamp": datetime.now(),
                "success": False,
                "error": None,
            }

            # Try to reconnect the session
            self.session_manager.set_session_connected(session_id, True)

            # Re-subscribe to events if event manager is available
            if self.event_manager:
                self.event_manager.subscribe_to_session(session_id)

            # Validate the reconnection
            if self.event_manager:
                connection_valid = self.event_manager.validate_session_connection(
                    session_id
                )
                if not connection_valid:
                    raise Exception("Event stream validation failed after reconnection")

            # Mark as successful
            attempt_info["success"] = True
            self.reconnection_attempts[session_id] = attempt_info
            self.last_reconnection_time = time.time()

            logger.info(f"Successfully reconnected session {session_id}")
            return True

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to reconnect session {session_id}: {error_msg}")

            # Record failed attempt
            attempt_info["error"] = error_msg
            self.reconnection_attempts[session_id] = attempt_info
            self.last_reconnection_time = time.time()

            return False

    def clear_reconnection_log(self) -> None:
        """Clear the reconnection log."""
        self.reconnection_attempts.clear()
        self.update_display()
        logger.info("Reconnection log cleared")

    def handle_key_event(self, key: str) -> bool:
        """Handle key events for the reconnection widget.

        Args:
            key: Key that was pressed

        Returns:
            True if the key was handled, False otherwise
        """
        if key == "c":
            # Clear reconnection log
            self.clear_reconnection_log()
            return True
        elif key == "s":
            # Show session health details (log to console)
            self._log_session_health_details()
            return True

        return False

    def _log_session_health_details(self) -> None:
        """Log detailed session health information."""
        try:
            sessions = self.session_manager.list_sessions()

            logger.info("=== Session Health Details ===")
            for session in sessions:
                health = self.session_manager.get_session_health(session.sid)
                logger.info(f"Session {session.sid[:8]}...: {health}")
            logger.info("=== End Session Health Details ===")

        except Exception as e:
            logger.error(f"Error logging session health details: {e}")
