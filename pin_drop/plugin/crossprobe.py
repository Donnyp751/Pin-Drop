"""Best-effort pcbnew -> eeschema cross-probe over KiCad's legacy socket.

KiCad's schematic editor runs a small TCP command server -- the same one the
built-in cross-probe uses.  Sending it ``$PART: "<refdes>"`` makes eeschema
select and centre that symbol; ``$NET: "<name>"`` highlights a whole net.  So
when a probe is picked in Pin Drop we can also surface it in the schematic,
which is handy for confirming *what* a candidate actually is.

This is purely best-effort and uses only the standard library:

* It talks to ``127.0.0.1`` on KiCad's fixed cross-probe service ports
  (eeschema listens on 4243, pcbnew on 4242).
* The transport is a short-lived TCP connection -- connect, write the command,
  close -- matching KiCad's own ``wxSocketClient`` sender.
* If eeschema isn't running (or isn't listening), the send fails silently and
  the board-side focus still works.

The server is only present when a schematic editor is open; opening the DUT via
the KiCad project manager (so the matching ``.kicad_sch`` is loaded) is the
reliable case.
"""

from __future__ import annotations

import socket

HOST = "127.0.0.1"
EESCHEMA_PORT = 4243   # KICAD_SCH_PORT_SERVICE_NUMBER
PCBNEW_PORT = 4242     # KICAD_PCB_PORT_SERVICE_NUMBER
_TIMEOUT = 0.25        # keep the UI snappy if nothing is listening


def _send(port: int, command: str) -> bool:
    """Send one cross-probe command; return True if it was delivered."""
    try:
        with socket.create_connection((HOST, port), timeout=_TIMEOUT) as sock:
            sock.sendall(command.encode("utf-8"))
        return True
    except OSError:
        return False


def select_in_schematic(refdes: str) -> bool:
    """Select and centre the symbol with this reference designator in eeschema."""
    if not refdes:
        return False
    return _send(EESCHEMA_PORT, '$PART: "{}"'.format(refdes))


def highlight_net_in_schematic(net: str) -> bool:
    """Highlight every pin on ``net`` in the open schematic."""
    if not net:
        return False
    return _send(EESCHEMA_PORT, '$NET: "{}"'.format(net))


def clear_schematic_selection() -> bool:
    """Clear any cross-probe selection/highlight in the schematic."""
    return _send(EESCHEMA_PORT, "$CLEAR:")
