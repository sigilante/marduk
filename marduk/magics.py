"""Cell-leading ``%magic`` parsing.

A cell's *magic block* is its run of leading ``%``-prefixed lines, with
blank lines between them allowed once at least one magic has been seen.
Anything else — comments, source forms, blank cells — ends the magic
block, and the rest is the cell's source body.

Three magics are recognized by the evaluator:

- ``%backend evaluate | bevaluate`` — pick the runtime evaluator. The
  evaluator scopes this to the current cell only.
- ``%reset`` — clear all bindings from the env. (Persistent.)
- ``%env`` — display the names currently bound. (Read-only.)

This module just *parses* the magic block; the evaluator dispatches each
directive (and decides what counts as a per-cell vs. persistent action).
Unknown directives are returned as-is — the dispatcher raises
``MagicError`` if it can't handle one.
"""

from __future__ import annotations

from dataclasses import dataclass, field


__all__ = ["MagicDirective", "MagicError", "parse_magics"]


class MagicError(Exception):
    """Raised when a magic directive is malformed, unsupported, or its
    arguments don't validate."""


@dataclass
class MagicDirective:
    name: str                            # e.g. 'backend', 'reset', 'env'
    args: list[str] = field(default_factory=list)

    @property
    def line(self) -> str:
        if not self.args:
            return f"%{self.name}"
        return f"%{self.name} {' '.join(self.args)}"


def parse_magics(source: str) -> tuple[list[MagicDirective], str]:
    """Split a cell's leading ``%magic`` lines from its source body.

    The body retains its original indentation/whitespace — only the
    consumed magic lines (and any blank lines between them) are removed.
    """
    lines = source.splitlines(keepends=True)
    directives: list[MagicDirective] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].lstrip()
        if stripped.startswith("%"):
            tokens = stripped[1:].split()
            if not tokens:
                # Bare `%` line — not a magic; treat as body so the user
                # gets a clear parse error rather than a silent skip.
                break
            directives.append(MagicDirective(name=tokens[0], args=tokens[1:]))
            i += 1
            continue
        if stripped == "" and directives:
            # Blank line *between* magics — absorb so a multi-magic block
            # can be visually separated without breaking the parse.
            i += 1
            continue
        break
    return directives, "".join(lines[i:])
