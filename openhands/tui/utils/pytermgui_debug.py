"""PyTermGUI Debug Utilities.

Comprehensive debug logging and validation utilities for PyTermGUI positioning and layout management.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import pytermgui as ptg

from openhands.core.logger import openhands_logger as logger


class PyTermGUIDebugLogger:
    """Debug logger for PyTermGUI positioning and layout events."""

    def __init__(self, enabled: bool = False):
        """Initialize the debug logger.

        Args:
            enabled: Whether debug logging is enabled
        """
        self.enabled = enabled
        self.position_history: List[Dict[str, Any]] = []
        self.layout_events: List[Dict[str, Any]] = []

    def enable(self) -> None:
        """Enable debug logging."""
        self.enabled = True
        logger.info("PyTermGUI debug logging enabled")

    def disable(self) -> None:
        """Disable debug logging."""
        self.enabled = False
        logger.info("PyTermGUI debug logging disabled")

    def log_widget_position(self, widget: ptg.Widget, name: str = "Widget") -> None:
        """Log the position and size of a PyTermGUI widget.

        Args:
            widget: The widget to log information about
            name: Descriptive name for the widget
        """
        if not self.enabled:
            return

        timestamp = time.time()
        widget_info = self._extract_widget_info(widget, name)
        
        # Log to main logger
        logger.debug(
            f"[PyTermGUI Debug] {name} - Position: {widget_info['position']}, "
            f"Size: {widget_info['size']}, Real Size: {widget_info['real_size']}"
        )

        # Store in history
        widget_info['timestamp'] = timestamp
        self.position_history.append(widget_info)

    def log_window_manager_state(self, manager: ptg.WindowManager) -> None:
        """Log the complete state of a window manager.

        Args:
            manager: The window manager to log
        """
        if not self.enabled or not manager:
            return

        logger.debug("[PyTermGUI Debug] === Window Manager State ===")
        
        # Access windows through _windows internal attribute
        windows = getattr(manager, '_windows', [])
        logger.debug(f"[PyTermGUI Debug] Number of windows: {len(windows)}")
        
        # Log layout information
        if hasattr(manager, 'layout'):
            layout = manager.layout
            try:
                # Build rows to get actual slots with positions
                rows = layout.build_rows()
                total_slots = sum(len(row) for row in rows)
                logger.debug(f"[PyTermGUI Debug] Layout slots: {total_slots}")
                
                for row_idx, row in enumerate(rows):
                    for slot_idx, slot in enumerate(row):
                        slot_info = self._extract_slot_info(slot, f"Row {row_idx}, Slot {slot_idx}")
                        logger.debug(
                            f"[PyTermGUI Debug] {slot_info['name']}: "
                            f"Position: {slot_info['position']}, "
                            f"Size: {slot_info['dimension']}"
                        )
            except Exception as e:
                logger.debug(f"[PyTermGUI Debug] Could not access layout slots: {e}")

        # Log each window
        for i, window in enumerate(windows):
            self.log_widget_position(window, f"Window {i}")

    def log_layout_application(self, layout: Any, description: str = "Layout Apply") -> None:
        """Log layout application events.

        Args:
            layout: The layout being applied
            description: Description of the layout operation
        """
        if not self.enabled:
            return

        timestamp = time.time()
        event_info = {
            'timestamp': timestamp,
            'event': 'layout_apply',
            'description': description,
            'terminal_size': (ptg.terminal.width, ptg.terminal.height)
        }

        logger.debug(f"[PyTermGUI Debug] Layout Event: {description}")
        logger.debug(f"[PyTermGUI Debug] Terminal size: {event_info['terminal_size']}")

        self.layout_events.append(event_info)

    def log_terminal_resize(self, old_size: Tuple[int, int], new_size: Tuple[int, int]) -> None:
        """Log terminal resize events.

        Args:
            old_size: Previous terminal size (width, height)
            new_size: New terminal size (width, height)
        """
        if not self.enabled:
            return

        timestamp = time.time()
        resize_info = {
            'timestamp': timestamp,
            'event': 'terminal_resize',
            'old_size': old_size,
            'new_size': new_size,
            'size_delta': (new_size[0] - old_size[0], new_size[1] - old_size[1])
        }

        logger.debug(f"[PyTermGUI Debug] Terminal resize: {old_size} -> {new_size}")
        logger.debug(f"[PyTermGUI Debug] Size delta: {resize_info['size_delta']}")

        self.layout_events.append(resize_info)

    def validate_window_positions(self, windows: List[ptg.Window], expected_layout: str = "side_by_side") -> bool:
        """Validate that windows are positioned correctly.

        Args:
            windows: List of windows to validate
            expected_layout: Expected layout type ("side_by_side", "stacked", etc.)

        Returns:
            True if positioning is correct, False otherwise
        """
        if not self.enabled or not windows:
            return True

        validation_results = []
        
        for i, window in enumerate(windows):
            window_info = self._extract_widget_info(window, f"Window {i}")
            validation_results.append(window_info)

        # Validate based on expected layout
        if expected_layout == "side_by_side" and len(windows) == 2:
            left_window, right_window = validation_results[0], validation_results[1]
            
            # Check that left window starts at x=0
            left_valid = left_window['position'][0] == 0
            
            # Check that right window starts where left window ends
            right_x_expected = left_window['position'][0] + left_window['size'][0]
            right_valid = right_window['position'][0] == right_x_expected
            
            # Check that both windows start at y=0
            top_valid = left_window['position'][1] == 0 and right_window['position'][1] == 0
            
            overall_valid = left_valid and right_valid and top_valid
            
            logger.debug(f"[PyTermGUI Debug] Layout validation ({expected_layout}): {overall_valid}")
            logger.debug(f"[PyTermGUI Debug] Left window at x=0: {left_valid}")
            logger.debug(f"[PyTermGUI Debug] Right window positioned correctly: {right_valid}")
            logger.debug(f"[PyTermGUI Debug] Both windows at top: {top_valid}")
            
            return overall_valid

        return True

    def check_panel_positioning(self, panels: Dict[str, ptg.Widget]) -> Dict[str, bool]:
        """Check positioning of named panels.

        Args:
            panels: Dictionary of panel name to widget mappings

        Returns:
            Dictionary of panel names to validation results
        """
        results = {}
        
        if not self.enabled:
            return results

        logger.debug("[PyTermGUI Debug] === Panel Positioning Check ===")
        
        for panel_name, panel in panels.items():
            panel_info = self._extract_widget_info(panel, panel_name)
            
            # Basic validation: panel should have valid position and size
            valid_position = panel_info['position'][0] >= 0 and panel_info['position'][1] >= 0
            valid_size = panel_info['size'][0] > 0 and panel_info['size'][1] > 0
            
            results[panel_name] = valid_position and valid_size
            
            logger.debug(
                f"[PyTermGUI Debug] {panel_name}: Valid position: {valid_position}, "
                f"Valid size: {valid_size}, Overall: {results[panel_name]}"
            )

        return results

    def dump_position_history(self, last_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """Dump position history for analysis.

        Args:
            last_n: Optional number of most recent entries to return

        Returns:
            List of position history entries
        """
        if last_n is not None:
            return self.position_history[-last_n:]
        return self.position_history.copy()

    def dump_layout_events(self, last_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """Dump layout events for analysis.

        Args:
            last_n: Optional number of most recent events to return

        Returns:
            List of layout event entries
        """
        if last_n is not None:
            return self.layout_events[-last_n:]
        return self.layout_events.copy()

    def clear_history(self) -> None:
        """Clear all recorded position and layout history."""
        self.position_history.clear()
        self.layout_events.clear()
        logger.debug("[PyTermGUI Debug] Cleared position and layout history")

    def _extract_widget_info(self, widget: ptg.Widget, name: str) -> Dict[str, Any]:
        """Extract position and size information from a widget.

        Args:
            widget: Widget to extract info from
            name: Name for the widget

        Returns:
            Dictionary containing widget information
        """
        info = {
            'name': name,
            'type': type(widget).__name__,
            'position': (0, 0),
            'size': (0, 0),
            'real_size': (0, 0)
        }

        try:
            # For Windows, use rect which returns (x, y, width, height)
            if hasattr(widget, 'rect'):
                rect = widget.rect
                if rect and hasattr(rect, '__len__') and len(rect) >= 4:
                    info['position'] = (rect[0], rect[1])
                    info['size'] = (rect[2], rect[3])
                    info['real_size'] = (rect[2], rect[3])
                    return info
            
            # Try to get position information
            if hasattr(widget, 'pos'):
                info['position'] = widget.pos
            elif hasattr(widget, 'position'):
                info['position'] = widget.position

            # Try to get size information
            if hasattr(widget, 'width') and hasattr(widget, 'height'):
                info['size'] = (widget.width, widget.height)
            elif hasattr(widget, 'size'):
                info['size'] = widget.size

            # Try to get real size (actual rendered size)
            if hasattr(widget, 'real_width') and hasattr(widget, 'real_height'):
                info['real_size'] = (widget.real_width, widget.real_height)
            elif hasattr(widget, 'real_size'):
                info['real_size'] = widget.real_size

        except (TypeError, AttributeError, Exception):
            # Handle cases where attributes don't behave as expected
            pass

        return info

    def _extract_slot_info(self, slot: Any, name: str) -> Dict[str, Any]:
        """Extract information from a layout slot.

        Args:
            slot: Layout slot to extract info from
            name: Name for the slot

        Returns:
            Dictionary containing slot information
        """
        info = {
            'name': name,
            'position': 'N/A',
            'dimension': 'N/A'
        }

        if hasattr(slot, 'position'):
            info['position'] = slot.position
        if hasattr(slot, 'dimension'):
            info['dimension'] = slot.dimension

        return info


# Global debug logger instance
_debug_logger: Optional[PyTermGUIDebugLogger] = None


def get_debug_logger() -> PyTermGUIDebugLogger:
    """Get the global PyTermGUI debug logger instance.

    Returns:
        Global debug logger instance
    """
    global _debug_logger
    if _debug_logger is None:
        _debug_logger = PyTermGUIDebugLogger()
    return _debug_logger


def enable_pytermgui_debug() -> None:
    """Enable PyTermGUI debug logging globally."""
    get_debug_logger().enable()


def disable_pytermgui_debug() -> None:
    """Disable PyTermGUI debug logging globally."""
    get_debug_logger().disable()


def log_widget_position(widget: ptg.Widget, name: str = "Widget") -> None:
    """Convenience function to log widget position using global logger.

    Args:
        widget: Widget to log
        name: Name for the widget
    """
    get_debug_logger().log_widget_position(widget, name)


def log_window_manager_state(manager: ptg.WindowManager) -> None:
    """Convenience function to log window manager state using global logger.

    Args:
        manager: Window manager to log
    """
    get_debug_logger().log_window_manager_state(manager)


def validate_window_positions(windows: List[ptg.Window], expected_layout: str = "side_by_side") -> bool:
    """Convenience function to validate window positions using global logger.

    Args:
        windows: Windows to validate
        expected_layout: Expected layout type

    Returns:
        True if positioning is correct
    """
    return get_debug_logger().validate_window_positions(windows, expected_layout) 