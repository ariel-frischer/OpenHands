"""PyTermGUI Positioning Fixes.

Utility functions to fix and maintain proper positioning of PyTermGUI windows and panels.
This module addresses issues where panels drift to the center instead of staying anchored
to their designated borders (top/bottom).
"""

from typing import List, Tuple, Optional
import pytermgui as ptg
from openhands.core.logger import openhands_logger as logger


class PositionAnchor:
    """Represents a positioning anchor for widgets."""
    
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CENTER = "center"
    TOP_FULL = "top_full"
    BOTTOM_FULL = "bottom_full"


class PositioningFixer:
    """Utility class to fix and maintain PyTermGUI positioning."""

    @staticmethod
    def force_window_position(window: ptg.Window, x: int, y: int, width: int, height: int) -> None:
        """Force a window to a specific position and size.
        
        Args:
            window: Window to position
            x: X coordinate
            y: Y coordinate  
            width: Window width
            height: Window height
        """
        try:
            # Use static_position for PyTermGUI windows
            window.static_position = (x, y)
            
            # Set size if the window supports it
            if hasattr(window, 'width'):
                window.width = width
            if hasattr(window, 'height'):
                window.height = height
            
            # Try to refresh if method exists
            if hasattr(window, 'refresh'):
                window.refresh()
            
            logger.debug(f"Forced window position: static_position=({x},{y}), size=({width}x{height})")
            
        except Exception as e:
            logger.error(f"Failed to force window position: {e}")

    @staticmethod
    def anchor_window_to_border(
        window: ptg.Window, 
        anchor: str, 
        terminal_width: int, 
        terminal_height: int,
        width_ratio: float = 1.0,
        height_ratio: float = 1.0,
        margin_x: int = 0,
        margin_y: int = 0
    ) -> Tuple[int, int, int, int]:
        """Anchor a window to a specific border position.
        
        Args:
            window: Window to anchor
            anchor: Anchor position (use PositionAnchor constants)
            terminal_width: Terminal width
            terminal_height: Terminal height
            width_ratio: Width as ratio of terminal width (0.0 to 1.0)
            height_ratio: Height as ratio of terminal height (0.0 to 1.0)
            margin_x: X margin from border
            margin_y: Y margin from border
            
        Returns:
            Tuple of (x, y, width, height) for the calculated position
        """
        # Calculate actual dimensions
        actual_width = max(1, int(terminal_width * width_ratio))
        actual_height = max(1, int(terminal_height * height_ratio))
        
        # Calculate position based on anchor
        if anchor == PositionAnchor.TOP_LEFT:
            x, y = margin_x, margin_y
        elif anchor == PositionAnchor.TOP_RIGHT:
            x = terminal_width - actual_width - margin_x
            y = margin_y
        elif anchor == PositionAnchor.BOTTOM_LEFT:
            x = margin_x
            y = terminal_height - actual_height - margin_y
        elif anchor == PositionAnchor.BOTTOM_RIGHT:
            x = terminal_width - actual_width - margin_x
            y = terminal_height - actual_height - margin_y
        elif anchor == PositionAnchor.CENTER:
            x = (terminal_width - actual_width) // 2
            y = (terminal_height - actual_height) // 2
        elif anchor == PositionAnchor.TOP_FULL:
            x, y = margin_x, margin_y
            actual_width = terminal_width - 2 * margin_x
        elif anchor == PositionAnchor.BOTTOM_FULL:
            x = margin_x
            y = terminal_height - actual_height - margin_y
            actual_width = terminal_width - 2 * margin_x
        else:
            # Default to top-left
            x, y = margin_x, margin_y
            
        # Apply the position
        PositioningFixer.force_window_position(window, x, y, actual_width, actual_height)
        
        return (x, y, actual_width, actual_height)

    @staticmethod
    def create_side_by_side_layout(
        left_window: ptg.Window,
        right_window: ptg.Window,
        terminal_width: int,
        terminal_height: int,
        left_width_ratio: float = 0.3,
        gap: int = 0
    ) -> None:
        """Create a robust side-by-side layout with explicit positioning.
        
        Args:
            left_window: Left side window
            right_window: Right side window
            terminal_width: Terminal width
            terminal_height: Terminal height
            left_width_ratio: Ratio of terminal width for left window
            gap: Gap between windows
        """
        # Calculate dimensions
        left_width = max(1, int(terminal_width * left_width_ratio))
        right_width = max(1, terminal_width - left_width - gap)
        
        # Force positioning - left window at top-left
        PositioningFixer.force_window_position(left_window, 0, 0, left_width, terminal_height)
        
        # Force positioning - right window adjacent to left
        PositioningFixer.force_window_position(
            right_window, 
            left_width + gap, 
            0, 
            right_width, 
            terminal_height
        )
        
        logger.info(f"Applied side-by-side layout: left={left_width}x{terminal_height}, right={right_width}x{terminal_height}")

    @staticmethod
    def fix_layout_drift(manager: ptg.WindowManager) -> bool:
        """Fix layout drift issues where windows move to center.
        
        Args:
            manager: Window manager to fix
            
        Returns:
            True if fixes were applied, False otherwise
        """
        if not manager:
            return False
        
        # Access windows through _windows internal attribute
        windows = getattr(manager, '_windows', [])
        if not windows:
            return False
            
        try:
            terminal_width = ptg.terminal.width
            terminal_height = ptg.terminal.height
            
            logger.debug(f"Fixing layout drift for {len(windows)} windows")
            
            # Handle two-window side-by-side layout (most common case)
            if len(windows) == 2:
                left_window, right_window = windows[0], windows[1]
                
                # Check if windows have drifted from expected positions
                left_pos = (0, 0)
                right_pos = (0, 0)
                
                # Get position from rect or static_position
                if hasattr(left_window, 'rect'):
                    rect = left_window.rect
                    left_pos = (rect[0], rect[1]) if rect else (0, 0)
                elif hasattr(left_window, 'static_position'):
                    left_pos = left_window.static_position or (0, 0)
                
                if hasattr(right_window, 'rect'):
                    rect = right_window.rect
                    right_pos = (rect[0], rect[1]) if rect else (0, 0)
                elif hasattr(right_window, 'static_position'):
                    right_pos = right_window.static_position or (0, 0)
                
                # Expected positions
                expected_left_x = 0
                expected_left_width = int(terminal_width * 0.3)
                expected_right_x = expected_left_width
                
                # Check if positions are incorrect
                left_needs_fix = (
                    left_pos[0] != expected_left_x or 
                    left_pos[1] != 0 or
                    getattr(left_window, 'width', 0) != expected_left_width
                )
                
                right_needs_fix = (
                    right_pos[0] != expected_right_x or 
                    right_pos[1] != 0 or
                    getattr(right_window, 'width', 0) != (terminal_width - expected_left_width)
                )
                
                if left_needs_fix or right_needs_fix:
                    logger.warning("Detected layout drift, applying fixes")
                    PositioningFixer.create_side_by_side_layout(
                        left_window, right_window, terminal_width, terminal_height
                    )
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Error fixing layout drift: {e}")
            return False

    @staticmethod
    def validate_and_fix_positions(
        manager: ptg.WindowManager,
        expected_layout: str = "side_by_side"
    ) -> bool:
        """Validate current positions and fix if necessary.
        
        Args:
            manager: Window manager to validate
            expected_layout: Expected layout type
            
        Returns:
            True if positions are valid or were successfully fixed
        """
        if not manager:
            return True
        
        # Access windows through _windows internal attribute
        windows = getattr(manager, '_windows', [])
        if not windows:
            return True
            
        try:
            # First validate current positions
            from .pytermgui_debug import validate_window_positions
            is_valid = validate_window_positions(windows, expected_layout)
            
            if not is_valid:
                logger.warning("Position validation failed, attempting to fix")
                # Apply fixes
                fixes_applied = PositioningFixer.fix_layout_drift(manager)
                
                if fixes_applied:
                    # Re-validate after fixes
                    is_valid = validate_window_positions(windows, expected_layout)
                    if is_valid:
                        logger.info("Position fixes successfully applied")
                    else:
                        logger.error("Position fixes failed to resolve issues")
                        
                return is_valid
            else:
                logger.debug("Position validation passed")
                return True
                
        except Exception as e:
            logger.error(f"Error during position validation and fixing: {e}")
            return False

    @staticmethod
    def setup_robust_layout(
        manager: ptg.WindowManager,
        windows: List[ptg.Window],
        layout_type: str = "side_by_side"
    ) -> None:
        """Set up a robust layout that resists drift.
        
        Args:
            manager: Window manager
            windows: List of windows to layout
            layout_type: Type of layout to create
        """
        if not manager or not windows:
            return
            
        try:
            terminal_width = ptg.terminal.width
            terminal_height = ptg.terminal.height
            
            logger.debug(f"Setting up robust {layout_type} layout")
            
            if layout_type == "side_by_side" and len(windows) == 2:
                left_window, right_window = windows[0], windows[1]
                
                # Apply robust side-by-side positioning using static positions
                # This bypasses the layout system to prevent drift
                PositioningFixer.create_side_by_side_layout(
                    left_window, right_window, terminal_width, terminal_height
                )
                
                # Set static positions to prevent layout system from moving windows
                left_window.static_position = (0, 0)
                right_window.static_position = (int(terminal_width * 0.3), 0)
                
                logger.debug("Applied static positioning to prevent layout drift")
                
                logger.info("Robust side-by-side layout established")
                
        except Exception as e:
            logger.error(f"Error setting up robust layout: {e}")

    @staticmethod
    def prevent_center_drift(window: ptg.Window, anchor_position: Tuple[int, int]) -> None:
        """Prevent a window from drifting towards the center.
        
        Args:
            window: Window to anchor
            anchor_position: Position to anchor to (x, y)
        """
        try:
            # Get current position from rect or static_position
            current_pos = (0, 0)
            if hasattr(window, 'rect'):
                rect = window.rect
                current_pos = (rect[0], rect[1]) if rect else (0, 0)
            elif hasattr(window, 'static_position'):
                current_pos = window.static_position or (0, 0)
            
            anchor_x, anchor_y = anchor_position
            
            # Check if window has drifted significantly from anchor
            drift_threshold = 5  # pixels
            x_drift = abs(current_pos[0] - anchor_x)
            y_drift = abs(current_pos[1] - anchor_y)
            
            if x_drift > drift_threshold or y_drift > drift_threshold:
                logger.warning(f"Window drift detected: {current_pos} -> {anchor_position}")
                window.static_position = anchor_position
                if hasattr(window, 'refresh'):
                    window.refresh()
                
        except Exception as e:
            logger.error(f"Error preventing center drift: {e}")


# Convenience functions for common positioning tasks

def fix_tui_positioning(app) -> bool:
    """Fix TUI positioning issues for an OpenHands TUI app.
    
    Args:
        app: OpenHandsTUIApp instance
        
    Returns:
        True if fixes were applied successfully
    """
    try:
        if not hasattr(app, 'manager') or not app.manager:
            return False
            
        # Validate and fix current positions
        return PositioningFixer.validate_and_fix_positions(app.manager, "side_by_side")
        
    except Exception as e:
        logger.error(f"Error in fix_tui_positioning: {e}")
        return False


def setup_side_by_side_layout(app) -> None:
    """Set up a robust side-by-side layout for OpenHands TUI.
    
    Args:
        app: OpenHandsTUIApp instance
    """
    try:
        if not hasattr(app, 'manager') or not app.manager:
            logger.error("No window manager available for layout setup")
            return
            
        windows = []
        if hasattr(app, 'left_window') and app.left_window:
            windows.append(app.left_window)
        if hasattr(app, 'chat_window') and app.chat_window:
            windows.append(app.chat_window)
            
        if len(windows) == 2:
            PositioningFixer.setup_robust_layout(app.manager, windows, "side_by_side")
        else:
            logger.warning(f"Expected 2 windows for side-by-side layout, got {len(windows)}")
            
    except Exception as e:
        logger.error(f"Error in setup_side_by_side_layout: {e}")


def monitor_and_fix_drift(app) -> None:
    """Monitor for layout drift and apply fixes continuously.
    
    Args:
        app: OpenHandsTUIApp instance
    """
    try:
        if hasattr(app, 'manager') and app.manager:
            drift_detected = PositioningFixer.fix_layout_drift(app.manager)
            if drift_detected:
                logger.info("Corrected layout drift during monitoring")
                
    except Exception as e:
        logger.error(f"Error in monitor_and_fix_drift: {e}") 