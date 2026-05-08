# plan-kernel — design notes

This file collects the non-obvious design decisions behind plan-kernel. For
the delivery plan, see [`PLAN.md`](PLAN.md).

## What plan-kernel is

A Jupyter kernel for the PLAN virtual machine, packaged as `plan-kernel` on
PyPI. Cells contain Plan Asm text; each cell parses, macro-expands, and
evaluates against a Python PLAN evaluator, then renders the resulting `Val`
(Pin / Law / App / Nat) structurally.

The audience is tutorial: someone reading the PLAN spec who wants to *run*
the examples, not just read them.

## What plan-kernel is not

- Not a Gallowglass kernel. Gallowglass already has its own kernel
  (`bootstrap/jupyter_kernel.py`); plan-kernel targets PLAN itself.
- Not a production runtime. The Python evaluator is correct but slow.
  Reaver is the production runtime; a Reaver shell-out backend is plausible
  future work but explicitly deferred.
- Not a compiler. plan-kernel evaluates Plan Asm; it does not compile from
  any higher-level language.

## Naming

This package was originally named *Marduk*. As the runtime portion grew
into a generally useful artifact, it took the name; the kernel was renamed
`plan-kernel` and the runtime now lives at [`packages/marduk/`](../marduk/)
in this monorepo.

The PyPI distribution is `plan-kernel`; the Python module is `plan_kernel`
(so that `python -m plan_kernel` and `import plan_kernel` work cleanly).

## Vendor provenance

The PLAN runtime in `plan_kernel/runtime/{plan.py, bplan.py, bplan_deps.py}`
is **vendored** from Gallowglass. Provenance, source SHAs, and sync policy
are recorded in [`plan_kernel/runtime/VENDOR.md`](plan_kernel/runtime/VENDOR.md).
Re-sync via [`scripts/sync_runtime.sh`](scripts/sync_runtime.sh).

The vendoring is provisional. Once the Marduk runtime in
[`packages/marduk/`](../marduk/) is ready (spec-faithful core + BPLAN op
coverage + jet overlay), it replaces both this vendored copy and the
upstream files in `dev/harness/`. plan-kernel will then depend on Marduk as
a real package and this directory will be removed. The import boundary is
kept clean (`plan_kernel.runtime.plan` is a stable path) so that transition
is painless.

## Repo layout

The directory currently develops at `gallowglass/vendor/marduk/packages/plan-kernel/` — physically
inside Gallowglass's gitignored `vendor/` tree, but logically a separate git
repo whose `origin` points at `git@github.com:sigilante/marduk.git`. Commits
flow to that repo; they never land in Gallowglass.

This is the canonical dev layout because the vendored runtime files are
edited alongside their upstream sources during early development. Once the
runtime stabilizes, the monorepo could move out of the Gallowglass tree without
disturbing anything beyond the default for `GALLOWGLASS_HOME` in
`scripts/sync_runtime.sh`.

## Source-of-truth references

These files in Gallowglass inform plan-kernel's implementation but are not edited
from this package:

| File | Role |
|---|---|
| `vendor/reaver/src/hs/Plan.hs` | Canonical PLAN runtime (3 opcodes, BPLAN at op 66, RPLAN at op 82) |
| `vendor/reaver/src/hs/PlanAssembler.hs` | Canonical Plan Asm text format — the parser + macro expander we port |
| `vendor/reaver/src/plan/*.plan` | Example Plan Asm files; tutorial fixture material |
| `bootstrap/jupyter_kernel.py` | Reference architecture for the kernel/evaluator split |
| `bootstrap/value_render.py` | Reference for structural rendering and the `Formatter` abstraction |
