"""BPLAN harness — compatibility shim.

The legacy plan-kernel BPLAN harness implemented jet-based dispatch on
top of the old runtime. Phase E moves the canonical BPLAN op table into
:mod:`marduk.runtime.bplan`, where dispatch is integrated with the
spec-faithful core. This module re-exports the new table so callers
that import from ``plan_kernel.runtime.bplan`` continue to resolve.

Note: the legacy file used to define a separate ``bevaluate`` driver
distinct from ``evaluate``. With Marduk both modes share the same
evaluator (the spec-faithful core does the right thing without a jet
overlay), so the historic distinction has gone away — ``bevaluate``
here is an alias for ``evaluate``.
"""

from marduk.runtime import evaluate as bevaluate
from marduk.runtime.bplan import OPS, dispatch


__all__ = ["OPS", "dispatch", "bevaluate"]
