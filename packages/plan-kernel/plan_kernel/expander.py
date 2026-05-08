"""Macro expander — compatibility shim.

Lifted to :mod:`marduk.asm.expander` as part of the Phase E Marduk swap.
This module re-exports the same API for callers that still import via
``plan_kernel.expander``. New code should import from ``marduk.asm``.
"""

from marduk.asm.expander import (
    Env,
    MacroError,
    macroexpand,
    thunk,
    eval_form,
)


__all__ = [
    "Env",
    "MacroError",
    "macroexpand",
    "thunk",
    "eval_form",
]
