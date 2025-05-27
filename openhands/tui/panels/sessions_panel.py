"""Sessions Panel.

Left panel showing session list and management.
"""

from typing import TYPE_CHECKING

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger

from .base_panel import BasePanel

if TYPE_CHECKING:
    from ..managers import SessionContext, SessionManager, TUIPanelFileManager


class SessionsPanel(BasePanel):
    """Left panel showing session list and management."""
    
    def __init__(self, session_manager: "SessionManager", file_manager: "TUIPanelFileManager"):
        """Initialize the sessions panel.
        
        Args:
            session_manager: Session manager instance
            file_manager: File manager instance
        """
        super().__init__(session_manager, file_manager, "Sessions")
        self.session_widgets: dict[str, ptg.Widget] = {}
        
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
        indicator = "●" if is_active else " "
        
        # Session info
        task_preview = session.task_description[:30]
        if len(session.task_description) > 30:
            task_preview += "..."
        
        label = f"{indicator} {task_preview}"
        
        # Create button with session switching callback
        button = ptg.Button(
            label,
            lambda s=session.sid: self.switch_to_session(s)
        )
        
        # Style active session differently
        if is_active:
            button.styles.label = "bold green"
        
        return button
    
    async def create_new_session(self) -> None:
        """Create new session with task input."""
        logger.info("Creating new session...")
        
        # TODO: Show input dialog for task description
        # For now, create with default task
        task = "New session"
        
        try:
            session_id = await self.session_manager.create_session(task)
            logger.info(f"Created new session: {session_id}")
            
            # Subscribe to session events for real-time updates
            if hasattr(self.session_manager, 'event_manager'):
                self.session_manager.event_manager.subscribe_to_session(session_id)
            
            # Start the session (this begins the agent controller loop)
            await self.session_manager.start_session(session_id)
            
            # Update display
            self.update_sessions()
            
        except Exception as e:
            logger.error(f"Failed to create new session: {e}")
    
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
            import asyncio
            
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self.create_new_session())
            except RuntimeError:
                # No running event loop, run in new loop
                asyncio.run(self.create_new_session())
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
        if hasattr(self, '_widgets'):
            for widget in self._widgets:
                if hasattr(widget, 'refresh'):
                    widget.refresh()
