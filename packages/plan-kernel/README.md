# plan-kernel

![](https://upload.wikimedia.org/wikipedia/commons/c/c3/Chaos_Monster_and_Sun_God.png)

A Jupyter kernel for the [PLAN virtual machine](https://github.com/xocore-tech/PLAN).
Type Plan Asm in a cell, see the reduced PLAN value back.

plan-kernel is intended for tutorial use: learning what PLAN's three opcodes
(Pin / Law / Elim) do, exercising BPLAN's named primitives, and walking
through small programs (Church booleans, factorial, Y-combinator) one
reduction at a time.

## Status

Alpha. All nine phases of [`PLAN.md`](PLAN.md) are complete: vendored
runtime, Plan Asm parser, macro expander, cell-level evaluator,
structural renderer, cell magics, BPLAN op prelude, Jupyter kernel +
CLI, and a starter set of teaching fixtures + tour notebook. A fresh
notebook can evaluate `(Add 2 3)` in cell 1.

PyPI publication is the next step.

## Install

### From PyPI (once published)

```bash
pip install plan-kernel
python -m plan_kernel install      # registers the kernelspec with Jupyter
jupyter notebook              # "PLAN" appears in the kernel picker
```

`plan-kernel` is the PyPI package; `plan_kernel` is the import name. The same
package supplies both the Python library and the Jupyter kernel — there is
no separate `plan-kernel-kernel` distribution.

### From a clone (local development)

If you've cloned this repo (the typical case while plan-kernel is pre-1.0), do an
editable install so changes to the source tree take effect without
re-installing:

```bash
git clone git@github.com:sigilante/marduk.git
cd marduk/packages/plan-kernel
python -m venv .venv && source .venv/bin/activate     # optional but recommended
pip install -e '.[dev]'                                # installs ipykernel + pytest
pytest                                                 # confirm the runtime smoke test passes
```

To register the kernel with Jupyter so it appears in the notebook kernel
picker:

```bash
python -m plan_kernel install               # user-level install (writes to ~/.local/share/jupyter/kernels/plan-kernel/)
# or
python -m plan_kernel install --prefix .venv   # install only inside the active virtualenv
```

Verify the registration:

```bash
jupyter kernelspec list                 # "plan-kernel" should appear
```

Launch:

```bash
jupyter notebook       # or: jupyter lab
```

In a new notebook, choose **"PLAN"** from the kernel picker. A
fresh notebook has the BPLAN op prelude pre-bound, so `(Add 2 3)` evaluates
to `5` in cell 1.

### Uninstall

```bash
jupyter kernelspec remove plan-kernel        # remove kernelspec only
pip uninstall plan-kernel               # remove the package
```

## Quickstart

A cell is a sequence of Plan Asm forms. The result of the last non-bind
form displays; bind-only cells render `bind <name>` summary lines.

```text
(Add 2 3)
```

```text
5
```

Define a law and apply it:

```text
(#bind id
  (#pin
    (#law "id" (id x)
      x)))

(id 42)
```

```text
42
```

The K combinator and a use:

```text
(#bind k
  (#pin
    (#law "k" (k a b)
      a)))

(k 7 99)
```

```text
7
```

The fixtures in [`tests/fixtures/`](tests/fixtures/) cover identity,
K, S, arithmetic, `Elim` on a nat, and Church booleans — copy any of
them into a cell to see them run.

## What's a cell?

A cell is a sequence of Plan Asm forms — the same syntax accepted by the
canonical Reaver parser
([`vendor/reaver/src/hs/PlanAssembler.hs`](https://github.com/xocore-tech/PLAN)),
minus `#macro`, `#export`, and `@include` (those need module-loading semantics
that don't make sense in a notebook).

Supported macros: `#pin`, `#law`, `#app`, `#bind`. The BPLAN op prelude
auto-loads on kernel start, so `(Add 2 3)` works in cell 1.

## Magic reference

Magics live on lines that start with `%`, at the very top of the cell.
Comments and blank lines above them stop magic parsing — magics must
lead the cell body.

| Magic                     | Scope        | Effect                                                                  |
|---------------------------|--------------|-------------------------------------------------------------------------|
| `%backend evaluate`       | this cell    | Use the formal Python evaluator (default).                              |
| `%backend bevaluate`      | this cell    | Use the jet-aware evaluator. Faster for arithmetic-heavy programs.      |
| `%reset`                  | persistent   | Drop all user bindings. The BPLAN op prelude is reloaded.                |
| `%env`                    | read-only    | Display user bindings (sorted, comma-separated). Prelude names are filtered out. |

`%backend` reverts at end-of-cell. `%reset` is permanent until the next
`%reset`. `%env`'s output prepends to the cell's value text when the
cell also has a body.

## Troubleshooting

**`No module named 'plan_kernel'` when launching the kernel.** The kernel.json's
`argv` uses the Python interpreter that ran `plan-kernel install`. Reinstall
from the active venv: `pip install -e '.[dev]'` and `python -m plan_kernel install`.

**plan-kernel not in the kernel picker.** Confirm the install:
`jupyter kernelspec list` should show a `plan-kernel` row. If `--prefix .venv`
was used, only that venv's Jupyter sees it; install without `--prefix`
for a user-wide registration.

**`unbound: <name>` for a name that's clearly defined.** Macro expansion
runs before the body's evaluation, so a bind form `(#bind name expr)`
must appear *before* any reference to `name` in cell-execution order.
Within a cell, this is the form order; across cells, the binding from
cell N is in scope for cell N+1.

**Recursive laws hit `RecursionError`.** plan-kernel bumps Python's recursion
limit to 200K during evaluation — past that, the BPLAN harness's own
depth guard fires. Most tutorial-scale recursion is fine; deep
factorials or Y-combinator-driven loops may exhaust it.

**`%env` shows nothing.** It filters the BPLAN op prelude. Pass
`prelude=False` when constructing `PlanKernelEvaluator` programmatically to
see *all* names, or just rely on the filtered view in the kernel.

## Naming

This package was originally called *Marduk*. As the runtime portion grew
into a generally useful artifact in its own right, it took the name; the
kernel was renamed `plan-kernel` and the runtime now lives at
[`packages/marduk/`](../marduk/) in this monorepo. See
[`PLAN_KERNEL.md`](PLAN_KERNEL.md) for design notes.

## License

MIT.
