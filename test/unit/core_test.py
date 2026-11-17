"""Tests for /opt/desktop/workspace/core.py (run inside the image)."""
import os
import socket
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, "/opt/desktop/workspace")
import core  # noqa: E402


def serve_once(path, reply, got):
    """A stand-in for the launcher of an attached container."""
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    srv.listen(1)

    def run():
        conn, _ = srv.accept()
        got.append(conn.makefile().readline())
        if reply is not None:
            conn.sendall(reply.encode())
        conn.close()
        srv.close()

    threading.Thread(target=run, daemon=True).start()


class DisplayTest(unittest.TestCase):
    def test_screen_suffix_is_dropped(self):
        # sesman sets DISPLAY=:10.0; the launcher only accepts ":10"
        self.assertEqual(core.display_name(":10.0"), ":10")

    def test_plain_display_is_kept(self):
        self.assertEqual(core.display_name(":11"), ":11")

    def test_remote_or_empty_display_is_refused(self):
        for bad in ("", "host:10", ":x", None):
            with self.assertRaises(ValueError):
                core.display_name(bad)


class RequestTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.sock = os.path.join(self.dir.name, "app.sock")

    def tearDown(self):
        self.dir.cleanup()

    def test_ok_reply(self):
        got = []
        serve_once(self.sock, "OK\n", got)
        self.assertEqual(core.request(self.sock, ":10"), (True, ""))
        self.assertEqual(got, [":10\n"])

    def test_err_reply_carries_the_reason(self):
        serve_once(self.sock, "ERR alice has no access to display :10\n", [])
        self.assertEqual(core.request(self.sock, ":10"),
                         (False, "alice has no access to display :10"))

    def test_missing_socket_is_a_failure_not_an_exception(self):
        ok, why = core.request(self.sock, ":10")
        self.assertFalse(ok)
        self.assertTrue(why)

    def test_silent_server_times_out(self):
        serve_once(self.sock, None, [])
        ok, why = core.request(self.sock, ":10", timeout=0.5)
        self.assertFalse(ok)
        self.assertTrue(why)


class ToolsTest(unittest.TestCase):
    def test_four_tools_in_toolbar_order(self):
        self.assertEqual([t.id for t in core.TOOLS], ["tkadm", "vscode", "jupyter", "firefox"])

    def test_three_cards_on_the_home_screen(self):
        self.assertEqual([t.id for t in core.TOOLS if t.card], ["tkadm", "vscode", "jupyter"])

    def test_window_class_matching_ignores_case(self):
        vscode = core.tool("vscode")
        self.assertTrue(vscode.owns("VSCodium"))
        self.assertTrue(vscode.owns("vscodium"))
        self.assertFalse(vscode.owns("firefox"))

    def test_vscodium_reports_its_upstream_class(self):
        # VSCodium 1.x windows carry the Code OSS application id as WM_CLASS
        self.assertEqual(core.owner("com.visualstudio.CodeOSS").id, "vscode")

    def test_windows_of_no_tool(self):
        self.assertIsNone(core.owner("Workspace-home"))
        self.assertIsNone(core.owner(None))

    def test_tkadm_and_firefox_windows_are_told_apart(self):
        self.assertTrue(core.tool("tkadm").owns("Tkadm"))
        self.assertFalse(core.tool("tkadm").owns("firefox"))
        self.assertFalse(core.tool("firefox").owns("Tkadm"))


class StateTest(unittest.TestCase):
    def state(self, **kw):
        args = dict(classes=[], active=None, starting=False, failed=False)
        args.update(kw)
        return core.state(core.tool("jupyter"), **args)

    def test_closed(self):
        self.assertEqual(self.state(classes=["firefox"]), "closed")

    def test_open(self):
        self.assertEqual(self.state(classes=["jupyterlab-desktop"], active="firefox"), "open")

    def test_active(self):
        self.assertEqual(self.state(classes=["jupyterlab-desktop"], active="jupyterlab-desktop"), "active")

    def test_starting_until_its_window_shows(self):
        self.assertEqual(self.state(starting=True), "starting")
        self.assertEqual(self.state(starting=True, classes=["jupyterlab-desktop"]), "open")

    def test_failed_until_it_runs(self):
        self.assertEqual(self.state(failed=True), "failed")
        self.assertEqual(self.state(failed=True, classes=["jupyterlab-desktop"]), "open")


class ThemeTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = os.path.join(self.dir.name, "sub", "theme")

    def tearDown(self):
        self.dir.cleanup()

    def test_light_by_default(self):
        self.assertEqual(core.load_theme(self.file), "light")

    def test_saved_choice_is_read_back(self):
        core.save_theme(self.file, "dark")
        self.assertEqual(core.load_theme(self.file), "dark")

    def test_garbage_falls_back_to_light(self):
        os.makedirs(os.path.dirname(self.file))
        with open(self.file, "w") as f:
            f.write("purple\n")
        self.assertEqual(core.load_theme(self.file), "light")

    def test_toggle(self):
        self.assertEqual(core.other_theme("light"), "dark")
        self.assertEqual(core.other_theme("dark"), "light")


class StrutTest(unittest.TestCase):
    def test_reserves_the_bottom_edge_across_the_screen(self):
        # left right top bottom, then start/end pairs for each edge
        self.assertEqual(core.strut(1280, 64), "0, 0, 0, 64, 0, 0, 0, 0, 0, 0, 0, 1279")


if __name__ == "__main__":
    unittest.main()
