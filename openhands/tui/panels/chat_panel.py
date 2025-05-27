"""Chat Panel.

Right panel showing chat interface with responsive layout and message display.
"""

import asyncio
import textwrap
import time
from typing import TYPE_CHECKING, Union

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger
from openhands.core.schema import AgentState
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
        self._last_button_click = 0  # For button debouncing
        self._sending_message = False  # Prevent multiple simultaneous message sending
        
        logger.debug(f"ChatPanel initialized with dimensions: {getattr(self, 'width', 'unknown')}x{getattr(self, 'height', 'unknown')}")
        
        # Chat history display with responsive sizing
        self.chat_display = ptg.Container()
        self.add_content(self.chat_display)
        
        # Add spacer
        self.add_content(ptg.Label(""))
        
        # Input area with Enter key binding
        self.input_field = ptg.InputField(prompt="Message: ")
        # Bind Enter key to send message
        self.input_field.bind(ptg.keys.ENTER, self.send_message)
        
        self.send_button = ptg.Button("Send", self.send_message_sync)
        self.pause_button = ptg.Button("Pause", self.pause_agent)
        
        # Status indicator for session readiness
        self.status_label = ptg.Label("[dim]No session active[/dim]")
        
        # Input container with horizontal layout
        input_container = ptg.Container(
            self.status_label,
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
                # No active session - clear display and show status
                self.chat_display._widgets.clear()
                self.chat_display += ptg.Label("[dim]No active session. Create a new session to start chatting.[/dim]")
                self.status_label.value = "[dim]No session active[/dim]"
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
            self.status_label.value = "[dim]No session active[/dim]"
            return
        
        # Update status label based on session state
        self.update_status_label(session)
        
        # Clear existing messages
        self.chat_display._widgets.clear()
        
        # Calculate available height for the chat_display container
        # Panel height - title(1) - spacer(1) - status_label(1) - input_field(1) - button_container(1) - bottom_spacer(1) = self.height - 6
        chat_display_container_height = max(1, self.height - 6)
        
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
    
    def update_status_label(self, session) -> None:
        """Update the status label based on session state.
        
        Args:
            session: Session context to get state from
        """
        from openhands.core.schema import AgentState
        
        if session.agent_state == AgentState.LOADING:
            self.status_label.value = "[yellow]⏳ Session loading...[/yellow]"
        elif session.agent_state == AgentState.AWAITING_USER_INPUT:
            self.status_label.value = "[green]✅ Ready for messages[/green]"
        elif session.agent_state == AgentState.RUNNING:
            self.status_label.value = "[blue]🔥 Agent working...[/blue]"
        elif session.agent_state == AgentState.STOPPED:
            self.status_label.value = "[red]⏹️ Session stopped[/red]"
        elif session.agent_state == AgentState.ERROR:
            self.status_label.value = "[red]❌ Session error[/red]"
        else:
            self.status_label.value = f"[dim]❓ Unknown state: {session.agent_state}[/dim]"
    
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
        if not active_session:
            logger.info("No active session found, creating a new session automatically")
            # Create a new session automatically
            try:
                # Use the message as the task description for the new session
                task_description = f"User message: {message[:50]}..." if len(message) > 50 else f"User message: {message}"
                
                # Create session synchronously in the background
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    # Create the session and wait for it to be ready
                    session_creation_task = asyncio.create_task(self._create_session_and_send_message(task_description, message))
                    return  # Exit early, the message will be sent after session creation
                except RuntimeError:
                    # No running event loop, run in new loop
                    asyncio.run(self._create_session_and_send_message(task_description, message))
                    return
            except Exception as e:
                logger.error(f"Failed to create new session automatically: {e}")
                return
        
        # Check if session is ready to receive messages
        if active_session.agent_state not in [AgentState.AWAITING_USER_INPUT, AgentState.RUNNING]:
            if active_session.agent_state == AgentState.LOADING:
                logger.warning("Session is still loading. Please wait for it to be ready (✅)")
            elif active_session.agent_state == AgentState.ERROR:
                logger.warning("Session is in error state. Please create a new session.")
            elif active_session.agent_state == AgentState.STOPPED:
                logger.warning("Session is stopped. Please create a new session.")
            else:
                logger.warning(f"Session is not ready (state: {active_session.agent_state})")
            return
        
        # Route message through event manager
        try:
            success = self.event_manager.route_user_input(active_session.sid, message)
            if success:
                # Clear input field only if message was sent successfully
                if self.input_field.value:
                    self.input_field.delete_back(len(self.input_field.value))
                
                # Update display
                self.update_chat_display(active_session.sid)
            else:
                logger.error("Failed to send message - event manager returned False")
        except Exception as e:
            logger.error(f"Failed to send message to session {active_session.sid}: {e}")
            # Don't clear input field so user can retry
    
    async def _create_session_and_send_message(self, task_description: str, message: str) -> None:
        """Create a new session and send the first message to it.
        
        Args:
            task_description: Description for the new session
            message: Message to send after session creation
        """
        try:
            logger.info(f"Creating new session with task: {task_description}")
            
            # Create the session
            session_id = await self.session_manager.create_session(task_description)
            logger.info(f"Created session {session_id}, subscribing to events")
            
            # Subscribe to session events
            if hasattr(self.session_manager, 'event_manager'):
                self.session_manager.event_manager.subscribe_to_session(session_id)
            
            # Start the session
            logger.info(f"Starting session {session_id}")
            await self.session_manager.start_session(session_id)
            logger.info(f"Session {session_id} started, now sending message")
            
            # Now send the message
            success = self.event_manager.route_user_input(session_id, message)
            if success:
                logger.info(f"Successfully sent message to new session {session_id}")
                # Clear input field
                if self.input_field.value:
                    self.input_field.delete_back(len(self.input_field.value))
                
                # Update displays
                self.update_chat_display(session_id)
                
                # Update other panels
                if hasattr(self.session_manager, 'event_manager') and hasattr(self.session_manager.event_manager, 'tui_app'):
                    tui_app = self.session_manager.event_manager.tui_app
                    if tui_app:
                        if hasattr(tui_app, 'sessions_panel'):
                            tui_app.sessions_panel.update_display()
                        if hasattr(tui_app, 'logs_panel'):
                            tui_app.logs_panel.update_display()
            else:
                logger.error("Failed to send message to new session")
                
        except Exception as e:
            logger.error(f"Failed to create session and send message: {e}", exc_info=True)
    
    def send_message_sync(self, *args) -> None:
        """Synchronous wrapper for send_message to work with PyTermGUI buttons.
        
        Args:
            *args: Arguments from PyTermGUI button callback (ignored)
        """
        # Button debouncing - prevent rapid clicks
        current_time = time.time()
        if current_time - self._last_button_click < 0.5:  # 0.5 second debounce
            logger.debug("Send button click ignored due to debouncing")
            return
        self._last_button_click = current_time
        
        # Prevent multiple simultaneous message sending
        if self._sending_message:
            logger.debug("Message sending already in progress")
            return
        
        self._sending_message = True
        
        try:
            # Try to get the running event loop
            try:
                loop = asyncio.get_running_loop()
                # Schedule message sending as a background task with exception handling
                task = asyncio.create_task(self.send_message())
                # Add exception handler to prevent unhandled exceptions from crashing TUI
                task.add_done_callback(self._handle_task_exception)
            except RuntimeError:
                # No running event loop, run in new loop
                asyncio.run(self.send_message())
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            self._sending_message = False
    
    def _handle_task_exception(self, task) -> None:
        """Handle exceptions from background tasks to prevent TUI crashes."""
        try:
            # This will raise the exception if the task failed
            task.result()
            logger.debug("Message sending completed successfully")
        except asyncio.CancelledError:
            logger.info("Message sending was cancelled")
        except Exception as e:
            logger.error(f"Background task failed: {e}", exc_info=True)
        finally:
            # Reset the sending message flag
            self._sending_message = False
    
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
