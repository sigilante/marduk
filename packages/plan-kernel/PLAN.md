# plan-kernel — Implementation Plan (historical)

This document is the original implementation plan for what is now
**plan-kernel**, a Jupyter kernel for the PLAN virtual machine intended for
tutorial use ("type Plan Asm in a cell, see the reduced PLAN value back"). It
was written under the project's original name *Marduk*; references below to
"Marduk" mean this kernel package.

All nine phases recorded here have shipped. The document is preserved for
historical context — it captures the design as initially negotiated. For
current architecture / design decisions, see [`PLAN_KERNEL.md`](PLAN_KERNEL.md).

## Goal

A Jupyter kernel that:

1. Accepts a subset of Plan Asm text in cells (the same syntax as
   `vendor/reaver/src/plan/*.plan` files).
2. Parses, macro-expands, and evaluates each cell against a Python PLAN
   evaluator.
3. Renders the resulting PLAN `Val` (Pin / Law / App / Nat) structurally.
4. Maintains a notebook-scoped environment so `#bind` accumulates across cells.

The kernel ships as the **`marduk-plan`** PyPI package; module name is
**`marduk`**. End-user install path:

```
pip install marduk-plan
python -m marduk install      # registers the kernelspec with Jupyter
jupyter notebook              # "Marduk (PLAN)" appears in the kernel picker
```

## Repository context

- **Develops at:** `/Users/neal/gallowglass/vendor/marduk/` — this directory.
- **Origin:** `git@github.com:sigilante/marduk.git` (already configured).
- **Position relative to gallowglass:** physically inside gallowglass's
  gitignored `vendor/` tree (per `gallowglass/CLAUDE.md`), but logically a
  separate git repo. Commits flow to `sigilante/marduk`, **never to
  gallowglass**.
- **Long-term naming:** "Marduk" is also planned to become the name of
  gallowglass's Python PLAN harness (`dev/harness/`) post-refactor. The kernel
  package name foreshadows that.

## Source-of-truth references (in gallowglass)

These files inform the implementation but are **not edited** from Marduk work:

| File | Role |
|---|---|
| `vendor/reaver/src/hs/Plan.hs` | Canonical PLAN runtime (3 opcodes, BPLAN at op 66, RPLAN at op 82) |
| `vendor/reaver/src/hs/PlanAssembler.hs` | Canonical Plan Asm text format — the parser + macro expander we port |
| `vendor/reaver/src/plan/*.plan` | Example Plan Asm files (boot.plan, silly.plan, raw.plan); tutorial fixture material |
| `dev/harness/plan.py` | Python PLAN evaluator (`evaluate`); to be vendored |
| `dev/harness/bplan.py` | Jet-aware Python evaluator (`bevaluate`); to be vendored |
| `bootstrap/bplan_deps.py` | BPLAN op + arity table; to be vendored |
| `bootstrap/jupyter_kernel.py` | Reference architecture for the kernel/evaluator split, MIME bundle emission, error envelope shape, kernelspec install |
| `bootstrap/value_render.py` | Reference for `_walk_structural` rendering and the `Formatter` / `HtmlFormatter` abstraction |

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Cell input format | **Plan Asm subset** (no `#macro`, `#export`, `@include`) | Faithful to Reaver; cells round-trip with real PLAN code. Macros: `#pin`, `#law`, `#app`, `#bind`. |
| Default backend | `evaluate` (formal Python) | Every reduction goes through the canonical rules — best for "see what PLAN actually does." |
| Alternate backend | `bevaluate` (jet-aware) | Available via `%backend bevaluate` magic. Faster for arithmetic-heavy programs. |
| Reaver backend | **Deferred** | Would require `nix`/`cabal` install on the user's machine. Revisit once Python path is stable. |
| BPLAN op prelude | **Auto-load on kernel start** | `boot.plan`-style `(bplan ...)` wrappers for every op in `bplan_deps.PRELUDE_INTRINSICS`. `(Add 2 3)` works in cell 1. |
| Runtime dependency | **Vendored** into `marduk/runtime/` from day one | Self-contained PyPI package; no Gallowglass dependency. Periodic sync via `scripts/sync_runtime.sh`. |
| PyPI package | `marduk-plan` | Module name is `marduk` (so `python -m marduk`). |

### Defaults taken (ask before changing)

- Multiple top-level forms per cell: **yes** (matches Reaver's `parseMany`).
- Env scope: **notebook-wide**; `%reset` magic clears it.
- Pygments lexer in `language_info`: `lisp` (no Plan-Asm lexer exists).
- `%trace` step-by-step reduction output: **deferred** (separate skill on top
  of `evaluate`).

## Repository layout

```
marduk/                            this repo's root (sigilante/marduk)
  PLAN.md                          this file
  README.md                        usage, install, quickstart, examples
  MARDUK.md                        design notes, vendor provenance, naming history
  pyproject.toml                   PEP 621; name="marduk-plan", deps=[ipykernel]
  .gitignore                       __pycache__/, *.egg-info/, .pytest_cache/, .ipynb_checkpoints/, etc.

  marduk/                          the Python package
    __init__.py                    version + top-level re-exports
    parser.py                      Plan Asm reader → PLAN Val (port of PlanAssembler.hs `parse`)
    expander.py                    macroexpand + lawExp/compileExpr port (handles #pin, #law, #app, #bind)
    evaluator.py                   MardukEvaluator class + CellResult dataclass
    magics.py                      %backend, %reset, %env directive parsing
    render.py                      structural text/plain + text/html rendering
    prelude.py                     BPLAN op auto-bind (boot.plan-style)
    kernel.py                      MardukKernel(ipykernel.kernelbase.Kernel) + _kernel_main + _install_kernelspec + _cli_main
    __main__.py                    entry point for `python -m marduk` (calls kernel._cli_main)

    runtime/                       VENDORED from gallowglass — treat as read-only
      __init__.py
      plan.py                      copy of gallowglass dev/harness/plan.py
      bplan.py                     copy of gallowglass dev/harness/bplan.py — imports rewritten to relative
      bplan_deps.py                copy of gallowglass bootstrap/bplan_deps.py
      VENDOR.md                    source SHAs + sync method + drift policy

  tests/
    __init__.py
    test_runtime_smoke.py          imports runtime, evaluates a small expr; canary for sync breakage
    test_parser.py
    test_expander.py
    test_evaluator.py
    test_render.py
    test_kernel_smoke.py           protocol-free kernel-class import test
    fixtures/
      *.plan                       small tutorial programs (id, K, factorial, church-bools)

  scripts/
    sync_runtime.sh                copies runtime files from $GALLOWGLASS_HOME (configurable) and bumps VENDOR.md SHA
```

### Vendoring details

- `bplan.py` imports `from dev.harness.plan import ...`. After vendoring this
  becomes `from .plan import ...` (relative within `marduk.runtime`).
- `bplan_deps.py` has no imports beyond `__future__`; vendors as-is.
- `plan.py` has no imports beyond stdlib; vendors as-is.
- VENDOR.md records: source repo, source paths, source SHA, sync date, sync
  method (script vs. manual), and the import-rewrite delta from upstream.

## Phases

Each phase ends with green tests before the next begins.

### Phase 1 — Vendor runtime + scaffolding

1. Create `marduk/marduk/runtime/{__init__.py, plan.py, bplan.py, bplan_deps.py}`
   — copy from gallowglass, rewrite `bplan.py` import to relative.
2. Write `marduk/marduk/runtime/VENDOR.md` with SHA + sync notes.
3. Write `marduk/scripts/sync_runtime.sh`.
4. Write `marduk/pyproject.toml` (PEP 621, dep on `ipykernel>=6.0`,
   dev extra with `pytest`).
5. Write `marduk/README.md` (skeleton; expand later phases).
6. Write `marduk/MARDUK.md` (design notes; vendor provenance).
7. Write `marduk/.gitignore`.
8. Write `marduk/marduk/__init__.py` with `__version__`.
9. Write `marduk/tests/__init__.py` and `marduk/tests/test_runtime_smoke.py`:
   imports `marduk.runtime.plan`, evaluates `App(App(B_PIN, "Add"), N(2), N(3))`
   under `evaluate`, asserts result is `5` (or simpler: just `evaluate(N(5))`
   round-trips).
10. Run `pytest marduk/tests/test_runtime_smoke.py` — must be green before
    phase 2.

**End state:** importable, smoke-tested, vendored runtime; package metadata in
place.

### Phase 2 — Plan Asm parser

Port `PlanAssembler.hs` lines 32–114 (the `parse` / `pseq` / `parseMany` block)
to Python.

- `marduk/marduk/parser.py`:
  - `parse(text: str) -> Val` — single form
  - `parse_many(text: str) -> list[Val]` — sequence of forms
  - Output is a PLAN `Val` (using `marduk.runtime.plan.A/N`), not a separate
    surface AST — matches PlanAssembler's `parse` semantics exactly:
    - `(...)` → `array(xs)` = `A(N 0, xs)`
    - `[...]` → `array([N "#brak"] + xs)`
    - `{...}` → `array([N "#curl"] + xs)`
    - `"foo"` → `(1 strNat("foo"))` = `A(N 1, [N (strNat "foo")])`
    - bare nat literal → `(1 N)`
    - bare symbol → `N (strNat sym)`
    - sym followed by `(` or `"` (no whitespace) → `(0 #juxt sym body)`
  - `;` line comments, whitespace handling.
  - Parse errors carry source offset (line + col).
- `marduk/tests/test_parser.py`:
  - Round-trip cases drawn from `vendor/reaver/src/plan/silly.plan` and
    `boot.plan` (top-of-file before macros take over).
  - All bracket types, strings, nats, syms, juxtaposition, comments, empty
    cells, whitespace-only cells.
  - Error cases: unterminated string, EOF in list, mismatched closer.

**End state:** `parser.parse_many(boot.plan-prefix)` produces the expected
`Val` tree.

### Phase 3 — Macro expander

Port `PlanAssembler.hs` lines 158–306 (`Macro` enum, `expand1`, `macroexpand`,
`lawExp`, `compileExpr`).

- `marduk/marduk/expander.py`:
  - `Env` — dict-shaped (Python dict) replacement for the Haskell BST. Key =
    name nat, value = `(val, is_macro)`. Order doesn't matter for our
    subset (no user macros).
  - `macroexpand(val: Val, env: Env, locals: list = []) -> Val`
  - `expand1(macro: Macro, val: Val, env: Env) -> Val` for each of:
    `#pin`, `#law`, `#app`, `#bind`. Skip `#macro`, `#export`, `@include`.
  - `law_exp(tag: Val, sig: Val, forms: list[Val], env: Env) -> Val` —
    builds the law's body via `compile_expr` over locals (self + args + binds).
  - `compile_expr(locals, val) -> Val` — the kal-body builder. References to
    locals become slot-index nats; references to globals become `(0 const)`
    embeddings; nested `(0 ...)` apps recurse.
  - `#bind` mutates the env (it's the side-effecting macro) and returns the
    `(0 1 nameNat)` "I just bound something" marker, matching PlanAssembler.
- `marduk/tests/test_expander.py`:
  - `#pin 5` → `P(5)` after eval.
  - `#law` round-trips for the `silly.plan` examples.
  - `#bind name expr` updates env and returns marker.
  - `#app f a b` reduces to the saturated application.

**End state:** the silly.plan / raw.plan / first-half-of-boot.plan examples
expand to the expected PLAN values.

### Phase 4 — Evaluator + CellResult

- `marduk/marduk/evaluator.py`:
  - `@dataclass class CellResult(value_text, value_html, error, decls_only)` —
    same shape as gallowglass's kernel.
  - `class MardukEvaluator(env=None, backend='evaluate')`:
    - `eval_cell(source: str) -> CellResult`
      - Parses magic lines (`%backend`, `%reset`, `%env`) and adjusts state.
      - `parse_many(remaining_source)` → list of forms.
      - For each form: `macroexpand → thunk-equivalent → backend()`.
        - "thunk-equivalent" mirrors PlanAssembler's `thunk`: `(0 …)` becomes
          an evaluated app; `(1 x)` is `x`; bare nat looks up env; otherwise
          recurse over arg vector.
      - Last non-bind form's result is the cell's value.
      - Bind-only cells render `bind <name>` summary lines (Jupyter "silent
        assignments" convention).
    - `reset()` — clears env (keeps prelude).
    - Recursion-limit bumping during evaluation, mirroring gallowglass's
      `_force` pattern.
- `marduk/tests/test_evaluator.py`:
  - Arithmetic: `(Add 2 3)` → `5` (with prelude loaded).
  - Identity / K combinator end-to-end.
  - Env accumulation across cells.
  - Error envelopes: parse stage, expand stage, eval stage.
  - Recursion limit surfaces as a structured error, not a Python crash.

**End state:** end-to-end pipeline works; identity / arithmetic / factorial
all evaluate correctly.

### Phase 5 — Renderer

- `marduk/marduk/render.py`:
  - `render_value(v: Val) -> tuple[str, str | None]` — returns `(text/plain,
    text/html)`.
  - text/plain: `42` for nats, `<…>` for pins, `{name arity body}` for laws
    (with `name` decoded via `nat_str`), `(f x)` for apps, depth-bounded.
  - text/html: token spans with inline-styled CSS classes (mirrors
    `bootstrap/value_render.HtmlFormatter` shape).
  - `pretty=True` flag collapses `Pin(Law)` to `<{name…}>` for readability.
- `marduk/tests/test_render.py`:
  - Each value type renders as expected.
  - HTML output is well-formed.
  - Depth bound prevents infinite recursion on cyclic-looking apps.

**End state:** kernel can produce nice MIME bundles.

### Phase 6 — Magics

- `marduk/marduk/magics.py`:
  - Parses leading `%` lines from cell source.
  - `%backend evaluate` / `%backend bevaluate` — switches the active backend
    for the rest of the cell.
  - `%reset` — clears env (keeps prelude).
  - `%env` — prints currently bound names.
  - Returns `(magic_directives, remaining_source)`.

**End state:** users can switch backends and inspect env mid-notebook.

### Phase 7 — Prelude

- `marduk/marduk/prelude.py`:
  - `load_prelude(env) -> None` — for each `(name, arity)` in
    `bplan_deps.PRELUDE_INTRINSICS`, build the boot.plan-style law:
    `Pin(Law(arity, name, ((Pin "B") ("Name" arg1...argN))))`, store in env.
  - `MardukEvaluator.__init__` calls `load_prelude(self.env)` by default;
    skip via `prelude=False` flag.

**End state:** `(Add 2 3)` works in any cell of a fresh notebook.

### Phase 8 — Kernel + CLI

- `marduk/marduk/kernel.py`:
  - `class MardukKernel(Kernel)` — `language_info` for `.plan`,
    `pygments_lexer='lisp'`. `do_execute` calls `evaluator.eval_cell`,
    emits MIME bundle, handles error envelope.
  - `_install_kernelspec(user=True, prefix=None)` — registers Marduk with
    Jupyter's `KernelSpecManager`. `display_name='Marduk (PLAN)'`.
  - `_kernel_main()` — launches via `IPKernelApp.launch_instance`. Lazy
    import of `ipykernel`.
  - `_cli_main(argv)` — `install` subcommand vs. default launch.
- `marduk/marduk/__main__.py` — `from .kernel import _cli_main; sys.exit(_cli_main(sys.argv))`.
- `marduk/tests/test_kernel_smoke.py`:
  - Module imports without ipykernel installed (lazy import works).
  - `_install_kernelspec` writes a kernel.json with the expected fields
    (test against tempdir prefix).

**End state:** `python -m marduk install` registers the kernel; opening a
notebook, the kernel evaluates cells.

### Phase 9 — Examples + tutorial

- `marduk/tests/fixtures/` — small PLAN programs covering id, K, S, factorial,
  Church bools, list cons/car/cdr.
- `marduk/examples/tour.ipynb` — worked notebook that walks through PLAN's
  three opcodes, then BPLAN ops, then a small program.
- `marduk/README.md` — full quickstart, magic reference, troubleshooting.

**End state:** a user can `pip install -e .`, register the kernel, open
`tour.ipynb`, and learn PLAN by running cells.

### Phase 10 — Initial commit + first push

- Stage everything, write the first commit message, push to
  `sigilante/marduk` `master`. Confirm with the user before the push.

## Out of scope (explicitly deferred)

- Reaver shell-out backend.
- `%trace` step-by-step reduction output.
- Tab completion / inspection.
- `#macro`, `#export`, `@include` macros (these need module loading
  semantics that aren't useful in a notebook).
- RPLAN ops (I/O) — the harness stubs them; no kernel surface needed.
- Pin content-addressing / BLAKE3 hashes — Marduk doesn't compute pin IDs,
  it just evaluates.
- Non-Python alternative implementations.

## Non-obvious risks

1. **`compile_expr` correctness** — the Haskell version handles the locals
   table (self, args, let-binds) and the `(0 …)` quoting / `#juxt` distinction
   carefully. A direct port is correct; getting clever is where bugs hide.
   Test against the let-binding examples in `raw.plan` early.
2. **Macro expansion order** — PlanAssembler walks `(0 …)` forms and
   resolves the head against env-bound *macros only* (the `True` flag in the
   BST node). Plain bound values do **not** trigger expansion. The Python port
   must preserve this.
3. **String vs. quoted-nat distinction** — `(#pin "B")` and `(#pin (strNat
   "B"))` evaluate to different things if you forget that `"B"` is `(1 66)`,
   not just `66`. The thunk step unwraps `(1 x)` to `x`; getting this wrong
   silently breaks BPLAN dispatch.
4. **Recursion ceiling** — Python's default limit hits before PLAN's
   `EVALUATE_DEPTH_LIMIT`. Bump it during evaluation, restore on return,
   like gallowglass's `_force`.
5. **Drift between vendored runtime and gallowglass source** — caught by
   `test_runtime_smoke.py` running before every commit. If the smoke test
   fails after a sync, the source has changed underneath us; investigate
   before re-syncing.

## Resuming

When a fresh session opens here:

1. Read this file (`PLAN.md`).
2. Read the three relevant memories: `project_marduk`, `project_marduk_naming`,
   `feedback_marduk_push_target`.
3. Confirm `vendor/marduk/` is empty git repo with `origin =
   sigilante/marduk` (`git remote -v`).
4. Start phase 1.
