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
from .utils.pytermgui_debug import (
    get_debug_logger,
    enable_pytermgui_debug,
    log_widget_position,
    log_window_manager_state,
    validate_window_positions,
)


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

        # Initialize PyTermGUI debug logging if enabled
        if self.tui_settings["debug_layout"]:
            enable_pytermgui_debug()
            logger.info("PyTermGUI debug layout mode enabled")
        
        # Get debug logger instance for positioning validation
        self.debug_logger = get_debug_logger()

    def setup_ui(self) -> None:
        """Set up the TUI interface with proper PyTermGUI layout management."""
        logger.info("Setting up TUI interface...")

        # Get terminal dimensions for logging
        terminal_width = ptg.terminal.width
        terminal_height = ptg.terminal.height
        logger.info(f"Terminal dimensions: {terminal_width}x{terminal_height}")

        # Create containers with proper height policies for full terminal height
        left_column = ptg.Container(
            self.sessions_panel, 
            self.logs_panel,
        )
        # Configure container for full height expansion
        left_column.height_policy = ptg.SizePolicy.FILL  # Key: height_policy not size_policy
        left_column.overflow = ptg.Overflow.SCROLL  # Prevent unwanted resizing
        
        header = ptg.Container(
            ptg.Label(
                "[bold blue]OpenHands TUI[/bold blue] | "
                "[dim]Select session: ←→ | Chat: ↵ | Quit: q[/dim]"
            )
        )
        
        # Create windows for each section  
        left_window = ptg.Window(left_column, title="", box="DOUBLE")
        left_window.height_policy = ptg.SizePolicy.FILL  # Window should also fill height
        
        right_window = ptg.Window(self.chat_panel, title="", box="DOUBLE") 
        right_window.height_policy = ptg.SizePolicy.FILL  # Window should also fill height
        
        header_window = ptg.Window(header, title="", box="SINGLE")

        # Create layout with proper slot heights to fill terminal
        self.layout = ptg.Layout()
        
        # Header slot - small fixed height
        self.layout.add_slot("header", width=1.0, height=3)
        
        # Main content slots - fill remaining height (height=1.0 means 100% of available)  
        self.layout.add_row()
        self.layout.add_slot("left", width=0.4, height=1.0)   # Key: height=1.0 fills terminal
        self.layout.add_slot("right", width=0.6, height=1.0)  # Key: height=1.0 fills terminal

        # Assign windows to slots
        self.layout.assign(header_window, slot="header")
        self.layout.assign(left_window, slot="left") 
        self.layout.assign(right_window, slot="right")

        # Apply layout to position and size everything
        self.layout.apply()

        # Store references for resize handling
        self.left_column = left_column
        self.left_window = left_window
        self.right_window = right_window
        self.header_window = header_window

        logger.info("TUI interface setup complete")

        # Create window manager and add windows
        self.manager = ptg.WindowManager()
        self.manager.add(header_window)
        self.manager.add(left_window) 
        self.manager.add(right_window)

        # Set the layout on the window manager
        self.manager.layout = self.layout

        # Enhanced PyTermGUI debug logging
        self.debug_logger.log_layout_application(self.layout, "Initial layout setup")

        # Setup PyTermGUI keybindings
        self.keybindings.setup_pytermgui_bindings()

        # Setup terminal resize detection
        self.setup_resize_handling()

        logger.debug("Layout-based setup complete")

    def setup_resize_handling(self) -> None:
        """Setup terminal resize detection and handling."""
        # PyTermGUI doesn't have built-in resize event binding
        # Resize detection will be handled in the main loop
        logger.debug("Using resize detection in main loop")

    def handle_terminal_resize(self) -> None:
        """Handle terminal size changes using proper PyTermGUI layout management."""
        current_size = (ptg.terminal.width, ptg.terminal.height)
        if current_size != self.last_terminal_size:
            logger.info(
                f"Terminal resized from {self.last_terminal_size} to {current_size}"
            )
            
            # Enhanced resize debug logging
            self.debug_logger.log_terminal_resize(self.last_terminal_size, current_size)
            
            self.last_terminal_size = current_size

            try:
                # Simply reapply the layout - PyTermGUI will handle the positioning and sizing
                if hasattr(self, "layout") and self.layout:
                    self.layout.apply()
                    
                    # Enhanced logging after layout application
                    self.debug_logger.log_layout_application(self.layout, "Resize layout update")
                    logger.info("Layout reapplied successfully for terminal resize")

                # Notify all panels of resize so they can update their content
                if hasattr(self.sessions_panel, "handle_terminal_resize"):
                    self.sessions_panel.handle_terminal_resize()
                if hasattr(self.chat_panel, "handle_terminal_resize"):
                    self.chat_panel.handle_terminal_resize()
                if hasattr(self.logs_panel, "handle_terminal_resize"):
                    self.logs_panel.handle_terminal_resize()

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

        # Create auto-session in background (non-blocking)
        if not self.tui_settings["debug_layout"]:
            logger.info("Normal mode: Creating auto-session in background")
            # Create auto-session task (non-blocking)
            auto_session_task = asyncio.create_task(self._create_auto_session())
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

    async def _create_auto_session(self) -> None:
        """Create session automatically in background with timeout handling."""
        try:
            logger.info("Creating auto-session in background...")
            
            # Wait a moment for UI to be fully ready
            await asyncio.sleep(0.5)
            
            # Create session using the fixed session manager with timeout
            try:
                session_id = await asyncio.wait_for(
                    self.session_manager.create_session("Auto-created session"),
                    timeout=60.0  # 60 second timeout for auto-session creation
                )
                logger.info(f"Auto-session {session_id} created successfully")
                
                # Update UI to show session is ready
                if hasattr(self, 'chat_panel') and self.chat_panel:
                    # Update chat panel to show the new session
                    self.chat_panel.update_display(session_id)
                    
            except asyncio.TimeoutError:
                logger.error("Auto-session creation timed out after 60 seconds")
                if hasattr(self, 'chat_panel') and self.chat_panel:
                    self.chat_panel._show_feedback("Auto-session creation timed out. You can create a session manually.", "error")
                
        except Exception as e:
            logger.error(f"Failed to create auto-session: {e}")
            # Show error in UI but don't crash TUI
            if hasattr(self, 'chat_panel') and self.chat_panel:
                self.chat_panel._show_feedback(f"Auto-session creation failed: {str(e)}", "error")
