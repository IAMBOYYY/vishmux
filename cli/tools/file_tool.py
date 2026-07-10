#!/usr/bin/env python3
"""
VISHMUX FileTool – manage files in the workspace directory.
"""

import shutil
from pathlib import Path
from typing import Optional


class FileTool:
    """Handles reading, writing, and listing files in the VISHMUX workspace."""

    def __init__(self, config):
        self.config = config
        self.workspace_dir = Path(config.data.get("workspace_dir", "~/vishmux-workspace")).expanduser()
        # Ensure workspace exists on first use
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def get_workspace_path(self) -> Path:
        """Return the expanded workspace path."""
        return self.workspace_dir

    def create_file(self, filename: str, content: str) -> str:
        """Save a file to the workspace."""
        try:
            file_path = self._resolve_path(filename)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"✅ Created: {file_path}"
        except Exception as e:
            return f"❌ Failed to create file: {e}"

    def read_file(self, path: str) -> str:
        """Read a file from disk, looking in workspace if path is relative."""
        try:
            file_path = self._resolve_path(path)
            if not file_path.exists():
                return f"❌ File not found: {path}"
            content = file_path.read_text(encoding="utf-8")
            max_chars = 10000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n... [truncated]"
            return content
        except Exception as e:
            return f"❌ Failed to read file: {e}"

    def append_to_file(self, filename: str, content: str) -> str:
        """Append text to a file in the workspace."""
        try:
            file_path = self._resolve_path(filename)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(content)
            return f"✅ Appended to: {file_path}"
        except Exception as e:
            return f"❌ Failed to append: {e}"

    def list_workspace(self) -> str:
        """List all files recursively in the workspace."""
        try:
            if not self.workspace_dir.exists():
                self.workspace_dir.mkdir(parents=True, exist_ok=True)
            items = sorted(self.workspace_dir.rglob("*"))
            if not items:
                return "📁 Workspace is empty."
            lines = [f"📁 Workspace: {self.workspace_dir}\n"]
            for item in items:
                rel = item.relative_to(self.workspace_dir)
                prefix = "📄 " if item.is_file() else "📁 "
                lines.append(f"{prefix}{rel}")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Failed to list workspace: {e}"

    def create_folder(self, name: str) -> str:
        """Create a folder in the workspace."""
        try:
            folder_path = self._resolve_path(name)
            folder_path.mkdir(parents=True, exist_ok=True)
            return f"✅ Created folder: {folder_path}"
        except Exception as e:
            return f"❌ Failed to create folder: {e}"

    def move_to_folder(self, files: list, folder: str) -> str:
        """Move existing workspace files into a project folder."""
        if not files:
            return "Nothing to move."
        try:
            dest_dir = self._resolve_path(folder)
            dest_dir.mkdir(parents=True, exist_ok=True)

            moved = []
            failed = []
            for f in files:
                src = self._resolve_path(f)
                if not src.exists():
                    failed.append(f"{f} (not found)")
                    continue
                try:
                    shutil.move(str(src), str(dest_dir / src.name))
                    moved.append(str(dest_dir / src.name))
                except Exception as e:
                    failed.append(f"{f} ({e})")

            msg = ""
            if moved:
                msg += f"Moved {len(moved)} file(s) to {dest_dir}:\n" + "\n".join(f"  {m}" for m in moved)
            if failed:
                msg += "\nFailed:\n" + "\n".join(f"  {f}" for f in failed)
            return msg.strip()
        except Exception as e:
            return f"❌ Failed to move files: {e}"

    def _resolve_path(self, path: str) -> Path:
        """Resolve a user-supplied path. If it's a simple filename, put it in workspace."""
        p = Path(path).expanduser()
        if p.parts and p.parts[0] in ("~", "/", "C:\\"):
            # Absolute path
            return p
        if p.parent == Path("."):
            # Plain filename, use workspace
            return self.workspace_dir / p.name
        # Relative path with subdirs, still treat as relative to cwd but maybe workspace?
        # For safety, resolve relative to workspace if not absolute
        return self.workspace_dir / p
