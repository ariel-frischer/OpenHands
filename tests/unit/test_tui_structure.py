"""Test TUI Structure.

Basic tests to verify the TUI directory structure and imports work correctly.
"""

import pytest


def test_tui_imports():
    """Test that TUI modules can be imported successfully."""
    # Test main TUI imports
    from openhands.tui import OpenHandsTUIApp, main
    
    assert OpenHandsTUIApp is not None
    assert main is not None


def test_manager_imports():
    """Test that TUI manager modules can be imported."""
    from openhands.tui.managers import (
        SessionContext,
        SessionManager,
        TUIEventManager,
        TUIPanelFileManager,
    )
    
    assert SessionContext is not None
    assert SessionManager is not None
    assert TUIEventManager is not None
    assert TUIPanelFileManager is not None


def test_panel_imports():
    """Test that TUI panel modules can be imported."""
    from openhands.tui.panels import BasePanel, ChatPanel, LogsPanel, SessionsPanel
    
    assert BasePanel is not None
    assert ChatPanel is not None
    assert LogsPanel is not None
    assert SessionsPanel is not None


def test_widget_imports():
    """Test that TUI widget modules can be imported."""
    from openhands.tui.widgets import ChatDisplay, LogViewer, SessionList
    
    assert ChatDisplay is not None
    assert LogViewer is not None
    assert SessionList is not None


def test_utils_imports():
    """Test that TUI utility modules can be imported."""
    from openhands.tui.utils import FileOperations, Formatter, KeyBindings
    
    assert FileOperations is not None
    assert Formatter is not None
    assert KeyBindings is not None


def test_session_manager_creation():
    """Test that SessionManager can be created."""
    from openhands.core.config import AppConfig
    from openhands.tui.managers import SessionManager
    
    config = AppConfig()
    session_manager = SessionManager(config, None)
    
    assert session_manager is not None
    assert session_manager.config == config
    assert session_manager.sessions == {}
    assert session_manager.active_session_id is None


def test_file_manager_creation():
    """Test that TUIPanelFileManager can be created."""
    from openhands.tui.managers import TUIPanelFileManager
    
    file_manager = TUIPanelFileManager()
    
    assert file_manager is not None
    assert file_manager.base_dir.name == "tui"


def test_formatter_utilities():
    """Test basic formatter utility functions."""
    from openhands.tui.utils import Formatter
    
    # Test text truncation
    text = "This is a long text that should be truncated"
    truncated = Formatter.truncate_text(text, 20)
    assert len(truncated) <= 20
    assert truncated.endswith("...")
    
    # Test timestamp formatting
    from datetime import datetime
    timestamp = datetime(2025, 1, 26, 14, 30, 15)
    formatted = Formatter.format_timestamp(timestamp)
    assert formatted == "14:30:15"


def test_file_operations_utilities():
    """Test basic file operations utility functions."""
    from openhands.tui.utils import FileOperations
    from pathlib import Path
    import tempfile
    
    # Test directory creation
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir) / "test_subdir"
        result = FileOperations.ensure_directory(test_dir)
        assert result.exists()
        assert result.is_dir()
    
    # Test file existence check
    assert not FileOperations.file_exists("/nonexistent/file.txt")


@pytest.mark.asyncio
async def test_session_manager_basic_operations():
    """Test basic session manager operations."""
    from openhands.core.config import AppConfig
    from openhands.tui.managers import SessionManager
    
    config = AppConfig()
    session_manager = SessionManager(config, None)
    
    # Test session creation
    session_id = await session_manager.create_session("Test task")
    assert session_id is not None
    assert len(session_manager.sessions) == 1
    assert session_manager.active_session_id == session_id
    
    # Test session retrieval
    session = session_manager.get_active_session()
    assert session is not None
    assert session.sid == session_id
    assert session.task_description == "Test task"
    
    # Test session listing
    sessions = session_manager.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].sid == session_id


if __name__ == "__main__":
    pytest.main([__file__])