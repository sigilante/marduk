"""Marduk — standalone Python runtime for the PLAN virtual machine.

This package is a thunked, spec-faithful translation of
``vendor/reaver/doc/plan-spec.txt`` into Python. The core interpreter
(spec rules E/F/X/S and friends, plus the ``Val`` cell type that supports
update-in-place for letrec / Y / fix) lives in :mod:`marduk.runtime.core`.

Public surface, re-exported from :mod:`marduk.runtime`:

* ``Val`` — universal cell type.
* ``Hol``, ``Nat``, ``Pin``, ``App``, ``Law`` — smart constructors.
* ``evaluate(v)`` — force to WHNF.
* ``force(v)`` — force the App spine to NF (pins and law bodies stay opaque).
* ``PlanError``, ``PlanLoop`` — exceptions for stuck states and hole-loops.

Optional jet overlay (see :mod:`marduk.runtime.jets`):

* ``register_jet(law, fn)`` — install a native Python implementation
  for a specific Law value.
* ``set_jets(bool)`` / ``jets_enabled()`` — global on/off switch. Use
  ``set_jets(False)`` to force every law to evaluate via the
  spec-faithful path (correctness oracle / differential testing).

Plan Asm I/O lives in :mod:`marduk.asm`.
"""

from .runtime import (
    Val,
    Hol, Nat, Pin, App, Law,
    evaluate, force,
    PlanError, PlanLoop,
    register_jet, lookup_jet, clear_jets,
    set_jets, jets_enabled,
)

__version__ = "0.0.1"

__all__ = [
    "Val",
    "Hol", "Nat", "Pin", "App", "Law",
    "evaluate", "force",
    "PlanError", "PlanLoop",
    "register_jet", "lookup_jet", "clear_jets",
    "set_jets", "jets_enabled",
]
