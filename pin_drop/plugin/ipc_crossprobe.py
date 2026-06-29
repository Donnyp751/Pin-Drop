"""Cross-probe to eeschema via KiCad's IPC API (``kicad-python`` / ``kipy``).

When the schematic and board are open together in the KiCad project manager they
share one process and cross-probe over *in-process* KIWAY mail, which the SWIG
``pcbnew`` API does not expose.  The supported way to reach that machinery is the
IPC API: if we *select* the footprint on the board through the API, KiCad runs
its own selection tool and cross-probes to the schematic for us -- so the
matching symbol gets selected in eeschema.

Two things make this fiddly, both handled here:

* **Threading.**  The action plugin runs on KiCad's GUI thread, but the IPC
  server is *serviced* on that same thread.  A synchronous API call from an
  event handler would deadlock (we'd block the very loop that must answer us).
  So all IPC work happens on a single background worker thread; the GUI thread
  only ever enqueues a reference designator.
* **Optional dependency.**  ``kipy`` is not part of the stdlib and may not be
  installed, and the API server may be disabled.  Everything here is best-effort:
  if anything is missing or fails, cross-probe silently does nothing and the
  board-side focus still works.

Requires: ``pip install --user kicad-python`` for KiCad's interpreter, and
Preferences -> Plugins -> "Enable KiCad API server" (then restart KiCad).
"""

from __future__ import annotations

import glob
import os
import queue
import threading

_lock = threading.Lock()
_worker = None          # type: ignore[var-annotated]
_unavailable = False    # remember a failed import so we don't retry every click
_expected_board = None  # basename of this instance's .kicad_pcb, for socket matching


def configure(board_filename: str) -> None:
    """Tell the cross-probe which board it belongs to.

    With several KiCad instances open, each runs its own API server on a
    separate socket (the lock holder on the bare ``api.sock``, the rest on
    ``api-<pid>.sock``).  We use this board filename to pick -- and verify -- the
    socket that belongs to *this* instance, so cross-probe never lands in another
    open project.  Call once with ``pcbnew.GetBoard().GetFileName()``.
    """
    global _expected_board
    _expected_board = os.path.basename(board_filename) if board_filename else None


def available() -> bool:
    """True if the IPC client library can be imported."""
    global _unavailable
    if _unavailable:
        return False
    if _import_kipy():
        return True
    _unavailable = True
    return False


def _import_kipy() -> bool:
    try:
        import kipy  # noqa: F401
        return True
    except Exception:
        pass
    # KiCad's embedded interpreter may have the user site disabled; the library
    # is typically installed there (pip install --user), so add it and retry.
    try:
        import site
        import sys
        usp = site.getusersitepackages()
        if usp and usp not in sys.path:
            sys.path.append(usp)
        import kipy  # noqa: F401
        return True
    except Exception:
        return False


def select_part(refdes: str) -> None:
    """Asynchronously select the footprint ``refdes`` on the board.

    Selecting it through the API makes KiCad cross-probe to the open schematic.
    Returns immediately; the work runs on the background IPC thread.
    """
    if not refdes:
        return
    w = _get_worker()
    if w is not None:
        w.submit(refdes)


def _candidate_sockets():
    """API socket addresses to try, most-likely-ours first.

    KiCad names each instance's socket after its process id, except the lock
    holder which uses the bare ``api.sock``.  This plugin runs *inside* a KiCad
    process, so our own pid points straight at our socket; the bare socket and
    any others follow as fallbacks (each verified by board name in ``_connect``).
    """
    env = os.environ.get("KICAD_API_SOCKET")
    if env:  # KiCad told us exactly which socket to use -- trust it.
        return [env if env.startswith("ipc://") else "ipc://" + env]

    try:
        from kipy.kicad import _default_socket_path
        default = _default_socket_path()
    except Exception:
        return []
    bare_fs = default[len("ipc://"):] if default.startswith("ipc://") else default
    directory = os.path.dirname(bare_fs)

    out = []

    def add(fs_path):
        if os.path.exists(fs_path):
            addr = "ipc://" + fs_path
            if addr not in out:
                out.append(addr)

    add(os.path.join(directory, "api-{}.sock".format(os.getpid())))
    add(bare_fs)
    for s in sorted(glob.glob(os.path.join(directory, "api*.sock"))):
        add(s)
    return out


def _get_worker():
    global _worker
    with _lock:
        if _worker is None:
            if not available():
                return None
            _worker = _Worker()
            _worker.start()
        return _worker


class _Worker(threading.Thread):
    """Owns the kipy client and applies selections off the GUI thread."""

    def __init__(self):
        super().__init__(daemon=True, name="pin_drop-ipc")
        self._q: "queue.Queue[str]" = queue.Queue()
        self._kicad = None
        self._board = None
        self._by_ref = {}

    def submit(self, refdes: str) -> None:
        self._q.put(refdes)

    def run(self) -> None:
        while True:
            refdes = self._q.get()
            # Coalesce a burst of clicks down to the most recent request.
            try:
                while True:
                    refdes = self._q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._select(refdes)
            except Exception:
                # Drop the cached connection so the next request reconnects.
                self._kicad = None
                self._board = None
                self._by_ref = {}

    def _connect(self) -> None:
        if self._kicad is not None and self._board is not None:
            return
        import kipy
        last_err = None
        for addr in _candidate_sockets():
            try:
                kc = kipy.KiCad(socket_path=addr)
                board = kc.get_board()
            except Exception as e:  # wrong/dead socket -- try the next one
                last_err = e
                continue
            if _expected_board:
                name = ""
                try:
                    name = os.path.basename(board.name or "")
                except Exception:
                    name = ""
                if name and name != _expected_board:
                    continue  # a different instance's board; keep looking
            self._kicad = kc
            self._board = board
            self._by_ref = {}
            return
        raise RuntimeError("no matching KiCad API socket") from last_err

    def _lookup(self, refdes: str):
        if refdes in self._by_ref:
            return self._by_ref[refdes]
        # (Re)build the reference -> footprint map from the live board.
        mapping = {}
        for fp in self._board.get_footprints():
            try:
                ref = fp.reference_field.text.value
            except Exception:
                continue
            if ref:
                mapping[ref] = fp
        self._by_ref = mapping
        return self._by_ref.get(refdes)

    def _select(self, refdes: str) -> None:
        self._connect()
        fp = self._lookup(refdes)
        self._board.clear_selection()
        if fp is not None:
            self._board.add_to_selection([fp])
