#!/usr/bin/env python3
"""
VISHMUX Agent Tools – tool definitions and dispatcher for AI tool calls.
"""
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. If given a plain filename with no path separators, it looks in the workspace folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read. Plain names are resolved in the workspace."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content. Plain filenames go into the workspace folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write. Plain names go into the workspace."
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete text content to write to the file."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Append text to the end of an existing file (creates it if missing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to append to."
                    },
                    "content": {
                        "type": "string",
                        "description": "Text to append."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files and folders currently in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_project_folder",
            "description": "Create a project folder inside the workspace. Call this FIRST before writing any files for a multi-file project (website, app, script collection). Then write files using paths like \"<folder_name>/index.html\".",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Short descriptive folder name for the project, e.g. \"portfolio-site\""
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_to_project_folder",
            "description": "Move existing files that are loose in the workspace into a project folder. Useful for organizing files you already created outside a folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of filenames (or relative paths) to move"
                    },
                    "folder": {
                        "type": "string",
                        "description": "Destination folder name"
                    }
                },
                "required": ["files", "folder"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command and wait for it to finish, max 60 seconds, inside the workspace folder. For quick one-shot commands (installing a package, making a directory, running a build step). Do NOT use this for commands that run forever like starting a server — use run_background_command for those instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_background_command",
            "description": "Start a long-running command in the background (like a local web server) and return immediately without waiting. Output goes to a log file. Use for anything that doesn't exit on its own, e.g. python3 -m http.server 8000.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run in the background."
                    }
                },
                "required": ["command"]
            }
        }
    }
]


def _run_sync(command: str, cwd: Path, timeout: int = 60) -> str:
    """
    Run a command synchronously with a timeout.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""

        # Truncate outputs if too long
        truncated_stdout = (stdout[:3000] + "\n... [truncated]") if len(stdout) > 3000 else stdout
        truncated_stderr = (stderr[:1500] + "\n... [truncated]") if len(stderr) > 1500 else stderr

        if not stdout.strip() and not stderr.strip():
            return f"Command finished (exit code {result.returncode}), no output."

        lines = []
        if truncated_stdout:
            lines.append(f"stdout:\n{truncated_stdout}")
        if truncated_stderr:
            lines.append(f"stderr:\n{truncated_stderr}")
        lines.append(f"exit code: {result.returncode}")
        return "\n\n".join(lines)
    except subprocess.TimeoutExpired:
        return f"❌ Command timed out after {timeout} seconds. For long-running commands, use run_background_command instead."
    except Exception as e:
        return f"❌ {e}"


def _run_background(command: str, cwd: Path) -> str:
    """
    Start a command in the background, log output to a file.
    """
    try:
        log_dir = cwd / ".vishmux_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"bg_{int(time.time())}.log"
        fh = open(log_file, "w")
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=str(cwd),
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        fh.close()  # the child process owns its own duplicated fd now
        return (
            f"✅ Started background process (PID {proc.pid})\n"
            f"Command: {command}\n"
            f"Log file: {log_file}\n"
            f"The process will keep running after this chat continues. "
            f"To stop it manually: kill {proc.pid}"
        )
    except Exception as e:
        return f"❌ {e}"


async def execute_tool(name: str, arguments: dict, tool_manager, display) -> str:
    """
    Execute a single tool call and return a plain string result.
    This result is fed directly back to the AI as the tool's output.
    """
    try:
        if name == "read_file":
            return tool_manager.files.read_file(arguments.get("path", ""))
        elif name == "write_file":
            return tool_manager.files.create_file(
                arguments.get("path", ""),
                arguments.get("content", "")
            )
        elif name == "append_file":
            return tool_manager.files.append_to_file(
                arguments.get("path", ""),
                arguments.get("content", "")
            )
        elif name == "list_files":
            return tool_manager.files.list_workspace()
        elif name == "create_project_folder":
            return tool_manager.files.create_folder(arguments.get("name", ""))
        elif name == "move_to_project_folder":
            return tool_manager.files.move_to_folder(
                arguments.get("files", []),
                arguments.get("folder", "")
            )
        elif name in ("run_command", "run_background_command"):
            command = arguments.get("command", "").strip()
            if not command:
                return "❌ No command provided."
            # Show confirmation UI
            action_type = "one‑shot command" if name == "run_command" else "background command"
            description = f"Run {action_type}:\n  {command}"
            if not display.confirm_action(description):
                return "User declined to run this command."
            cwd = tool_manager.files.get_workspace_path()
            if name == "run_command":
                return _run_sync(command, cwd)
            else:
                return _run_background(command, cwd)
        else:
            return f"❌ Unknown tool: {name}"
    except Exception as e:
        return f"❌ Tool execution failed: {e}"
