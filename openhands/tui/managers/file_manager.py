"""File Manager.

Manages file-based panel content for Ctrl+E functionality in the TUI.
"""

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openhands.core.logger import openhands_logger as logger

if TYPE_CHECKING:
    from .session_manager import SessionContext


class TUIPanelFileManager:
    """Manages file-based panel content for Ctrl+E functionality."""
    
    def __init__(self, base_dir: str = "~/.openhands/tui"):
        """Initialize the file manager.
        
        Args:
            base_dir: Base directory for TUI files
        """
        self.base_dir = Path(base_dir).expanduser()
        self.sessions_dir = self.base_dir / "sessions"
        
        # Ensure directories exist
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
    
    def get_panel_file(self, panel: str, session_id: str = "") -> Path:
        """Get file path for panel content.
        
        Args:
            panel: Panel name ('sessions', 'chat', 'logs')
            session_id: Session ID (required for chat and logs panels)
            
        Returns:
            Path to the panel file
        """
        panel_files = {
            'sessions': self.sessions_dir / "session_list.json",
            'chat': self.sessions_dir / session_id / "chat_history.txt",
            'logs': self.sessions_dir / session_id / "logs.txt",
        }
        
        if panel not in panel_files:
            raise ValueError(f"Unknown panel: {panel}")
        
        file_path = panel_files[panel]
        
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        return file_path
    
    def update_chat_file(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        """Update chat history file.
        
        Args:
            session_id: Session ID
            messages: List of chat messages
        """
        try:
            file_path = self.get_panel_file('chat', session_id)
            
            # Format messages as readable text
            content_lines = []
            for msg in messages:
                timestamp = msg.get('timestamp', '')
                sender = msg.get('sender', 'Unknown')
                content = msg.get('content', '')
                
                content_lines.append(f"[{timestamp}] {sender}: {content}")
                content_lines.append("")  # Empty line for readability
            
            content = "\n".join(content_lines)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.debug(f"Updated chat file for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to update chat file for session {session_id}: {e}")
    
    def update_logs_file(self, session_id: str, logs: list[dict[str, Any]]) -> None:
        """Update logs file.
        
        Args:
            session_id: Session ID
            logs: List of log entries
        """
        try:
            file_path = self.get_panel_file('logs', session_id)
            
            # Format logs as readable text
            content_lines = []
            for log in logs:
                timestamp = log.get('timestamp', '')
                level = log.get('level', 'INFO')
                message = log.get('message', '')
                
                content_lines.append(f"{timestamp} {level} {message}")
            
            content = "\n".join(content_lines)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.debug(f"Updated logs file for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to update logs file for session {session_id}: {e}")
    
    def update_sessions_file(self, sessions: list["SessionContext"]) -> None:
        """Update sessions list file.
        
        Args:
            sessions: List of session contexts
        """
        try:
            file_path = self.get_panel_file('sessions')
            
            # Convert sessions to JSON-serializable format
            sessions_data = []
            for session in sessions:
                session_data = {
                    'sid': session.sid,
                    'task_description': session.task_description,
                    'agent_state': session.agent_state.value if session.agent_state else 'unknown',
                    'created_at': session.created_at.isoformat(),
                    'last_activity': session.last_activity.isoformat(),
                }
                sessions_data.append(session_data)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(sessions_data, f, indent=2)
            
            logger.debug(f"Updated sessions file with {len(sessions)} sessions")
            
        except Exception as e:
            logger.error(f"Failed to update sessions file: {e}")
    
    def open_in_neovim(self, file_path: Path) -> None:
        """Open file in neovim.
        
        Args:
            file_path: Path to the file to open
        """
        try:
            # Ensure file exists
            if not file_path.exists():
                file_path.touch()
            
            logger.info(f"Opening file in neovim: {file_path}")
            
            # Open in neovim
            subprocess.run(['nvim', str(file_path)], check=True)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to open file in neovim: {e}")
        except FileNotFoundError:
            logger.error("neovim not found. Please install neovim to use Ctrl+E functionality.")
        except Exception as e:
            logger.error(f"Unexpected error opening file in neovim: {e}")
    
    def cleanup_session_files(self, session_id: str) -> None:
        """Clean up files for a closed session.
        
        Args:
            session_id: Session ID to clean up
        """
        try:
            session_dir = self.sessions_dir / session_id
            if session_dir.exists():
                # Remove session directory and all its contents
                import shutil
                shutil.rmtree(session_dir)
                logger.debug(f"Cleaned up files for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to cleanup files for session {session_id}: {e}")
    
    def get_file_content(self, panel: str, session_id: str = "") -> str:
        """Get content of a panel file.
        
        Args:
            panel: Panel name
            session_id: Session ID (if required)
            
        Returns:
            File content as string
        """
        try:
            file_path = self.get_panel_file(panel, session_id)
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return ""
        except Exception as e:
            logger.error(f"Failed to read file content for panel {panel}: {e}")
            return ""