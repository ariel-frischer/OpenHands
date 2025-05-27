"""Base Panel.

Base class for all TUI panels.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pytermgui as ptg

if TYPE_CHECKING:
    from ..managers import SessionManager, TUIPanelFileManager


class BasePanel(ptg.Container, ABC):
    """Base class for all TUI panels."""

    def __init__(
        self,
        session_manager: "SessionManager",
        file_manager: "TUIPanelFileManager",
        title: str = "Panel",
    ):
        """Initialize the base panel.

        Args:
            session_manager: Session manager instance
            file_manager: File manager instance
            title: Panel title
        """
        super().__init__()
        self.session_manager = session_manager
        self.file_manager = file_manager
        self.title = title
        self._focused = False  # Track focus state

        # Set height policy to fill available space in container (key for full height)
        self.height_policy = ptg.SizePolicy.FILL
        self.overflow = ptg.Overflow.SCROLL  # Allow scrolling if content exceeds panel height

        # Add title label
        self += ptg.Label(f"[bold]{title}[/bold]")
        self += ptg.Label("")  # Spacer

    @abstractmethod
    def update_display(self, session_id: str = "") -> None:
        """Update the panel display.

        Args:
            session_id: Session ID to update for (if applicable)
        """
        pass

    @abstractmethod
    def get_panel_name(self) -> str:
        """Get the panel name for file operations.

        Returns:
            Panel name string
        """
        pass

    def clear_content(self) -> None:
        """Clear the panel content (keeping title)."""
        # Keep the first two items (title and spacer)
        while len(self._widgets) > 2:
            self._widgets.pop()

    def add_content(self, widget: ptg.Widget) -> None:
        """Add content widget to the panel.

        Args:
            widget: Widget to add
        """
        self += widget

    def set_focus(self, focused: bool = True) -> None:
        """Set focus to this panel.

        Args:
            focused: Whether to focus (True) or unfocus (False) this panel
        """
        # TODO: Implement focus management
        # For now, just store the focus state
        self._focused = focused

    def handle_key_event(self, key: str) -> bool:
        """Handle key events for this panel.

        Args:
            key: Key that was pressed

        Returns:
            True if the key was handled, False otherwise
        """
        # Default implementation - panels can override this
        return False
