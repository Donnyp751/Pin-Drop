"""A tiny S-expression emitter for KiCad ``.kicad_mod`` / ``.kicad_sym`` files.

KiCad's board/footprint/symbol files are S-expressions based on the Specctra DSN
format.  We only ever *write* them here, so this module is deliberately small: it
turns nested Python data into the same indentation style KiCad itself produces.

Node model
----------
* ``Sym("foo")``      -> a bare token       ``foo``
* ``"foo bar"``       -> a quoted string    ``"foo bar"``
* ``int`` / ``float`` -> a number           ``1``, ``10.16``
* ``bool``            -> ``yes`` / ``no``   (KiCad's boolean spelling)
* ``[head, *rest]``   -> a list             ``(head rest...)``  where ``head`` is
  conventionally a ``Sym``.

A list is rendered on one line when it is short and contains no child lists,
otherwise each child list is placed on its own indented line -- matching KiCad's
own formatter closely enough that diffs stay readable.
"""

from __future__ import annotations

from typing import Iterable


class Sym:
    """A bare (unquoted) S-expression token, e.g. ``footprint`` or ``thru_hole``."""

    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Sym({self.name!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Sym) and other.name == self.name

    def __hash__(self) -> int:
        return hash(self.name)


def fmt_num(value: float) -> str:
    """Format a number the way KiCad does: fixed point, trailing zeros stripped."""
    if isinstance(value, bool):  # bool is an int subclass; handle before int
        raise TypeError("bool should be rendered as a Sym yes/no, not a number")
    if isinstance(value, int):
        return str(value)
    # 6 decimal places is KiCad's working precision for mm.
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    if text in ("", "-0"):
        text = "0"
    return text


def _quote(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    # KiCad escapes newlines/tabs within quoted strings.
    escaped = escaped.replace("\n", "\\n").replace("\t", "\\t")
    return f'"{escaped}"'


def _atom(node) -> str:
    if isinstance(node, Sym):
        return node.name
    if isinstance(node, bool):
        return "yes" if node else "no"
    if isinstance(node, (int, float)):
        return fmt_num(node)
    if isinstance(node, str):
        return _quote(node)
    raise TypeError(f"cannot render atom of type {type(node).__name__}: {node!r}")


def _is_list(node) -> bool:
    return isinstance(node, (list, tuple))


def _has_child_list(node: Iterable) -> bool:
    return any(_is_list(child) for child in node)


def dumps(node, indent: int = 0, indent_str: str = "\t") -> str:
    """Render ``node`` to a string."""
    if not _is_list(node):
        return _atom(node)

    if not node:
        return "()"

    pad = indent_str * indent
    head = _atom(node[0]) if not _is_list(node[0]) else dumps(node[0], indent)
    rest = node[1:]

    # Inline short, flat lists (no nested lists) for compactness.
    if not _has_child_list(node):
        inline = " ".join(_atom(child) for child in rest)
        return f"({head} {inline})".rstrip() if rest else f"({head})"

    # Leading scalar atoms ride on the head line, e.g. (pad "1" thru_hole circle ...
    lead = []
    i = 0
    while i < len(rest) and not _is_list(rest[i]):
        lead.append(_atom(rest[i]))
        i += 1
    head_line = f"{pad}({head}"
    if lead:
        head_line += " " + " ".join(lead)
    lines = [head_line]
    child_pad = indent_str * (indent + 1)
    for child in rest[i:]:
        if _is_list(child):
            if _has_child_list(child):
                lines.append(dumps(child, indent + 1, indent_str))
            else:
                # Inline list: render flat, then indent it ourselves.
                lines.append(child_pad + dumps(child, 0, indent_str))
        else:
            lines.append(f"{child_pad}{_atom(child)}")
    lines.append(f"{pad})")
    return "\n".join(lines)
