"""Tests for PyTermGUI positioning and debug logging utilities."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

import pytest

# Import directly to test our implementation
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../'))

# Import our modules for testing
from openhands.tui.utils.pytermgui_debug import (
    PyTermGUIDebugLogger,
    get_debug_logger,
    enable_pytermgui_debug,
    disable_pytermgui_debug,
    log_widget_position,
    log_window_manager_state,
    validate_window_positions,
)


class TestPyTermGUIDebugLogger(unittest.TestCase):
    """Test the PyTermGUI debug logger functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.debug_logger = PyTermGUIDebugLogger(enabled=True)
        
        # Create mock widgets with positioning attributes
        self.mock_widget = Mock()
        self.mock_widget.pos = (10, 20)
        self.mock_widget.width = 80
        self.mock_widget.height = 24
        self.mock_widget.real_width = 80
        self.mock_widget.real_height = 24
        
        # Create mock window manager
        self.mock_manager = Mock()
        self.mock_manager.windows = [self.mock_widget]
        self.mock_manager.layout = Mock()
        self.mock_manager.layout.slots = []

    def test_initialization(self):
        """Test logger initialization."""
        logger = PyTermGUIDebugLogger(enabled=False)
        self.assertFalse(logger.enabled)
        self.assertEqual(len(logger.position_history), 0)
        self.assertEqual(len(logger.layout_events), 0)

    def test_enable_disable(self):
        """Test enabling and disabling debug logging."""
        logger = PyTermGUIDebugLogger(enabled=False)
        self.assertFalse(logger.enabled)
        
        logger.enable()
        self.assertTrue(logger.enabled)
        
        logger.disable()
        self.assertFalse(logger.enabled)

    @patch('openhands.tui.utils.pytermgui_debug.logger')
    def test_log_widget_position(self, mock_logger):
        """Test widget position logging."""
        self.debug_logger.log_widget_position(self.mock_widget, "Test Widget")
        
        # Check that debug log was called
        self.assertTrue(mock_logger.debug.called)
        
        # Check that position was recorded in history
        self.assertEqual(len(self.debug_logger.position_history), 1)
        
        history_entry = self.debug_logger.position_history[0]
        self.assertEqual(history_entry['name'], "Test Widget")
        self.assertEqual(history_entry['position'], (10, 20))
        self.assertEqual(history_entry['size'], (80, 24))

    @patch('openhands.tui.utils.pytermgui_debug.logger')
    def test_log_widget_position_disabled(self, mock_logger):
        """Test that logging is skipped when disabled."""
        self.debug_logger.disable()
        self.debug_logger.log_widget_position(self.mock_widget, "Test Widget")
        
        # Should not log or record when disabled
        mock_logger.debug.assert_not_called()
        self.assertEqual(len(self.debug_logger.position_history), 0)

    @patch('openhands.tui.utils.pytermgui_debug.logger')
    def test_log_window_manager_state(self, mock_logger):
        """Test window manager state logging."""
        self.debug_logger.log_window_manager_state(self.mock_manager)
        
        # Should log debug information
        self.assertTrue(mock_logger.debug.called)
        
        # Should log information about windows
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        window_count_logged = any("Number of windows: 1" in call for call in debug_calls)
        self.assertTrue(window_count_logged)

    @patch('openhands.tui.utils.pytermgui_debug.ptg')
    @patch('openhands.tui.utils.pytermgui_debug.logger')
    def test_log_terminal_resize(self, mock_logger, mock_ptg):
        """Test terminal resize event logging."""
        mock_ptg.terminal.width = 120
        mock_ptg.terminal.height = 40
        
        old_size = (80, 24)
        new_size = (120, 40)
        
        self.debug_logger.log_terminal_resize(old_size, new_size)
        
        # Check debug logging
        self.assertTrue(mock_logger.debug.called)
        
        # Check layout events were recorded
        self.assertEqual(len(self.debug_logger.layout_events), 1)
        
        event = self.debug_logger.layout_events[0]
        self.assertEqual(event['event'], 'terminal_resize')
        self.assertEqual(event['old_size'], old_size)
        self.assertEqual(event['new_size'], new_size)
        self.assertEqual(event['size_delta'], (40, 16))

    def test_validate_window_positions_side_by_side(self):
        """Test window position validation for side-by-side layout."""
        # Create mock windows with correct positioning
        left_window = Mock()
        left_window.pos = (0, 0)
        left_window.width = 40
        left_window.height = 24
        
        right_window = Mock()
        right_window.pos = (40, 0)
        right_window.width = 40
        right_window.height = 24
        
        windows = [left_window, right_window]
        
        with patch('openhands.tui.utils.pytermgui_debug.logger'):
            result = self.debug_logger.validate_window_positions(windows, "side_by_side")
        
        self.assertTrue(result)

    def test_validate_window_positions_side_by_side_invalid(self):
        """Test window position validation for incorrectly positioned windows."""
        # Create mock windows with incorrect positioning
        left_window = Mock()
        left_window.pos = (10, 5)  # Should be (0, 0)
        left_window.width = 40
        left_window.height = 24
        
        right_window = Mock()
        right_window.pos = (30, 10)  # Should be (40, 0)
        right_window.width = 40
        right_window.height = 24
        
        windows = [left_window, right_window]
        
        with patch('openhands.tui.utils.pytermgui_debug.logger'):
            result = self.debug_logger.validate_window_positions(windows, "side_by_side")
        
        self.assertFalse(result)

    def test_check_panel_positioning(self):
        """Test panel positioning validation."""
        panels = {
            "test_panel": self.mock_widget
        }
        
        with patch('openhands.tui.utils.pytermgui_debug.logger'):
            results = self.debug_logger.check_panel_positioning(panels)
        
        self.assertIn("test_panel", results)
        self.assertTrue(results["test_panel"])

    def test_check_panel_positioning_invalid(self):
        """Test panel positioning validation with invalid panel."""
        invalid_widget = Mock()
        invalid_widget.pos = (-10, -5)  # Invalid negative position
        invalid_widget.width = 0  # Invalid zero width
        invalid_widget.height = 24
        
        panels = {
            "invalid_panel": invalid_widget
        }
        
        with patch('openhands.tui.utils.pytermgui_debug.logger'):
            results = self.debug_logger.check_panel_positioning(panels)
        
        self.assertIn("invalid_panel", results)
        self.assertFalse(results["invalid_panel"])

    def test_extract_widget_info_with_rect(self):
        """Test widget info extraction when widget has rect attribute."""
        widget_with_rect = Mock()
        widget_with_rect.rect = (5, 10, 100, 50)  # x, y, width, height
        del widget_with_rect.pos  # Remove pos to test rect fallback
        del widget_with_rect.width
        del widget_with_rect.height
        
        info = self.debug_logger._extract_widget_info(widget_with_rect, "Rect Widget")
        
        self.assertEqual(info['position'], (5, 10))
        self.assertEqual(info['size'], (100, 50))
        self.assertEqual(info['name'], "Rect Widget")

    def test_extract_widget_info_minimal(self):
        """Test widget info extraction with minimal attributes."""
        minimal_widget = Mock()
        # Remove all positioning attributes
        for attr in ['pos', 'position', 'width', 'height', 'size', 'real_width', 'real_height', 'real_size', 'rect']:
            if hasattr(minimal_widget, attr):
                delattr(minimal_widget, attr)
        
        info = self.debug_logger._extract_widget_info(minimal_widget, "Minimal Widget")
        
        # Should have default values
        self.assertEqual(info['position'], (0, 0))
        self.assertEqual(info['size'], (0, 0))
        self.assertEqual(info['real_size'], (0, 0))
        self.assertEqual(info['name'], "Minimal Widget")

    def test_dump_position_history(self):
        """Test position history dumping."""
        # Add some history entries
        self.debug_logger.log_widget_position(self.mock_widget, "Widget 1")
        self.debug_logger.log_widget_position(self.mock_widget, "Widget 2")
        self.debug_logger.log_widget_position(self.mock_widget, "Widget 3")
        
        with patch('openhands.tui.utils.pytermgui_debug.logger'):
            # Test getting all history
            all_history = self.debug_logger.dump_position_history()
            self.assertEqual(len(all_history), 3)
            
            # Test getting last N entries
            last_2 = self.debug_logger.dump_position_history(last_n=2)
            self.assertEqual(len(last_2), 2)
            self.assertEqual(last_2[0]['name'], "Widget 2")
            self.assertEqual(last_2[1]['name'], "Widget 3")

    def test_clear_history(self):
        """Test clearing position and layout history."""
        # Add some entries
        self.debug_logger.log_widget_position(self.mock_widget, "Test Widget")
        self.debug_logger.log_terminal_resize((80, 24), (120, 40))
        
        with patch('openhands.tui.utils.pytermgui_debug.logger'):
            self.assertEqual(len(self.debug_logger.position_history), 1)
            self.assertEqual(len(self.debug_logger.layout_events), 1)
            
            self.debug_logger.clear_history()
            
            self.assertEqual(len(self.debug_logger.position_history), 0)
            self.assertEqual(len(self.debug_logger.layout_events), 0)


class TestGlobalFunctions(unittest.TestCase):
    """Test global convenience functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset global logger state
        import openhands.tui.utils.pytermgui_debug as debug_module
        debug_module._debug_logger = None

    @patch('openhands.tui.utils.pytermgui_debug.logger')
    def test_get_debug_logger_singleton(self, mock_logger):
        """Test that get_debug_logger returns a singleton."""
        logger1 = get_debug_logger()
        logger2 = get_debug_logger()
        
        self.assertIs(logger1, logger2)

    @patch('openhands.tui.utils.pytermgui_debug.logger')
    def test_enable_disable_global(self, mock_logger):
        """Test global enable/disable functions."""
        logger = get_debug_logger()
        
        # Test enable
        enable_pytermgui_debug()
        self.assertTrue(logger.enabled)
        
        # Test disable
        disable_pytermgui_debug()
        self.assertFalse(logger.enabled)

    @patch('openhands.tui.utils.pytermgui_debug.logger')
    def test_convenience_functions(self, mock_logger):
        """Test convenience wrapper functions."""
        enable_pytermgui_debug()
        
        mock_widget = Mock()
        mock_widget.pos = (0, 0)
        mock_widget.width = 80
        mock_widget.height = 24
        
        mock_manager = Mock()
        mock_manager.windows = [mock_widget]
        mock_manager.layout = Mock()
        mock_manager.layout.slots = []
        
        # Test log_widget_position convenience function
        log_widget_position(mock_widget, "Test Widget")
        
        # Test log_window_manager_state convenience function
        log_window_manager_state(mock_manager)
        
        # Test validate_window_positions convenience function
        mock_widget.pos = (0, 0)
        mock_widget2 = Mock()
        mock_widget2.pos = (80, 0)
        mock_widget2.width = 40
        mock_widget2.height = 24
        
        result = validate_window_positions([mock_widget, mock_widget2], "side_by_side")
        self.assertTrue(result)


class TestPositioningEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions in positioning validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.debug_logger = PyTermGUIDebugLogger(enabled=True)

    def test_validate_empty_windows_list(self):
        """Test validation with empty windows list."""
        result = self.debug_logger.validate_window_positions([], "side_by_side")
        self.assertTrue(result)  # Should return True for empty list

    def test_validate_single_window(self):
        """Test validation with single window (should pass)."""
        mock_window = Mock()
        mock_window.pos = (0, 0)
        mock_window.width = 80
        mock_window.height = 24
        
        with patch('openhands.tui.utils.pytermgui_debug.logger'):
            result = self.debug_logger.validate_window_positions([mock_window], "side_by_side")
        
        self.assertTrue(result)  # Should return True for non-matching layout

    def test_validate_unsupported_layout(self):
        """Test validation with unsupported layout type."""
        mock_window = Mock()
        mock_window.pos = (0, 0)
        mock_window.width = 80
        mock_window.height = 24
        
        with patch('openhands.tui.utils.pytermgui_debug.logger'):
            result = self.debug_logger.validate_window_positions([mock_window], "unsupported_layout")
        
        self.assertTrue(result)  # Should return True for unsupported layouts

    def test_extract_widget_info_with_exception(self):
        """Test widget info extraction when attribute access raises exception."""
        problematic_widget = Mock()
        # Make pos property raise an exception
        type(problematic_widget).pos = property(lambda self: (_ for _ in ()).throw(AttributeError("Test error")))
        
        info = self.debug_logger._extract_widget_info(problematic_widget, "Problematic Widget")
        
        # Should still return valid structure with defaults
        self.assertEqual(info['position'], (0, 0))
        self.assertEqual(info['name'], "Problematic Widget")

    def test_window_manager_state_with_none(self):
        """Test window manager state logging with None manager."""
        with patch('openhands.tui.utils.pytermgui_debug.logger') as mock_logger:
            self.debug_logger.log_window_manager_state(None)
            
            # Should not call debug logging for None manager
            mock_logger.debug.assert_not_called()

    def test_layout_application_with_disabled_logger(self):
        """Test layout application logging when logger is disabled."""
        self.debug_logger.disable()
        
        mock_layout = Mock()
        
        with patch('openhands.tui.utils.pytermgui_debug.logger') as mock_logger:
            self.debug_logger.log_layout_application(mock_layout, "Test Layout")
            
            # Should not log when disabled
            mock_logger.debug.assert_not_called()
            self.assertEqual(len(self.debug_logger.layout_events), 0)


if __name__ == '__main__':
    unittest.main() 