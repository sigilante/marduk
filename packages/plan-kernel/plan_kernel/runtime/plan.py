"""PLAN runtime — compatibility shim re-exporting Marduk's runtime under
the legacy plan-kernel API names.

Plan-kernel originally vendored a copy of the gallowglass harness at
``runtime/plan.py``. As part of the Phase E swap, the runtime is now
provided by :mod:`marduk.runtime`; this file maps the old names
(``A``, ``L``, ``N``, ``P``, ``is_app``/``is_law``/``is_nat``/``is_pin``,
``_unapp``, ``evaluate``, ``str_nat``, ``nat_str``) onto the new API so
existing callers don't have to change.

A few semantics differ from the legacy runtime that matter for callers:

* ``L(arity, name, body)`` constructs a Marduk law via the smart
  constructor — it forces the body's let-binding spine via ``B`` (per
  spec), so callers shouldn't expect deferred evaluation of binding
  values.
* ``N(n)`` returns a ``Val`` (not a raw int). Comparisons of the form
  ``some_val == 0`` no longer work — use ``some_val.nat == 0``.
"""

from __future__ import annotations

from marduk.runtime import (
    Val, Hol,
    Nat as _Nat,
    Pin as _Pin,
    App as _App,
    Law as _Law,
    evaluate as _evaluate,
    force,
    PlanError,
    PlanLoop,
)
from marduk.runtime.strnat import str_nat, nat_str


__all__ = [
    # constructors (legacy short names)
    "A", "L", "N", "P", "Hol",
    # new long names also exposed for forward-compat
    "App", "Law", "Nat", "Pin", "Val",
    # type predicates
    "is_app", "is_law", "is_nat", "is_pin",
    # spine flatten
    "_unapp", "unapp",
    # drivers
    "evaluate", "force",
    # str-nat helpers
    "str_nat", "nat_str",
    # exceptions
    "PlanError", "PlanLoop",
]


# ---- New-API aliases -------------------------------------------------------

App = _App
Law = _Law
Nat = _Nat
Pin = _Pin
evaluate = _evaluate


# ---- Legacy short-name aliases --------------------------------------------

def _coerce(x):
    """Coerce a Python int to a Marduk ``Val``; pass other ``Val`` through.

    Plan-kernel's legacy runtime treated raw Python ints as nats, so call
    sites like ``P(5)`` meant "pin a nat 5". Marduk has no raw-int
    representation for nats — every nat is a ``Val``. The legacy
    constructor shims auto-coerce so existing code keeps working.
    """
    if isinstance(x, Val):
        return x
    if isinstance(x, int):
        return _Nat(x)
    return x


def A(f, x):
    """Legacy alias for :func:`marduk.runtime.App`."""
    return _App(_coerce(f), _coerce(x))


def L(arity, name, body):
    """Legacy law constructor: ``L(arity, name, body)``.

    Plan-kernel's ``class L`` was ``__init__(self, arity, name, body)``.
    Marduk's smart constructor uses ``Law(name, arity, body)``; this
    shim flips the order back, wraps int arity in a ``Nat``, and
    coerces int name/body args.
    """
    arity_val = arity if isinstance(arity, Val) else _Nat(arity)
    return _Law(_coerce(name), arity_val, _coerce(body))


def N(n):
    """Legacy alias for :func:`marduk.runtime.Nat`. Wraps an int as a Val."""
    return _Nat(n)


def P(item):
    """Legacy alias for :func:`marduk.runtime.Pin`."""
    return _Pin(_coerce(item))


# ---- Type predicates -------------------------------------------------------

def is_app(v):
    return isinstance(v, Val) and v.type == "app"


def is_law(v):
    return isinstance(v, Val) and v.type == "law"


def is_nat(v):
    return isinstance(v, Val) and v.type == "nat"


def is_pin(v):
    return isinstance(v, Val) and v.type == "pin"


# ---- Spine flatten ---------------------------------------------------------

def unapp(v):
    """Public alias for :attr:`marduk.runtime.Val.spine`."""
    return v.spine


_unapp = unapp
