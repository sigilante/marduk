# Marduk

Python implementation of the PLAN Combinator Calculus with a Jupyter kernel for interactive evaluation.  Emulates the [Reaver](https://github.com/sol-plunder/reaver) system.

**Status:  Marduk successfully implements PLAN and the `plan` Jupyter kernel works.  While there may be bugfixes or minor QOL updates, the project nears completion.**

![](https://upload.wikimedia.org/wikipedia/commons/c/c3/Chaos_Monster_and_Sun_God.png)

This project consists of two packages:

1. `marduk`: Core library implementing PLAN evaluation.
2. `plan-kernel`: Jupyter kernel for interactive PLAN/BPLAN evaluation.

## Marduk - Core Library

Library supplying a Python implementation of the PLAN Combinator Calculus.

### Installation

```bash
git clone https://github.com/sigilante/marduk.git
pip install ./packages/plan
# or from GitHub:
pip install git+https://github.com/sigilante/marduk.git#subdirectory=packages/marduk
```

### Usage

```python
from marduk import plan, parse_noun

# Parse and evaluate Nock expressions
result = plan(42, parse_noun("[0 1]"))
print(result)  # 42

# Increment
result = plan(41, parse_noun("[4 0 1]"))
print(result)  # 42
```

See the [README](packages/marduk/README.md) for further details.

## PLAN Kernel

A Jupyter kernel for interactive PLAN evaluation.

### Installation

```bash
# Install the core library first
pip install marduk

# Then install the kernel
pip install plan-kernel
plan-kernel-install
```

### Usage

Start Jupyter:

```bash
jupyter notebook
```

Create a new notebook and select "PLAN" as the kernel.

```
:subject [1 2 3 4 5]
```

```
:formula [4 4 4 4 0 6]
```

See the [README](packages/plan_kernel/README.md) for further details and the [TUTORIAL](packages/plan_kernel/TUTORIAL.ipynb) for more examples of use.

## Examples

* TODO

## License

This project is licensed under the MIT License - see [LICENSE](./LICENSE) for details.

## Versions
