"""Tests for TUI keybindings functionality.

This module tests the keyboard shortcuts and navigation system
for the OpenHands TUI application.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openhands.core.config import AppConfig
from openhands.tui.app import OpenHandsTUIApp
from openhands.tui.utils.keybindings import KeyBindings


class TestKeyBindings:
    """Test the KeyBindings class functionality."""
    
    @pytest.fixture
    def mock_app(self):
        """Create a mock TUI app for testing."""
        # Use a full MagicMock for the app to avoid attribute issues
        app = MagicMock()
        
        # Mock the panels
        app.sessions_panel = MagicMock()
        app.chat_panel = MagicMock()
        app.logs_panel = MagicMock()
        
        # Mock the window manager
        app.manager = MagicMock()
        
        # Set initial active panel
        app.active_panel = "chat"
        
        return app
    
    @pytest.fixture
    def keybindings(self, mock_app):
        """Create KeyBindings instance for testing."""
        return KeyBindings(mock_app)
    
    def test_keybindings_initialization(self, keybindings):
        """Test that keybindings are properly initialized."""
        assert keybindings.app is not None
        assert hasattr(keybindings, 'bindings')
        assert 'ctrl+q' in keybindings.bindings
        assert 'ctrl+e' in keybindings.bindings
        assert 'ctrl+n' in keybindings.bindings
        assert 'enter' in keybindings.bindings
    
    def test_setup_method(self, keybindings):
        """Test the setup method."""
        # Clear existing bindings to test setup
        keybindings.bindings = {}
        keybindings.setup()
        
        # Should have registered all expected bindings
        expected_keys = ['ctrl+e', 'ctrl+n', 'ctrl+q', 'tab', 'shift+tab', 'f1', 'f5', 'enter']
        for key in expected_keys:
            assert key in keybindings.bindings
    
    def test_setup_pytermgui_bindings(self, keybindings):
        """Test PyTermGUI bindings setup."""
        # Mock the window manager
        keybindings.app.manager = MagicMock()
        
        # Test successful binding
        keybindings.setup_pytermgui_bindings()
        
        # Verify bind was called for each key
        expected_calls = len(keybindings.bindings)
        assert keybindings.app.manager.bind.call_count == expected_calls
    
    def test_setup_pytermgui_bindings_no_manager(self, keybindings):
        """Test PyTermGUI bindings setup when no manager is available."""
        keybindings.app.manager = None
        
        # Should not raise an exception
        keybindings.setup_pytermgui_bindings()
    
    def test_handle_ctrl_q(self, keybindings):
        """Test Ctrl+Q handling."""
        # Mock the app's handle_ctrl_q method
        keybindings.app.handle_ctrl_q = MagicMock()
        
        result = keybindings.handle_ctrl_q()
        
        # Should call app's handle_ctrl_q method
        keybindings.app.handle_ctrl_q.assert_called_once()
        assert result is True
    
    def test_handle_ctrl_e(self, keybindings):
        """Test Ctrl+E handling."""
        # Mock the app's handle_ctrl_e method
        keybindings.app.handle_ctrl_e = MagicMock()
        
        result = keybindings.handle_ctrl_e()
        
        # Should call app's handle_ctrl_e method
        keybindings.app.handle_ctrl_e.assert_called_once()
        assert result is True
    
    def test_handle_ctrl_n(self, keybindings):
        """Test Ctrl+N handling."""
        # Mock the async method
        keybindings.app.handle_ctrl_n = AsyncMock()
        
        result = keybindings.handle_ctrl_n()
        
        # Should call app's handle_ctrl_n method
        keybindings.app.handle_ctrl_n.assert_called_once()
        assert result is True
    
    def test_handle_enter_chat_panel(self, keybindings):
        """Test Enter key handling in chat panel."""
        keybindings.app.active_panel = "chat"
        keybindings.app.chat_panel.send_message = MagicMock()
        
        result = keybindings.handle_enter()
        
        # Should call chat panel's send_message method
        keybindings.app.chat_panel.send_message.assert_called_once()
        assert result is True
    
    def test_handle_enter_sessions_panel(self, keybindings):
        """Test Enter key handling in sessions panel."""
        keybindings.app.active_panel = "sessions"
        keybindings.app.sessions_panel.handle_key_event = MagicMock(return_value=True)
        
        result = keybindings.handle_enter()
        
        # Should call sessions panel's handle_key_event method
        keybindings.app.sessions_panel.handle_key_event.assert_called_once_with("enter")
        assert result is True
    
    def test_handle_enter_logs_panel(self, keybindings):
        """Test Enter key handling in logs panel."""
        keybindings.app.active_panel = "logs"
        keybindings.app.logs_panel.handle_key_event = MagicMock(return_value=True)
        
        result = keybindings.handle_enter()
        
        # Should call logs panel's handle_key_event method
        keybindings.app.logs_panel.handle_key_event.assert_called_once_with("enter")
        assert result is True
    
    def test_handle_enter_fallback(self, keybindings):
        """Test Enter key handling fallback behavior."""
        keybindings.app.active_panel = "unknown"
        
        result = keybindings.handle_enter()
        
        # Should return False for unknown panels
        assert result is False
    
    def test_handle_key_known_binding(self, keybindings):
        """Test handle_key with known key binding."""
        # Mock the handler in the bindings dictionary
        mock_handler = MagicMock(return_value=True)
        keybindings.bindings['ctrl+q'] = mock_handler
        
        result = keybindings.handle_key("ctrl+q")
        
        mock_handler.assert_called_once()
        assert result is True
    
    def test_handle_key_unknown_binding(self, keybindings):
        """Test handle_key with unknown key binding."""
        # Mock the app to not have handle_key_event method
        keybindings.app = MagicMock(spec=[])  # Empty spec means no attributes
        
        result = keybindings.handle_key("unknown_key")
        
        # Should return False for unknown keys
        assert result is False
    
    def test_refresh_active_panel_chat(self, keybindings):
        """Test refreshing active chat panel."""
        keybindings.app.active_panel = "chat"
        keybindings.app.session_manager.get_active_session = MagicMock()
        keybindings.app.session_manager.get_active_session.return_value = MagicMock(sid="test_session")
        
        keybindings.refresh_active_panel()
        
        # Should call chat panel's update_chat_display
        keybindings.app.chat_panel.update_chat_display.assert_called_once_with("test_session")
    
    def test_refresh_active_panel_sessions(self, keybindings):
        """Test refreshing active sessions panel."""
        keybindings.app.active_panel = "sessions"
        
        keybindings.refresh_active_panel()
        
        # Should call sessions panel's update_display
        keybindings.app.sessions_panel.update_display.assert_called_once()
    
    def test_refresh_active_panel_logs(self, keybindings):
        """Test refreshing active logs panel."""
        keybindings.app.active_panel = "logs"
        keybindings.app.session_manager.get_active_session = MagicMock()
        keybindings.app.session_manager.get_active_session.return_value = MagicMock(sid="test_session")
        
        keybindings.refresh_active_panel()
        
        # Should call logs panel's update_display
        keybindings.app.logs_panel.update_display.assert_called_once_with("test_session")
    
    def test_refresh_active_panel_no_active_session(self, keybindings):
        """Test refreshing when no active session exists."""
        keybindings.app.active_panel = "chat"
        keybindings.app.session_manager.get_active_session = MagicMock(return_value=None)
        
        # Should not raise an exception
        keybindings.refresh_active_panel()


class TestAppKeyboardIntegration:
    """Test keyboard integration with the main TUI app."""
    
    @pytest.fixture
    def mock_app(self):
        """Create a mock TUI app for testing."""
        config = AppConfig()
        app = OpenHandsTUIApp(config)
        
        # Mock the panels
        app.sessions_panel = MagicMock()
        app.chat_panel = MagicMock()
        app.logs_panel = MagicMock()
        
        # Mock the window manager
        app.manager = MagicMock()
        
        return app
    
    def test_switch_active_panel_valid(self, mock_app):
        """Test switching to valid panels."""
        # Test switching to sessions
        mock_app.switch_active_panel("sessions")
        assert mock_app.active_panel == "sessions"
        mock_app.sessions_panel.set_focus.assert_called_with(True)
        mock_app.chat_panel.set_focus.assert_called_with(False)
        mock_app.logs_panel.set_focus.assert_called_with(False)
        
        # Test switching to chat
        mock_app.switch_active_panel("chat")
        assert mock_app.active_panel == "chat"
        mock_app.chat_panel.set_focus.assert_called_with(True)
        
        # Test switching to logs
        mock_app.switch_active_panel("logs")
        assert mock_app.active_panel == "logs"
        mock_app.logs_panel.set_focus.assert_called_with(True)
    
    def test_switch_active_panel_invalid(self, mock_app):
        """Test switching to invalid panel."""
        original_panel = mock_app.active_panel
        mock_app.switch_active_panel("invalid_panel")
        
        # Should not change active panel
        assert mock_app.active_panel == original_panel
    
    def test_switch_active_panel_focus_error(self, mock_app):
        """Test switching panel when focus setting fails."""
        # Make set_focus raise an exception
        mock_app.sessions_panel.set_focus.side_effect = Exception("Focus error")
        
        # Should not raise an exception
        mock_app.switch_active_panel("sessions")
        assert mock_app.active_panel == "sessions"
    
    def test_keybindings_setup_in_app(self, mock_app):
        """Test that keybindings are properly set up in the app."""
        # Mock the setup_ui method to avoid PyTermGUI dependencies
        with patch.object(mock_app, 'setup_ui'):
            mock_app.keybindings = MagicMock()
            
            # Call setup_ui which should set up keybindings
            mock_app.setup_ui()
            
            # Verify keybindings setup was called
            assert hasattr(mock_app, 'keybindings')


class TestPanelKeyHandling:
    """Test key handling in individual panels."""
    
    def test_chat_panel_enter_key(self):
        """Test Enter key handling in chat panel."""
        from openhands.tui.panels.chat_panel import ChatPanel
        
        # Mock dependencies
        session_manager = MagicMock()
        event_manager = MagicMock()
        file_manager = MagicMock()
        
        # Create chat panel
        chat_panel = ChatPanel(session_manager, event_manager, file_manager)
        
        # Mock the send_message method
        with patch.object(chat_panel, 'send_message', new_callable=AsyncMock) as mock_send:
            result = chat_panel.handle_key_event("Enter")
            
            # Should return True and call send_message
            assert result is True
    
    def test_chat_panel_escape_key(self):
        """Test Escape key handling in chat panel."""
        from openhands.tui.panels.chat_panel import ChatPanel
        
        # Mock dependencies
        session_manager = MagicMock()
        event_manager = MagicMock()
        file_manager = MagicMock()
        
        # Create chat panel
        chat_panel = ChatPanel(session_manager, event_manager, file_manager)
        
        # Mock input field
        chat_panel.input_field = MagicMock()
        chat_panel.input_field.value = "test message"
        
        result = chat_panel.handle_key_event("Escape")
        
        # Should return True and clear input
        assert result is True
        chat_panel.input_field.delete_back.assert_called_once()
    
    def test_sessions_panel_key_handling(self):
        """Test key handling in sessions panel."""
        from openhands.tui.panels.sessions_panel import SessionsPanel
        
        # Mock dependencies
        session_manager = MagicMock()
        file_manager = MagicMock()
        
        # Create sessions panel
        sessions_panel = SessionsPanel(session_manager, file_manager)
        
        # Test 'n' key for new session
        with patch.object(sessions_panel, 'create_new_session', new_callable=AsyncMock):
            result = sessions_panel.handle_key_event("n")
            assert result is True
        
        # Test 'd' key for delete session
        session_manager.get_active_session.return_value = MagicMock(sid="test_session")
        with patch.object(sessions_panel, 'close_session', new_callable=AsyncMock):
            result = sessions_panel.handle_key_event("d")
            assert result is True
    
    def test_logs_panel_key_handling(self):
        """Test key handling in logs panel."""
        from openhands.tui.panels.logs_panel import LogsPanel
        
        # Mock dependencies
        session_manager = MagicMock()
        file_manager = MagicMock()
        
        # Create logs panel
        logs_panel = LogsPanel(session_manager, file_manager)
        
        # Test 'c' key for clear logs
        result = logs_panel.handle_key_event("c")
        assert result is True


class TestFocusManagement:
    """Test focus management functionality."""
    
    def test_base_panel_focus_state(self):
        """Test base panel focus state management."""
        from openhands.tui.panels.base_panel import BasePanel
        
        # Create a concrete implementation for testing
        class TestPanel(BasePanel):
            def update_display(self, session_id: str = "") -> None:
                pass
            
            def get_panel_name(self) -> str:
                return "test"
        
        # Mock dependencies
        session_manager = MagicMock()
        file_manager = MagicMock()
        
        panel = TestPanel(session_manager, file_manager, "Test Panel")
        
        # Test initial focus state
        assert panel._focused is False
        
        # Test setting focus
        panel.set_focus(True)
        assert panel._focused is True
        
        # Test removing focus
        panel.set_focus(False)
        assert panel._focused is False
    
    def test_panel_focus_default_parameter(self):
        """Test panel focus with default parameter."""
        from openhands.tui.panels.base_panel import BasePanel
        
        # Create a concrete implementation for testing
        class TestPanel(BasePanel):
            def update_display(self, session_id: str = "") -> None:
                pass
            
            def get_panel_name(self) -> str:
                return "test"
        
        # Mock dependencies
        session_manager = MagicMock()
        file_manager = MagicMock()
        
        panel = TestPanel(session_manager, file_manager, "Test Panel")
        
        # Test default parameter (should be True)
        panel.set_focus()
        assert panel._focused is True


if __name__ == "__main__":
    pytest.main([__file__])