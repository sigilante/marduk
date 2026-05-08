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

BPLAN (outer ``<66>``) and RPLAN (outer ``<82>``) primitive coverage and
Plan Asm I/O ride on top of this core in subsequent commits.
"""

from .runtime import (
    Val,
    Hol, Nat, Pin, App, Law,
    evaluate, force,
    PlanError, PlanLoop,
)

__version__ = "0.0.1"

__all__ = [
    "Val",
    "Hol", "Nat", "Pin", "App", "Law",
    "evaluate", "force",
    "PlanError", "PlanLoop",
]
