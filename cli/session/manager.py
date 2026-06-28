#!/usr/bin/env python3
"""
VISHMUX SessionManager – session lifecycle, file tracking, skills.
"""

import os
import json
import uuid
import shutil
import re as regex
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx


class SessionManager:
    """Manages a single VISHMUX session from start to exit."""

    def __init__(self, config):
        self.config = config
        self.session_id = str(uuid.uuid4())[:8]
        self.start_time = datetime.now()

        # Expand user paths
        self.workspace = Path(config.data["workspace_dir"]).expanduser()
        self.sessions_dir = Path(config.data["sessions_dir"]).expanduser()
        self.skills_dir = Path(config.data["skills_dir"]).expanduser()

        # Session‑specific temp folder
        self.session_temp_dir = self.workspace / f"temp_session_{self.session_id}"

        # Summary file path
        timestamp = self.start_time.strftime("%Y-%m-%d_%Hh%M")
        self.summary_file = (
            self.sessions_dir / "summaries" / f"{timestamp}_{self.session_id}.txt"
        )

        # Runtime tracking
        self.actions: list[str] = []
        self.files_created: list[Path] = []
        self.current_project: Optional[str] = None
        self.loaded_skills: list[str] = []

    def initialize(self) -> None:
        """Create all required directories."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        (self.sessions_dir / "summaries").mkdir(parents=True, exist_ok=True)
        (self.sessions_dir / "saved").mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.session_temp_dir.mkdir(parents=True, exist_ok=True)

    def get_last_session_summary(self) -> Optional[str]:
        """Return contents of the most recent summary file, if any."""
        summaries_dir = self.sessions_dir / "summaries"
        if not summaries_dir.exists():
            return None
        txt_files = sorted(summaries_dir.glob("*.txt"), reverse=True)
        if not txt_files:
            return None
        return txt_files[0].read_text(encoding="utf-8")

    def log_action(self, action: str) -> None:
        """Record an action and write it to the summary file."""
        self.actions.append(action)

        # Ensure directory exists
        self.summary_file.parent.mkdir(parents=True, exist_ok=True)

        if not self.summary_file.exists():
            header = (
                f"SESSION: {self.session_id}\n"
                f"STARTED: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{'='*40}\n"
            )
            self.summary_file.write_text(header, encoding="utf-8")

        timestamp = datetime.now().strftime("%H:%M")
        with open(self.summary_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {action}\n")

    def log_file_created(self, path: Path) -> None:
        """Log a file creation event."""
        self.files_created.append(path)
        self.log_action(f"Created file: {path}")

    def get_temp_file_count(self) -> int:
        """Count files recursively in the temp session directory."""
        if not self.session_temp_dir.exists():
            return 0
        return len(list(self.session_temp_dir.rglob("*")))

    def exit_simple(self) -> None:
        """Clean exit — delete temp files and write final summary."""
        self.log_action("SESSION ENDED (clean exit)")
        if self.session_temp_dir.exists():
            shutil.rmtree(self.session_temp_dir)

    def exit_save(self, project_name: str) -> Path:
        """Save exit — move temp folder to saved/ under project name."""
        self.log_action(f"SESSION SAVED as: {project_name}")
        saved_dir = self.sessions_dir / "saved"
        saved_dir.mkdir(parents=True, exist_ok=True)
        saved_path = saved_dir / project_name
        if self.session_temp_dir.exists():
            if saved_path.exists():
                shutil.rmtree(saved_path)
            shutil.move(str(self.session_temp_dir), str(saved_path))
            return saved_path
        return saved_path

    def load_skills(self) -> list[str]:
        """Scan skills_dir for *.skill.json files and load names."""
        self.loaded_skills = []
        if self.skills_dir.exists():
            for skill_file in self.skills_dir.glob("*.skill.json"):
                try:
                    data = json.loads(skill_file.read_text(encoding="utf-8"))
                    name = data.get("name", skill_file.stem.replace(".skill", ""))
                    self.loaded_skills.append(name)
                except (json.JSONDecodeError, Exception):
                    pass
        return self.loaded_skills

    def download_skill(self, url: str) -> dict:
        """Download a skill JSON file from URL and save it locally."""
        try:
            response = httpx.get(url, timeout=15.0)
            response.raise_for_status()
            skill_data = response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"Failed to download skill: HTTP {e.response.status_code}")
        except Exception as e:
            raise Exception(f"Failed to download skill: {e}")

        if "name" not in skill_data:
            raise ValueError("Invalid skill file: missing 'name' field")

        skill_name = skill_data["name"].lower().replace(" ", "-")
        skill_name = regex.sub(r'[^\w\-]', '', skill_name)
        skill_path = self.skills_dir / f"{skill_name}.skill.json"

        with open(skill_path, "w", encoding="utf-8") as f:
            json.dump(skill_data, f, indent=2)

        if skill_data["name"] not in self.loaded_skills:
            self.loaded_skills.append(skill_data["name"])

        return skill_data

    def get_session_context(self) -> str:
        """Build a concise context string for the AI."""
        lines = [
            f"Session ID: {self.session_id}",
            f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M')}",
            f"Workspace: {self.workspace}",
            f"Temp folder: {self.session_temp_dir}",
        ]
        if self.current_project:
            lines.append(f"Current project: {self.current_project}")
        if self.loaded_skills:
            lines.append(f"Loaded skills: {', '.join(self.loaded_skills)}")
        if self.actions:
            lines.append(f"Actions this session: {len(self.actions)}")
            lines.append("Recent actions:")
            for a in self.actions[-5:]:
                lines.append(f"  - {a}")
        return "\n".join(lines)
