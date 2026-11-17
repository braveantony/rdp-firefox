"""Workspace mode: the parts that need no X server.

The desktop shows four tools. Two of them (VSCodium, JupyterLab) run in other
containers of the pod and are started by asking their launcher over a unix
socket; the other two (tkadm, Firefox) are Firefox instances started here.
"""
import os
import re
import socket
from dataclasses import dataclass

THEMES = ("light", "dark")


@dataclass(frozen=True)
class Tool:
    id: str
    label: str
    icon: str            # image file (relative to this directory); empty = drawn by the desktop
    classes: tuple       # WM_CLASS names of its windows, lower case
    card: bool = True    # shown as a card on the home screen
    socket: str = ""     # launcher socket, for tools in other containers

    def owns(self, wm_class):
        return (wm_class or "").lower() in self.classes


TOOLS = (
    Tool("tkadm", "tkadm", "", ("tkadm",)),
    Tool("vscode", "VSCodium", "icons/vscodium.png", ("vscodium", "codium", "com.visualstudio.codeoss"),
         socket=os.environ.get("VSCODE_SOCKET", "/run/rdp-workspace/vscode.sock")),
    Tool("jupyter", "JupyterLab", "icons/jupyterlab.svg", ("jupyterlab-desktop", "jupyterlab"),
         socket=os.environ.get("JUPYTER_SOCKET", "/run/rdp-workspace/jupyter.sock")),
    Tool("firefox", "Firefox", "/usr/share/icons/hicolor/128x128/apps/firefox.png", ("firefox", "firefox-default", "navigator"), card=False),
)


def owner(wm_class):
    """The tool a window belongs to, or None."""
    return next((t for t in TOOLS if t.owns(wm_class)), None)


def tool(tool_id):
    return next(t for t in TOOLS if t.id == tool_id)


def display_name(display):
    """":10.0" -> ":10". The launchers accept a local display without a screen."""
    m = re.fullmatch(r":(\d{1,4})(\.\d+)?", display or "")
    if not m:
        raise ValueError(f"not a local X display: {display!r}")
    return f":{m.group(1)}"


def request(path, display, timeout=5.0):
    """Ask a launcher to start its program on `display`. Returns (ok, reason)."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(path)
            s.sendall(f"{display}\n".encode())
            reply = s.makefile().readline().strip()
    except OSError as e:
        return False, str(e) or e.__class__.__name__
    if reply == "OK":
        return True, ""
    if reply.startswith("ERR"):
        return False, reply[3:].strip() or "refused"
    return False, f"unexpected reply: {reply!r}" if reply else "no reply"


def state(t, classes, active, starting, failed):
    """One of closed / starting / failed / open / active.

    classes: WM_CLASS of every open window; active: WM_CLASS of the focused one.
    A window of the tool wins over an earlier "starting" or "failed" mark.
    """
    if any(t.owns(c) for c in classes):
        return "active" if t.owns(active) else "open"
    if starting:
        return "starting"
    if failed:
        return "failed"
    return "closed"


def load_theme(path):
    try:
        with open(path) as f:
            value = f.read().strip()
    except OSError:
        return "light"
    return value if value in THEMES else "light"


def save_theme(path, theme):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(theme + "\n")


def other_theme(theme):
    return "dark" if theme == "light" else "light"


def strut(screen_width, height):
    """_NET_WM_STRUT_PARTIAL value that keeps `height` px free at the bottom."""
    return f"0, 0, 0, {height}, 0, 0, 0, 0, 0, 0, 0, {screen_width - 1}"
