"""
FileSystemTool — File system operations for agents.
"""
import os
import shutil
from pathlib import Path
from typing import Optional, List

from backend.utils.logging import get_logger

logger = get_logger(__name__)

# Default base path from environment or project root
DEFAULT_BASE_PATH = Path(__file__).parent.parent.parent.resolve() / "projects"


class FileSystemTool:
    """Tool for filesystem operations with configurable base path."""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path) if base_path else DEFAULT_BASE_PATH
        self.base_path.mkdir(parents=True, exist_ok=True)

    def mkdir(self, path: str) -> str:
        """Create a directory."""
        full_path = self.base_path / path
        full_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory created: {path}")
        return f"Directory created: {path}"

    def write_file(self, path: str, content: str) -> str:
        """Write content to a file."""
        full_path = self.base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.debug(f"File written: {path}")
        return f"File written: {path}"

    def read_file(self, path: str) -> str:
        """Read content from a file."""
        full_path = self.base_path / path
        
        if not full_path.exists():
            return f"File not found: {path}"
        
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def list_dir(self, path: str = ".") -> List[str]:
        """List directory contents."""
        full_path = self.base_path / path
        
        if not full_path.exists():
            return f"Path does not exist: {path}"
        
        return os.listdir(full_path)

    def delete(self, path: str) -> str:
        """Delete a file or directory."""
        full_path = self.base_path / path
        
        if full_path.is_file():
            full_path.unlink()
            logger.debug(f"File deleted: {path}")
            return f"File deleted: {path}"
        elif full_path.is_dir():
            shutil.rmtree(full_path)
            logger.debug(f"Directory deleted: {path}")
            return f"Directory deleted: {path}"
        
        return f"Path does not exist: {path}"

    def exists(self, path: str) -> bool:
        """Check if a path exists."""
        full_path = self.base_path / path
        return full_path.exists()


# Global fs_tool instance
fs_tool = FileSystemTool()
