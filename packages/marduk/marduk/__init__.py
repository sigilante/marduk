"""Marduk — standalone Python runtime for the PLAN virtual machine.

This package is a work-in-progress reimplementation of PLAN that follows
``vendor/reaver/doc/plan-spec.txt`` line-for-line: a thunked, spec-faithful
small-step evaluator with BPLAN op coverage and an optional jet overlay
for performance.

Until the runtime ships its first usable surface, the public API is empty.
The companion package ``plan-kernel`` (in ``packages/plan-kernel/``)
currently vendors the legacy harness from gallowglass; it will switch to
depending on this package as the API stabilizes.
"""

__version__ = "0.0.1"

__all__: list[str] = []
