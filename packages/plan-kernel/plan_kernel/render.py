"""Structural value renderer.

``render_value(val)`` returns a ``(text/plain, text/html)`` pair the
kernel emits as a Jupyter MIME bundle. Both forms are depth-bounded so
a pathological structure (a malformed App tree, a Pin loop) can't blow
the stack while we're trying to *show* it.

Format:

- Nat ``n``           → ``"42"`` (decimal).
- Pin ``v``           → ``"<v>"``.
- Pin ``Law``         → ``"<{'name'…}>"`` when ``pretty=True`` (default);
                        otherwise expanded as ``"<{name arity body}>"``.
- Law ``{a n b}``     → ``"{'name' arity body}"``; ``name`` is decoded
                        via ``nat_str`` and shown single-quoted (or
                        decimal if the nat doesn't decode to printable
                        UTF-8).
- App ``f x``         → ``"(f x)"``.

The HTML output uses inline ``style="…"`` (Jupyter strips ``<style>``
blocks) and a cross-theme palette that reads on both light and dark
backgrounds.

Phase E note: this module now reads Marduk's ``Val`` accessors —
``.head``/``.tail`` for App, ``.item`` for Pin, ``.args`` for Law's
arity (a ``Val``, not an int), ``.name`` (also a ``Val``). The
predicates ``is_app``/``is_law``/etc. come from the runtime shim,
which dispatches on ``val.type``.
"""

from __future__ import annotations

import html

from marduk.runtime.strnat import nat_str

from .runtime.plan import is_app, is_law, is_nat, is_pin


__all__ = ["render_value"]


_DEFAULT_DEPTH = 32

# Cross-theme-friendly palette.
_NAT   = "color:#0097a7"                         # cyan
_LAW   = "color:#e65100;font-style:italic"       # orange italic
_NAME  = "color:#388e3c"                         # green (decoded name)
_MUTED = "color:#999"                            # gray (brackets)


def render_value(val, *, pretty: bool = True,
                 max_depth: int = _DEFAULT_DEPTH) -> tuple[str, str]:
    """Return ``(text, html)`` for ``val``.

    Parameters
    ----------
    pretty
        Collapse ``Pin(Law(...))`` to ``<{name…}>`` for terse display
        (default). Set to ``False`` to fully expand into
        ``<{name arity body}>``.
    max_depth
        Recursion bound. Past this depth the renderer emits an ellipsis.
    """
    text = _text(val, depth=0, pretty=pretty, max_depth=max_depth)
    body = _html(val, depth=0, pretty=pretty, max_depth=max_depth)
    full_html = (
        '<code style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;'
        f'font-size:0.9em">{body}</code>'
    )
    return text, full_html


# ---------------------------------------------------------------------------
# text/plain
# ---------------------------------------------------------------------------

def _text(val, *, depth: int, pretty: bool, max_depth: int) -> str:
    if depth >= max_depth:
        return "..."
    if is_nat(val):
        return str(val.nat)
    if is_pin(val):
        if pretty and is_law(val.item):
            return f"<{{{_law_name_text(val.item)}…}}>"
        inner = _text(val.item, depth=depth + 1, pretty=pretty, max_depth=max_depth)
        return f"<{inner}>"
    if is_law(val):
        body = _text(val.body, depth=depth + 1, pretty=pretty, max_depth=max_depth)
        return f"{{{_law_name_text(val)} {val.args.nat} {body}}}"
    if is_app(val):
        f = _text(val.head, depth=depth + 1, pretty=pretty, max_depth=max_depth)
        a = _text(val.tail, depth=depth + 1, pretty=pretty, max_depth=max_depth)
        return f"({f} {a})"
    return repr(val)


def _law_name_text(law) -> str:
    """Decode a law's ``name`` via ``nat_str`` for display.

    Returns ``'identifier'`` (single-quoted) for printable UTF-8 nats, or
    decimal for nats that don't decode. Non-nat names recurse through the
    text renderer with a small depth bound.
    """
    if is_nat(law.name):
        s = nat_str(law.name.nat)
        if s and not s.startswith("<nat:"):
            return f"'{s}'"
        return str(law.name.nat)
    return _text(law.name, depth=0, pretty=True, max_depth=4)


# ---------------------------------------------------------------------------
# text/html
# ---------------------------------------------------------------------------

def _html(val, *, depth: int, pretty: bool, max_depth: int) -> str:
    if depth >= max_depth:
        return f'<span style="{_MUTED}">…</span>'
    if is_nat(val):
        return f'<span style="{_NAT}">{val.nat}</span>'
    if is_pin(val):
        if pretty and is_law(val.item):
            return (
                f'<span style="{_MUTED}">&lt;{{</span>'
                f"{_law_name_html(val.item)}"
                f'<span style="{_MUTED}">…}}&gt;</span>'
            )
        inner = _html(val.item, depth=depth + 1, pretty=pretty, max_depth=max_depth)
        return (
            f'<span style="{_MUTED}">&lt;</span>'
            f"{inner}"
            f'<span style="{_MUTED}">&gt;</span>'
        )
    if is_law(val):
        body = _html(val.body, depth=depth + 1, pretty=pretty, max_depth=max_depth)
        return (
            f'<span style="{_MUTED}">{{</span>'
            f"{_law_name_html(val)} "
            f'<span style="{_NAT}">{val.args.nat}</span> '
            f"{body}"
            f'<span style="{_MUTED}">}}</span>'
        )
    if is_app(val):
        f = _html(val.head, depth=depth + 1, pretty=pretty, max_depth=max_depth)
        a = _html(val.tail, depth=depth + 1, pretty=pretty, max_depth=max_depth)
        return (
            f'<span style="{_MUTED}">(</span>'
            f"{f} {a}"
            f'<span style="{_MUTED}">)</span>'
        )
    return html.escape(repr(val), quote=False)


def _law_name_html(law) -> str:
    if is_nat(law.name):
        s = nat_str(law.name.nat)
        if s and not s.startswith("<nat:"):
            return f'<span style="{_NAME}">\'{html.escape(s)}\'</span>'
        return f'<span style="{_NAT}">{law.name.nat}</span>'
    return f'<span style="{_LAW}">{html.escape(repr(law.name))}</span>'
