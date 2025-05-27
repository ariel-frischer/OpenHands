"""TUI Utilities.

Utility functions and helpers for the TUI system.
"""

from .file_operations import FileOperations
from .formatting import Formatter
from .keybindings import KeyBindings
from .pytermgui_debug import (
    PyTermGUIDebugLogger,
    get_debug_logger,
    enable_pytermgui_debug,
    disable_pytermgui_debug,
    log_widget_position,
    log_window_manager_state,
    validate_window_positions,
)
from .positioning_fixes import (
    PositionAnchor,
    PositioningFixer,
    fix_tui_positioning,
    setup_side_by_side_layout,
    monitor_and_fix_drift,
)
from .resource_manager import (
    TUICleanupMixin,
    TUIResourceManager,
    AsyncTUIResourceManager,
    TUIResourcePool,
    managed_resource,
    async_managed_resource,
    pooled_resource,
    register_tui_resource,
    unregister_tui_resource,
    cleanup_all_tui_resources,
    get_tui_memory_stats,
    get_tui_memory_summary,
    get_tui_resource_stats,
    force_tui_garbage_collection,
)

__all__ = [
    "FileOperations",
    "Formatter",
    "KeyBindings",
    "PyTermGUIDebugLogger",
    "get_debug_logger",
    "enable_pytermgui_debug",
    "disable_pytermgui_debug",
    "log_widget_position",
    "log_window_manager_state",
    "validate_window_positions",
    "PositionAnchor",
    "PositioningFixer",
    "fix_tui_positioning",
    "setup_side_by_side_layout",
    "monitor_and_fix_drift",
    "TUICleanupMixin",
    "TUIResourceManager",
    "AsyncTUIResourceManager",
    "TUIResourcePool",
    "managed_resource",
    "async_managed_resource",
    "pooled_resource",
    "register_tui_resource",
    "unregister_tui_resource",
    "cleanup_all_tui_resources",
    "get_tui_memory_stats",
    "get_tui_memory_summary",
    "get_tui_resource_stats",
    "force_tui_garbage_collection",
]
