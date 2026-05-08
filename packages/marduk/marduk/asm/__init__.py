"""marduk.asm — Plan Asm I/O.

Read, macro-expand, and print Plan Asm text against the Marduk runtime.

* :func:`parse` / :func:`parse_many` — Plan Asm text → ``Val``.
* :class:`Env` — top-level mutable environment for ``#bind``.
* :func:`macroexpand` / :func:`thunk` / :func:`eval_form` — the macro-layer
  pipeline. ``eval_form(val, env)`` is the full driver: macroexpand →
  thunk → runtime evaluate.
* :func:`dump` — ``Val`` → Plan Asm text (best-effort round-trippable).

A typical interactive flow:

    >>> from marduk.asm import parse, eval_form, Env, dump
    >>> env = Env()
    >>> # Bind ``add`` to a 2-arg law that calls BPLAN's Add.
    >>> form = parse('(#bind add (#law "add" (self n m) (Add n m)))')
    >>> # ``Add`` would need to be in env first; see prelude wiring.

The expander's API is shape-compatible with plan-kernel's lifted-from
predecessor so the kernel's evaluator can swap the import path with
minimal change.
"""

from .reader import ParseError, parse, parse_many
from .expander import (
    Env,
    MacroError,
    macroexpand,
    thunk,
    eval_form,
)
from .printer import dump


__all__ = [
    # reader
    "ParseError", "parse", "parse_many",
    # expander
    "Env", "MacroError", "macroexpand", "thunk", "eval_form",
    # printer
    "dump",
]
