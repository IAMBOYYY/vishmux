#!/usr/bin/env python3
"""
VISHMUX FileTool – manage files in the workspace directory.
"""

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