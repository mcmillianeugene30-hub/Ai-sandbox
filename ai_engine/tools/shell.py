import subprocess
import os

class ShellTool:
    def execute(self, command: str, workdir: str = None) -> str:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30, cwd=workdir
            )
            output = result.stdout + "\n" + result.stderr
            return output.strip() if output.strip() else "[Success: No Output]"
        except Exception as e:
            return f"[Error]: {str(e)}"

class PythonExecutor:
    def run(self, code: str, filename: str = "sandbox_exec.py") -> str:
        with open(filename, "w") as f:
            f.write(code)
        
        return ShellTool().execute(f"python {filename}")
