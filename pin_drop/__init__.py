"""pin_drop: generate KiCad bed-of-nails test fixtures from a DUT board.

The package is usable two ways:

* As a KiCad **action plugin** (runs inside pcbnew, see ``pin_drop.plugin``).
* As plain Python modules for the pieces that do not need KiCad
  (``sexpr``, ``nail_library``, ``fixture_model``, ``reconcile`` and the
  generators), which keeps them unit-testable without launching KiCad.

Only the standard library is imported at module load time so the package can be
dropped into KiCad's bundled interpreter without any ``pip install`` step.
"""

__version__ = "0.1.0"
