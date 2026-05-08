"""Tests for the BPLAN named-op dispatch (outer ``<66>``).

One test per op family — the per-op coverage matrix is in the op
implementations themselves; tests here verify the dispatch path,
arity checking, and a representative result for each family. Add a
test when you change semantics, not when you add a one-line port.
"""

from __future__ import annotations

import pytest

from marduk import (
    Val, Hol, Nat, Pin, App, Law,
    evaluate, force,
    PlanError,
)
from marduk.runtime.strnat import str_nat


def app(*xs: Val) -> Val:
    out = xs[0]
    for x in xs[1:]:
        out = App(out, x)
    return out


BPLAN = Pin(Nat(66))   # <66> — BPLAN dispatcher
PLAN = Pin(Nat(0))


def call(name: str, *args: Val) -> Val:
    """Build and evaluate ``(<66> (name args...))``."""
    inner = app(Nat(str_nat(name)), *args) if args else Nat(str_nat(name))
    return evaluate(app(BPLAN, inner))


def n(v: Val) -> int:
    """Convenience: extract the nat value (assumes already forced)."""
    assert v.type == "nat", f"expected nat, got {v}"
    return v.nat


# ---------------------------------------------------------------------------
# Dispatch boundary
# ---------------------------------------------------------------------------

class TestDispatch:

    def test_unknown_op_raises_not_implemented(self):
        with pytest.raises(NotImplementedError, match="ZebraOp"):
            call("ZebraOp", Nat(1))

    def test_arity_mismatch_raises_plan_error(self):
        # Add takes 2 args; supplying 1 should error before the body runs.
        # We need to force the saturated form — Add expects exactly 2 args
        # in the spine. With 1, the dispatch detects mismatch.
        with pytest.raises(PlanError, match="expected 2 args"):
            call("Add", Nat(1))


# ---------------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------------

class TestArithmetic:

    def test_inc(self):
        assert n(call("Inc", Nat(41))) == 42

    def test_dec_clamps_at_zero(self):
        assert n(call("Dec", Nat(5))) == 4
        assert n(call("Dec", Nat(0))) == 0

    def test_add(self):
        assert n(call("Add", Nat(2), Nat(3))) == 5

    def test_sub_saturates(self):
        assert n(call("Sub", Nat(10), Nat(3))) == 7
        assert n(call("Sub", Nat(3), Nat(10))) == 0

    def test_mul(self):
        assert n(call("Mul", Nat(6), Nat(7))) == 42

    def test_div_by_zero_returns_zero(self):
        assert n(call("Div", Nat(10), Nat(3))) == 3
        assert n(call("Div", Nat(10), Nat(0))) == 0

    def test_mod_by_zero_returns_zero(self):
        assert n(call("Mod", Nat(10), Nat(3))) == 1
        assert n(call("Mod", Nat(10), Nat(0))) == 0

    def test_shifts(self):
        assert n(call("Lsh", Nat(1), Nat(4))) == 16
        assert n(call("Rsh", Nat(16), Nat(2))) == 4


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

class TestComparison:

    def test_eq_ne(self):
        assert n(call("Eq", Nat(3), Nat(3))) == 1
        assert n(call("Eq", Nat(3), Nat(4))) == 0
        assert n(call("Ne", Nat(3), Nat(3))) == 0
        assert n(call("Ne", Nat(3), Nat(4))) == 1

    def test_lt_le_gt_ge(self):
        assert n(call("Lt", Nat(3), Nat(5))) == 1
        assert n(call("Le", Nat(3), Nat(3))) == 1
        assert n(call("Gt", Nat(5), Nat(3))) == 1
        assert n(call("Ge", Nat(3), Nat(3))) == 1

    def test_cmp_three_way(self):
        assert n(call("Cmp", Nat(3), Nat(5))) == 0  # LT
        assert n(call("Cmp", Nat(5), Nat(5))) == 1  # EQ
        assert n(call("Cmp", Nat(7), Nat(5))) == 2  # GT


# ---------------------------------------------------------------------------
# Boolean / control
# ---------------------------------------------------------------------------

class TestBooleanControl:

    def test_truth(self):
        assert n(call("Truth", Nat(0))) == 0
        assert n(call("Truth", Nat(7))) == 1

    def test_or(self):
        # Or x y: if x is zero return y, else x.
        assert n(call("Or", Nat(0), Nat(7))) == 7
        assert n(call("Or", Nat(3), Nat(7))) == 3

    def test_and(self):
        # And x y: if x is zero return 0, else y.
        assert n(call("And", Nat(0), Nat(7))) == 0
        assert n(call("And", Nat(3), Nat(7))) == 7

    def test_if(self):
        # If c t e: if c is non-zero return t, else e.
        assert n(call("If", Nat(1), Nat(7), Nat(99))) == 7
        assert n(call("If", Nat(0), Nat(7), Nat(99))) == 99

    def test_ifz(self):
        # Ifz c t e: if c is zero return t, else e.
        assert n(call("Ifz", Nat(0), Nat(7), Nat(99))) == 7
        assert n(call("Ifz", Nat(1), Nat(7), Nat(99))) == 99


# ---------------------------------------------------------------------------
# Bit / byte ops
# ---------------------------------------------------------------------------

class TestBitOps:

    def test_test_set_clear(self):
        assert n(call("Test", Nat(0), Nat(0b101))) == 1
        assert n(call("Test", Nat(1), Nat(0b101))) == 0
        assert n(call("Set", Nat(1), Nat(0b101))) == 0b111
        assert n(call("Clear", Nat(0), Nat(0b101))) == 0b100

    def test_bex(self):
        assert n(call("Bex", Nat(0))) == 1
        assert n(call("Bex", Nat(8))) == 256

    def test_nib_load8(self):
        # 0xABCD: nibbles are [D, C, B, A] little-endian.
        assert n(call("Nib", Nat(0), Nat(0xABCD))) == 0xD
        assert n(call("Nib", Nat(1), Nat(0xABCD))) == 0xC
        # 0x1234: bytes are [0x34, 0x12].
        assert n(call("Load8", Nat(0), Nat(0x1234))) == 0x34
        assert n(call("Load8", Nat(1), Nat(0x1234))) == 0x12

    def test_store8(self):
        # Replace byte 0 of 0x1234 with 0xAB → 0x12AB.
        assert n(call("Store8", Nat(0), Nat(0xAB), Nat(0x1234))) == 0x12AB

    def test_trunc(self):
        assert n(call("Trunc8", Nat(0x1FF))) == 0xFF
        assert n(call("Trunc16", Nat(0x1FFFF))) == 0xFFFF
        assert n(call("Trunc", Nat(4), Nat(0xABC))) == 0xC

    def test_bits_bytes(self):
        assert n(call("Bits", Nat(0))) == 0
        assert n(call("Bits", Nat(1))) == 1
        assert n(call("Bits", Nat(7))) == 3
        assert n(call("Bytes", Nat(0xFF))) == 1
        assert n(call("Bytes", Nat(0x100))) == 2


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------

class TestIntrospection:

    def test_type_tags(self):
        assert n(call("Type", Nat(0))) == 0
        assert n(call("Type", Pin(Nat(0)))) == 1
        assert n(call("Type", Law(Nat(0), Nat(1), Nat(0)))) == 2
        assert n(call("Type", App(Nat(0), Nat(0)))) == 3

    def test_is_predicates(self):
        assert n(call("IsNat", Nat(0))) == 1
        assert n(call("IsNat", Pin(Nat(0)))) == 0
        assert n(call("IsPin", Pin(Nat(0)))) == 1
        assert n(call("IsLaw", Law(Nat(0), Nat(1), Nat(0)))) == 1
        assert n(call("IsApp", App(Nat(0), Nat(0)))) == 1

    def test_arity_name_body(self):
        l = Law(Nat(42), Nat(3), Nat(99))
        assert n(call("Arity", l)) == 3
        assert n(call("Name", l)) == 42
        assert n(call("Body", l)) == 99
        # Non-laws return 0.
        assert n(call("Arity", Nat(7))) == 0

    def test_unpin(self):
        result = call("Unpin", Pin(Nat(7)))
        assert n(result) == 7
        # Non-pin: Reaver returns N 0.
        assert n(call("Unpin", Nat(99))) == 0

    def test_sz_app_spine(self):
        # A two-element list ``Cons 0 (Cons 1 nil)`` shaped as
        # App(App(N(0), v0), v1) has spine [N(0), v0, v1] — size 2.
        v = App(App(Nat(0), Nat(7)), Nat(8))
        assert n(call("Sz", v)) == 2
        # Three-element: App(App(App(N(0), a), b), c) — size 3.
        v3 = App(App(App(Nat(0), Nat(1)), Nat(2)), Nat(3))
        assert n(call("Sz", v3)) == 3

    def test_sz_non_app_is_zero(self):
        assert n(call("Sz", Nat(99))) == 0
        assert n(call("Sz", Pin(Nat(7)))) == 0


class TestDiagnostics:

    def test_nil_recognises_zero(self):
        assert n(call("Nil", Nat(0))) == 1
        assert n(call("Nil", Nat(1))) == 0
        assert n(call("Nil", Pin(Nat(0)))) == 0
        assert n(call("Nil", App(Nat(0), Nat(0)))) == 0

    def test_trace_returns_second_arg(self, capsys):
        # Trace writes its first arg via dump() to stderr, returns the
        # second. We don't pin down the exact stderr formatting (it
        # differs from Reaver's showVal); we just check the return
        # value is the second arg and that *something* was emitted.
        result = call("Trace", Nat(42), Nat(99))
        assert n(result) == 99
        captured = capsys.readouterr()
        assert "42" in captured.err


# ---------------------------------------------------------------------------
# Sequencing / strict apply
# ---------------------------------------------------------------------------

class TestSeqApply:

    def test_seq(self):
        assert n(call("Seq", Nat(99), Nat(7))) == 7
        assert n(call("Seq2", Nat(1), Nat(2), Nat(3))) == 3
        assert n(call("Seq3", Nat(1), Nat(2), Nat(3), Nat(4))) == 4

    def test_sap(self):
        # Sap (id) 7 → 7.  Build id via the inner-op-1 Law construction.
        ident = evaluate(app(PLAN, app(Nat(1), Nat(1), Nat(0), Nat(1))))
        result = call("Sap", ident, Nat(7))
        assert n(result) == 7

    def test_sap2(self):
        # K combinator: \a b. a — body $1.
        k = evaluate(app(PLAN, app(Nat(1), Nat(2), Nat(0), Nat(1))))
        result = call("Sap2", k, Nat(7), Nat(99))
        assert n(result) == 7


# ---------------------------------------------------------------------------
# Construction aliases
# ---------------------------------------------------------------------------

class TestConstructionAliases:
    """Pin/Law/Elim are reachable both as inner-op-0/1/2 of <0> and as
    named primitives via <66>. Both paths should produce the same result."""

    def test_pin_via_op66(self):
        result = call("Pin", Nat(42))
        assert result.type == "pin"
        assert n(result.item) == 42

    def test_law_via_op66(self):
        # Law name=0 arity=1 body=$1 — identity.
        result = call("Law", Nat(1), Nat(0), Nat(1))
        assert result.type == "law"
        assert n(result.args) == 1
        assert n(evaluate(App(result, Nat(99)))) == 99

    def test_elim_via_op66_dispatches_on_nat(self):
        result = call("Elim",
                      Nat(1), Nat(2), Nat(3),    # p, l, ap
                      Nat(99),                    # z (returned for nat 0)
                      Nat(5),                     # m
                      Nat(0))                     # o
        assert n(result) == 99


# ---------------------------------------------------------------------------
# Small Case dispatchers (Case2..Case16)
# ---------------------------------------------------------------------------

class TestSmallCases:

    def test_case2(self):
        # Case2 picks branch_0 if x==0, else fb.
        assert n(call("Case2", Nat(0), Nat(7), Nat(99))) == 7
        assert n(call("Case2", Nat(1), Nat(7), Nat(99))) == 99
        assert n(call("Case2", Nat(50), Nat(7), Nat(99))) == 99

    def test_case3(self):
        # Case3 picks branch_0/1 if x in {0,1}, else fb.
        assert n(call("Case3", Nat(0), Nat(10), Nat(20), Nat(99))) == 10
        assert n(call("Case3", Nat(1), Nat(10), Nat(20), Nat(99))) == 20
        assert n(call("Case3", Nat(2), Nat(10), Nat(20), Nat(99))) == 99

    def test_case16(self):
        # 15 branches + fallback. Pick branch 7.
        branches = [Nat(i * 10) for i in range(15)]
        fb = Nat(999)
        result = call("Case16", Nat(7), *branches, fb)
        assert n(result) == 70
        result = call("Case16", Nat(20), *branches, fb)
        assert n(result) == 999


# ---------------------------------------------------------------------------
# Force
# ---------------------------------------------------------------------------

class TestForceOp:

    def test_force_walks_app_spine(self):
        ident = evaluate(app(PLAN, app(Nat(1), Nat(1), Nat(0), Nat(1))))
        v = App(ident, App(ident, Nat(11)))
        result = call("Force", v)
        # After force, v has reduced through the App spine to Nat(11).
        assert n(result) == 11
