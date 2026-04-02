"""
Shell Tool — Execute shell commands and Python code.
"""
import subprocess
import os
from pathlib import Path
from typing import Optional

from backend.utils.logging import get_logger

logger = get_logger(__name__)


class ShellTool:
    """Tool for executing shell commands."""
    
    def execute(self, command: str, workdir: str = None) -> str:
        """Execute a shell command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=workdir
            )
            output = result.stdout + "\n" + result.stderr
            logger.debug(f"Shell command executed: {command}")
            return output.strip() if output.strip() else "[Success: No Output]"
        except subprocess.TimeoutExpired:
            logger.warning(f"Shell command timed out: {command}")
            return "[Error]: Command timed out"
        except Exception as e:
            logger.error(f"Shell command error: {e}")
            return f"[Error]: {str(e)}"


class PythonExecutor:
    """Tool for executing Python code."""
    
    def __init__(self, work_dir: str = None):
        self.work_dir = Path(work_dir) if work_dir else Path.cwd()
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def run(self, code: str, filename: str = "sandbox_exec.py") -> str:
        """Execute Python code in a sandbox file."""
        filepath = self.work_dir / filename
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)
            
            result = ShellTool().execute(f"python {filepath}", str(self.work_dir))
            logger.debug(f"Python code executed: {filename}")
            return result
        except Exception as e:
            logger.error(f"Python execution error: {e}")
            return f"[Error]: {str(e)}"
        finally:
            # Cleanup sandbox file
            try:
                if filepath.exists():
                    filepath.unlink()
            except Exception:
                pass
