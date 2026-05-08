# Marduk

![](https://upload.wikimedia.org/wikipedia/commons/c/c3/Chaos_Monster_and_Sun_God.png)

A standalone Python runtime for the [PLAN virtual machine](https://github.com/xocore-tech/PLAN), plus a Jupyter kernel for tutorial / interactive use.

This repository is a monorepo following the structure of [`sigilante/pinochle`](https://github.com/sigilante/pinochle). Each `packages/<name>/` directory is independently installable and ships as its own PyPI distribution.

## Packages

| Path                         | PyPI dist     | Purpose                                                                |
|------------------------------|---------------|------------------------------------------------------------------------|
| [`packages/marduk/`](packages/marduk/)         | `marduk`      | Standalone PLAN/BPLAN runtime — spec-faithful core + jet overlay.      |
| [`packages/plan-kernel/`](packages/plan-kernel/) | `plan-kernel` | Jupyter kernel for PLAN. Type Plan Asm in a cell, see the reduced value back. |

`plan-kernel` consumes Marduk as its runtime backend.

## History

Both packages descend from a single Jupyter-kernel-only project that was originally called *Marduk*. As the runtime portion grew into a generally useful artifact in its own right, it took the name; the kernel was renamed to `plan-kernel`. See [`packages/marduk/README.md`](packages/marduk/README.md) for the runtime's design notes and [`packages/plan-kernel/README.md`](packages/plan-kernel/README.md) for kernel install / usage.
