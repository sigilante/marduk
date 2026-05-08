# marduk

A standalone Python runtime for the [PLAN virtual machine](https://github.com/xocore-tech/PLAN).

**Status:** pre-alpha. The package is a placeholder — the spec-faithful core, BPLAN op coverage, and jet overlay land in subsequent commits. Until then, callers that need a Python PLAN runtime use [`packages/plan-kernel/`](../plan-kernel/)'s vendored harness.

## Goals

- **Spec-faithful core.** A direct translation of [`vendor/reaver/doc/plan-spec.txt`](https://github.com/xocore-tech/PLAN) — `E`/`R`/`H`/`J`/`B`/`S`/`C`/`I`/`X` as Python functions over a `Thunk`-cell value type with update-in-place `force`. Strictness comes from the spec's `;` sequencing, not from Python's evaluation order.
- **Complete BPLAN op coverage.** All of Reaver's `op 66` named primitives, including the IO family that today's harness stubs.
- **Jet overlay.** An optional id-keyed performance layer; correctness lives in the spec-faithful interpreter regardless of jet presence.
- **Differential against Reaver.** A small Plan Asm corpus run on both Marduk and Reaver in CI.
- **No coupling to gallowglass.** Marduk imports nothing from gallowglass; gallowglass eventually depends on Marduk as a library.

## Non-goals

- Native-speed PLAN execution. Marduk is correctness-first; production workloads belong on Reaver.
- Hosting Reaver-itself-as-BPLAN. A future possibility once IO ops and performance reach the bar; not in scope for the initial release.

## Layout

```
packages/marduk/
├── marduk/         # Python package
│   └── __init__.py
├── tests/
└── pyproject.toml
```

## License

MIT.
