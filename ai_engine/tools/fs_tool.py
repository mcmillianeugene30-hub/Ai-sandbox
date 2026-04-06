import os

class FileSystemTool:
    def __init__(self, base_path=None):
        if base_path is None:
            # Default to projects folder in the container root
            base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "projects")
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def mkdir(self, path: str):
        full_path = os.path.join(self.base_path, path)
        os.makedirs(full_path, exist_ok=True)
        return f"Directory created: {path}"

    def write_file(self, path: str, content: str):
        full_path = os.path.join(self.base_path, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return f"File written: {path}"

    def list_dir(self, path: str = "."):
        full_path = os.path.join(self.base_path, path)
        if not os.path.exists(full_path):
            return f"Path does not exist: {path}"
        return os.listdir(full_path)

    def delete(self, path: str):
        full_path = os.path.join(self.base_path, path)
        if os.path.isfile(full_path):
            os.remove(full_path)
            return f"File deleted: {path}"
        elif os.path.isdir(full_path):
            import shutil
            shutil.rmtree(full_path)
            return f"Directory deleted: {path}"
        return f"Path does not exist: {path}"

fs_tool = FileSystemTool()
