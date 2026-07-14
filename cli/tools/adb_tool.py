#!/usr/bin/env python3
"""
VISHMUX ADBTool – control an Android device via ADB (Android Debug Bridge).
Requires 'adb' binary available on PATH (auto‑installed on Termux).
All methods return a plain string result, never raise.
"""
import os
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

def _is_termux() -> bool:
    return "com.termux" in os.environ.get("PREFIX", "") or Path("/data/data/com.termux").exists()

def ensure_adb_available() -> tuple:
    """Returns (available: bool, message: str). Auto‑installs android-tools on Termux if missing."""
    if shutil.which("adb"):
        return True, "adb is available."
    if _is_termux():
        try:
            print("[adb_tool] adb not found — installing android-tools (one‑time)...")
            result = subprocess.run(
                ["pkg", "install", "-y", "android-tools"],
                timeout=180, capture_output=True, text=True
            )
            if shutil.which("adb"):
                return True, "android-tools installed successfully."
            return False, f"Auto‑install failed: {result.stderr[-500:] if result.stderr else 'unknown error'}"
        except Exception as e:
            return False, f"Auto‑install failed: {e}"
    else:
        return False, (
            "adb not found. Install Android platform‑tools for your OS "
            "(e.g. `sudo apt install android-tools-adb` on Linux, "
            "`brew install android-platform-tools` on macOS, "
            "or download platform‑tools from developer.android.com on Windows), "
            "then restart VISHMUX."
        )

class ADBTool:
    def __init__(self, config):
        self.config = config
        # Reuse workspace resolution logic from FileTool
        from .file_tool import FileTool
        ft = FileTool(config)
        self.workspace = ft.get_workspace_path()

    def is_connected(self) -> bool:
        """Returns True if at least one device is in 'device' state."""
        ok, _ = ensure_adb_available()
        if not ok:
            return False
        try:
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
            for line in res.stdout.splitlines()[1:]:
                if line.strip().endswith("\tdevice"):
                    return True
            return False
        except Exception:
            return False

    def _connection_error(self) -> str:
        return (
            "❌ No Android device connected via ADB.\n"
            "1. Enable Developer Options on your phone (Settings → About → tap Build Number 7 times).\n"
            "2. Enable Wireless Debugging (Settings → Developer Options).\n"
            "3. Tap 'Pair device with pairing code' and note the IP, port, and pairing code.\n"
            "4. In Termux, run: adb pair <ip>:<port>   (enter pairing code when prompted)\n"
            "5. Then run: adb connect <ip>:<port>\n"
            "After that, VISHMUX should be able to control your phone."
        )

    def _run(self, cmd: list, timeout: int = 15) -> str:
        """Helper: run an adb command and return stripped stdout, or an error string."""
        ok, msg = ensure_adb_available()
        if not ok:
            return msg
        if not self.is_connected():
            return self._connection_error()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            if stderr and not stdout:
                return f"❌ {stderr}"
            return stdout
        except subprocess.TimeoutExpired:
            return "❌ adb command timed out."
        except Exception as e:
            return f"❌ adb error: {e}"

    def tap(self, x: int, y: int) -> str:
        return self._run(["adb", "shell", "input", "tap", str(x), str(y)])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> str:
        return self._run(["adb", "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)])

    def type_text(self, text: str) -> str:
        # Escape spaces and special characters for shell
        escaped = text.replace(" ", "%s").replace("'", "\\'")
        return self._run(["adb", "shell", "input", "text", escaped])

    def press_key(self, keycode: str) -> str:
        return self._run(["adb", "shell", "input", "keyevent", keycode])

    def open_app(self, package: str) -> str:
        return self._run(["adb", "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"])

    def open_url(self, url: str) -> str:
        return self._run(["adb", "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url])

    def list_apps(self, query: str = "") -> str:
        cmd = ["adb", "shell", "pm", "list", "packages"]
        if query:
            cmd.extend(["-f", query])
        else:
            cmd.append("-f")
        out = self._run(cmd)
        if out.startswith("❌"):
            return out
        lines = out.splitlines()
        packages = []
        for line in lines:
            # format: package:com.example.app
            parts = line.strip().split("=")
            if len(parts) == 2:
                packages.append(parts[1])
        if not packages:
            return "No matching apps found."
        return "\n".join(packages[:50])  # cap

    def current_app(self) -> str:
        out = self._run(["adb", "shell", "dumpsys", "window"])
        if out.startswith("❌"):
            return out
        for line in out.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                return line.strip()
        return "Could not determine current app."

    def get_battery(self) -> str:
        out = self._run(["adb", "shell", "dumpsys", "battery"])
        if out.startswith("❌"):
            return out
        level = ""
        status = ""
        for line in out.splitlines():
            if line.startswith("  level:"):
                level = line.split(":")[1].strip()
            elif line.startswith("  status:"):
                status = line.split(":")[1].strip()
        if level:
            return f"Battery {level}% (status: {status})"
        return "Battery info not available."

    def screenshot(self) -> str:
        timestamp = int(time.time())
        remote_path = "/sdcard/vishmux_shot.png"
        local_dir = self.workspace / "adb_screenshots"
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / f"shot_{timestamp}.png"
        try:
            self._run(["adb", "shell", "screencap", "-p", remote_path])
            self._run(["adb", "pull", remote_path, str(local_path)])
            self._run(["adb", "shell", "rm", remote_path])
            if local_path.exists():
                return f"✅ Screenshot saved to {local_path}"
            return "❌ Screenshot pull failed."
        except Exception as e:
            return f"❌ Screenshot error: {e}"

    def dump_ui(self) -> str:
        remote_xml = "/sdcard/window_dump.xml"
        local_tmp = self.workspace / "adb_screenshots" / "ui_dump.xml"
        local_tmp.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._run(["adb", "shell", "uiautomator", "dump", remote_xml])
            self._run(["adb", "pull", remote_xml, str(local_tmp)])
            self._run(["adb", "shell", "rm", remote_xml])
            if not local_tmp.exists():
                return "❌ UI dump file not found."
            tree = ET.parse(local_tmp)
            root = tree.getroot()
            elements = []
            for node in root.iter("node"):
                text = node.get("text", "").strip()
                resource_id = node.get("resource-id", "")
                class_name = node.get("class", "")
                bounds = node.get("bounds", "")
                clickable = node.get("clickable", "false")
                if text or clickable == "true":
                    elements.append({
                        "text": text[:60],
                        "resource_id": resource_id.split("/")[-1] if "/" in resource_id else resource_id,
                        "class": class_name,
                        "bounds": bounds,
                        "clickable": clickable,
                    })
            # Cap to 40 elements, prioritizing clickable + text-bearing
            sorted_els = sorted(elements, key=lambda e: (e["clickable"] == "true", bool(e["text"])), reverse=True)[:40]
            lines = []
            for el in sorted_els:
                lines.append(
                    f"{el['text'] or '(no text)'} [{el['resource_id']}] {el['bounds']} "
                    f"{'clickable' if el['clickable']=='true' else ''}"
                )
            return "\n".join(lines) if lines else "No interactive elements found."
        except Exception as e:
            return f"❌ UI dump error: {e}"
