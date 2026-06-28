#!/usr/bin/env python3
"""
VISHMUX ExitHandler – clean exit, save exit, and exit menus.
"""

import re as regex
from .manager import SessionManager
from ..ui.display import Display


class ExitHandler:
    """Handles all exit flows for VISHMUX sessions."""

    def __init__(self, session: SessionManager, display: Display):
        self.session = session
        self.display = display

    def handle_exit(self, command: str) -> bool:
        """
        Process an exit command.
        Returns True if session should end, False if user cancelled.
        """
        command = command.strip().lower()

        if command == "exit /s":
            return self._do_simple_exit()

        elif command == "exit /ss":
            return self._do_save_exit()

        elif command in ("exit", "quit", "q"):
            choice = self.display.show_exit_menu()
            if choice == "1":
                return self._do_simple_exit()
            elif choice == "2":
                return self._do_save_exit()
            else:
                self.display.show_info("Cancelled. Continuing session.")
                return False

        return False

    def _do_simple_exit(self) -> bool:
        """Perform a clean exit, deleting all temp files."""
        file_count = self.session.get_temp_file_count()
        if file_count > 0:
            self.display.show_info(
                f"Deleting {file_count} temp files from this session..."
            )
        self.session.exit_simple()
        self.display.show_success("Session ended. Temp files cleaned up.")
        self.display.show_info("Goodbye! Run 'vishmux' to start a new session.")
        return True

    def _do_save_exit(self) -> bool:
        """Perform a save exit, preserving files under a project name."""
        print()
        project_name = input(
            "Save as project name (or press Enter to use session ID): "
        ).strip()
        if not project_name:
            project_name = f"session_{self.session.session_id}"

        # Sanitize: replace spaces with dashes, remove special chars
        project_name = regex.sub(r'[^\w\-]', '', project_name.replace(' ', '-'))

        saved_path = self.session.exit_save(project_name)
        self.display.show_success(f"Session saved as '{project_name}'")
        self.display.show_info(f"Files at: {saved_path}")
        self.display.show_info("Goodbye! Run 'vishmux' to start a new session.")
        return True
