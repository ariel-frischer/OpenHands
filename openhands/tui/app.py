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
from .utils import KeyBindings


class OpenHandsTUIApp:
    """Main TUI application using PyTermGUI."""
    
    def __init__(
        self, 
        config: AppConfig, 
        settings_store: Optional[FileSettingsStore] = None,
        args: Optional[argparse.Namespace] = None
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
            'theme': getattr(args, 'tui_theme', 'default') if args else 'default',
            'log_level': getattr(args, 'tui_log_level', 'INFO') if args else 'INFO',
            'refresh_rate': getattr(args, 'tui_refresh_rate', 0.1) if args else 0.1,
            'max_history': getattr(args, 'tui_max_history', 1000) if args else 1000,
            'timeout': getattr(args, 'tui_timeout', 0) if args else 0,
            'debug_layout': getattr(args, 'tui_debug_layout', False) if args else False,
        }
        
        # Initialize managers
        self.session_manager = SessionManager(config, self.settings_store)
        self.file_manager = TUIPanelFileManager()
        self.event_manager = TUIEventManager(self.session_manager, self.file_manager, self.config, self)
        
        # Initialize panels
        self.sessions_panel = SessionsPanel(self.session_manager, self.file_manager)
        self.chat_panel = ChatPanel(self.session_manager, self.event_manager, self.file_manager)
        self.logs_panel = LogsPanel(self.session_manager, self.file_manager)
        
        # Current active panel for Ctrl+E
        self.active_panel = "chat"
        
        # Terminal resize handling
        self.last_terminal_size: Tuple[int, int] = (ptg.terminal.width, ptg.terminal.height)
        
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
        
        # Create header window
        header = ptg.Window(
            ptg.Label("[bold]OpenHands TUI v0.39[/bold]", parent_align=ptg.HorizontalAlignment.CENTER),
            title="",
            box="SINGLE"
        )
        
        # Create a vertical container for the left column (sessions + logs)
        left_column = ptg.Container(
            self.sessions_panel,
            self.logs_panel
        )
        
        # Create left column window
        left_window = ptg.Window(
            left_column,
            title="",
            box="SINGLE"
        )
        
        # Create chat window
        chat_window = ptg.Window(
            self.chat_panel,
            title="",
            box="SINGLE"
        )
        
        # Create window manager first
        self.manager = ptg.WindowManager()
        
        # Add header window separately (not part of the responsive layout)
        self.manager.add(header)
        self.manager.add(left_window)
        self.manager.add(chat_window)
        
        # Configure the layout with responsive slots
        layout = self.manager.layout
        
        # Add slots: left column (30%) and right column (70%), both using full height
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
        self.window = header  # Keep for compatibility
            
    def setup_resize_handling(self) -> None:
        """Setup terminal resize detection and handling."""
        # PyTermGUI doesn't have built-in resize event binding
        # Resize detection will be handled in the main loop
        logger.debug("Using resize detection in main loop")
    
    def handle_terminal_resize(self) -> None:
        """Handle terminal size changes and update layout."""
        current_size = (ptg.terminal.width, ptg.terminal.height)
        if current_size != self.last_terminal_size:
            logger.info(f"Terminal resized from {self.last_terminal_size} to {current_size}")
            self.last_terminal_size = current_size
            
            # With Layout system, responsiveness is automatic
            # Just need to reapply layout and refresh components
            try:
                # Reapply the layout to handle new terminal dimensions
                if hasattr(self, 'layout'):
                    self.layout.apply()
                
                # Notify all panels of resize so they can update their content
                if hasattr(self.sessions_panel, 'handle_terminal_resize'):
                    self.sessions_panel.handle_terminal_resize()
                if hasattr(self.chat_panel, 'handle_terminal_resize'):
                    self.chat_panel.handle_terminal_resize()
                if hasattr(self.logs_panel, 'handle_terminal_resize'):
                    self.logs_panel.handle_terminal_resize()
                
                # Refresh all windows
                if hasattr(self, 'header') and self.header:
                    self.header.refresh()
                if hasattr(self, 'left_window') and self.left_window:
                    self.left_window.refresh()
                if hasattr(self, 'chat_window') and self.chat_window:
                    self.chat_window.refresh()
                    
                logger.debug("Layout reapplied and panels refreshed for terminal resize")
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

        # Skip session creation in debug layout mode for faster startup
        if not self.tui_settings['debug_layout']:
            await self.session_manager.create_session("Welcome to OpenHands TUI!")
            # Ensure panels are updated with initial data before the manager starts drawing.
            self.sessions_panel.update_sessions()
            if self.session_manager.active_session_id:
                self.chat_panel.update_display(self.session_manager.active_session_id)
                self.logs_panel.update_display(self.session_manager.active_session_id)
        else:
            logger.info("Debug layout mode: Skipping session creation and runtime startup")

        resize_task = asyncio.create_task(self._resize_monitor())
        timeout_task = None
        
        # Setup timeout if specified
        if self.tui_settings['timeout'] > 0:
            timeout_task = asyncio.create_task(self._timeout_monitor())
            logger.info(f"TUI will timeout after {self.tui_settings['timeout']} seconds")

        try:
            # The `with self.manager:` block calls manager.run() (via manager.start())
            # and blocks here until the TUI exits. manager.run() itself runs an asyncio loop.
            with self.manager:
                # The TUI is running here. The `with` block handles the manager's lifecycle.
                # Other async tasks (like _resize_monitor and _timeout_monitor) run concurrently.
                pass  # Manager loop is active within this context

        finally:
            logger.info("TUI application shutting down...")
            resize_task.cancel()
            if timeout_task:
                timeout_task.cancel()
            try:
                await resize_task
                if timeout_task:
                    await timeout_task
            except asyncio.CancelledError:
                logger.debug("Monitor tasks cancelled.")
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
            await asyncio.sleep(self.tui_settings['timeout'])
            logger.info(f"TUI timeout of {self.tui_settings['timeout']} seconds reached, exiting...")
            if self.manager:
                self.manager.stop()
        except asyncio.CancelledError:
            logger.debug("Timeout monitor cancelled")
        except Exception as e:
            logger.error(f"Error in timeout monitor: {e}")
