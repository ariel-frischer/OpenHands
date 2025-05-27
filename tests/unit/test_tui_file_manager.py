"""Tests for TUI File Manager functionality."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from openhands.core.schema.agent import AgentState
from openhands.tui.managers.file_manager import TUIPanelFileManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def file_manager(temp_dir):
    """Create a file manager instance with temporary directory."""
    return TUIPanelFileManager(base_dir=temp_dir)


@pytest.fixture
def mock_session():
    """Create a mock session context."""
    session = Mock()
    session.sid = "test_session_123"
    session.task_description = "Test task description"
    session.agent_state = AgentState.RUNNING
    session.created_at = datetime(2024, 1, 1, 12, 0, 0)
    session.last_activity = datetime(2024, 1, 1, 12, 30, 0)
    return session


class TestTUIPanelFileManager:
    """Test cases for TUIPanelFileManager."""

    def test_initialization(self, temp_dir):
        """Test file manager initialization."""
        file_manager = TUIPanelFileManager(base_dir=temp_dir)
        
        assert file_manager.base_dir == Path(temp_dir)
        assert file_manager.sessions_dir == Path(temp_dir) / "sessions"
        assert file_manager.base_dir.exists()
        assert file_manager.sessions_dir.exists()

    def test_get_panel_file_sessions(self, file_manager):
        """Test getting sessions panel file path."""
        file_path = file_manager.get_panel_file('sessions')
        
        assert file_path == file_manager.sessions_dir / "session_list.json"
        assert file_path.parent.exists()

    def test_get_panel_file_chat(self, file_manager):
        """Test getting chat panel file path."""
        session_id = "test_session"
        file_path = file_manager.get_panel_file('chat', session_id)
        
        expected_path = file_manager.sessions_dir / session_id / "chat_history.txt"
        assert file_path == expected_path
        assert file_path.parent.exists()

    def test_get_panel_file_logs(self, file_manager):
        """Test getting logs panel file path."""
        session_id = "test_session"
        file_path = file_manager.get_panel_file('logs', session_id)
        
        expected_path = file_manager.sessions_dir / session_id / "logs.txt"
        assert file_path == expected_path
        assert file_path.parent.exists()

    def test_get_panel_file_invalid_panel(self, file_manager):
        """Test getting file path for invalid panel."""
        with pytest.raises(ValueError, match="Unknown panel: invalid"):
            file_manager.get_panel_file('invalid')

    def test_update_chat_file(self, file_manager):
        """Test updating chat history file."""
        session_id = "test_session"
        messages = [
            {
                'timestamp': '2024-01-01 12:00:00',
                'sender': 'User',
                'content': 'Hello, how are you?'
            },
            {
                'timestamp': '2024-01-01 12:00:05',
                'sender': 'Assistant',
                'content': 'I am doing well, thank you!'
            }
        ]
        
        file_manager.update_chat_file(session_id, messages)
        
        file_path = file_manager.get_panel_file('chat', session_id)
        assert file_path.exists()
        
        content = file_path.read_text(encoding='utf-8')
        assert '[2024-01-01 12:00:00] User: Hello, how are you?' in content
        assert '[2024-01-01 12:00:05] Assistant: I am doing well, thank you!' in content

    def test_update_logs_file(self, file_manager):
        """Test updating logs file."""
        session_id = "test_session"
        logs = [
            {
                'timestamp': '2024-01-01 12:00:00',
                'level': 'INFO',
                'message': 'Session started'
            },
            {
                'timestamp': '2024-01-01 12:00:05',
                'level': 'DEBUG',
                'message': 'Processing user input'
            }
        ]
        
        file_manager.update_logs_file(session_id, logs)
        
        file_path = file_manager.get_panel_file('logs', session_id)
        assert file_path.exists()
        
        content = file_path.read_text(encoding='utf-8')
        assert '2024-01-01 12:00:00 INFO Session started' in content
        assert '2024-01-01 12:00:05 DEBUG Processing user input' in content

    def test_update_sessions_file(self, file_manager, mock_session):
        """Test updating sessions list file."""
        sessions = [mock_session]
        
        file_manager.update_sessions_file(sessions)
        
        file_path = file_manager.get_panel_file('sessions')
        assert file_path.exists()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert len(data) == 1
        session_data = data[0]
        assert session_data['sid'] == 'test_session_123'
        assert session_data['task_description'] == 'Test task description'
        assert session_data['agent_state'] == 'running'
        assert session_data['created_at'] == '2024-01-01T12:00:00'
        assert session_data['last_activity'] == '2024-01-01T12:30:00'

    def test_get_file_content_existing_file(self, file_manager):
        """Test getting content of existing file."""
        session_id = "test_session"
        test_content = "Test chat content"
        
        # Create a test file
        file_path = file_manager.get_panel_file('chat', session_id)
        file_path.write_text(test_content, encoding='utf-8')
        
        content = file_manager.get_file_content('chat', session_id)
        assert content == test_content

    def test_get_file_content_nonexistent_file(self, file_manager):
        """Test getting content of non-existent file."""
        content = file_manager.get_file_content('chat', 'nonexistent_session')
        assert content == ""

    def test_cleanup_session_files(self, file_manager):
        """Test cleaning up session files."""
        session_id = "test_session"
        
        # Create some test files
        file_manager.update_chat_file(session_id, [{'timestamp': 'now', 'sender': 'test', 'content': 'test'}])
        file_manager.update_logs_file(session_id, [{'timestamp': 'now', 'level': 'INFO', 'message': 'test'}])
        
        session_dir = file_manager.sessions_dir / session_id
        assert session_dir.exists()
        
        file_manager.cleanup_session_files(session_id)
        assert not session_dir.exists()

    @patch('subprocess.run')
    def test_open_in_neovim_success(self, mock_run, file_manager):
        """Test opening file in neovim successfully."""
        file_path = file_manager.get_panel_file('sessions')
        
        file_manager.open_in_neovim(file_path)
        
        mock_run.assert_called_once_with(['nvim', str(file_path)], check=True)
        assert file_path.exists()  # File should be created if it doesn't exist

    @patch('subprocess.run')
    def test_open_in_neovim_file_not_found(self, mock_run, file_manager):
        """Test opening file in neovim when nvim is not found."""
        mock_run.side_effect = FileNotFoundError()
        file_path = file_manager.get_panel_file('sessions')
        
        # Should not raise exception, just log error
        file_manager.open_in_neovim(file_path)
        
        mock_run.assert_called_once()

    def test_update_chat_file_error_handling(self, file_manager):
        """Test error handling in update_chat_file."""
        # Test with invalid session_id that would cause path issues
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            # Should not raise exception, just log error
            file_manager.update_chat_file("test", [])

    def test_update_logs_file_error_handling(self, file_manager):
        """Test error handling in update_logs_file."""
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            # Should not raise exception, just log error
            file_manager.update_logs_file("test", [])

    def test_update_sessions_file_error_handling(self, file_manager):
        """Test error handling in update_sessions_file."""
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            # Should not raise exception, just log error
            file_manager.update_sessions_file([])

    def test_get_file_content_error_handling(self, file_manager):
        """Test error handling in get_file_content."""
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            content = file_manager.get_file_content('sessions')
            assert content == ""

    def test_cleanup_session_files_error_handling(self, file_manager):
        """Test error handling in cleanup_session_files."""
        with patch('shutil.rmtree', side_effect=PermissionError("Access denied")):
            # Should not raise exception, just log error
            file_manager.cleanup_session_files("test")