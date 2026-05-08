"""Vendor-sync canary: imports the vendored runtime and exercises the
PLAN core opcode and BPLAN dispatch tables. If this fails after running
``scripts/sync_runtime.sh``, the upstream Gallowglass runtime has changed
shape — investigate before re-syncing.
"""

from plan_kernel.runtime import plan as plan_mod
from plan_kernel.runtime import bplan as bplan_mod
from plan_kernel.runtime import bplan_deps as bplan_deps_mod
from plan_kernel.runtime.plan import (
    A, L, P, N,
    is_nat, is_pin, is_law, is_app,
    evaluate,
    op, str_nat, nat_str,
    _BPLAN_OPCODE, _bplan_op,
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


def test_evaluate_nat_roundtrip():
    assert evaluate(N(5)) == 5


def test_evaluate_pin_roundtrip():
    assert evaluate(P(N(7))) == P(N(7))


def test_str_nat_roundtrip():
    assert nat_str(str_nat("Add")) == "Add"
    assert _BPLAN_OPCODE == str_nat("B") == 66


def test_bplan_add_dispatch():
    # Drive the BPLAN dispatch table directly: parts = [name_nat, arg1, arg2].
    result = _bplan_op([str_nat("Add"), N(2), N(3)])
    assert result == 5


def test_bplan_inc_dispatch():
    result = _bplan_op([str_nat("Inc"), N(41)])
    assert result == 42


def test_prelude_intrinsics_present():
    # PRELUDE_INTRINSICS is the {name: arity} table the kernel will iterate
    # in phase 7 to build boot.plan-style wrappers.
    intrinsics = bplan_deps_mod.PRELUDE_INTRINSICS
    assert intrinsics["Add"] == 2
    assert intrinsics["Mul"] == 2
    # Inc lives in CORE_PRIMITIVES, not PRELUDE_INTRINSICS, but ALL_DEPS
    # unions both — the kernel may need to walk it too.
    assert "Inc" in bplan_deps_mod.ALL_DEPS
