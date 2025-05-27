"""File Operations.

File I/O operations and utilities for the TUI system.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Any, Union

from openhands.core.logger import openhands_logger as logger


class FileOperations:
    """File I/O operations and utilities."""

    @staticmethod
    def ensure_directory(path: Union[Path, str]) -> Path:
        """Ensure a directory exists, creating it if necessary.

        Args:
            path: Directory path to ensure

        Returns:
            Path object for the directory
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def read_text_file(file_path: Union[Path, str], encoding: str = "utf-8") -> str:
        """Read text from a file.

        Args:
            file_path: Path to the file
            encoding: File encoding

        Returns:
            File content as string
        """
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"File not found: {file_path}")
            return ""
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return ""

    @staticmethod
    def write_text_file(
        file_path: Union[Path, str], content: str, encoding: str = "utf-8"
    ) -> bool:
        """Write text to a file.

        Args:
            file_path: Path to the file
            content: Content to write
            encoding: File encoding

        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            FileOperations.ensure_directory(file_path.parent)

            with open(file_path, "w", encoding=encoding) as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            return False

    @staticmethod
    def read_json_file(file_path: Union[Path, str]) -> Any:
        """Read JSON data from a file.

        Args:
            file_path: Path to the JSON file

        Returns:
            Parsed JSON data or None if error
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"JSON file not found: {file_path}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in file {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading JSON file {file_path}: {e}")
            return None

    @staticmethod
    def write_json_file(
        file_path: Union[Path, str], data: Any, indent: int = 2
    ) -> bool:
        """Write JSON data to a file.

        Args:
            file_path: Path to the JSON file
            data: Data to write as JSON
            indent: JSON indentation

        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            FileOperations.ensure_directory(file_path.parent)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error writing JSON file {file_path}: {e}")
            return False

    @staticmethod
    def append_to_file(
        file_path: Union[Path, str], content: str, encoding: str = "utf-8"
    ) -> bool:
        """Append content to a file.

        Args:
            file_path: Path to the file
            content: Content to append
            encoding: File encoding

        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            FileOperations.ensure_directory(file_path.parent)

            with open(file_path, "a", encoding=encoding) as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error appending to file {file_path}: {e}")
            return False

    @staticmethod
    def copy_file(src: Union[Path, str], dst: Union[Path, str]) -> bool:
        """Copy a file.

        Args:
            src: Source file path
            dst: Destination file path

        Returns:
            True if successful, False otherwise
        """
        try:
            dst_path = Path(dst)
            FileOperations.ensure_directory(dst_path.parent)

            shutil.copy2(src, dst)
            return True
        except Exception as e:
            logger.error(f"Error copying file {src} to {dst}: {e}")
            return False

    @staticmethod
    def move_file(src: Union[Path, str], dst: Union[Path, str]) -> bool:
        """Move a file.

        Args:
            src: Source file path
            dst: Destination file path

        Returns:
            True if successful, False otherwise
        """
        try:
            dst_path = Path(dst)
            FileOperations.ensure_directory(dst_path.parent)

            shutil.move(src, dst)
            return True
        except Exception as e:
            logger.error(f"Error moving file {src} to {dst}: {e}")
            return False

    @staticmethod
    def delete_file(file_path: Union[Path, str]) -> bool:
        """Delete a file.

        Args:
            file_path: Path to the file to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            os.remove(file_path)
            return True
        except FileNotFoundError:
            logger.warning(f"File not found for deletion: {file_path}")
            return True  # Consider it successful if file doesn't exist
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False

    @staticmethod
    def delete_directory(dir_path: Union[Path, str], recursive: bool = False) -> bool:
        """Delete a directory.

        Args:
            dir_path: Path to the directory to delete
            recursive: If True, delete recursively

        Returns:
            True if successful, False otherwise
        """
        try:
            if recursive:
                shutil.rmtree(dir_path)
            else:
                os.rmdir(dir_path)
            return True
        except FileNotFoundError:
            logger.warning(f"Directory not found for deletion: {dir_path}")
            return True  # Consider it successful if directory doesn't exist
        except Exception as e:
            logger.error(f"Error deleting directory {dir_path}: {e}")
            return False

    @staticmethod
    def get_file_size(file_path: Union[Path, str]) -> int:
        """Get file size in bytes.

        Args:
            file_path: Path to the file

        Returns:
            File size in bytes, or 0 if error
        """
        try:
            return os.path.getsize(file_path)
        except Exception as e:
            logger.error(f"Error getting file size for {file_path}: {e}")
            return 0

    @staticmethod
    def file_exists(file_path: Union[Path, str]) -> bool:
        """Check if a file exists.

        Args:
            file_path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        return Path(file_path).exists()

    @staticmethod
    def is_directory(path: Union[Path, str]) -> bool:
        """Check if a path is a directory.

        Args:
            path: Path to check

        Returns:
            True if path is a directory, False otherwise
        """
        return Path(path).is_dir()

    @staticmethod
    def list_files(directory: Union[Path, str], pattern: str = "*") -> list[Path]:
        """List files in a directory.

        Args:
            directory: Directory to list
            pattern: File pattern to match

        Returns:
            List of file paths
        """
        try:
            dir_path = Path(directory)
            if not dir_path.exists():
                return []

            return list(dir_path.glob(pattern))
        except Exception as e:
            logger.error(f"Error listing files in {directory}: {e}")
            return []

    @staticmethod
    def create_backup(file_path: Union[Path, str], backup_suffix: str = ".bak") -> bool:
        """Create a backup of a file.

        Args:
            file_path: Path to the file to backup
            backup_suffix: Suffix for backup file

        Returns:
            True if successful, False otherwise
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning(f"Cannot backup non-existent file: {file_path}")
            return False

        backup_path = file_path.with_suffix(file_path.suffix + backup_suffix)
        return FileOperations.copy_file(file_path, backup_path)

    @staticmethod
    def get_temp_file(prefix: str = "openhands_tui_", suffix: str = ".tmp") -> Path:
        """Get a temporary file path.

        Args:
            prefix: Filename prefix
            suffix: Filename suffix

        Returns:
            Path to temporary file
        """
        import tempfile

        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
        os.close(fd)  # Close the file descriptor
        return Path(path)
