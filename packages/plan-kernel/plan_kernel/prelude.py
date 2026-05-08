"""BPLAN op prelude — boot.plan-style wrappers auto-loaded on kernel start.

For each ``(name, arity)`` in ``runtime.bplan_deps.ALL_DEPS``, this module
constructs the boot.plan-style wrapper:

.. code-block:: text

    (#bind Name
      (#pin
        (#law "Name" (Name a b ...)
          ((#pin "B") ("Name" a b ...)))))

and evaluates it against the supplied env. After loading, expressions like
``(Add 2 3)``, ``(Inc 41)``, ``(Eq x y)`` work in any cell.

Under Phase E (the Marduk swap), the runtime is :mod:`marduk.runtime` and
the BPLAN op table is :mod:`marduk.runtime.bplan`. Wrappers for op names
in ``ALL_DEPS`` that aren't yet implemented in Marduk's op table still
*bind* successfully — the wrapper Law is constructed without evaluating
its body — but calling them at runtime will raise NotImplementedError
from the BPLAN dispatcher. Add the op upstream rather than working
around it here.
"""

from __future__ import annotations

from marduk.asm import Env, eval_form, parse_many
from marduk.runtime.strnat import str_nat

from .runtime.bplan_deps import ALL_DEPS


__all__ = ["PRELUDE_NAMES", "load_prelude"]


# Single-letter argument names. ``ALL_DEPS`` arities cap at 6 (``Elim``);
# 26 letters is plenty.
_ARG_LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _arg_names(arity: int) -> str:
    if arity > len(_ARG_LETTERS):
        raise ValueError(
            f"prelude: arity {arity} exceeds supported letters ({len(_ARG_LETTERS)})"
        )
    return " ".join(_ARG_LETTERS[i] for i in range(arity))


def _wrapper_source(name: str, arity: int) -> str:
    args = _arg_names(arity)
    sig = f"{name} {args}"
    body = f'((#pin "B") ("{name}" {args}))'
    return f'(#bind {name} (#pin (#law "{name}" ({sig}) {body})))'


def load_prelude(env: Env) -> set[int]:
    """Load every BPLAN op wrapper into ``env``.

    Returns the set of name nats that were bound — useful for the
    evaluator's ``%env`` magic to filter prelude noise from user bindings.
    """
    bound: set[int] = set()
    for name, arity in ALL_DEPS.items():
        if arity < 1:
            continue
        src = _wrapper_source(name, arity)
        for form in parse_many(src):
            eval_form(form, env)
        bound.add(str_nat(name))
    return bound


# Precomputed set of all prelude name nats. Equivalent to the return value
# of ``load_prelude(...)`` but available without performing the load.
PRELUDE_NAMES: frozenset[int] = frozenset(
    str_nat(name) for name, arity in ALL_DEPS.items() if arity >= 1
)
