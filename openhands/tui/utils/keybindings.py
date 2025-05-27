"""Key Bindings.

Keyboard shortcuts and key handling for the TUI.
"""

from typing import TYPE_CHECKING

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger

if TYPE_CHECKING:
    from ..app import OpenHandsTUIApp


class KeyBindings:
    """Manages keyboard shortcuts for the TUI."""
    
    def __init__(self, app: "OpenHandsTUIApp"):
        """Initialize key bindings.
        
        Args:
            app: Main TUI application instance
        """
        self.app = app
        self.bindings: dict[str, callable] = {}
        # Setup bindings immediately
        self.setup()
    
    def setup(self) -> None:
        """Setup keyboard shortcuts."""
        logger.debug("Setting up key bindings")
        
        # Register key bindings
        self.bindings = {
            'ctrl+e': self.handle_ctrl_e,
            'ctrl+n': self.handle_ctrl_n,
            'ctrl+q': self.handle_ctrl_q,
            'tab': self.handle_tab,
            'shift+tab': self.handle_shift_tab,
            'f1': self.handle_help,
            'f5': self.handle_refresh,
            'enter': self.handle_enter,
        }
        
        logger.debug(f"Registered {len(self.bindings)} key bindings")
    
    def handle_key(self, key: str) -> bool:
        """Handle a key press.
        
        Args:
            key: The key combination pressed
            
        Returns:
            True if the key was handled, False otherwise
        """
        if key in self.bindings:
            handler = self.bindings[key]
            try:
                return handler()
            except Exception as e:
                logger.error(f"Error handling key {key}: {e}")
                return False
        
        # Fallback to app's handle_key_event if available
        if hasattr(self.app, 'handle_key_event'):
            try:
                result = self.app.handle_key_event(key)
                # Ensure we return a boolean
                return bool(result) if result is not None else False
            except Exception as e:
                logger.error(f"Error in app.handle_key_event: {e}")
                return False
        
        return False
    
    def _handle_async_call(self, async_func) -> None:
        """Handle async function calls safely.
        
        Args:
            async_func: Async function to call
        """
        import asyncio
        import inspect
        
        try:
            # Check if it's actually an async function
            if inspect.iscoroutinefunction(async_func):
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.create_task(async_func())
                except RuntimeError:
                    # No running event loop, run in new loop
                    asyncio.run(async_func())
            else:
                # Not async, call directly (for mocks in tests)
                async_func()
        except Exception as e:
            logger.error(f"Error handling async call: {e}")
    
    def setup_pytermgui_bindings(self) -> None:
        """Setup key bindings with PyTermGUI's window manager."""
        if not self.app.manager:
            logger.warning("Window manager not available for key binding setup")
            return
        
        try:
            # Register global key bindings with PyTermGUI
            for key, handler in self.bindings.items():
                self.app.manager.bind(key, handler)
                logger.debug(f"Bound {key} to PyTermGUI window manager")
                
        except Exception as e:
            logger.error(f"Failed to setup PyTermGUI key bindings: {e}")
            # Fallback to manual key handling
            logger.info("Using fallback key handling")
    
    def handle_ctrl_e(self) -> bool:
        """Handle Ctrl+E to open current panel in neovim.
        
        Returns:
            True if handled successfully
        """
        logger.info("Ctrl+E pressed - opening current panel in neovim")
        try:
            self.app.handle_ctrl_e()
            return True
        except Exception as e:
            logger.error(f"Error handling Ctrl+E: {e}")
            return False
    
    def handle_ctrl_n(self) -> bool:
        """Handle Ctrl+N to create new session.
        
        Returns:
            True if handled successfully
        """
        logger.info("Ctrl+N pressed - creating new session")
        try:
            self._handle_async_call(self.app.handle_ctrl_n)
            return True
        except Exception as e:
            logger.error(f"Error handling Ctrl+N: {e}")
            return False
    
    def handle_ctrl_q(self) -> bool:
        """Handle Ctrl+Q to quit application.
        
        Returns:
            True if handled successfully
        """
        logger.info("Ctrl+Q pressed - quitting application")
        try:
            self.app.handle_ctrl_q()
            return True
        except Exception as e:
            logger.error(f"Error handling Ctrl+Q: {e}")
            return False
    
    def handle_tab(self) -> bool:
        """Handle Tab to switch between panels.
        
        Returns:
            True if handled successfully
        """
        logger.debug("Tab pressed - switching to next panel")
        try:
            self.cycle_active_panel(forward=True)
            return True
        except Exception as e:
            logger.error(f"Error handling Tab: {e}")
            return False
    
    def handle_shift_tab(self) -> bool:
        """Handle Shift+Tab to switch between panels (reverse).
        
        Returns:
            True if handled successfully
        """
        logger.debug("Shift+Tab pressed - switching to previous panel")
        try:
            self.cycle_active_panel(forward=False)
            return True
        except Exception as e:
            logger.error(f"Error handling Shift+Tab: {e}")
            return False
    
    def handle_help(self) -> bool:
        """Handle F1 to show help.
        
        Returns:
            True if handled successfully
        """
        logger.info("F1 pressed - showing help")
        try:
            self.show_help()
            return True
        except Exception as e:
            logger.error(f"Error handling F1: {e}")
            return False
    
    def handle_refresh(self) -> bool:
        """Handle F5 to refresh current panel.
        
        Returns:
            True if handled successfully
        """
        logger.debug("F5 pressed - refreshing current panel")
        try:
            self.refresh_current_panel()
            return True
        except Exception as e:
            logger.error(f"Error handling F5: {e}")
            return False
    
    def cycle_active_panel(self, forward: bool = True) -> None:
        """Cycle through active panels.
        
        Args:
            forward: If True, cycle forward; if False, cycle backward
        """
        panels = ["sessions", "chat", "logs"]
        current_index = panels.index(self.app.active_panel)
        
        if forward:
            next_index = (current_index + 1) % len(panels)
        else:
            next_index = (current_index - 1) % len(panels)
        
        new_panel = panels[next_index]
        self.app.switch_active_panel(new_panel)
        
        logger.debug(f"Switched active panel from {self.app.active_panel} to {new_panel}")
    
    def show_help(self) -> None:
        """Show help dialog with key bindings."""
        help_text = """
OpenHands TUI Key Bindings:

Global:
  Ctrl+E    Open current panel in neovim
  Ctrl+N    Create new session
  Ctrl+Q    Quit application
  Tab       Switch to next panel
  Shift+Tab Switch to previous panel
  F1        Show this help
  F5        Refresh current panel

Sessions Panel:
  n         Create new session
  d         Delete/close active session

Chat Panel:
  Enter     Send message
  Escape    Clear input field

Logs Panel:
  c         Clear logs
  r         Refresh logs
"""
        
        # TODO: Show help in a modal dialog
        # For now, just log it
        logger.info("Help requested")
        print(help_text)
    
    def refresh_current_panel(self) -> None:
        """Refresh the currently active panel."""
        active_session = self.app.session_manager.get_active_session()
        session_id = active_session.sid if active_session else ""
        
        if self.app.active_panel == "sessions":
            self.app.sessions_panel.update_display()
        elif self.app.active_panel == "chat":
            self.app.chat_panel.update_chat_display(session_id)
        elif self.app.active_panel == "logs":
            self.app.logs_panel.update_display(session_id)
        
        logger.debug(f"Refreshed {self.app.active_panel} panel")
    
    def refresh_active_panel(self) -> None:
        """Alias for refresh_current_panel for backward compatibility."""
        self.refresh_current_panel()
    
    def handle_enter(self) -> bool:
        """Handle Enter key based on current context.
        
        Returns:
            True if the key was handled, False otherwise
        """
        logger.debug("Enter key pressed")
        
        # Context-aware Enter key handling
        if self.app.active_panel == "chat":
            # In chat panel, Enter should send message if input field is focused
            try:
                if hasattr(self.app.chat_panel, 'input_field') and \
                   hasattr(self.app.chat_panel.input_field, 'is_focused') and \
                   self.app.chat_panel.input_field.is_focused:
                    # Handle async send_message call
                    self._handle_async_call(self.app.chat_panel.send_message)
                    return True
            except AttributeError:
                # Fallback: always try to send message in chat panel
                self._handle_async_call(self.app.chat_panel.send_message)
                return True
        
        elif self.app.active_panel == "sessions":
            # In sessions panel, Enter could switch to selected session
            try:
                return self.app.sessions_panel.handle_key_event("enter")
            except Exception as e:
                logger.debug(f"Sessions panel Enter handling failed: {e}")
        
        elif self.app.active_panel == "logs":
            # In logs panel, Enter could refresh or do nothing
            try:
                return self.app.logs_panel.handle_key_event("enter")
            except Exception as e:
                logger.debug(f"Logs panel Enter handling failed: {e}")
        
        # Default: let PyTermGUI handle it
        return False
    

    
    def register_binding(self, key: str, handler: callable) -> None:
        """Register a new key binding.
        
        Args:
            key: Key combination to bind
            handler: Function to call when key is pressed
        """
        self.bindings[key] = handler
        logger.debug(f"Registered key binding: {key}")
    
    def unregister_binding(self, key: str) -> None:
        """Unregister a key binding.
        
        Args:
            key: Key combination to unbind
        """
        if key in self.bindings:
            del self.bindings[key]
            logger.debug(f"Unregistered key binding: {key}")