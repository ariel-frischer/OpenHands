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

        # Create containers with default sizing to ensure content is visible
        left_column = ptg.Container(
            self.sessions_panel, 
            self.logs_panel,
        )
        # Ensure left column distributes width to child panels
        left_column.width_policy = ptg.SizePolicy.FILL
        
        header = ptg.Container(
            ptg.Label(
                "[bold blue]OpenHands TUI[/bold blue] | "
                "[dim]Select session: ←→ | Chat: ↵ | Quit: q[/dim]"
            )
        )
        
        # Create windows for each section with dragging disabled for fixed layout
        left_window = ptg.Window(left_column, title="", box="DOUBLE", draggable=False)
        
        right_window = ptg.Window(self.chat_panel, title="", box="DOUBLE", draggable=False) 
        
        # Header window without box to prevent text clipping, and ensure visibility
        header_window = ptg.Window(header, title="", box="EMPTY", draggable=False)

        # Create layout with proper header sizing and debug logging
        self.layout = ptg.Layout()
        
        # Header slot - optimized height for more main content space
        self.layout.add_slot("header", width=1.0, height=4)
        logger.info(f"Added header slot: width=1.0, height=4")
        
        # Add a row break to put main content slots on the next row
        self.layout.add_break()
        
        # Main content slots - default sizing for height, fixed width split
        self.layout.add_slot("left", width=0.4)   
        self.layout.add_slot("right", width=0.6)
        logger.info(f"Added main content slots: left width=0.4, right width=0.6")

        # Assign windows to slots using correct PyTermGUI API with indices
        self.layout.assign(header_window, index=0)  # Header slot (index 0)
        self.layout.assign(left_window, index=1)    # Left slot (index 1) 
        self.layout.assign(right_window, index=2)   # Right slot (index 2)

        # Apply layout to position and size everything
        self.layout.apply()

        # Comprehensive debug logging of all sizes and positions
        logger.info("=== LAYOUT DEBUG INFORMATION ===")
        logger.info(f"Terminal size: {terminal_width}x{terminal_height}")
        
        # Debug slot information
        try:
            rows = self.layout.build_rows()
            logger.info(f"Layout has {len(rows)} rows")
            for i, row in enumerate(rows):
                logger.info(f"Row {i}: {len(row)} slots")
                for j, slot in enumerate(row):
                    logger.info(f"  Slot {j} ({slot.name}): pos={getattr(slot, 'position', 'unknown')}, dim={getattr(slot, 'dimension', 'unknown')}")
        except Exception as e:
            logger.error(f"Error reading slot info: {e}")
        
        # Debug window information
        try:
            logger.info(f"Header window: pos={getattr(header_window, 'pos', 'unknown')}, size={getattr(header_window, 'width', 'unknown')}x{getattr(header_window, 'height', 'unknown')}")
            logger.info(f"Left window: pos={getattr(left_window, 'pos', 'unknown')}, size={getattr(left_window, 'width', 'unknown')}x{getattr(left_window, 'height', 'unknown')}")
            logger.info(f"Right window: pos={getattr(right_window, 'pos', 'unknown')}, size={getattr(right_window, 'width', 'unknown')}x{getattr(right_window, 'height', 'unknown')}")
        except Exception as e:
            logger.error(f"Error reading window info: {e}")
            
        # Debug container information
        try:
            logger.info(f"Left container: size={getattr(left_column, 'width', 'unknown')}x{getattr(left_column, 'height', 'unknown')}")
            logger.info(f"Header container: size={getattr(header, 'width', 'unknown')}x{getattr(header, 'height', 'unknown')}")
        except Exception as e:
            logger.error(f"Error reading container info: {e}")
            
        # Debug panel information  
        try:
            logger.info(f"Sessions panel: size={getattr(self.sessions_panel, 'width', 'unknown')}x{getattr(self.sessions_panel, 'height', 'unknown')}, width_policy={getattr(self.sessions_panel, 'width_policy', 'unknown')}")
            logger.info(f"Logs panel: size={getattr(self.logs_panel, 'width', 'unknown')}x{getattr(self.logs_panel, 'height', 'unknown')}, width_policy={getattr(self.logs_panel, 'width_policy', 'unknown')}")
            logger.info(f"Chat panel: size={getattr(self.chat_panel, 'width', 'unknown')}x{getattr(self.chat_panel, 'height', 'unknown')}, width_policy={getattr(self.chat_panel, 'width_policy', 'unknown')}")
        except Exception as e:
            logger.error(f"Error reading panel info: {e}")
        logger.info("=== END LAYOUT DEBUG ===")

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

        # Initialize panel content to ensure text is visible
        logger.info("Initializing panel content...")
        try:
            # Add test content to ensure visibility
            self.sessions_panel += ptg.Label("Test: Sessions Panel Content")
            self.sessions_panel += ptg.Label("- This should be visible")
            self.logs_panel += ptg.Label("Test: Logs Panel Content") 
            self.logs_panel += ptg.Label("- This should also be visible")
            self.chat_panel += ptg.Label("Test: Chat Panel Content")
            self.chat_panel += ptg.Label("- Ready for chat")
            
            # Also call the normal update methods
            self.sessions_panel.update_display()
            self.logs_panel.update_display()
            self.chat_panel.update_display()
            logger.info("Panel content initialized successfully")
            
            # Reapply layout to accommodate the new content
            self.layout.apply()
            logger.info("Layout reapplied after content initialization")
            
            # Force panels to use full container width and height
            try:
                # Get the left window/container dimensions after layout application
                left_container_width = getattr(left_window, 'width', None)
                left_container_height = getattr(left_window, 'height', None)
                
                # Get the right window/container dimensions
                right_container_width = getattr(right_window, 'width', None)
                right_container_height = getattr(right_window, 'height', None)
                
                if left_container_width and left_container_height:
                    # Set left panels to use full width and split height of their container
                    panel_width = left_container_width - 4  # Account for window box padding
                    panel_height = (left_container_height - 6) // 2  # Split height between 2 panels, account for padding
                    
                    self.sessions_panel.width = panel_width
                    self.sessions_panel.height = panel_height
                    self.logs_panel.width = panel_width
                    self.logs_panel.height = panel_height
                    
                    logger.info(f"Set left panel dimensions to {panel_width}x{panel_height} (container: {left_container_width}x{left_container_height})")
                else:
                    logger.warning("Could not determine left container dimensions")
                    
                if right_container_width and right_container_height:
                    # Set chat panel to use maximum width and height of its container
                    chat_width = right_container_width - 2  # Reduce padding for more space
                    chat_height = right_container_height - 2  # Reduce padding for more height
                    
                    self.chat_panel.width = chat_width
                    self.chat_panel.height = chat_height
                    
                    logger.info(f"Set chat panel dimensions to {chat_width}x{chat_height} (container: {right_container_width}x{right_container_height})")
                else:
                    logger.warning("Could not determine right container dimensions")
                    
            except Exception as e:
                logger.error(f"Error setting panel dimensions: {e}")
                
        except Exception as e:
            logger.error(f"Error initializing panel content: {e}")

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
                    
                    # Debug logging for resize
                    logger.info("=== RESIZE DEBUG INFORMATION ===")
                    logger.info(f"New terminal size: {current_size[0]}x{current_size[1]}")
                    try:
                        rows = self.layout.build_rows()
                        for i, row in enumerate(rows):
                            for j, slot in enumerate(row):
                                logger.info(f"  Slot {j} ({slot.name}): pos={getattr(slot, 'position', 'unknown')}, dim={getattr(slot, 'dimension', 'unknown')}")
                    except Exception as e:
                        logger.error(f"Error reading resize slot info: {e}")
                    logger.info("=== END RESIZE DEBUG ===")
                    
                    # Recalculate and apply panel dimensions after resize
                    try:
                        # Get updated container dimensions
                        left_container_width = getattr(self.left_window, 'width', None)
                        left_container_height = getattr(self.left_window, 'height', None)
                        right_container_width = getattr(self.right_window, 'width', None)
                        right_container_height = getattr(self.right_window, 'height', None)
                        
                        if left_container_width and left_container_height:
                            panel_width = left_container_width - 4
                            panel_height = (left_container_height - 6) // 2
                            
                            self.sessions_panel.width = panel_width
                            self.sessions_panel.height = panel_height
                            self.logs_panel.width = panel_width
                            self.logs_panel.height = panel_height
                            
                        if right_container_width and right_container_height:
                            chat_width = right_container_width - 2
                            chat_height = right_container_height - 2
                            
                            self.chat_panel.width = chat_width
                            self.chat_panel.height = chat_height
                            
                        logger.info("Panel dimensions updated for resize")
                    except Exception as e:
                        logger.error(f"Error updating panel dimensions on resize: {e}")
                    
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
        auto_session_task = None
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
            if auto_session_task:
                auto_session_task.cancel()

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
                if auto_session_task:
                    await auto_session_task
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
        """Create session automatically in background with timeout handling and loading indicators."""
        try:
            logger.info("Creating auto-session in background...")
            
            # Wait a moment for UI to be fully ready
            await asyncio.sleep(0.5)
            
            # Show loading status in sessions panel
            if hasattr(self, 'sessions_panel') and self.sessions_panel:
                self.sessions_panel.clear()
                self.sessions_panel += ptg.Label("[bold yellow]⠋ Creating session...[/bold yellow]")
            
            # Get session name and task from args
            session_name = getattr(self.args, 'name', '') or "default"
            task_description = getattr(self.args, 'task', '') or "Ready to help!"
            
            # Create session using the fixed session manager with timeout
            try:
                session_id = await asyncio.wait_for(
                    self.session_manager.create_session(task_description, session_name),
                    timeout=60.0  # 60 second timeout for auto-session creation
                )
                logger.info(f"Auto-session {session_id} created successfully")
                
                # Update loading status
                if hasattr(self, 'sessions_panel') and self.sessions_panel:
                    self.sessions_panel.clear()
                    self.sessions_panel += ptg.Label("[bold yellow]⠙ Starting session...[/bold yellow]")
                
                # Start the session with timeout
                await asyncio.wait_for(
                    self.session_manager.start_session(session_id),
                    timeout=30.0  # 30 second timeout for session start
                )
                
                # Switch to the new session
                await self.session_manager.switch_session(session_id)
                
                # Clear loading status and update all panels
                if hasattr(self, 'sessions_panel') and self.sessions_panel:
                    self.sessions_panel.update_display()
                
                if hasattr(self, 'chat_panel') and self.chat_panel:
                    self.chat_panel.update_display(session_id)
                    
                logger.info(f"Auto-session {session_id} started and activated successfully")
                    
            except asyncio.TimeoutError:
                error_msg = "Session creation timed out. Please try creating a session manually."
                logger.error(error_msg)
                
                # Show error in sessions panel
                if hasattr(self, 'sessions_panel') and self.sessions_panel:
                    self.sessions_panel.clear()
                    self.sessions_panel += ptg.Label(f"[bold red]✗ {error_msg}[/bold red]")
                
                # Also show in chat panel
                if hasattr(self, 'chat_panel') and self.chat_panel:
                    self.chat_panel._show_feedback(error_msg, "error")
                
        except Exception as e:
            error_msg = f"Failed to create auto-session: {str(e)}"
            logger.error(error_msg)
            
            # Show error in sessions panel
            if hasattr(self, 'sessions_panel') and self.sessions_panel:
                self.sessions_panel.clear()
                self.sessions_panel += ptg.Label(f"[bold red]✗ Auto-session failed[/bold red]")
                self.sessions_panel += ptg.Label(f"[dim]{str(e)}[/dim]")
            
            # Also show in chat panel
            if hasattr(self, 'chat_panel') and self.chat_panel:
                self.chat_panel._show_feedback(error_msg, "error")
