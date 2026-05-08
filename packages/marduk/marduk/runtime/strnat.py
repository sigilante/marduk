"""Plan Asm string-nat encoding.

A string ``s`` encodes to a nat by interpreting the UTF-8 bytes as a
little-endian unsigned integer. ``"B"`` ↦ ``66``, ``"R"`` ↦ ``82``,
``"Add"`` ↦ ``0x646441``, etc. The empty string maps to ``0``.

These helpers are not part of PLAN-the-language — they're the encoding
convention Plan Asm and BPLAN use to address named primitives.
"""

from __future__ import annotations


def str_nat(s: str) -> int:
    """Encode ``s`` as a little-endian-bytes nat (Reaver's ``strNat``)."""
    return int.from_bytes(s.encode("utf-8"), "little")


def nat_str(n: int) -> str:
    """Decode a little-endian-bytes nat back to its UTF-8 string.

    Best-effort: returns ``"<nat:N>"`` for nats whose bytes don't decode as
    UTF-8 (so callers always get a ``str`` they can stringify and compare).
    Zero decodes to the empty string.
    """
    n = int(n)
    if n == 0:
        return ""
    raw = n.to_bytes((n.bit_length() + 7) // 8, "little")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return f"<nat:{n}>"
