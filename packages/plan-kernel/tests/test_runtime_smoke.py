"""Smoke test: Marduk runtime is reachable through plan-kernel's shim.

After Phase E (the Marduk swap), plan-kernel no longer vendors a copy
of the runtime from gallowglass — the runtime is :mod:`marduk.runtime`,
exposed through a thin compatibility shim at
``plan_kernel.runtime.plan``. This test confirms the shim's legacy API
names still resolve and that they're actually wired to Marduk.
"""

from plan_kernel.runtime import plan as plan_mod
from plan_kernel.runtime import bplan as bplan_mod
from plan_kernel.runtime import bplan_deps as bplan_deps_mod
from plan_kernel.runtime.plan import (
    A, L, P, N,
    is_nat, is_pin, is_law, is_app,
    evaluate,
    str_nat, nat_str,
)


def test_imports_resolve():
    assert plan_mod is not None
    assert bplan_mod is not None
    assert bplan_deps_mod is not None
    assert hasattr(bplan_mod, "bevaluate")
    assert hasattr(bplan_deps_mod, "PRELUDE_INTRINSICS")


def test_constructors():
    assert is_nat(N(5))
    assert is_pin(P(N(0)))
    assert is_law(L(2, N(0), N(0)))
    assert is_app(A(N(0), N(1)))


def test_evaluate_nat_is_idempotent():
    v = N(5)
    evaluate(v)
    assert is_nat(v) and v.nat == 5


def test_evaluate_pin_is_idempotent():
    v = P(N(7))
    evaluate(v)
    assert is_pin(v) and v.item.nat == 7


def test_str_nat_roundtrip():
    assert nat_str(str_nat("Add")) == "Add"
    assert str_nat("B") == 66


def test_prelude_intrinsics_present():
    # PRELUDE_INTRINSICS is the {name: arity} table the kernel uses to
    # build boot.plan-style wrappers.
    intrinsics = bplan_deps_mod.PRELUDE_INTRINSICS
    assert intrinsics["Add"] == 2
    assert intrinsics["Mul"] == 2
    # Inc lives in CORE_PRIMITIVES, not PRELUDE_INTRINSICS, but ALL_DEPS
    # unions both.
    assert "Inc" in bplan_deps_mod.ALL_DEPS
