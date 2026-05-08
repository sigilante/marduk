"""Plan Asm printer.

Turn a ``Val`` back into Plan Asm text suitable for re-parsing. Pin
content and Law bodies are inlined verbatim — the printer doesn't
content-address or compress, since the goal is round-trippability for
debugging and snapshot tests.

Format (matches the reader's surface conventions):

* Bare nat ``n``      → decimal ``n``
* String-nat (a nat whose bytes decode as printable UTF-8) → ``"foo"``
* Pin ``v``           → ``<v>``
* Law ``{a m b}``     → ``{tag (sig...) body}`` if reconstructable from
                        an arity, else the raw spec form ``{name arity body}``
* App spine           → ``(head args...)``

Hole values (``Hol()``) print as ``<>`` — purely for diagnostics; a hole
is not valid Plan Asm input.

The printer is depth-bounded so a malformed cyclic structure can't
exhaust the stack — we emit ``…`` past the depth limit.
"""

from __future__ import annotations

from ..runtime import Val
from ..runtime.strnat import nat_str


__all__ = ["dump"]


_DEFAULT_DEPTH = 64
_DEFAULT_WIDTH = 32


def dump(val: Val, *,
         max_depth: int = _DEFAULT_DEPTH,
         max_width: int = _DEFAULT_WIDTH) -> str:
    """Render ``val`` as Plan Asm text. Best-effort round-trippable; for
    pathological inputs (cyclic via a held reference, malformed
    constructors), the output is depth- and width-bounded."""
    return _go(val, depth=0, max_depth=max_depth, max_width=max_width)


def _go(val: Val, depth: int, max_depth: int, max_width: int) -> str:
    if depth >= max_depth:
        return "…"
    t = val.type
    if t == "hol":
        return "<>"
    if t == "nat":
        return _format_nat(val.nat)
    if t == "pin":
        return f"<{_go(val.item, depth + 1, max_depth, max_width)}>"
    if t == "law":
        # Spec form: {name arity body}. Surface form (#law tag (sig...)
        # body) requires recovering binder names, which we don't carry —
        # so we emit the spec form. It re-parses via the reader (since
        # ``{...}`` is a curl-bracket form), at the cost of round-tripping
        # at the runtime level rather than at the macro level.
        name = _go(val.name, depth + 1, max_depth, max_width)
        arity = _go(val.args, depth + 1, max_depth, max_width)
        body = _go(val.body, depth + 1, max_depth, max_width)
        return "{" + name + " " + arity + " " + body + "}"
    if t == "app":
        parts = val.spine
        # Cap spine width: deeply spined Apps print with ellipsis at the
        # end rather than dumping the entire chain.
        if len(parts) > max_width:
            shown = parts[: max_width]
            rendered = [_go(p, depth + 1, max_depth, max_width) for p in shown]
            return "(" + " ".join(rendered) + " …)"
        rendered = [_go(p, depth + 1, max_depth, max_width) for p in parts]
        return "(" + " ".join(rendered) + ")"
    return f"<unknown:{t}>"


def _format_nat(n: int) -> str:
    """Decimal for small / non-string nats; quoted UTF-8 only for nats
    whose decoded form is ≥2 bytes and printable.

    The single-byte cutoff matters: ``Nat(42)`` is the byte ``"*"`` but
    overwhelmingly likely to be the number 42 in practice. Switching to
    string form on every printable single byte trashes ordinary numeric
    output. Two-byte+ strings rarely appear by accident in arithmetic
    output, so the heuristic is safe in practice and round-trippable
    for the cases that matter (op names, "id", error tags, etc.).
    """
    if n == 0:
        return "0"
    s = nat_str(n)
    if (s
            and len(s) >= 2
            and not s.startswith("<nat:")
            and all(_is_safe_string_char(c) for c in s)):
        return f'"{s}"'
    return str(n)


def _is_safe_string_char(c: str) -> bool:
    if c in (" ", "\t", "\n", "\r", '"', "(", ")", "[", "]", "{", "}", ";"):
        return False
    # Printable: ASCII >= 0x20 and not in the list above. We accept
    # higher Unicode too — Plan Asm doesn't constrain string contents
    # beyond the closing quote.
    return ord(c) >= 0x20
