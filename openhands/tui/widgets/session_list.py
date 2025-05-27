"""Session List Widget.

Specialized widget for displaying and managing session lists.
"""

from typing import TYPE_CHECKING, Callable, Union

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger

if TYPE_CHECKING:
    from ..managers import SessionContext


class SessionList(ptg.Container):
    """Specialized widget for session list display and interaction."""
    
    def __init__(self, on_session_select: Union[Callable[[str], None], None] = None):
        """Initialize the session list widget.
        
        Args:
            on_session_select: Callback function when a session is selected
        """
        super().__init__()
        self.on_session_select = on_session_select
        self.sessions: dict[str, "SessionContext"] = {}
        self.session_widgets: dict[str, ptg.Widget] = {}
        self.active_session_id: Union[str, None] = None
    
    def update_sessions(
        self,
        sessions: list["SessionContext"],
        active_session_id: Union[str, None] = None
    ) -> None:
        """Update the session list.
        
        Args:
            sessions: List of session contexts
            active_session_id: ID of the currently active session
        """
        logger.debug(f"Updating session list with {len(sessions)} sessions")
        
        # Clear existing widgets
        self.clear()
        self.session_widgets.clear()
        
        # Store sessions and active session ID
        self.sessions = {session.sid: session for session in sessions}
        self.active_session_id = active_session_id
        
        if not sessions:
            self += ptg.Label("[dim]No active sessions[/dim]")
            return
        
        # Add session widgets
        for session in sessions:
            widget = self.create_session_widget(session)
            self += widget
            self.session_widgets[session.sid] = widget
    
    def create_session_widget(self, session: "SessionContext") -> ptg.Widget:
        """Create a widget for a single session.
        
        Args:
            session: Session context to create widget for
            
        Returns:
            Widget representing the session
        """
        # Determine if this session is active
        is_active = session.sid == self.active_session_id
        
        # Create session indicator
        indicator = "●" if is_active else " "
        
        # Format session info
        task_preview = self.format_task_description(session.task_description)
        status = self.format_session_status(session.agent_state.value if session.agent_state else "unknown")
        
        # Create session label
        label_text = f"{indicator} {task_preview}"
        
        # Create clickable button
        button = ptg.Button(
            label_text,
            lambda s=session.sid: self.select_session(s)
        )
        
        # Style active session differently
        if is_active:
            button.styles.label = "bold green"
        else:
            button.styles.label = "white"
        
        return button
    
    def format_task_description(self, description: str, max_length: int = 25) -> str:
        """Format task description for display.
        
        Args:
            description: Task description
            max_length: Maximum length to display
            
        Returns:
            Formatted task description
        """
        if not description:
            return "[dim]Untitled[/dim]"
        
        if len(description) <= max_length:
            return description
        
        return description[:max_length - 3] + "..."
    
    def format_session_status(self, status: str) -> str:
        """Format session status with color coding.
        
        Args:
            status: Session status
            
        Returns:
            Formatted status string
        """
        status_colors = {
            'init': 'yellow',
            'running': 'green',
            'paused': 'orange',
            'finished': 'blue',
            'error': 'red',
            'stopped': 'dim'
        }
        
        color = status_colors.get(status.lower(), 'white')
        return f"[{color}]{status}[/{color}]"
    
    def select_session(self, session_id: str) -> None:
        """Handle session selection.
        
        Args:
            session_id: ID of the selected session
        """
        logger.debug(f"Session selected: {session_id}")
        
        if self.on_session_select:
            self.on_session_select(session_id)
    
    def highlight_session(self, session_id: str) -> None:
        """Highlight a specific session.
        
        Args:
            session_id: ID of the session to highlight
        """
        # Update active session ID
        self.active_session_id = session_id
        
        # Update widget styles
        for sid, widget in self.session_widgets.items():
            if isinstance(widget, ptg.Button):
                if sid == session_id:
                    widget.styles.label = "bold green"
                else:
                    widget.styles.label = "white"
    
    def add_session(self, session: "SessionContext") -> None:
        """Add a new session to the list.
        
        Args:
            session: Session context to add
        """
        logger.debug(f"Adding session to list: {session.sid}")
        
        # Add to sessions dict
        self.sessions[session.sid] = session
        
        # Create and add widget
        widget = self.create_session_widget(session)
        self += widget
        self.session_widgets[session.sid] = widget
        
        # Remove "no sessions" message if it exists
        if len(self.sessions) == 1:
            # This was the first session, refresh the display
            self.update_sessions(list(self.sessions.values()), self.active_session_id)
    
    def remove_session(self, session_id: str) -> None:
        """Remove a session from the list.
        
        Args:
            session_id: ID of the session to remove
        """
        logger.debug(f"Removing session from list: {session_id}")
        
        if session_id in self.sessions:
            # Remove from sessions dict
            del self.sessions[session_id]
            
            # Remove widget
            if session_id in self.session_widgets:
                widget = self.session_widgets[session_id]
                self.remove(widget)
                del self.session_widgets[session_id]
            
            # Update active session if needed
            if self.active_session_id == session_id:
                self.active_session_id = None
            
            # Show "no sessions" message if list is empty
            if not self.sessions:
                self.clear()
                self += ptg.Label("[dim]No active sessions[/dim]")
    
    def get_session_count(self) -> int:
        """Get the number of sessions in the list.
        
        Returns:
            Number of sessions
        """
        return len(self.sessions)
    
    def get_selected_session(self) -> Union["SessionContext", None]:
        """Get the currently selected/active session.
        
        Returns:
            Active session context or None
        """
        if self.active_session_id and self.active_session_id in self.sessions:
            return self.sessions[self.active_session_id]
        return None
    
    def clear_selection(self) -> None:
        """Clear the current session selection."""
        self.active_session_id = None
        
        # Update widget styles
        for widget in self.session_widgets.values():
            if isinstance(widget, ptg.Button):
                widget.styles.label = "white"