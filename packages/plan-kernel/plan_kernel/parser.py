"""Plan Asm reader — compatibility shim.

Lifted to :mod:`marduk.asm.reader` as part of the Phase E Marduk swap.
This module re-exports the same API for callers that still import via
``plan_kernel.parser``. New code should import from ``marduk.asm``.
"""

from marduk.asm.reader import ParseError, parse, parse_many


__all__ = ["ParseError", "parse", "parse_many"]
