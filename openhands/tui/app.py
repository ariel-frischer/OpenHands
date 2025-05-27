"""Main TUI Application.

The main OpenHands TUI application using PyTermGUI.
"""

import argparse
import asyncio
from typing import Optional, Tuple

import pytermgui as ptg

from openhands.core.config import AppConfig
from openhands.core.logger import openhands_logger as logger
from openhands.storage.settings.file_settings_store import FileSettingsStore

from .managers import SessionManager, TUIEventManager, TUIPanelFileManager
from .panels import ChatPanel, LogsPanel, SessionsPanel
from .panels.logs_panel import get_tui_log_handler
from .utils import KeyBindings


class OpenHandsTUIApp:
    """Main TUI application using PyTermGUI."""

    def __init__(
        self,
        config: AppConfig,
        settings_store: Optional[FileSettingsStore] = None,
        args: Optional[argparse.Namespace] = None,
    ):
        """Initialize the TUI application.

        Args:
            config: Application configuration
            settings_store: Optional settings store for persistence
            args: Optional command line arguments
        """
        self.config = config
        self.settings_store = settings_store  # Will be None if not provided
        self.args = args or argparse.Namespace()

        # Store TUI-specific settings
        self.tui_settings = {
            "theme": getattr(args, "tui_theme", "default") if args else "default",
            "log_level": getattr(args, "tui_log_level", "INFO") if args else "INFO",
            "refresh_rate": getattr(args, "tui_refresh_rate", 0.1) if args else 0.1,
            "max_history": getattr(args, "tui_max_history", 1000) if args else 1000,
            "timeout": getattr(args, "tui_timeout", 0) if args else 0,
            "debug_layout": getattr(args, "tui_debug_layout", False) if args else False,
            "offline_mode": getattr(args, "tui_offline_mode", False) if args else False,
        }

        # Initialize managers
        self.session_manager = SessionManager(
            config, self.settings_store, offline_mode=self.tui_settings["offline_mode"]
        )
        self.file_manager = TUIPanelFileManager()
        self.event_manager = TUIEventManager(
            self.session_manager, self.file_manager, self.config, self
        )

        # Give session manager access to event manager for new session creation
        self.session_manager.event_manager = self.event_manager

        # Initialize TUI log handler to capture logs for display
        self.tui_log_handler = get_tui_log_handler()

        # Ensure the log handler is properly set up and capturing logs
        logger.info("TUI log handler initialized and ready to capture logs")

        # Initialize panels
        self.sessions_panel = SessionsPanel(self.session_manager, self.file_manager)
        self.chat_panel = ChatPanel(
            self.session_manager, self.event_manager, self.file_manager
        )
        self.logs_panel = LogsPanel(self.session_manager, self.file_manager)

        # Current active panel for Ctrl+E
        self.active_panel = "chat"

        # Terminal resize handling
        self.last_terminal_size: Tuple[int, int] = (
            ptg.terminal.width,
            ptg.terminal.height,
        )

        # Setup UI components
        self.window: Optional[ptg.Window] = None
        self.manager: Optional[ptg.WindowManager] = None
        self.main_container: Optional[ptg.Container] = None

        # Setup keybindings
        self.keybindings = KeyBindings(self)

    def setup_ui(self) -> None:
        """Setup PyTermGUI responsive layout using Layout system with WindowManager."""
        logger.debug("Setting up responsive TUI layout using PyTermGUI Layout system")

        # Get terminal dimensions for logging
        terminal_width = ptg.terminal.width
        terminal_height = ptg.terminal.height
        logger.info(f"Terminal dimensions: {terminal_width}x{terminal_height}")
        logger.debug(
            f"Setting up layout with terminal size: {terminal_width}x{terminal_height}"
        )

        # Create a vertical container for the left column (sessions + logs only)
        left_column = ptg.Container(self.sessions_panel, self.logs_panel)

        # Create header as a separate container that will span both columns
        header = ptg.Container(
            ptg.Label(
                "[bold]OpenHands TUI v0.39[/bold]",
                parent_align=ptg.HorizontalAlignment.CENTER,
            )
        )

        # Create a container for the chat panel with header
        chat_column = ptg.Container(header, self.chat_panel)

        # Create left column window - use full height with explicit positioning
        left_width = int(terminal_width * 0.3)
        right_width = int(terminal_width * 0.7)

        left_window = ptg.Window(
            left_column,
            title="",
            box="DOUBLE",
            width=left_width,
            height=terminal_height,
            pos=(0, 0),  # Explicitly position at top-left
        )

        # Create chat window with header - use full height with explicit positioning
        chat_window = ptg.Window(
            chat_column,
            title="",
            box="DOUBLE",
            width=right_width,
            height=terminal_height,
            pos=(left_width, 0),  # Position to the right of left window
        )

        logger.debug(
            f"Created windows - Left: {left_width}x{terminal_height}, Right: {right_width}x{terminal_height}"
        )
        logger.debug(f"Left window position will be: (0, 0)")
        logger.debug(f"Right window position will be: ({left_width}, 0)")

        # Create window manager first
        self.manager = ptg.WindowManager()

        # Add only the layout windows (header is now part of left column)
        self.manager.add(left_window)
        self.manager.add(chat_window)

        # Configure the layout with responsive slots to use full terminal height
        layout = self.manager.layout

        # Add slots: left column (30%) and right column (70%), both using full terminal height
        # Use height=1.0 to fill the entire terminal height
        layout.add_slot("left", width=0.3, height=1.0)
        layout.add_slot("right", width=0.7, height=1.0)

        # Assign windows to slots by index (0 = first slot, 1 = second slot)
        layout.assign(left_window, index=0, apply=False)  # left slot
        layout.assign(chat_window, index=1, apply=False)  # right slot

        logger.info(f"Layout setup complete:")
        logger.info(f"  Left column (30%): Sessions + Logs panels")
        logger.info(f"  Right column (70%): Chat panel")
        logger.info(f"  Using Layout system for responsive design")

        # Apply the layout after window manager is set up
        layout.apply()

        # Debug: Log actual window positions after layout application
        logger.debug(f"After layout.apply():")
        logger.debug(f"  Left window pos: {getattr(left_window, 'pos', 'unknown')}")
        logger.debug(f"  Chat window pos: {getattr(chat_window, 'pos', 'unknown')}")
        logger.debug(
            f"  Left window size: {getattr(left_window, 'width', 'unknown')}x{getattr(left_window, 'height', 'unknown')}"
        )
        logger.debug(
            f"  Chat window size: {getattr(chat_window, 'width', 'unknown')}x{getattr(chat_window, 'height', 'unknown')}"
        )

        # Setup PyTermGUI keybindings after window manager is created
        self.keybindings.setup_pytermgui_bindings()

        # Setup terminal resize detection
        self.setup_resize_handling()

        logger.debug("Responsive layout setup complete")

        # Store references for resize handling
        self.left_column = left_column
        self.header = header
        self.left_window = left_window
        self.chat_window = chat_window
        self.layout = layout
        self.window = left_window  # Keep for compatibility

    def setup_resize_handling(self) -> None:
        """Setup terminal resize detection and handling."""
        # PyTermGUI doesn't have built-in resize event binding
        # Resize detection will be handled in the main loop
        logger.debug("Using resize detection in main loop")

    def handle_terminal_resize(self) -> None:
        """Handle terminal size changes and update layout."""
        current_size = (ptg.terminal.width, ptg.terminal.height)
        if current_size != self.last_terminal_size:
            logger.info(
                f"Terminal resized from {self.last_terminal_size} to {current_size}"
            )
            self.last_terminal_size = current_size

            try:
                # Recalculate window dimensions and positions
                terminal_width, terminal_height = current_size
                left_width = int(terminal_width * 0.3)
                right_width = int(terminal_width * 0.7)

                # Update window sizes and positions
                if hasattr(self, "left_window") and self.left_window:
                    self.left_window.width = left_width
                    self.left_window.height = terminal_height
                    self.left_window.pos = (0, 0)

                if hasattr(self, "chat_window") and self.chat_window:
                    self.chat_window.width = right_width
                    self.chat_window.height = terminal_height
                    self.chat_window.pos = (left_width, 0)

                # Reapply the layout to handle new terminal dimensions
                if hasattr(self, "layout"):
                    # Update layout slots with new dimensions
                    self.layout.clear()
                    self.layout.add_slot("left", width=0.3, height=1.0)
                    self.layout.add_slot("right", width=0.7, height=1.0)
                    self.layout.assign(self.left_window, index=0, apply=False)
                    self.layout.assign(self.chat_window, index=1, apply=False)
                    self.layout.apply()

                # Notify all panels of resize so they can update their content
                if hasattr(self.sessions_panel, "handle_terminal_resize"):
                    self.sessions_panel.handle_terminal_resize()
                if hasattr(self.chat_panel, "handle_terminal_resize"):
                    self.chat_panel.handle_terminal_resize()
                if hasattr(self.logs_panel, "handle_terminal_resize"):
                    self.logs_panel.handle_terminal_resize()

                # Refresh all windows
                if hasattr(self, "header") and self.header:
                    self.header.refresh()
                if hasattr(self, "left_window") and self.left_window:
                    self.left_window.refresh()
                if hasattr(self, "chat_window") and self.chat_window:
                    self.chat_window.refresh()

                logger.debug(
                    f"Layout updated for new terminal size: {terminal_width}x{terminal_height}"
                )
                logger.debug(f"Left window: {left_width}x{terminal_height} at (0,0)")
                logger.debug(
                    f"Right window: {right_width}x{terminal_height} at ({left_width},0)"
                )

            except Exception as e:
                logger.error(f"Error handling terminal resize: {e}")

    def handle_ctrl_e(self) -> None:
        """Handle Ctrl+E to open current panel in neovim."""
        active_session = self.session_manager.get_active_session()
        if not active_session:
            return

        file_path = self.file_manager.get_panel_file(
            self.active_panel, active_session.sid
        )
        self.file_manager.open_in_neovim(file_path)

    async def handle_ctrl_n(self) -> None:
        """Handle Ctrl+N to create new session."""
        await self.sessions_panel.create_new_session()

    def handle_ctrl_q(self) -> None:
        """Handle Ctrl+Q to quit application."""
        logger.info("Quitting TUI application...")
        if self.manager:
            self.manager.stop()

    def switch_active_panel(self, panel_name: str) -> None:
        """Switch the active panel for Ctrl+E functionality.

        Args:
            panel_name: Name of the panel to make active
        """
        if panel_name in ["sessions", "chat", "logs"]:
            old_panel = self.active_panel
            self.active_panel = panel_name

            # Set focus to the new active panel
            try:
                if panel_name == "sessions":
                    self.sessions_panel.set_focus(True)
                    self.chat_panel.set_focus(False)
                    self.logs_panel.set_focus(False)
                elif panel_name == "chat":
                    self.sessions_panel.set_focus(False)
                    self.chat_panel.set_focus(True)
                    self.logs_panel.set_focus(False)
                elif panel_name == "logs":
                    self.sessions_panel.set_focus(False)
                    self.chat_panel.set_focus(False)
                    self.logs_panel.set_focus(True)

                logger.debug(f"Switched active panel from {old_panel} to {panel_name}")

            except Exception as e:
                logger.warning(f"Failed to set focus for panel {panel_name}: {e}")
        else:
            logger.warning(f"Invalid panel name: {panel_name}")

    async def run(self) -> None:
        """Run the TUI application with resize monitoring and optional timeout."""
        logger.info("Setting up TUI interface...")
        self.setup_ui()  # Creates self.manager
        logger.info("TUI interface ready")

        if not self.manager:
            logger.error("Failed to initialize window manager")
            raise RuntimeError("Window manager not initialized")

        # Skip automatic session creation to avoid blocking TUI startup
        if not self.tui_settings["debug_layout"]:
            logger.info(
                "Normal mode: Session creation will be handled by user interaction"
            )
            # Note: Sessions will be created when user clicks "New Session" button
            # This avoids blocking the TUI startup with Docker container initialization
        else:
            logger.info(
                "Debug layout mode: Skipping session creation and runtime startup"
            )

        resize_task = asyncio.create_task(self._resize_monitor())
        timeout_task = None

        # Setup timeout if specified
        if self.tui_settings["timeout"] > 0:
            timeout_task = asyncio.create_task(self._timeout_monitor())
            logger.info(
                f"TUI will timeout after {self.tui_settings['timeout']} seconds"
            )

        try:
            # The `with self.manager:` block calls manager.run() (via manager.start())
            # and blocks here until the TUI exits. manager.run() itself runs an asyncio loop.
            with self.manager:
                # The TUI is running here. The `with` block handles the manager's lifecycle.
                # Other async tasks (like _resize_monitor and _timeout_monitor) run concurrently.
                pass  # Manager loop is active within this context

        except Exception as e:
            logger.error(f"Unhandled exception in TUI main loop: {e}", exc_info=True)
            # Don't re-raise to allow graceful shutdown
        finally:
            logger.info("TUI application shutting down...")

            # Cancel all background tasks
            resize_task.cancel()
            if timeout_task:
                timeout_task.cancel()

            # Clean up sessions and their background tasks
            try:
                if hasattr(self, "session_manager") and self.session_manager:
                    await self.session_manager.cleanup_all_sessions()
            except Exception as e:
                logger.debug(f"Error during session cleanup: {e}")

            # Wait for tasks to complete cancellation
            try:
                await resize_task
                if timeout_task:
                    await timeout_task
            except asyncio.CancelledError:
                logger.debug("Monitor tasks cancelled.")

            # Cancel any remaining tasks in the event loop
            try:
                current_task = asyncio.current_task()
                tasks = [
                    task
                    for task in asyncio.all_tasks()
                    if not task.done() and task != current_task
                ]
                if tasks:
                    logger.debug(f"Cancelling {len(tasks)} remaining tasks...")
                    for task in tasks:
                        if not task.cancelled():
                            task.cancel()
                    # Wait briefly for tasks to cancel, but don't use gather to avoid recursion
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.debug(f"Error cancelling remaining tasks: {e}")

            # The `with self.manager:` block ensures `manager.stop()` is called.
            logger.info("OpenHands TUI exited.")

    async def _resize_monitor(self) -> None:
        """Monitor for terminal resize events."""
        while True:
            try:
                # Check for resize every 100ms
                self.handle_terminal_resize()
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                logger.debug("Resize monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in resize monitor: {e}")
                await asyncio.sleep(1.0)  # Wait longer on error

    async def _timeout_monitor(self) -> None:
        """Monitor for timeout and exit TUI when reached."""
        try:
            await asyncio.sleep(self.tui_settings["timeout"])
            logger.info(
                f"TUI timeout of {self.tui_settings['timeout']} seconds reached, exiting..."
            )
            if self.manager:
                self.manager.stop()
        except asyncio.CancelledError:
            logger.debug("Timeout monitor cancelled")
        except Exception as e:
            logger.error(f"Error in timeout monitor: {e}")
