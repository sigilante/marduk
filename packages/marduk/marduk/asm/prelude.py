"""Default BPLAN op prelude for ``marduk.asm``.

For each named op in :mod:`marduk.runtime.bplan`, builds a wrapper
``Law`` whose body invokes the op via the BPLAN dispatcher. Loading
the prelude into an :class:`Env` makes expressions like ``(Add 2 3)``
or ``(Mul x y)`` evaluate the way you'd expect.

The wrapper for ``(name args...)`` of arity ``N`` has shape::

    Law name N body
      where body = (0 (0 BPLAN) (0 (0 ... (0 (0 name) $1) ...) $N))

* ``BPLAN`` is the pinned-nat dispatcher ``<66>``.
* ``(0 X)`` is the body-syntax quote (return X without descending).
* ``(0 X Y)`` is body-syntax apply (build ``App(R(X), R(Y))``).
* ``$i`` is the de Bruijn slot reference for the i-th argument.

Construction is direct (using Marduk's smart constructors) rather than
going through ``#law`` macroexpansion — same end result, smaller code
path. Prelude laws share the same body shape as ``#law``-built ones,
so a jet registered for either form fires identically.

Usage::

    from marduk.asm import Env, parse, eval_form
    from marduk.asm.prelude import load_prelude

    env = Env()
    load_prelude(env)
    eval_form(parse('(Add 2 3)'), env)   # → Nat(5)
"""

from __future__ import annotations

from ..runtime import App, Law, Nat, Pin, Val
from ..runtime.bplan import OPS
from ..runtime.strnat import str_nat
from .expander import Env


__all__ = ["BPLAN", "make_bplan_wrapper", "load_prelude", "PRELUDE_NAMES"]


# The pinned-nat dispatcher for BPLAN named ops (str_nat("B") == 66).
BPLAN = Pin(Nat(66))


def _wrapper_body(name: str, arity: int) -> Val:
    """Build the wrapper-law body in PLAN body-syntax for an op of the
    given name + arity. See module docstring for shape."""
    name_nat = Nat(str_nat(name))
    # Inner spine: starts with (0 name_nat) and grows by left-folded
    # apply for each arg slot.
    inner = App(Nat(0), name_nat)
    for i in range(1, arity + 1):
        inner = App(App(Nat(0), inner), Nat(i))
    # Outer: apply BPLAN-quoted to the inner spine.
    bplan_q = App(Nat(0), BPLAN)
    return App(App(Nat(0), bplan_q), inner)


def make_bplan_wrapper(name: str) -> Val:
    """Construct a wrapper ``Law`` for the BPLAN op ``name``. Raises
    ``KeyError`` if the op isn't registered, ``ValueError`` if its
    arity is zero (a Law must have arity ≥ 1)."""
    if name not in OPS:
        raise KeyError(f"unknown BPLAN op {name!r}")
    arity, _fn = OPS[name]
    if arity < 1:
        raise ValueError(
            f"can't wrap nullary op {name!r} (a Law must have arity ≥ 1)"
        )
    return Law(Nat(str_nat(name)), Nat(arity), _wrapper_body(name, arity))


def load_prelude(env: Env, *, ops: list[str] | None = None) -> set[int]:
    """Bind every BPLAN op as a wrapper Law in ``env``.

    Parameters
    ----------
    env
        The environment to populate. Existing bindings under prelude
        names get overwritten.
    ops
        If provided, restrict to this subset of op names. Default:
        every op in :data:`marduk.runtime.bplan.OPS` with arity ≥ 1.

    Returns
    -------
    set[int]
        The set of name nats that were bound — useful for callers that
        want to filter prelude bindings out of an ``%env``-style listing.
    """
    bound: set[int] = set()
    candidates = ops if ops is not None else list(OPS.keys())
    for name in candidates:
        if name not in OPS:
            raise KeyError(f"unknown BPLAN op {name!r}")
        arity, _fn = OPS[name]
        if arity < 1:
            continue
        env.put(str_nat(name), make_bplan_wrapper(name))
        bound.add(str_nat(name))
    return bound


# Precomputed: every prelude name nat. Equivalent to a fresh
# ``load_prelude(env)`` return value.
PRELUDE_NAMES: frozenset[int] = frozenset(
    str_nat(name) for name, (arity, _) in OPS.items() if arity >= 1
)
