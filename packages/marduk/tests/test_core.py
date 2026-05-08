"""Tests for the spec-faithful PLAN core.

The tests fall into three groups:

1. **Smoke / rule coverage.** Each spec rule (A, R, L, B, C, X, F, E)
   has at least one direct test exercising the cases enumerated in the
   spec. These are the granularity at which to add tests when adding
   primitives or fixing rule bugs.
2. **Constructions.** End-to-end checks of the three core opcodes:
   Pin construction (``<0>``), Law construction (``<1>``), and Elim
   (``<2>``). Each verifies the result against a hand-rolled expected
   shape.
3. **Knot-tying.** Letrec patterns that exercise the ``Val.box`` cyclic
   update — the whole reason the spec uses an in-place force loop. If
   any of these regress, the box-mutation discipline in ``E`` and ``L``
   is broken and we'd see infinite recursion or wrong values.
"""

from __future__ import annotations

import pytest

from marduk import (
    Val, Hol, Nat, Pin, App, Law,
    evaluate, force,
    PlanError, PlanLoop,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def app(*xs: Val) -> Val:
    """Left-fold ``xs`` into an App spine: ``app(f, a, b)`` → ``App(App(f, a), b)``."""
    if not xs:
        raise ValueError("app: need at least one arg")
    out = xs[0]
    for x in xs[1:]:
        out = App(out, x)
    return out


# Pinned-nat dispatcher constants.
PLAN = Pin(Nat(0))     # <0> — core PLAN dispatcher
BPLAN = Pin(Nat(66))   # <66> — BPLAN dispatcher (not yet implemented)
RPLAN = Pin(Nat(82))   # <82> — RPLAN dispatcher (not yet implemented)


def pin_of(v: Val) -> Val:
    """Run the Pin-construction primitive: ``(<0> (0 v))`` → ``<v>``."""
    return evaluate(app(PLAN, app(Nat(0), v)))


def law_of(name: int, arity: int, body: Val) -> Val:
    """Run the Law-construction primitive: ``(<0> (1 a m b))`` → ``{a m b}``."""
    return evaluate(app(PLAN, app(Nat(1), Nat(arity), Nat(name), body)))


def elim(p: Val, l: Val, ap: Val, z: Val, m: Val, o: Val) -> Val:
    """Run Elim: ``(<0> (2 p l a z m o))``."""
    return evaluate(app(PLAN, app(Nat(2), p, l, ap, z, m, o)))


def vals_eq(x: Val, y: Val) -> bool:
    """Structural equality after forcing both sides to NF along the App spine."""
    force(x)
    force(y)
    if x.type != y.type:
        return False
    t = x.type
    if t == "nat":
        return x.nat == y.nat
    if t == "hol":
        return False  # holes are loops, never equal
    if t == "pin":
        return vals_eq(x.item, y.item)
    if t == "law":
        return (vals_eq(x.name, y.name)
                and vals_eq(x.args, y.args)
                and vals_eq(x.body, y.body))
    if t == "app":
        return vals_eq(x.head, y.head) and vals_eq(x.tail, y.tail)
    return False


# ---------------------------------------------------------------------------
# Group 1: spec rule smoke tests
# ---------------------------------------------------------------------------

class TestArity:
    """A: arity table per ``plan-spec.txt``."""

    def test_bare_nat_arity_is_zero(self):
        # New ABI: bare nats are data, never callable.
        from marduk.runtime.core import A
        for n in (0, 1, 2, 3, 66, 82, 1000):
            assert A(Nat(n)) == 0, f"Nat({n}) should have arity 0"

    def test_pinned_nat_arity_is_one(self):
        # ``A<i> = 1`` for pin'd-anything-not-law.
        from marduk.runtime.core import A
        for n in (0, 1, 2, 66, 82):
            assert A(Pin(Nat(n))) == 1

    def test_law_arity_is_declared(self):
        from marduk.runtime.core import A
        l = Law(Nat(0), Nat(3), Nat(0))
        assert A(l) == 3

    def test_pinned_law_arity_matches_inner(self):
        from marduk.runtime.core import A
        l = Law(Nat(0), Nat(2), Nat(0))
        assert A(Pin(l)) == 2

    def test_app_arity_decrements_clamped_at_zero(self):
        from marduk.runtime.core import A
        # <0> arity 1; (<0> x) arity 0; ((<0> x) y) still 0.
        assert A(PLAN) == 1
        assert A(App(PLAN, Nat(7))) == 0
        assert A(App(App(PLAN, Nat(7)), Nat(8))) == 0

    def test_hole_arity_raises(self):
        from marduk.runtime.core import A
        with pytest.raises(PlanLoop):
            A(Hol())


# ---------------------------------------------------------------------------
# Group 2: core construction primitives
# ---------------------------------------------------------------------------

class TestPinConstruction:
    """``S0(0 i) = Ei; <i>``."""

    def test_pin_a_nat(self):
        result = pin_of(Nat(7))
        assert result.type == "pin"
        assert result.item.type == "nat"
        assert result.item.nat == 7

    def test_pin_an_app(self):
        # An App that's just data (head is a bare nat, arity 0): pinning it
        # should preserve the App structure inside.
        inner = App(Nat(5), Nat(6))
        result = pin_of(inner)
        assert result.type == "pin"
        assert result.item.type == "app"

    def test_pin_only_forces_inner_to_whnf(self):
        # Pin a saturated App that *would* reduce on E. The inner gets
        # forced to WHNF — i.e. reduced to its result — and then wrapped.
        # If pin used full F instead of E, this would still pass; the
        # weaker check we actually have here is that pinning succeeds
        # without trying to recurse into pin contents on the way back.
        ident = law_of(name=0, arity=1, body=Nat(1))
        will_reduce_to_seven = App(ident, Nat(7))
        pinned = pin_of(will_reduce_to_seven)
        assert pinned.type == "pin"
        assert pinned.item.type == "nat" and pinned.item.nat == 7


class TestLawConstruction:
    """``S0(1 a m b) = Ea; J(Na+1)mb`` ⇒ ``{a m b}``."""

    def test_construct_a_law(self):
        # (<0> (1 1 0 0)) → {0 1 0} — a unary law named 0 with body 0.
        result = law_of(name=0, arity=1, body=Nat(0))
        assert result.type == "law"
        assert result.args.nat == 1
        assert result.name.nat == 0

    def test_law_arity_zero_crashes(self):
        with pytest.raises(PlanError):
            law_of(name=0, arity=0, body=Nat(0))

    def test_constructed_law_is_callable(self):
        # Law of arity 1 whose body is just $1 (its only argument): the
        # identity function. id 7 → 7.
        ident = law_of(name=0, arity=1, body=Nat(1))
        result = evaluate(App(ident, Nat(7)))
        assert result.type == "nat"
        assert result.nat == 7


class TestElim:
    """``S0(2 p l a z m o) = Eo; Cplazmo`` ⇒ unified eliminator on o."""

    def test_elim_on_zero_returns_z(self):
        # Send sentinel values for unused arms; only z should fire.
        z = Nat(99)
        result = elim(p=Nat(1), l=Nat(2), ap=Nat(3), z=z, m=Nat(5), o=Nat(0))
        assert result.type == "nat"
        assert result.nat == 99

    def test_elim_on_succ_returns_m_applied_to_pred(self):
        # o = Nat(5) → (m (5-1)). With m = identity-as-an-id-law, we'd get
        # 4 — but the simplest check is that the result is App(m, Nat(4)).
        m = Nat(7)  # not callable; we just check the produced shape
        result = elim(p=Nat(1), l=Nat(2), ap=Nat(3),
                      z=Nat(0), m=m, o=Nat(5))
        # Result should be App(m, Nat(4)) — but evaluate may try to step it
        # if m has arity. Since Nat(7) has arity 0, the App is stuck data.
        assert result.type == "app"
        assert result.head.nat == 7
        assert result.tail.nat == 4

    def test_elim_on_pin_returns_p_applied_to_inner(self):
        result = elim(p=Nat(7), l=Nat(2), ap=Nat(3),
                      z=Nat(0), m=Nat(5), o=Pin(Nat(42)))
        assert result.type == "app"
        assert result.head.nat == 7
        assert result.tail.nat == 42

    def test_elim_on_app_returns_a_applied_to_head_and_tail(self):
        # o = (App(Nat(8), Nat(9))) — bare-nat App, arity 0, just data.
        o_arg = App(Nat(8), Nat(9))
        result = elim(p=Nat(1), l=Nat(2), ap=Nat(7),
                      z=Nat(0), m=Nat(5), o=o_arg)
        # Expected: App(App(7, 8), 9)
        assert result.type == "app"
        assert result.head.type == "app"
        assert result.head.head.nat == 7
        assert result.head.tail.nat == 8
        assert result.tail.nat == 9

    def test_elim_on_law_returns_l_applied_to_components(self):
        l_arg = Law(Nat(11), Nat(2), Nat(99))
        result = elim(p=Nat(1), l=Nat(7), ap=Nat(3),
                      z=Nat(0), m=Nat(5), o=l_arg)
        # Expected: App(App(App(7, name=11), arity=2), body=99)
        # With Nat(7) arity 0, the whole thing is stuck data.
        assert result.type == "app"
        assert result.tail.nat == 99
        assert result.head.tail.nat == 2
        assert result.head.head.tail.nat == 11
        assert result.head.head.head.nat == 7


# ---------------------------------------------------------------------------
# Group 3: dispatcher boundaries (BPLAN / RPLAN not yet wired)
# ---------------------------------------------------------------------------

class TestUnimplementedDispatchers:
    """``<82>`` (RPLAN) raises NotImplementedError until its op table
    gets wired up. ``<66>`` (BPLAN) is wired — see ``test_bplan.py``."""

    def test_rplan_raises_not_implemented(self):
        with pytest.raises(NotImplementedError, match="RPLAN"):
            evaluate(app(RPLAN, app(Nat(0), Nat(1))))


# ---------------------------------------------------------------------------
# Group 4: combinators built from constructed laws (end-to-end)
# ---------------------------------------------------------------------------

class TestCombinators:
    """Small programs constructed via the law-construction primitive,
    exercising the full E/X/B/L/R pipeline."""

    def test_identity(self):
        # \x. x — a law of arity 1 whose body is the argument $1.
        ident = law_of(name=0, arity=1, body=Nat(1))
        result = evaluate(App(ident, Nat(42)))
        assert result.type == "nat" and result.nat == 42

    def test_k_combinator(self):
        # \a b. a — a law of arity 2 whose body is $1 (the first arg).
        k = law_of(name=0, arity=2, body=Nat(1))
        result = evaluate(app(k, Nat(7), Nat(99)))
        assert result.type == "nat" and result.nat == 7

    def test_k_combinator_returning_second(self):
        # \a b. b — body is $2.
        k2 = law_of(name=0, arity=2, body=Nat(2))
        result = evaluate(app(k2, Nat(7), Nat(99)))
        assert result.type == "nat" and result.nat == 99

    def test_law_self_reference(self):
        # \a. self — body is $0 (the law itself). Doesn't call itself,
        # just returns its own Val as data. Saturates and yields the law.
        self_returning = law_of(name=0, arity=1, body=Nat(0))
        result = evaluate(App(self_returning, Nat(5)))
        # The result is the law itself (since body $0 references position 0
        # which holds the self-Val).
        assert result.type == "law"


# ---------------------------------------------------------------------------
# Group 5: knot-tying — the whole reason for Val.box
# ---------------------------------------------------------------------------

class TestKnotTying:
    """Letrec / cyclic-environment patterns. If these regress, the
    cyclic-update discipline in ``E`` (``o.update(X(o, o))``) or ``L``
    (``I(...).update(R(n, e, v))``) is broken."""

    def test_let_binding_referenced_after_definition(self):
        # \x. let y = 9 in y    — body: (1 9 $2)
        # Built as: (#1 (quoted 9) $2) — i.e. App(App(Nat(1), App(Nat(0), Nat(9))), Nat(2))
        # Body refs: $0 = self, $1 = x, $2 = y.
        body = app(Nat(1), app(Nat(0), Nat(9)), Nat(2))
        f = law_of(name=0, arity=1, body=body)
        result = evaluate(App(f, Nat(5)))
        assert result.type == "nat" and result.nat == 9

    def test_let_binding_refers_to_argument(self):
        # \x. let y = x in y    — body: (1 $1 $2). $1 = x.
        body = app(Nat(1), Nat(1), Nat(2))
        f = law_of(name=0, arity=1, body=body)
        result = evaluate(App(f, Nat(13)))
        assert result.type == "nat" and result.nat == 13

    def test_cycle_unused_is_ok(self):
        # From Sol's PoC: a let-binding that references itself is fine
        # as long as it's not actually demanded. \a b. let c = 7 in
        # let d = d in c — body chain.
        # Bindings: c at slot 3, d at slot 4. Body returns $3.
        # Form: (1 (quoted 7) (1 $4 $3))
        body = app(Nat(1), app(Nat(0), Nat(7)),
                   app(Nat(1), Nat(4), Nat(3)))
        f = law_of(name=0, arity=2, body=body)
        result = evaluate(app(f, Nat(99), Nat(99)))
        assert result.type == "nat" and result.nat == 7


# ---------------------------------------------------------------------------
# Group 6: forcing discipline
# ---------------------------------------------------------------------------

class TestForcing:
    """E vs F: WHNF only forces the head; F walks the App spine."""

    def test_evaluate_is_idempotent_on_whnf_values(self):
        # Nats, pins, laws are all already WHNF; E should not change them.
        v = Nat(42)
        evaluate(v)
        assert v.type == "nat" and v.nat == 42

        p = Pin(Nat(7))
        evaluate(p)
        assert p.type == "pin" and p.item.nat == 7

    def test_force_walks_app_spine(self):
        # An App over identity that returns its arg: force should reduce
        # both head and tail of the resulting App spine.
        ident = law_of(name=0, arity=1, body=Nat(1))
        v = App(ident, App(ident, Nat(11)))
        force(v)
        # After full force: head has been forced, tail (which was
        # App(ident, Nat(11))) has been forced to Nat(11), so v should
        # now be Nat(11) at the top (since the outer App's head is ident
        # and applying it to its tail = Nat(11) gives Nat(11)).
        assert v.type == "nat" and v.nat == 11

    def test_force_does_not_recurse_into_pin(self):
        # Wrap something in a Pin and check that force leaves the pin's
        # interior alone — we shouldn't enter S0(0)'s contract by
        # accident.
        wrapped = App(law_of(name=0, arity=1, body=Nat(1)), Nat(5))
        # wrapped is a saturated App that reduces to Nat(5) under E.
        # Pinning gives <Nat(5)> after one E pass.
        pinned = pin_of(wrapped)
        force(pinned)
        # The pin should still be a pin; force doesn't unwrap pins.
        assert pinned.type == "pin"


# ---------------------------------------------------------------------------
# Group 7: depth — the E trampoline + raised recursion limit
# ---------------------------------------------------------------------------

class TestDepth:
    """Regression: ``E``'s saturation step is iterative (the spec's
    ``Eo`` after cyclic update is a Python ``while`` loop, not a
    recursive call). Combined with the import-time recursion-limit
    bump, linear-recursive PLAN of meaningful depth runs without
    stack exhaustion. If either of those pieces regresses, this test
    catches it."""

    def test_deep_self_application_via_identity(self):
        # Build identity directly and apply it 3000 times in a chain:
        # (id (id (id ... (id 7)))) — 3000 nested Apps, each saturating
        # one level. The trampoline turns each saturation step into a
        # loop iteration rather than a recursive call.
        ident = law_of(name=0, arity=1, body=Nat(1))
        v = Nat(7)
        for _ in range(3000):
            v = App(ident, v)
        result = evaluate(v)
        assert result.type == "nat" and result.nat == 7
