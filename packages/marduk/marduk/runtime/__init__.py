"""marduk.runtime — the spec-faithful PLAN interpreter.

The single module ``marduk.runtime.core`` is a direct translation of
``vendor/reaver/doc/plan-spec.txt`` into Python. See that module's docstring
for the full design and provenance notes.

Public surface (re-exported here for convenience):

* ``Val`` — the universal cell type. All PLAN values are ``Val`` instances.
* ``Hol``, ``Nat``, ``Pin``, ``App``, ``Law`` — smart constructors.
* ``evaluate(v)`` — force to WHNF (the spec's E rule).
* ``force(v)`` — force the App spine to NF (the spec's F rule); leaves
  pin contents and law bodies opaque.
* ``PlanError``, ``PlanLoop`` — raised on stuck states / forcing a hole.
"""

from .core import (
    Val,
    Hol, Nat, Pin, App, Law,
    evaluate, force,
    PlanError, PlanLoop,
)
from .jets import (
    register_jet, lookup_jet, clear_jets,
    set_jets, jets_enabled,
)

__all__ = [
    # Value types
    "Val",
    "Hol", "Nat", "Pin", "App", "Law",
    # Drivers
    "evaluate", "force",
    # Exceptions
    "PlanError", "PlanLoop",
    # Jet overlay
    "register_jet", "lookup_jet", "clear_jets",
    "set_jets", "jets_enabled",
]
