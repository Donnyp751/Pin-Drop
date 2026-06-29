"""Tests for the eeschema cross-probe helper (stdlib sockets only)."""

import os
import socket
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pin_drop.plugin import crossprobe


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


if __name__ == "__main__":
    unittest.main()
