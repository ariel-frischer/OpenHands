"""Chat Display Widget.

Specialized widget for displaying chat messages and interactions.
"""

from datetime import datetime
from typing import Any, Union

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger
from openhands.events.action import MessageAction
from openhands.events.event import Event
from openhands.events.observation import CmdOutputObservation, ErrorObservation


class ChatDisplay(ptg.Container):
    """Specialized widget for chat message display."""

    def __init__(self, max_messages: int = 100):
        """Initialize the chat display widget.

        Args:
            max_messages: Maximum number of messages to keep in memory
        """
        super().__init__()
        self.max_messages = max_messages
        self.messages: list[dict[str, Any]] = []
        self.auto_scroll = True

    def add_message(
        self,
        content: str,
        sender: str = "user",
        timestamp: Union[datetime, None] = None,
        message_type: str = "text",
    ) -> None:
        """Add a message to the chat display.

        Args:
            content: Message content
            sender: Message sender (user, agent, system)
            timestamp: Message timestamp (defaults to current time)
            message_type: Type of message (text, command, output, error)
        """
        if timestamp is None:
            timestamp = datetime.now()

        message = {
            "content": content,
            "sender": sender,
            "timestamp": timestamp,
            "type": message_type,
        }

        self.messages.append(message)

        # Limit message history
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

        # Add message widget
        widget = self.create_message_widget(message)
        self += widget

        # Remove old widgets if we exceed the limit
        if len(self._widgets) > self.max_messages:
            self._widgets.pop(0)

        logger.debug(f"Added {message_type} message from {sender}")

    def add_event(self, event: Event) -> None:
        """Add an event as a message to the chat display.

        Args:
            event: Event to display
        """
        if isinstance(event, MessageAction):
            sender = getattr(event, "source", "unknown")
            if hasattr(sender, "value"):
                sender = sender.value

            self.add_message(
                content=event.content, sender=sender, message_type="message"
            )

        elif isinstance(event, CmdOutputObservation):
            self.add_message(
                content=event.content, sender="system", message_type="command_output"
            )

        elif isinstance(event, ErrorObservation):
            self.add_message(
                content=event.content, sender="system", message_type="error"
            )

        # Add more event types as needed

    def create_message_widget(self, message: dict[str, Any]) -> ptg.Widget:
        """Create a widget for a single message.

        Args:
            message: Message dictionary

        Returns:
            Widget representing the message
        """
        content = message["content"]
        sender = message["sender"]
        timestamp = message["timestamp"]
        message_type = message["type"]

        # Format timestamp
        time_str = (
            timestamp.strftime("%H:%M:%S")
            if isinstance(timestamp, datetime)
            else str(timestamp)
        )

        # Create message based on type and sender
        if message_type == "error":
            return ptg.Label(f"[red][{time_str}] Error:[/red] {content}")

        elif message_type == "command_output":
            # Truncate long output
            display_content = self.truncate_content(content, max_length=200)
            return ptg.Label(f"[yellow][{time_str}] Output:[/yellow] {display_content}")

        elif sender == "user":
            return ptg.Label(f"[green][{time_str}] You:[/green] {content}")

        elif sender == "agent":
            return ptg.Label(f"[blue][{time_str}] Agent:[/blue] {content}")

        else:
            return ptg.Label(f"[dim][{time_str}] {sender}:[/dim] {content}")

    def truncate_content(self, content: str, max_length: int = 100) -> str:
        """Truncate content for display.

        Args:
            content: Content to truncate
            max_length: Maximum length

        Returns:
            Truncated content
        """
        if len(content) <= max_length:
            return content

        return content[: max_length - 3] + "..."

    def clear_messages(self) -> None:
        """Clear all messages from the display."""
        self.clear()
        self.messages.clear()
        logger.debug("Cleared chat messages")

    def get_messages(self) -> list[dict[str, Any]]:
        """Get all messages.

        Returns:
            List of message dictionaries
        """
        return self.messages.copy()

    def get_message_count(self) -> int:
        """Get the number of messages.

        Returns:
            Number of messages
        """
        return len(self.messages)

    def search_messages(self, query: str) -> list[dict[str, Any]]:
        """Search for messages containing a query.

        Args:
            query: Search query

        Returns:
            List of matching messages
        """
        query_lower = query.lower()
        matches = []

        for message in self.messages:
            if query_lower in message["content"].lower():
                matches.append(message)

        return matches

    def filter_by_sender(self, sender: str) -> list[dict[str, Any]]:
        """Filter messages by sender.

        Args:
            sender: Sender to filter by

        Returns:
            List of messages from the specified sender
        """
        return [msg for msg in self.messages if msg["sender"] == sender]

    def filter_by_type(self, message_type: str) -> list[dict[str, Any]]:
        """Filter messages by type.

        Args:
            message_type: Message type to filter by

        Returns:
            List of messages of the specified type
        """
        return [msg for msg in self.messages if msg["type"] == message_type]

    def export_messages(self) -> str:
        """Export messages as formatted text.

        Returns:
            Formatted text representation of all messages
        """
        lines = []

        for message in self.messages:
            timestamp = message["timestamp"]
            if isinstance(timestamp, datetime):
                time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_str = str(timestamp)

            sender = message["sender"]
            content = message["content"]

            lines.append(f"[{time_str}] {sender}: {content}")

        return "\n".join(lines)

    def set_auto_scroll(self, enabled: bool) -> None:
        """Enable or disable auto-scrolling to new messages.

        Args:
            enabled: Whether to enable auto-scrolling
        """
        self.auto_scroll = enabled

    def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the chat display."""
        # TODO: Implement scrolling functionality
        # This will depend on PyTermGUI's scrolling capabilities
        pass

    def scroll_to_top(self) -> None:
        """Scroll to the top of the chat display."""
        # TODO: Implement scrolling functionality
        # This will depend on PyTermGUI's scrolling capabilities
        pass
