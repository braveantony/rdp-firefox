#!/usr/bin/python3
"""Workspace mode desktop: the home screen (three cards) and the toolbar.

  workspace.py            run the desktop (started by session.sh)
  workspace.py windows    print "name<TAB>active|-<TAB>WxH<TAB>class" for every window;
                          name is the tool's id, or the window class for other windows

Clicking a tool switches to its window, or starts it when it has none.
"""
import os
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
gi.require_version("Wnck", "3.0")
from gi.repository import Gdk, GdkPixbuf, GdkX11, Gio, GLib, Gtk, Wnck  # noqa: E402,F401

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BAR_HEIGHT = 64
CARD_ICON = 128
ITEM_ICON = 24
START_TIMEOUT = 180   # seconds a tool may take to show its window
TKADM_URL = os.environ.get("TKADM_URL", "http://localhost:2210")

# Light first; .dark overrides. One spacing unit (8px), one radius, one accent.
CSS = b"""
window.ws { background-color: #f4f4f1; color: #1f2328; font-family: "DejaVu Sans"; }
window.ws.dark { background-color: #1e1f22; color: #e8e8e6; }
window.ws.bar { background-color: #ffffff; border-top: 1px solid #d9d9d3; }
window.ws.bar.dark { background-color: #2a2c30; border-top-color: #3c3f45; }

.ws button { background-image: none; box-shadow: none; text-shadow: none; -gtk-icon-shadow: none;
  color: inherit; padding: 0; outline-color: #1f5fbf; outline-width: 2px; outline-offset: 4px; }
.dark button { outline-color: #7fb0ff; }

button.card { background-color: #ffffff; border: 1px solid #d9d9d3; border-radius: 12px;
  font-size: 32px; font-weight: bold; }
button.card:hover { border-color: #1f5fbf; box-shadow: inset 0 0 0 1px #1f5fbf; }
button.card:active { background-color: #e6edf9; }
button.card.starting { color: #5f6670; }
button.card.starting image { opacity: 0.35; }
button.card.failed { border-color: #1f2328; box-shadow: inset 0 0 0 1px #1f2328; }
.dark button.card { background-color: #2a2c30; border-color: #3c3f45; }
.dark button.card:hover { border-color: #7fb0ff; box-shadow: inset 0 0 0 1px #7fb0ff; }
.dark button.card:active { background-color: #363b45; }
.dark button.card.starting { color: #a0a6ad; }
.dark button.card.failed { border-color: #e8e8e6; box-shadow: inset 0 0 0 1px #e8e8e6; }

.badge { background-color: #1f2328; color: #ffffff; border-radius: 16px;
  min-width: 32px; min-height: 32px; font-size: 20px; font-weight: bold; }
.dark .badge { background-color: #e8e8e6; color: #1e1f22; }

progressbar trough { min-height: 4px; min-width: 128px; border: none; border-radius: 2px; background-color: #d9d9d3; }
progressbar progress { min-height: 4px; border: none; border-radius: 2px; background-color: #1f5fbf; }
.dark progressbar trough { background-color: #3c3f45; }
.dark progressbar progress { background-color: #7fb0ff; }

button.item { background-color: transparent; border: none; border-radius: 12px; font-size: 16px; }
button.item:hover { background-color: #f4f4f1; }
button.item.open, button.item.active { color: #1f5fbf; }
button.item.active, button.item.failed { font-weight: bold; }
button.item.starting { color: #5f6670; }
.dark button.item:hover { background-color: #363b45; }
.dark button.item.open, .dark button.item.active { color: #7fb0ff; }
.dark button.item.starting { color: #a0a6ad; }

button.toggle { background-color: transparent; border: 1px solid #d9d9d3; border-radius: 12px; font-size: 20px; }
button.toggle:hover { border-color: #1f5fbf; }
.dark button.toggle { border-color: #3c3f45; }
.dark button.toggle:hover { border-color: #7fb0ff; }
"""

TKADM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96" fill="none">
<rect x="4" y="4" width="88" height="88" rx="20" fill="{fg}"/>
<path d="M28 36l16 12-16 12" stroke="{bg}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M52 62h18" stroke="{bg}" stroke-width="7" stroke-linecap="round"/></svg>"""
STATES = ("closed", "starting", "failed", "open", "active")


def window_class(win):
    return win.get_class_group_name() or win.get_class_instance_name() or ""


def wnck_screen():
    screen = Wnck.Screen.get_default()
    screen.force_update()
    return screen


def list_windows():
    screen = wnck_screen()
    active = screen.get_active_window()
    for win in screen.get_windows():
        _, _, w, h = win.get_client_window_geometry()
        mark = "active" if active is not None and win.get_xid() == active.get_xid() else "-"
        cls = window_class(win)
        t = core.owner(cls)
        print(f"{t.id if t else cls.lower()}\t{mark}\t{w}x{h}\t{cls}")


class Desktop:
    def __init__(self):
        self.session = os.environ.get("WORKSPACE_SESSION_DIR") or GLib.get_user_runtime_dir()
        self.display = core.display_name(os.environ.get("DISPLAY"))
        self.theme_file = os.path.join(GLib.get_user_config_dir(), "rdp-workspace", "theme")
        self.theme = core.load_theme(self.theme_file)
        self.starting = {}     # tool id -> GLib timeout source
        self.failed = set()
        self.cards = {}        # tool id -> widgets of its card
        self.items = {}        # tool id -> widgets of its toolbar item
        self.toggles = []

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        self.gdk_screen = Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(
            self.gdk_screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.home = self.build_home()
        self.bar = self.build_bar()
        self.apply_theme()
        self.layout()
        self.home.show_all()

        self.gdk_screen.connect("size-changed", lambda *_: self.layout())
        self.wnck = wnck_screen()
        for signal in ("window-opened", "window-closed", "active-window-changed"):
            self.wnck.connect(signal, lambda *_: self.refresh())
        self.refresh()

    # ---- widgets -------------------------------------------------------

    def window(self, name, hint):
        win = Gtk.Window()
        win.set_wmclass(name, name.capitalize())
        win.set_title(name)
        win.set_type_hint(hint)
        win.set_decorated(False)
        win.set_skip_taskbar_hint(True)
        win.get_style_context().add_class("ws")
        win.connect("delete-event", lambda *_: True)
        return win

    def icon(self, t, size):
        if not t.icon:
            dark = self.theme == "dark"
            svg = TKADM_SVG.format(fg="#e8e8e6" if dark else "#1f2328", bg="#2a2c30" if dark else "#ffffff")
            stream = Gio.MemoryInputStream.new_from_data(svg.encode())
            return GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream, size, size, True, None)
        return GdkPixbuf.Pixbuf.new_from_file_at_size(os.path.join(HERE, t.icon), size, size)

    def toggle_button(self):
        button = Gtk.Button()
        button.get_style_context().add_class("toggle")
        button.set_size_request(48, 48)
        button.get_accessible().set_name("切換深色與淺色")
        button.connect("clicked", lambda *_: self.toggle_theme())
        self.toggles.append(button)
        return button

    def build_home(self):
        win = self.window("workspace-home", Gdk.WindowTypeHint.DESKTOP)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=32)
        row.set_halign(Gtk.Align.CENTER)
        row.set_valign(Gtk.Align.CENTER)
        for t in core.TOOLS:
            if not t.card:
                continue
            image = Gtk.Image()
            label = Gtk.Label(label=t.label)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=40)
            box.set_valign(Gtk.Align.CENTER)
            box.pack_start(image, False, False, 0)
            box.pack_start(label, False, False, 0)
            progress = Gtk.ProgressBar()
            progress.set_halign(Gtk.Align.CENTER)
            progress.set_valign(Gtk.Align.END)
            progress.set_margin_bottom(24)
            progress.set_no_show_all(True)
            badge = Gtk.Label(label="!")
            badge.get_style_context().add_class("badge")
            badge.set_halign(Gtk.Align.END)
            badge.set_valign(Gtk.Align.START)
            badge.set_margin_top(16)
            badge.set_margin_end(16)
            badge.set_no_show_all(True)
            overlay = Gtk.Overlay()
            overlay.add(box)
            overlay.add_overlay(progress)
            overlay.add_overlay(badge)
            button = Gtk.Button()
            button.add(overlay)
            button.set_size_request(320, 320)
            button.get_style_context().add_class("card")
            button.connect("clicked", lambda _b, tool=t: self.activate(tool))
            row.pack_start(button, False, False, 0)
            self.cards[t.id] = dict(button=button, image=image, progress=progress, badge=badge, size=CARD_ICON)
        toggle = self.toggle_button()
        toggle.set_halign(Gtk.Align.END)
        toggle.set_valign(Gtk.Align.START)
        toggle.set_margin_top(24)
        toggle.set_margin_end(24)
        overlay = Gtk.Overlay()
        overlay.add(row)
        overlay.add_overlay(toggle)
        win.add(overlay)
        return win

    def build_bar(self):
        win = self.window("workspace-bar", Gdk.WindowTypeHint.DOCK)
        win.get_style_context().add_class("bar")
        win.set_keep_above(True)
        win.set_accept_focus(False)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_margin_start(16)
        row.set_margin_end(16)
        row.set_valign(Gtk.Align.CENTER)
        for t in core.TOOLS:
            image = Gtk.Image()
            label = Gtk.Label(label=t.label)
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_halign(Gtk.Align.CENTER)
            box.pack_start(image, False, False, 0)
            box.pack_start(label, False, False, 0)
            button = Gtk.Button()
            button.add(box)
            # Same width for every item, so a bold label never moves its neighbours
            button.set_size_request(168, 48)
            button.get_style_context().add_class("item")
            button.connect("clicked", lambda _b, tool=t: self.activate(tool))
            row.pack_start(button, False, False, 0)
            self.items[t.id] = dict(button=button, image=image, label=label, size=ITEM_ICON)
        row.pack_end(self.toggle_button(), False, False, 0)
        win.add(row)
        win.connect("realize", lambda *_: self.reserve())
        return win

    # ---- layout and theme ----------------------------------------------

    def screen_size(self):
        display = Gdk.Display.get_default()
        area = (display.get_primary_monitor() or display.get_monitor(0)).get_geometry()
        return area.width, area.height

    def layout(self):
        width, height = self.screen_size()
        self.home.move(0, 0)
        self.home.resize(width, height)
        self.bar.set_size_request(width, BAR_HEIGHT)
        self.bar.resize(width, BAR_HEIGHT)
        self.bar.move(0, height - BAR_HEIGHT)
        self.reserve()

    def reserve(self):
        """Tell the window manager to keep maximized windows above the toolbar."""
        gdk_window = self.bar.get_window()
        if gdk_window is None:
            return
        value = core.strut(self.screen_size()[0], BAR_HEIGHT)
        for prop, cells in (("_NET_WM_STRUT_PARTIAL", value), ("_NET_WM_STRUT", ", ".join(value.split(", ")[:4]))):
            subprocess.run(["xprop", "-id", str(gdk_window.get_xid()), "-f", prop, "32c", "-set", prop, cells],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def apply_theme(self):
        dark = self.theme == "dark"
        for win in (self.home, self.bar):
            context = win.get_style_context()
            (context.add_class if dark else context.remove_class)("dark")
        for button in self.toggles:
            button.set_label("☀" if dark else "☾")   # sun / moon
        for group in (self.cards, self.items):
            for tool_id, widgets in group.items():
                widgets["image"].set_from_pixbuf(self.icon(core.tool(tool_id), widgets["size"]))

    def toggle_theme(self):
        self.theme = core.other_theme(self.theme)
        try:
            core.save_theme(self.theme_file, self.theme)
        except OSError as e:
            print(f"[workspace] cannot save the theme: {e}", file=sys.stderr, flush=True)
        self.apply_theme()

    # ---- tools ---------------------------------------------------------

    def tool_windows(self, t):
        return [w for w in self.wnck.get_windows() if t.owns(window_class(w))]

    def refresh(self):
        classes = [window_class(w) for w in self.wnck.get_windows()]
        active_window = self.wnck.get_active_window()
        active = window_class(active_window) if active_window is not None else None
        busy = False
        for t in core.TOOLS:
            s = core.state(t, classes, active, t.id in self.starting, t.id in self.failed)
            if s in ("open", "active"):
                self.settle(t)
            busy = busy or s != "closed"
            for group in (self.cards, self.items):
                widgets = group.get(t.id)
                if widgets is None:
                    continue
                context = widgets["button"].get_style_context()
                for name in STATES:
                    (context.add_class if name == s else context.remove_class)(name)
                if "label" in widgets:
                    widgets["label"].set_text(t.label + {"starting": "…", "failed": " !"}.get(s, ""))
                if "progress" in widgets:
                    widgets["progress"].set_visible(s == "starting")
                    widgets["badge"].set_visible(s == "failed")
        if busy and not self.bar.get_visible():
            self.bar.show_all()
            self.layout()
        elif not busy and self.bar.get_visible():
            self.bar.hide()

    def settle(self, t):
        source = self.starting.pop(t.id, None)
        if source:
            GLib.source_remove(source)
        self.failed.discard(t.id)

    def fail(self, t, why):
        print(f"[workspace] {t.id}: {why}", file=sys.stderr, flush=True)
        self.settle(t)
        self.failed.add(t.id)
        self.refresh()

    def pulse(self):
        for tool_id in self.starting:
            card = self.cards.get(tool_id)
            if card:
                card["progress"].pulse()
        return bool(self.starting)

    def activate(self, t):
        windows = self.tool_windows(t)
        if windows:
            windows[-1].activate(Gtk.get_current_event_time())
            return
        if t.id in self.starting:
            return
        self.failed.discard(t.id)
        if not self.starting:
            GLib.timeout_add(150, self.pulse)
        self.starting[t.id] = GLib.timeout_add_seconds(
            START_TIMEOUT, lambda: self.fail(t, f"no window after {START_TIMEOUT}s") or False)
        self.refresh()
        threading.Thread(target=self.launch, args=(t,), daemon=True).start()

    def launch(self, t):
        """Runs off the main loop: a launcher that does not answer must not freeze the desktop."""
        if t.socket:
            ok, why = core.request(t.socket, self.display)
        else:
            ok, why = self.start_firefox(t)
        if not ok:
            GLib.idle_add(lambda: self.fail(t, why) or False)

    def start_firefox(self, t):
        # tkadm and Firefox are separate instances with their own window class,
        # so the toolbar can tell them apart; profiles are per session
        profile = os.path.join(self.session, f"firefox-{t.id}")
        command = ["firefox", "--new-instance", "--profile", profile]
        if t.id == "tkadm":
            command += ["--class", "Tkadm", "--name", "Tkadm", TKADM_URL]
        else:
            command += ["about:blank"]
        try:
            os.makedirs(profile, mode=0o700, exist_ok=True)
            subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as e:
            return False, str(e)
        return True, ""


def main():
    if sys.argv[1:] == ["windows"]:
        Gtk.init([])
        list_windows()
        return
    Gtk.init([])
    Desktop()
    Gtk.main()


if __name__ == "__main__":
    main()
