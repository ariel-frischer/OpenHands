"""TUI Utilities.

Utility functions and helpers for the TUI system.
"""

from .file_operations import FileOperations
from .formatting import Formatter
from .keybindings import KeyBindings
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
