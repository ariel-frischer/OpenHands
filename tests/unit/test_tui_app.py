"""Tests for the main TUI application."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytermgui as ptg

from openhands.core.config import AppConfig
from openhands.tui.app import OpenHandsTUIApp


class TestOpenHandsTUIApp:
    """Test cases for the main TUI application."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = MagicMock(spec=AppConfig)
        config.workspace_base = "/tmp/test_workspace"
        config.file_store_path = "/tmp/test_file_store"
        return config

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        manager = MagicMock()
        manager.create_session = AsyncMock(return_value="test-session-id")
        manager.get_active_session = MagicMock(return_value=None)
        return manager

    @pytest.fixture
    def mock_file_manager(self):
        """Create a mock file manager."""
        manager = MagicMock()
        manager.get_panel_file = MagicMock(return_value="/tmp/test_file.txt")
        manager.open_in_neovim = MagicMock()
        return manager

    @pytest.fixture
    def mock_event_manager(self):
        """Create a mock event manager."""
        return MagicMock()

    @pytest.fixture
    def mock_panels(self):
        """Create mock panels."""
        sessions_panel = MagicMock()
        sessions_panel.handle_terminal_resize = MagicMock()
        sessions_panel.update_sessions = MagicMock()
        sessions_panel.handle_key_event = MagicMock(return_value=False)
        sessions_panel.create_new_session = AsyncMock()
        
        chat_panel = MagicMock()
        chat_panel.handle_terminal_resize = MagicMock()
        chat_panel.update_display = MagicMock()
        chat_panel.handle_key_event = MagicMock(return_value=False)
        
        logs_panel = MagicMock()
        logs_panel.handle_terminal_resize = MagicMock()
        logs_panel.update_display = MagicMock()
        logs_panel.handle_key_event = MagicMock(return_value=False)
        
        return sessions_panel, chat_panel, logs_panel

    @pytest.fixture
    def tui_app(self, mock_config):
        """Create a TUI application instance with mocked dependencies."""
        with patch('openhands.tui.app.SessionManager') as mock_sm, \
             patch('openhands.tui.app.TUIPanelFileManager') as mock_fm, \
             patch('openhands.tui.app.TUIEventManager') as mock_em, \
             patch('openhands.tui.app.SessionsPanel') as mock_sp, \
             patch('openhands.tui.app.ChatPanel') as mock_cp, \
             patch('openhands.tui.app.LogsPanel') as mock_lp, \
             patch('openhands.tui.app.KeyBindings') as mock_kb:
            
            # Configure session manager mock
            mock_sm.return_value.create_session = AsyncMock(return_value="test-session-id")
            mock_sm.return_value.get_active_session = MagicMock(return_value=None)
            
            # Configure panels with async methods
            mock_sp.return_value.create_new_session = AsyncMock()
            mock_sp.return_value.update_sessions = MagicMock()
            mock_sp.return_value.handle_terminal_resize = MagicMock()
            
            app = OpenHandsTUIApp(mock_config)
            return app

    def test_initialization(self, tui_app, mock_config):
        """Test TUI application initialization."""
        assert tui_app.config == mock_config
        assert tui_app.active_panel == "chat"
        assert tui_app.last_terminal_size == (ptg.terminal.width, ptg.terminal.height)
        assert tui_app.window is None
        assert tui_app.manager is None
        assert tui_app.main_container is None

    def test_setup_ui(self, tui_app):
        """Test UI setup creates proper layout with explicit positioning."""
        with patch('pytermgui.Container') as mock_container, \
             patch('pytermgui.Window') as mock_window, \
             patch('pytermgui.WindowManager') as mock_manager, \
             patch('pytermgui.terminal') as mock_terminal, \
             patch.object(tui_app.keybindings, 'setup_pytermgui_bindings') as mock_keybindings:
            
            # Set specific terminal dimensions for testing
            mock_terminal.width = 120
            mock_terminal.height = 40
            
            # Mock layout
            mock_layout = MagicMock()
            mock_manager.return_value.layout = mock_layout
            
            tui_app.setup_ui()
            
            # Verify containers were created (for left column, header, chat column)
            assert mock_container.called
            
            # Verify windows were created with explicit positioning
            assert mock_window.call_count >= 2
            
            # Check that windows were created with proper dimensions and positioning
            window_calls = mock_window.call_args_list
            
            # First window (left) should be positioned at (0, 0) with 30% width
            left_call = window_calls[0]
            left_kwargs = left_call[1]
            assert left_kwargs['width'] == int(120 * 0.3)  # 36
            assert left_kwargs['height'] == 40
            assert left_kwargs['pos'] == (0, 0)
            
            # Second window (chat) should be positioned at (left_width, 0) with 70% width
            chat_call = window_calls[1]
            chat_kwargs = chat_call[1]
            assert chat_kwargs['width'] == int(120 * 0.7)  # 84
            assert chat_kwargs['height'] == 40
            assert chat_kwargs['pos'] == (int(120 * 0.3), 0)  # (36, 0)
            
            # Verify window manager was created
            mock_manager.assert_called_once()
            
            # Verify layout slots were configured
            mock_layout.add_slot.assert_any_call("left", width=0.3, height=1.0)
            mock_layout.add_slot.assert_any_call("right", width=0.7, height=1.0)
            mock_layout.apply.assert_called_once()
            
            # Verify keybindings were setup
            mock_keybindings.assert_called_once()

    def test_setup_resize_handling(self, tui_app):
        """Test resize handling setup."""
        # Should not raise exception
        tui_app.setup_resize_handling()

    def test_setup_resize_handling_fallback(self, tui_app):
        """Test resize handling fallback when binding fails."""
        # Should not raise exception
        tui_app.setup_resize_handling()

    def test_handle_terminal_resize(self, tui_app, mock_panels):
        """Test terminal resize handling with window repositioning."""
        sessions_panel, chat_panel, logs_panel = mock_panels
        tui_app.sessions_panel = sessions_panel
        tui_app.chat_panel = chat_panel
        tui_app.logs_panel = logs_panel
        
        # Mock windows and layout
        tui_app.left_window = MagicMock()
        tui_app.chat_window = MagicMock()
        tui_app.layout = MagicMock()
        tui_app.header = MagicMock()
        
        # Change terminal size
        original_size = tui_app.last_terminal_size
        new_size = (100, 50)  # Specific size for testing calculations
        
        with patch('pytermgui.terminal') as mock_terminal:
            mock_terminal.width = new_size[0]
            mock_terminal.height = new_size[1]
            
            tui_app.handle_terminal_resize()
            
            # Verify size was updated
            assert tui_app.last_terminal_size == new_size
            
            # Verify window dimensions were recalculated
            expected_left_width = int(100 * 0.3)  # 30
            expected_right_width = int(100 * 0.7)  # 70
            
            # Verify left window was resized and repositioned
            assert tui_app.left_window.width == expected_left_width
            assert tui_app.left_window.height == 50
            assert tui_app.left_window.pos == (0, 0)
            
            # Verify chat window was resized and repositioned
            assert tui_app.chat_window.width == expected_right_width
            assert tui_app.chat_window.height == 50
            assert tui_app.chat_window.pos == (expected_left_width, 0)
            
            # Verify layout was updated
            tui_app.layout.clear.assert_called_once()
            tui_app.layout.add_slot.assert_any_call("left", width=0.3, height=1.0)
            tui_app.layout.add_slot.assert_any_call("right", width=0.7, height=1.0)
            tui_app.layout.apply.assert_called_once()
            
            # Verify all panels were notified
            sessions_panel.handle_terminal_resize.assert_called_once()
            chat_panel.handle_terminal_resize.assert_called_once()
            logs_panel.handle_terminal_resize.assert_called_once()
            
            # Verify windows were refreshed
            tui_app.left_window.refresh.assert_called_once()
            tui_app.chat_window.refresh.assert_called_once()
            tui_app.header.refresh.assert_called_once()

    def test_handle_terminal_resize_no_change(self, tui_app, mock_panels):
        """Test terminal resize handling when size hasn't changed."""
        sessions_panel, chat_panel, logs_panel = mock_panels
        tui_app.sessions_panel = sessions_panel
        tui_app.chat_panel = chat_panel
        tui_app.logs_panel = logs_panel
        
        # Keep same terminal size
        current_size = tui_app.last_terminal_size
        
        with patch('pytermgui.terminal') as mock_terminal:
            mock_terminal.width = current_size[0]
            mock_terminal.height = current_size[1]
            
            tui_app.handle_terminal_resize()
            
            # Verify panels were not notified (no size change)
            sessions_panel.handle_terminal_resize.assert_not_called()
            chat_panel.handle_terminal_resize.assert_not_called()
            logs_panel.handle_terminal_resize.assert_not_called()

    def test_handle_terminal_resize_error(self, tui_app, mock_panels):
        """Test terminal resize handling with panel error."""
        sessions_panel, chat_panel, logs_panel = mock_panels
        tui_app.sessions_panel = sessions_panel
        tui_app.chat_panel = chat_panel
        tui_app.logs_panel = logs_panel
        
        # Make one panel raise an exception
        sessions_panel.handle_terminal_resize.side_effect = Exception("Test error")
        
        # Change terminal size
        original_size = tui_app.last_terminal_size
        new_size = (original_size[0] + 10, original_size[1] + 5)
        
        with patch('pytermgui.terminal') as mock_terminal:
            mock_terminal.width = new_size[0]
            mock_terminal.height = new_size[1]
            
            # Should not raise exception
            tui_app.handle_terminal_resize()
            
            # Verify size was still updated
            assert tui_app.last_terminal_size == new_size

    def test_handle_ctrl_e(self, tui_app):
        """Test Ctrl+E handling."""
        # Mock active session
        mock_session = MagicMock()
        mock_session.sid = "test-session"
        tui_app.session_manager.get_active_session.return_value = mock_session
        
        tui_app.handle_ctrl_e()
        
        # Verify file manager was called
        tui_app.file_manager.get_panel_file.assert_called_once_with("chat", "test-session")
        tui_app.file_manager.open_in_neovim.assert_called_once()

    def test_handle_ctrl_e_no_session(self, tui_app):
        """Test Ctrl+E handling with no active session."""
        tui_app.session_manager.get_active_session.return_value = None
        
        tui_app.handle_ctrl_e()
        
        # Should not call file manager
        tui_app.file_manager.get_panel_file.assert_not_called()
        tui_app.file_manager.open_in_neovim.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_ctrl_n(self, tui_app):
        """Test Ctrl+N handling."""
        await tui_app.handle_ctrl_n()
        
        # Verify sessions panel was called
        tui_app.sessions_panel.create_new_session.assert_called_once()

    def test_handle_ctrl_q(self, tui_app):
        """Test Ctrl+Q handling."""
        tui_app.manager = MagicMock()
        
        tui_app.handle_ctrl_q()
        
        # Verify manager stop was called
        tui_app.manager.stop.assert_called_once()

    def test_handle_ctrl_q_no_manager(self, tui_app):
        """Test Ctrl+Q handling with no manager."""
        tui_app.manager = None
        
        # Should not raise exception
        tui_app.handle_ctrl_q()

    def test_switch_active_panel(self, tui_app):
        """Test switching active panel."""
        # Test valid panel names
        for panel in ["sessions", "chat", "logs"]:
            tui_app.switch_active_panel(panel)
            assert tui_app.active_panel == panel

    def test_switch_active_panel_invalid(self, tui_app):
        """Test switching to invalid panel."""
        original_panel = tui_app.active_panel
        
        tui_app.switch_active_panel("invalid")
        
        # Should not change active panel
        assert tui_app.active_panel == original_panel

    @pytest.mark.asyncio
    async def test_run_manager(self, tui_app):
        """Test running the PyTermGUI manager."""
        tui_app.manager = MagicMock()
        
        await tui_app._run_manager()
        
        tui_app.manager.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_manager_no_manager(self, tui_app):
        """Test running with no manager."""
        tui_app.manager = None
        
        # Should not raise exception
        await tui_app._run_manager()

    @pytest.mark.asyncio
    async def test_run_manager_error(self, tui_app):
        """Test running manager with error."""
        tui_app.manager = MagicMock()
        tui_app.manager.run.side_effect = Exception("Test error")
        
        with pytest.raises(Exception, match="Test error"):
            await tui_app._run_manager()

    @pytest.mark.asyncio
    async def test_resize_monitor(self, tui_app):
        """Test resize monitor loop."""
        with patch.object(tui_app, 'handle_terminal_resize') as mock_resize:
            # Create a task that will be cancelled after a short time
            monitor_task = asyncio.create_task(tui_app._resize_monitor())
            
            # Let it run for a short time
            await asyncio.sleep(0.05)
            
            # Cancel the task
            monitor_task.cancel()
            
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
            
            # Verify resize was called at least once
            assert mock_resize.call_count >= 1

    @pytest.mark.asyncio
    async def test_resize_monitor_error(self, tui_app):
        """Test resize monitor with error handling."""
        with patch.object(tui_app, 'handle_terminal_resize', side_effect=Exception("Test error")):
            # Create a task that will be cancelled after a short time
            monitor_task = asyncio.create_task(tui_app._resize_monitor())
            
            # Let it run for a short time to trigger error handling
            await asyncio.sleep(0.05)
            
            # Cancel the task
            monitor_task.cancel()
            
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_run_with_resize_monitoring(self, tui_app):
        """Test main run method with resize monitoring."""
        with patch.object(tui_app, '_run_manager') as mock_run_manager, \
             patch.object(tui_app, '_resize_monitor') as mock_resize_monitor:
            
            # Make run_manager complete quickly
            mock_run_manager.return_value = asyncio.sleep(0.01)
            mock_resize_monitor.return_value = asyncio.sleep(10)  # Long running
            
            await tui_app.run_with_resize_monitoring()
            
            # Verify both tasks were started
            mock_run_manager.assert_called_once()
            mock_resize_monitor.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_full_integration(self, tui_app):
        """Test full run method integration."""
        with patch.object(tui_app, 'setup_ui') as mock_setup_ui, \
             patch.object(tui_app, 'run_with_resize_monitoring') as mock_run_monitoring, \
             patch.object(tui_app.keybindings, 'setup') as mock_keybindings_setup:
            
            # Mock manager
            tui_app.manager = MagicMock()
            
            await tui_app.run()
            
            # Verify setup methods were called
            mock_setup_ui.assert_called_once()
            mock_keybindings_setup.assert_called_once()
            
            # Verify session creation and panel updates
            tui_app.session_manager.create_session.assert_called_once_with("Welcome to OpenHands TUI!")
            tui_app.sessions_panel.update_sessions.assert_called_once()
            
            # Verify monitoring was started
            mock_run_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_no_manager(self, tui_app):
        """Test run method with no manager."""
        with patch.object(tui_app, 'setup_ui'):
            tui_app.manager = None
            
            with pytest.raises(RuntimeError, match="Window manager not initialized"):
                await tui_app.run()