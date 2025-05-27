"""OpenHands TUI System.

A PyTermGUI-based terminal user interface for OpenHands that supports
multiple concurrent sessions with a three-panel layout.
"""

from .app import OpenHandsTUIApp
from .main import main

__all__ = ['OpenHandsTUIApp', 'main']