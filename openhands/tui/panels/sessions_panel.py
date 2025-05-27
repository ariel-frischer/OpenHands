"""Sessions Panel.

Left panel showing session list and management.
"""

import asyncio
import time
from typing import TYPE_CHECKING

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger

from .base_panel import BasePanel

if TYPE_CHECKING:
    from ..managers import SessionContext, SessionManager, TUIPanelFileManager


class SessionsPanel(BasePanel):
    """Left panel showing session list and management."""

    def __init__(
        self, session_manager: "SessionManager", file_manager: "TUIPanelFileManager"
    ):
        """Initialize the sessions panel.

        Args:
            session_manager: Session manager instance
            file_manager: File manager instance
        """
        super().__init__(session_manager, file_manager, "Sessions")
        self.session_widgets: dict[str, ptg.Widget] = {}
        self._last_button_click = 0  # For button debouncing
        self._creating_session = False  # Prevent multiple simultaneous session creation

        logger.debug(
            f"SessionsPanel initialized with dimensions: {getattr(self, 'width', 'unknown')}x{getattr(self, 'height', 'unknown')}"
        )

        # Session list container
        self.session_list = ptg.Container()
        self.add_content(self.session_list)

        # New session button
        self.add_content(ptg.Label(""))  # Spacer
        self.add_content(ptg.Button("New Session", self.create_new_session))

    def get_panel_name(self) -> str:
        """Get the panel name for file operations.

        Returns:
            Panel name string
        """
        return "sessions"

    def update_display(self, session_id: str = "") -> None:
        """Update the sessions display.

        Args:
            session_id: Not used for sessions panel
        """
        self.update_sessions()

    def update_sessions(self) -> None:
        """Update session list display."""
        logger.debug("Updating sessions display")

        # Clear existing widgets
        self.session_list._widgets.clear()
        self.session_widgets.clear()

        # Add session widgets
        sessions = self.session_manager.list_sessions()
        for session in sessions:
            widget = self.create_session_widget(session)
            self.session_list += widget
            self.session_widgets[session.sid] = widget

        if not sessions:
            self.session_list += ptg.Label("[dim]No active sessions[/dim]")

        # Update sessions file for Ctrl+E
        self.file_manager.update_sessions_file(sessions)

    def create_session_widget(self, session: "SessionContext") -> ptg.Widget:
        """Create widget for individual session.

        Args:
            session: Session context to create widget for

        Returns:
            Widget representing the session
        """
        # Active session indicator
        is_active = session.sid == self.session_manager.active_session_id
        active_indicator = "●" if is_active else " "

        # Session status indicator
        from openhands.core.schema import AgentState

        if session.agent_state == AgentState.LOADING:
            status_indicator = "⏳"  # Loading
        elif session.agent_state == AgentState.AWAITING_USER_INPUT:
            status_indicator = "✅"  # Ready
        elif session.agent_state == AgentState.RUNNING:
            status_indicator = "🔥"  # Running
        elif session.agent_state == AgentState.STOPPED:
            status_indicator = "⏹️"  # Stopped
        elif session.agent_state == AgentState.ERROR:
            status_indicator = "❌"  # Error
        else:
            status_indicator = "❓"  # Unknown

        # Session info
        task_preview = session.task_description[:25]  # Shorter to fit status
        if len(session.task_description) > 25:
            task_preview += "..."

        label = f"{active_indicator} {status_indicator} {task_preview}"

        # Create button with session switching callback
        button = ptg.Button(label, lambda s=session.sid: self.switch_to_session_sync(s))

        # Style active session differently
        if is_active:
            button.styles.label = "bold green"

        return button

    def create_new_session(self, *args) -> None:
        """Create new session with task input.

        Args:
            *args: Arguments from PyTermGUI button callback (ignored)
        """
        # Button debouncing - prevent rapid clicks
        current_time = time.time()
        if current_time - self._last_button_click < 1.0:  # 1 second debounce
            logger.debug("Button click ignored due to debouncing")
            return
        self._last_button_click = current_time

        # Prevent multiple simultaneous session creation
        if self._creating_session:
            logger.debug("Session creation already in progress")
            return

        logger.info("Creating new session...")
        self._creating_session = True

        # Add a temporary "Creating..." indicator to the session list
        self.session_list += ptg.Label("[yellow]🔄 Creating new session...[/yellow]")

        # TODO: Show input dialog for task description
        # For now, create with default task
        task_description = "New session - ready for your first message"

        try:
            # Create session asynchronously in background
            import asyncio

            # Try to get the running event loop
            try:
                loop = asyncio.get_running_loop()
                # Schedule session creation as a background task with exception handling
                async_task = asyncio.create_task(
                    self._create_session_async(task_description)
                )
                # Add exception handler to prevent unhandled exceptions from crashing TUI
                async_task.add_done_callback(self._handle_task_exception)
            except RuntimeError:
                # No running event loop, run in new loop
                asyncio.run(self._create_session_async(task_description))

        except Exception as e:
            logger.error(f"Failed to create new session: {e}", exc_info=True)
            self._creating_session = False
            # Remove the "Creating..." indicator
            self.update_sessions()

    def _handle_task_exception(self, task) -> None:
        """Handle exceptions from background tasks to prevent TUI crashes."""
        try:
            # This will raise the exception if the task failed
            task.result()
            logger.info("Session creation completed successfully")
        except asyncio.CancelledError:
            logger.info("Session creation was cancelled")
        except Exception as e:
            logger.error(f"Background task failed: {e}", exc_info=True)
        finally:
            # Reset the creating session flag and update display
            self._creating_session = False
            # Remove the "Creating..." indicator
            self.update_sessions()

    async def _create_session_async(self, task: str) -> None:
        """Async helper for session creation."""
        try:
            session_id = await self.session_manager.create_session(task)
            logger.info(f"Created new session: {session_id}")

            # Subscribe to session events for real-time updates
            if hasattr(self.session_manager, "event_manager"):
                self.session_manager.event_manager.subscribe_to_session(session_id)

            # Start the session immediately to make it ready for messages
            logger.info(f"Starting session {session_id}...")
            await self.session_manager.start_session(session_id)
            logger.info(f"Session {session_id} is now ready for messages")

            # Update display to remove the "Creating..." indicator and show the new session
            self.update_sessions()

            # Update other panels to reflect the new active session
            if hasattr(self.session_manager, "event_manager") and hasattr(
                self.session_manager.event_manager, "tui_app"
            ):
                tui_app = self.session_manager.event_manager.tui_app
                if tui_app:
                    if hasattr(tui_app, "chat_panel"):
                        tui_app.chat_panel.update_display()
                    if hasattr(tui_app, "logs_panel"):
                        tui_app.logs_panel.update_display()

        except Exception as e:
            logger.error(f"Failed to create new session: {e}", exc_info=True)
            # Provide user-friendly error messages for common issues
            error_msg = str(e).lower()
            if "docker" in error_msg:
                logger.error(
                    "Docker-related error. Please ensure Docker is running and accessible."
                )
            elif "network" in error_msg or "connection" in error_msg:
                logger.error(
                    "Network connectivity issue. Please check your internet connection."
                )
            elif "permission" in error_msg:
                logger.error(
                    "Permission error. Please check file/directory permissions."
                )
            else:
                logger.error(f"Session creation failed with error: {e}")

    def switch_to_session_sync(self, session_id: str) -> None:
        """Synchronous wrapper for switching to a session.

        Args:
            session_id: ID of the session to switch to
        """
        try:
            # Create async task for session switching
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self.switch_to_session(session_id))
            except RuntimeError:
                # No running event loop, run in new loop
                asyncio.run(self.switch_to_session(session_id))
        except Exception as e:
            logger.error(f"Error switching to session {session_id}: {e}")

    async def switch_to_session(self, session_id: str) -> None:
        """Switch to selected session.

        Args:
            session_id: ID of the session to switch to
        """
        logger.info(f"Switching to session: {session_id}")

        try:
            await self.session_manager.switch_session(session_id)

            # Update display to reflect active session change
            self.update_sessions()

            logger.info(f"Switched to session: {session_id}")

        except Exception as e:
            logger.error(f"Failed to switch to session {session_id}: {e}")

    async def close_session(self, session_id: str) -> None:
        """Close a session.

        Args:
            session_id: ID of the session to close
        """
        logger.info(f"Closing session: {session_id}")

        try:
            await self.session_manager.close_session(session_id)

            # Update display
            self.update_sessions()

            logger.info(f"Closed session: {session_id}")

        except Exception as e:
            logger.error(f"Failed to close session {session_id}: {e}")

    def handle_key_event(self, key: str) -> bool:
        """Handle key events for the sessions panel.

        Args:
            key: Key that was pressed

        Returns:
            True if the key was handled, False otherwise
        """
        if key == "n":
            # Create new session
            try:
                self.create_new_session()
            except Exception as e:
                logger.error(f"Error creating new session: {e}")
            return True
        elif key == "d":
            # Delete/close active session
            active_session = self.session_manager.get_active_session()
            if active_session:
                try:
                    import asyncio

                    loop = asyncio.get_running_loop()
                    asyncio.create_task(self.close_session(active_session.sid))
                except RuntimeError:
                    # No event loop running, run in new loop
                    asyncio.run(self.close_session(active_session.sid))
                except Exception as e:
                    logger.error(f"Error closing session: {e}")
            return True

        return False

    def handle_terminal_resize(self) -> None:
        """Handle terminal resize events."""
        logger.debug("Sessions panel handling terminal resize")

        # Update sessions display to adapt to new terminal size
        self.update_sessions()

        # Refresh the panel content
        if hasattr(self, "_widgets"):
            for widget in self._widgets:
                if hasattr(widget, "refresh"):
                    widget.refresh()
