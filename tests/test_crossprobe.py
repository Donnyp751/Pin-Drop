"""Tests for the eeschema cross-probe helper (stdlib sockets only)."""

import os
import socket
import sys
import threading
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pin_drop.plugin import crossprobe
from pin_drop.plugin import ipc_crossprobe


class _Listener:
    """A throwaway TCP server that records one received message."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((crossprobe.HOST, 0))   # ephemeral port
        self.port = self.sock.getsockname()[1]
        self.sock.listen(1)
        self.received = None
        self._t = threading.Thread(target=self._serve, daemon=True)
        self._t.start()

    def _serve(self):
        conn, _ = self.sock.accept()
        self.received = conn.recv(256)
        conn.close()

    def close(self):
        self._t.join(timeout=2)
        self.sock.close()


class TestCrossProbe(unittest.TestCase):
    def test_select_wire_format(self):
        srv = _Listener()
        try:
            ok = crossprobe._send(srv.port, '$PART: "TP25"')
        finally:
            srv.close()
        self.assertTrue(ok)
        self.assertEqual(srv.received, b'$PART: "TP25"')

    def test_select_in_schematic_builds_part_command(self):
        srv = _Listener()
        sent = {}
        orig = crossprobe._send
        crossprobe._send = lambda port, cmd: sent.update(port=port, cmd=cmd) or True
        try:
            crossprobe.select_in_schematic("J5")
        finally:
            crossprobe._send = orig
            srv.close()
        self.assertEqual(sent["cmd"], '$PART: "J5"')
        self.assertEqual(sent["port"], crossprobe.EESCHEMA_PORT)

    def test_empty_refdes_is_noop(self):
        self.assertFalse(crossprobe.select_in_schematic(""))
        self.assertFalse(crossprobe.highlight_net_in_schematic(""))

    def test_no_listener_fails_silently(self):
        # Grab an ephemeral port then close it, so the connect is refused.
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((crossprobe.HOST, 0))
        port = s.getsockname()[1]
        s.close()
        self.assertFalse(crossprobe._send(port, "$CLEAR:"))


class TestIpcSocketResolution(unittest.TestCase):
    """The multi-instance socket picker (which KiCad am I talking to?)."""

    def test_env_var_wins(self):
        with mock.patch.dict(os.environ, {"KICAD_API_SOCKET": "ipc:///x/y.sock"}):
            self.assertEqual(ipc_crossprobe._candidate_sockets(), ["ipc:///x/y.sock"])

    def test_env_var_gets_ipc_prefix(self):
        with mock.patch.dict(os.environ, {"KICAD_API_SOCKET": "/x/y.sock"}):
            self.assertEqual(ipc_crossprobe._candidate_sockets(), ["ipc:///x/y.sock"])

    def _patched_candidates(self, existing, pid=4242):
        """Run _candidate_sockets with a faked socket dir and pid."""
        fake = types.ModuleType("kipy.kicad")
        fake._default_socket_path = lambda: "ipc:///tmp/kicad/api.sock"
        env = {k: v for k, v in os.environ.items() if k != "KICAD_API_SOCKET"}
        with mock.patch.dict(sys.modules, {"kipy.kicad": fake}), \
                mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(ipc_crossprobe.os, "getpid", return_value=pid), \
                mock.patch.object(ipc_crossprobe.os.path, "exists",
                                  side_effect=lambda p: p in existing), \
                mock.patch.object(ipc_crossprobe.glob, "glob",
                                  return_value=sorted(existing)):
            return ipc_crossprobe._candidate_sockets()

    def test_our_pid_socket_is_tried_first(self):
        existing = {"/tmp/kicad/api.sock", "/tmp/kicad/api-4242.sock",
                    "/tmp/kicad/api-9999.sock"}
        got = self._patched_candidates(existing, pid=4242)
        self.assertEqual(got[0], "ipc:///tmp/kicad/api-4242.sock")
        self.assertIn("ipc:///tmp/kicad/api.sock", got)
        # every existing socket appears exactly once
        self.assertEqual(len(got), len(set(got)))
        self.assertEqual(len(got), 3)

    def test_falls_back_to_bare_socket(self):
        # Lock-holder instance: no api-<pid>.sock, only the bare one.
        got = self._patched_candidates({"/tmp/kicad/api.sock"}, pid=4242)
        self.assertEqual(got, ["ipc:///tmp/kicad/api.sock"])


if __name__ == "__main__":
    unittest.main()
