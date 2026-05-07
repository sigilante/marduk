# Marduk — design notes

This file collects the non-obvious design decisions behind Marduk. For the
delivery plan, see [`PLAN.md`](PLAN.md).

## What Marduk is

A Jupyter kernel for the PLAN virtual machine, packaged as `marduk-plan` on
PyPI. Cells contain Plan Asm text; each cell parses, macro-expands, and
evaluates against a Python PLAN evaluator, then renders the resulting `Val`
(Pin / Law / App / Nat) structurally.

The audience is tutorial: someone reading the PLAN spec who wants to *run*
the examples, not just read them.

## What Marduk is not

- Not a Gallowglass kernel. Gallowglass already has its own kernel
  (`bootstrap/jupyter_kernel.py`); Marduk targets PLAN itself.
- Not a production runtime. The Python evaluator is correct but slow.
  Reaver is the production runtime; a Reaver shell-out backend is plausible
  future work but explicitly deferred.
- Not a compiler. Marduk evaluates Plan Asm; it does not compile from any
  higher-level language.

## Naming

"Marduk" is the long-term name for the Python PLAN harness. The Gallowglass
repo's `dev/harness/plan.py`, `dev/harness/bplan.py`, and
`bootstrap/bplan_deps.py` together implement the harness; a future refactor
will consolidate them under the name "Marduk." This Jupyter kernel adopts
the name early so that when the harness rename lands, the package and the
runtime are already aligned.

The PyPI package is `marduk-plan` (the `-plan` suffix disambiguates from
unrelated packages); the Python module name is `marduk` (so that
`python -m marduk` and `import marduk` work cleanly).

## Vendor provenance

The PLAN runtime in `marduk/runtime/{plan.py, bplan.py, bplan_deps.py}` is
**vendored** from Gallowglass. Provenance, source SHAs, and sync policy are
recorded in [`marduk/runtime/VENDOR.md`](marduk/runtime/VENDOR.md). Re-sync
via [`scripts/sync_runtime.sh`](scripts/sync_runtime.sh).

The vendoring is deliberate: Marduk ships as a self-contained PyPI package
without a Gallowglass dependency. When the future harness rename lands, the
vendoring may collapse — at that point Marduk could depend on the renamed
harness as a real package. The import boundary is kept clean
(`marduk.runtime.plan` is a stable path) so that transition is painless.

## Repo layout

The directory currently develops at `gallowglass/vendor/marduk/` — physically
inside Gallowglass's gitignored `vendor/` tree, but logically a separate git
repo whose `origin` points at `git@github.com:sigilante/marduk.git`. Commits
flow to that repo; they never land in Gallowglass.

This is the canonical dev layout because the vendored runtime files are
edited alongside their upstream sources during early development. Once the
runtime stabilizes, Marduk could move out of the Gallowglass tree without
disturbing anything beyond the default for `GALLOWGLASS_HOME` in
`scripts/sync_runtime.sh`.

## Source-of-truth references

These files in Gallowglass inform Marduk's implementation but are not edited
from Marduk:

| File | Role |
|---|---|
| `vendor/reaver/src/hs/Plan.hs` | Canonical PLAN runtime (3 opcodes, BPLAN at op 66, RPLAN at op 82) |
| `vendor/reaver/src/hs/PlanAssembler.hs` | Canonical Plan Asm text format — the parser + macro expander we port |
| `vendor/reaver/src/plan/*.plan` | Example Plan Asm files; tutorial fixture material |
| `bootstrap/jupyter_kernel.py` | Reference architecture for the kernel/evaluator split |
| `bootstrap/value_render.py` | Reference for structural rendering and the `Formatter` abstraction |
