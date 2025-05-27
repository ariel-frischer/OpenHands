"""Chat Panel.

Right panel showing chat interface with responsive layout and message display.
"""

import textwrap
from typing import TYPE_CHECKING, Union

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger
from openhands.events.action import MessageAction
from openhands.events.event import Event
from openhands.events.observation import CmdOutputObservation

from .base_panel import BasePanel

if TYPE_CHECKING:
    from ..managers import SessionManager, TUIEventManager, TUIPanelFileManager


class ChatPanel(BasePanel):
    """Right panel showing chat interface."""
    
    def __init__(
        self,
        session_manager: "SessionManager",
        event_manager: "TUIEventManager",
        file_manager: "TUIPanelFileManager"
    ):
        """Initialize the chat panel.
        
        Args:
            session_manager: Session manager instance
            event_manager: Event manager instance
            file_manager: File manager instance
        """
        super().__init__(session_manager, file_manager, "Chat")
        self.event_manager = event_manager
        
        # Chat history display with responsive sizing
        self.chat_display = ptg.Container()
        self.add_content(self.chat_display)
        
        # Add spacer
        self.add_content(ptg.Label(""))
        
        # Input area with Enter key binding
        self.input_field = ptg.InputField(prompt="Message: ")
        # Bind Enter key to send message
        self.input_field.bind(ptg.keys.ENTER, self.send_message)
        
        self.send_button = ptg.Button("Send", self.send_message)
        self.pause_button = ptg.Button("Pause", self.pause_agent)
        
        # Input container with horizontal layout
        input_container = ptg.Container(
            self.input_field,
            ptg.Container(
                self.send_button,
                self.pause_button,
                horizontal=True
            )
        )
        self.add_content(input_container)
        
        # Maximum number of messages to display for performance
        self.max_messages = 50
    
    def get_panel_name(self) -> str:
        """Get the panel name for file operations.
        
        Returns:
            Panel name string
        """
        return "chat"
    
    def update_display(self, session_id: str = "") -> None:
        """Update the chat display.
        
        Args:
            session_id: Session ID to update for
        """
        if not session_id:
            active_session = self.session_manager.get_active_session()
            if active_session:
                session_id = active_session.sid
            else:
                return
        
        self.update_chat_display(session_id)
    
    def update_chat_display(self, session_id: str) -> None:
        """Update chat display for active session with responsive sizing.
        
        Args:
            session_id: Session ID to update chat for
        """
        logger.debug(f"Updating chat display for session: {session_id}")
        
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found")
            return
        
        # Clear existing messages
        self.chat_display._widgets.clear()
        
        # Calculate available height for the chat_display container
        # Panel height - title(1) - spacer(1) - input_field(1) - button_container(1) - bottom_spacer(1) = self.height - 5
        chat_display_container_height = max(1, self.height - 5)
        
        # Add messages from event stream with responsive layout
        if session.event_stream:
            events = list(session.event_stream.get_events())
            # Limit number of events for performance and display
            recent_events = events[-self.max_messages:] if len(events) > self.max_messages else events
            
            for event in recent_events:
                widget = self.create_message_widget(event)
                if widget:
                    self.chat_display += widget
                    
            # If we have too many widgets for the available height, remove oldest ones
            # This is a rough estimate as widgets can have variable lines due to wrapping.
            # A more robust solution might involve a ScrollView or more complex line counting.
            if len(self.chat_display._widgets) > chat_display_container_height:
                widgets_to_remove = len(self.chat_display._widgets) - chat_display_container_height
                for _ in range(widgets_to_remove):
                    if self.chat_display._widgets:
                        self.chat_display._widgets.pop(0)
        else:
            # No event stream yet, show placeholder
            self.chat_display += ptg.Label("[dim]No messages yet[/dim]")
        
        # Update chat file for Ctrl+E
        messages = self.get_chat_messages(session_id)
        self.file_manager.update_chat_file(session_id, messages)
    
    def create_message_widget(self, event: Event) -> Union[ptg.Widget, None]:
        """Create widget for chat message with responsive text wrapping.
        
        Args:
            event: Event to create widget for
            
        Returns:
            Widget representing the event or None if not displayable
        """
        # Calculate available width for message content within the panel
        # self.width is the panel's width. Subtract ~2 for internal padding/borders of the label.
        label_content_area_width = max(10, self.width - 2)
        
        if isinstance(event, MessageAction):
            # User or agent message with text wrapping
            if hasattr(event, 'source'):
                if event.source.value == 'user':
                    prefix = "[bold green]User:[/bold green] "
                else:
                    prefix = "[bold blue]Agent:[/bold blue] "
            else:
                prefix = "[bold]Message:[/bold] "
            
            prefix_visual_len = len(ptg.strip_markup(prefix))
            content_wrap_width = max(10, label_content_area_width - prefix_visual_len)
            wrapped_content = self.wrap_message_content(event.content, content_wrap_width)
            return ptg.Label(f"{prefix}{wrapped_content}")
        
        elif isinstance(event, CmdOutputObservation):
            # Command output with truncation and wrapping
            content = event.content[:200] + "..." if len(event.content) > 200 else event.content
            prefix = "[bold yellow]Output:[/bold yellow] "
            prefix_visual_len = len(ptg.strip_markup(prefix))
            content_wrap_width = max(10, label_content_area_width - prefix_visual_len)
            wrapped_content = self.wrap_message_content(content, content_wrap_width)
            return ptg.Label(f"{prefix}{wrapped_content}")
        
        # Add more event types as needed
        return None
    
    def wrap_message_content(self, content: str, max_width: int) -> str:
        """Wrap message content to fit terminal width.
        
        Args:
            content: Message content to wrap
            max_width: Maximum width for wrapped text
            
        Returns:
            Wrapped message content
        """
        if not content:
            return ""
        
        # Use textwrap to handle long messages
        wrapped_lines = textwrap.wrap(
            content,
            width=max_width,
            break_long_words=True,
            break_on_hyphens=True
        )
        
        # Join with newlines for multi-line display
        return '\n'.join(wrapped_lines) if wrapped_lines else content
    
    def get_chat_messages(self, session_id: str) -> list[dict]:
        """Get chat messages for file export.
        
        Args:
            session_id: Session ID to get messages for
            
        Returns:
            List of message dictionaries
        """
        messages = []
        session = self.session_manager.get_session(session_id)
        
        if session and session.event_stream:
            events = session.event_stream.get_events()
            for event in events:
                if isinstance(event, MessageAction):
                    messages.append({
                        'timestamp': getattr(event, 'timestamp', ''),
                        'sender': getattr(event, 'source', 'unknown').value if hasattr(getattr(event, 'source', None), 'value') else 'unknown',
                        'content': event.content
                    })
        
        return messages
    
    def handle_terminal_resize(self) -> None:
        """Handle terminal resize events by refreshing chat display.
        
        This method is called when the terminal is resized to adjust
        the chat display layout and message wrapping.
        """
        logger.debug("Handling terminal resize for chat panel")
        
        # Refresh the chat display for the active session
        active_session = self.session_manager.get_active_session()
        if active_session:
            self.update_chat_display(active_session.sid)
    
    async def send_message(self, *args) -> None:
        """Send user message to active session."""
        # *args is used to catch any arguments passed by ptg.InputField.bind
        message = self.input_field.value.strip()
        if not message:
            return
        
        logger.info(f"Sending message: {message[:50]}...")
        
        active_session = self.session_manager.get_active_session()
        if active_session:
            # Route message through event manager
            self.event_manager.route_user_input(active_session.sid, message)
            
            # Clear input field
            if self.input_field.value:
                self.input_field.delete_back(len(self.input_field.value))
            
            # Update display
            self.update_chat_display(active_session.sid)
        else:
            logger.warning("No active session to send message to")
    
    async def pause_agent(self) -> None:
        """Pause active session agent."""
        logger.info("Pausing agent...")
        
        active_session = self.session_manager.get_active_session()
        if active_session and active_session.controller:
            # TODO: Implement pause logic from CLI
            logger.info("Agent paused")
        else:
            logger.warning("No active session or controller to pause")
    
    def handle_key_event(self, key: str) -> bool:
        """Handle key events for the chat panel.
        
        Args:
            key: Key that was pressed
            
        Returns:
            True if the key was handled, False otherwise
        """
        if key == "Enter":
            # Send message
            import asyncio
            
            try:
                loop = asyncio.get_running_loop()
                # Directly create task, assuming send_message is async
                asyncio.create_task(self.send_message())
            except RuntimeError:
                # No running event loop, run in new loop
                asyncio.run(self.send_message())
            except Exception as e:
                logger.error(f"Error sending message: {e}")
            return True
        elif key == "Escape":
            # Clear input field
            if self.input_field.value:
                self.input_field.delete_back(len(self.input_field.value))
            return True
        
        return False
    
    def clear_chat(self) -> None:
        """Clear the chat display."""
        self.chat_display._widgets.clear()
        self.chat_display += ptg.Label("[dim]Chat cleared[/dim]")
    
    def set_input_focus(self) -> None:
        """Set focus to the input field."""
        # TODO: Implement focus management for input field
        pass
