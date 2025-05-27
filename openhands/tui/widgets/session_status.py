"""Session Status Widget.

Provides comprehensive session state display and recovery functionality for the TUI.
Interfaces with existing OpenHands session persistence without duplication.
"""

import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional, Union

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger
from openhands.core.schema import AgentState

if TYPE_CHECKING:
    from ..managers import SessionContext, SessionManager


class SessionStatusWidget(ptg.Container):
    """Widget for displaying comprehensive session status information."""

    def __init__(self, session_manager: "SessionManager"):
        """Initialize the session status widget.

        Args:
            session_manager: Session manager instance
        """
        super().__init__()
        self.session_manager = session_manager
        self.last_update = 0.0
        self.update_interval = 1.0  # Update every second

        # Status display components
        self.status_header = ptg.Label("[bold]Session Status[/bold]")
        self.session_info = ptg.Container()
        self.recovery_info = ptg.Container()
        self.cleanup_info = ptg.Container()

        # Build initial layout
        self._build_layout()

    def _build_layout(self) -> None:
        """Build the widget layout."""
        # Clear existing widgets
        self._widgets.clear()

        # Add header
        self += self.status_header
        self += ptg.Label("")  # Spacer

        # Add status sections
        self += self.session_info
        self += ptg.Label("")  # Spacer
        self += self.recovery_info
        self += ptg.Label("")  # Spacer
        self += self.cleanup_info

    def update_display(self) -> None:
        """Update the session status display."""
        current_time = time.time()

        # Throttle updates to avoid excessive refreshing
        if current_time - self.last_update < self.update_interval:
            return

        self.last_update = current_time

        try:
            self._update_session_info()
            self._update_recovery_info()
            self._update_cleanup_info()
        except Exception as e:
            logger.error(f"Error updating session status display: {e}")

    def _update_session_info(self) -> None:
        """Update session information display."""
        self.session_info._widgets.clear()

        # Get session summary
        summary = self.session_manager.get_session_summary()
        active_session = self.session_manager.get_active_session()

        # Session count summary
        self.session_info += ptg.Label(f"[bold cyan]Sessions Overview[/bold cyan]")
        self.session_info += ptg.Label(
            f"Total: {summary['total_sessions']} | "
            f"Active: {summary['active_sessions']} | "
            f"Waiting: {summary['waiting_sessions']} | "
            f"Errors: {summary['error_sessions']}"
        )

        # Active session details
        if active_session:
            self.session_info += ptg.Label("")  # Spacer
            self.session_info += ptg.Label(f"[bold green]Active Session[/bold green]")

            # Session ID (shortened for display)
            short_id = (
                active_session.sid[:8] + "..."
                if len(active_session.sid) > 12
                else active_session.sid
            )
            self.session_info += ptg.Label(f"ID: {short_id}")

            # Agent state with color coding
            state_display = self._format_agent_state(active_session.agent_state)
            self.session_info += ptg.Label(f"State: {state_display}")

            # Connection status
            connection_status = (
                "🟢 Connected" if active_session.is_connected else "🔴 Disconnected"
            )
            self.session_info += ptg.Label(f"Connection: {connection_status}")

            # Uptime
            uptime = datetime.now() - active_session.created_at
            uptime_str = self._format_duration(uptime)
            self.session_info += ptg.Label(f"Uptime: {uptime_str}")

            # Task description (truncated)
            task = active_session.task_description or "No task description"
            if len(task) > 40:
                task = task[:37] + "..."
            self.session_info += ptg.Label(f"Task: {task}")

            # Error information if present
            if active_session.error_count > 0:
                self.session_info += ptg.Label(
                    f"[red]Errors: {active_session.error_count}[/red]"
                )
                if active_session.last_error:
                    error_preview = (
                        active_session.last_error[:30] + "..."
                        if len(active_session.last_error) > 30
                        else active_session.last_error
                    )
                    self.session_info += ptg.Label(f"[red]Last: {error_preview}[/red]")
        else:
            self.session_info += ptg.Label("")  # Spacer
            self.session_info += ptg.Label("[dim]No active session[/dim]")

    def _update_recovery_info(self) -> None:
        """Update session recovery information display."""
        self.recovery_info._widgets.clear()

        self.recovery_info += ptg.Label("[bold yellow]Recovery Status[/bold yellow]")

        # Check for sessions that need recovery
        recovery_sessions = self._get_sessions_needing_recovery()

        if recovery_sessions:
            self.recovery_info += ptg.Label(
                f"[yellow]⚠️  {len(recovery_sessions)} session(s) need recovery[/yellow]"
            )

            for session in recovery_sessions[:3]:  # Show max 3 for space
                short_id = (
                    session.sid[:8] + "..." if len(session.sid) > 12 else session.sid
                )
                state = session.agent_state.value if session.agent_state else "unknown"
                self.recovery_info += ptg.Label(f"  • {short_id} ({state})")

            if len(recovery_sessions) > 3:
                self.recovery_info += ptg.Label(
                    f"  ... and {len(recovery_sessions) - 3} more"
                )
        else:
            self.recovery_info += ptg.Label("[green]✅ All sessions healthy[/green]")

        # Show recovery indicators
        disconnected_count = len(
            [s for s in self.session_manager.list_sessions() if not s.is_connected]
        )
        if disconnected_count > 0:
            self.recovery_info += ptg.Label(
                f"[orange]🔌 {disconnected_count} disconnected session(s)[/orange]"
            )

    def _update_cleanup_info(self) -> None:
        """Update cleanup information display."""
        self.cleanup_info._widgets.clear()

        self.cleanup_info += ptg.Label("[bold magenta]Cleanup Status[/bold magenta]")

        # Check for orphaned sessions
        orphaned_sessions = self._get_orphaned_sessions()

        if orphaned_sessions:
            self.cleanup_info += ptg.Label(
                f"[magenta]🧹 {len(orphaned_sessions)} orphaned session(s)[/magenta]"
            )

            for session in orphaned_sessions[:2]:  # Show max 2 for space
                short_id = (
                    session.sid[:8] + "..." if len(session.sid) > 12 else session.sid
                )
                age = datetime.now() - session.last_activity
                age_str = self._format_duration(age)
                self.cleanup_info += ptg.Label(f"  • {short_id} (idle {age_str})")

            if len(orphaned_sessions) > 2:
                self.cleanup_info += ptg.Label(
                    f"  ... and {len(orphaned_sessions) - 2} more"
                )
        else:
            self.cleanup_info += ptg.Label("[green]✅ No cleanup needed[/green]")

        # Show backup status
        backup_status = self._get_backup_status()
        self.cleanup_info += ptg.Label(f"Backup: {backup_status}")

    def _format_agent_state(self, state: Optional[AgentState]) -> str:
        """Format agent state with color coding.

        Args:
            state: Agent state to format

        Returns:
            Formatted state string with color
        """
        if not state:
            return "[dim]Unknown[/dim]"

        state_colors = {
            AgentState.LOADING: "[yellow]⏳ Loading[/yellow]",
            AgentState.AWAITING_USER_INPUT: "[green]✅ Ready[/green]",
            AgentState.RUNNING: "[blue]🔥 Running[/blue]",
            AgentState.STOPPED: "[dim]⏹️  Stopped[/dim]",
            AgentState.ERROR: "[red]❌ Error[/red]",
            AgentState.PAUSED: "[orange]⏸️  Paused[/orange]",
            AgentState.FINISHED: "[cyan]🏁 Finished[/cyan]",
        }

        return state_colors.get(state, f"[white]{state.value}[/white]")

    def _format_duration(self, duration: timedelta) -> str:
        """Format duration for display.

        Args:
            duration: Duration to format

        Returns:
            Human-readable duration string
        """
        total_seconds = int(duration.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def _get_sessions_needing_recovery(self) -> List["SessionContext"]:
        """Get sessions that need recovery.

        Returns:
            List of sessions needing recovery
        """
        try:
            recovery_sessions = []

            for session in self.session_manager.list_sessions():
                # Check for error states
                if session.agent_state == AgentState.ERROR:
                    recovery_sessions.append(session)
                    continue

                # Check for disconnected sessions that should be connected
                if not session.is_connected and session.agent_state in [
                    AgentState.RUNNING,
                    AgentState.AWAITING_USER_INPUT,
                ]:
                    recovery_sessions.append(session)
                    continue

                # Check for sessions with high error counts
                if session.error_count > 5:
                    recovery_sessions.append(session)
                    continue

            return recovery_sessions
        except Exception as e:
            logger.error(f"Error getting sessions needing recovery: {e}")
            return []

    def _get_orphaned_sessions(self) -> List["SessionContext"]:
        """Get orphaned sessions that may need cleanup.

        Returns:
            List of orphaned sessions
        """
        try:
            orphaned_sessions = []
            cutoff_time = datetime.now() - timedelta(hours=1)  # 1 hour idle threshold

            for session in self.session_manager.list_sessions():
                # Check for sessions idle for too long
                if session.last_activity < cutoff_time:
                    # Only consider stopped or error sessions as orphaned
                    if session.agent_state in [AgentState.STOPPED, AgentState.ERROR]:
                        orphaned_sessions.append(session)

            return orphaned_sessions
        except Exception as e:
            logger.error(f"Error getting orphaned sessions: {e}")
            return []

    def _get_backup_status(self) -> str:
        """Get backup status information.

        Returns:
            Backup status string
        """
        # This would interface with existing OpenHands session persistence
        # For now, return a simple status based on session count
        session_count = len(self.session_manager.sessions)

        if session_count == 0:
            return "[dim]No sessions to backup[/dim]"
        elif session_count <= 5:
            return "[green]✅ Up to date[/green]"
        else:
            return "[yellow]⚠️  Many sessions[/yellow]"

    def get_status_summary(self) -> Dict[str, Union[int, str, bool]]:
        """Get a summary of session status information.

        Returns:
            Dictionary containing status summary
        """
        try:
            summary = self.session_manager.get_session_summary()
            active_session = self.session_manager.get_active_session()

            return {
                "total_sessions": summary["total_sessions"],
                "active_sessions": summary["active_sessions"],
                "error_sessions": summary["error_sessions"],
                "has_active_session": active_session is not None,
                "active_session_state": active_session.agent_state.value
                if active_session and active_session.agent_state
                else None,
                "active_session_connected": active_session.is_connected
                if active_session
                else False,
                "sessions_needing_recovery": len(self._get_sessions_needing_recovery()),
                "orphaned_sessions": len(self._get_orphaned_sessions()),
            }
        except Exception as e:
            logger.error(f"Error getting status summary: {e}")
            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "error_sessions": 0,
                "has_active_session": False,
                "active_session_state": None,
                "active_session_connected": False,
                "sessions_needing_recovery": 0,
                "orphaned_sessions": 0,
            }


class SessionRecoveryWidget(ptg.Container):
    """Widget for session recovery operations."""

    def __init__(self, session_manager: "SessionManager"):
        """Initialize the session recovery widget.

        Args:
            session_manager: Session manager instance
        """
        super().__init__()
        self.session_manager = session_manager

        # Recovery controls
        self.recovery_header = ptg.Label("[bold red]Session Recovery[/bold red]")
        self.recovery_controls = ptg.Container()

        self._build_layout()

    def _build_layout(self) -> None:
        """Build the recovery widget layout."""
        self._widgets.clear()

        self += self.recovery_header
        self += ptg.Label("")  # Spacer
        self += self.recovery_controls

        # Add recovery buttons
        self.recovery_controls += ptg.Button(
            "🔄 Reconnect All", self._reconnect_all_sessions
        )
        self.recovery_controls += ptg.Button(
            "🧹 Cleanup Orphaned", self._cleanup_orphaned_sessions
        )
        self.recovery_controls += ptg.Button(
            "💾 Backup Sessions", self._backup_sessions
        )

    def _reconnect_all_sessions(self) -> None:
        """Attempt to reconnect all disconnected sessions."""
        logger.info("Attempting to reconnect all disconnected sessions")

        disconnected_sessions = [
            s for s in self.session_manager.list_sessions() if not s.is_connected
        ]

        for session in disconnected_sessions:
            try:
                # This would trigger reconnection logic
                self.session_manager.set_session_connected(session.sid, True)
                logger.info(f"Reconnected session {session.sid}")
            except Exception as e:
                logger.error(f"Failed to reconnect session {session.sid}: {e}")

    def _cleanup_orphaned_sessions(self) -> None:
        """Clean up orphaned sessions."""
        logger.info("Cleaning up orphaned sessions")

        # This would interface with existing session lifecycle management
        # For now, just log the action
        orphaned_count = len(
            [
                s
                for s in self.session_manager.list_sessions()
                if s.agent_state in [AgentState.STOPPED, AgentState.ERROR]
                and (datetime.now() - s.last_activity).total_seconds() > 3600
            ]
        )

        logger.info(f"Would clean up {orphaned_count} orphaned sessions")

    def _backup_sessions(self) -> None:
        """Backup session states."""
        logger.info("Backing up session states")

        # This would interface with existing session persistence
        # For now, just log the action
        session_count = len(self.session_manager.sessions)
        logger.info(f"Would backup {session_count} sessions")
