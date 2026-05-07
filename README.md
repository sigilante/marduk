# Marduk

A Jupyter kernel for the [PLAN virtual machine](https://github.com/xocore-tech/PLAN).
Type Plan Asm in a cell, see the reduced PLAN value back.

Marduk is intended for tutorial use: learning what PLAN's three opcodes
(Pin / Law / Elim) do, exercising BPLAN's named primitives, and walking
through small programs (Church booleans, factorial, Y-combinator) one
reduction at a time.

## Status

Pre-alpha. The PLAN runtime is vendored and tested (phase 1, complete).
The parser, expander, evaluator, kernel, and prelude are under active
development. See [`PLAN.md`](PLAN.md) for the implementation plan and the
current phase. **Until phase 8 lands, the kernel module itself does not
exist** — the install steps below that depend on `python -m marduk` will
fail with `No module named marduk.__main__` until then.

## Install

### From PyPI (once published)

```bash
pip install marduk-plan
python -m marduk install      # registers the kernelspec with Jupyter
jupyter notebook              # "Marduk (PLAN)" appears in the kernel picker
```

`marduk-plan` is the PyPI package; `marduk` is the import name. The same
package supplies both the Python library and the Jupyter kernel — there is
no separate `marduk-kernel` distribution.

### From a clone (local development)

If you've cloned this repo (the typical case while Marduk is pre-1.0), do an
editable install so changes to the source tree take effect without
re-installing:

```bash
git clone git@github.com:sigilante/marduk.git
cd marduk
python -m venv .venv && source .venv/bin/activate     # optional but recommended
pip install -e '.[dev]'                                # installs ipykernel + pytest
pytest                                                 # confirm the runtime smoke test passes
```

To register the kernel with Jupyter so it appears in the notebook kernel
picker (requires phase 8):

```bash
python -m marduk install               # user-level install (writes to ~/.local/share/jupyter/kernels/marduk/)
# or
python -m marduk install --prefix .venv   # install only inside the active virtualenv
```

Verify the registration:

```bash
jupyter kernelspec list                 # "marduk" should appear
```

Launch:

```bash
jupyter notebook       # or: jupyter lab
```

In a new notebook, choose **"Marduk (PLAN)"** from the kernel picker. A
fresh notebook has the BPLAN op prelude pre-bound, so `(Add 2 3)` evaluates
to `5` in cell 1.

### Uninstall

```bash
jupyter kernelspec remove marduk        # remove kernelspec only
pip uninstall marduk-plan               # remove the package
```

## What's a cell?

A cell is a sequence of Plan Asm forms — the same syntax accepted by the
canonical Reaver parser
([`vendor/reaver/src/hs/PlanAssembler.hs`](https://github.com/xocore-tech/PLAN)),
minus `#macro`, `#export`, and `@include` (those need module-loading semantics
that don't make sense in a notebook).

Supported macros: `#pin`, `#law`, `#app`, `#bind`. The BPLAN op prelude
auto-loads on kernel start, so `(Add 2 3)` works in cell 1.

## Naming

"Marduk" is the project's name for both this Jupyter kernel and (eventually)
the standalone Python PLAN harness it embeds. See
[`MARDUK.md`](MARDUK.md) for design notes and naming history.

## License

MIT.
