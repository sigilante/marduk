# Marduk

A Jupyter kernel for the [PLAN virtual machine](https://github.com/xocore-tech/PLAN).
Type Plan Asm in a cell, see the reduced PLAN value back.

Marduk is intended for tutorial use: learning what PLAN's three opcodes
(Pin / Law / Elim) do, exercising BPLAN's named primitives, and walking
through small programs (Church booleans, factorial, Y-combinator) one
reduction at a time.

## Status

Pre-alpha. The runtime is vendored and tested; the parser, expander,
evaluator, and kernel are under active development. See
[`PLAN.md`](PLAN.md) for the implementation plan and current phase.

## Install (eventual)

```bash
pip install marduk-plan
python -m marduk install      # registers the kernelspec with Jupyter
jupyter notebook              # "Marduk (PLAN)" appears in the kernel picker
```

For development:

```bash
pip install -e '.[dev]'
pytest
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
