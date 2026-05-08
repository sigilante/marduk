"""Tests for the optional jet overlay.

Three concerns:

1. **Registration mechanics** — register / lookup / clear / arity
   protection / GC pinning.
2. **Dispatch** — when X reaches a saturated Law with a registered
   jet, the jet runs (and its result propagates correctly).
3. **Flag** — ``set_jets(False)`` makes the runtime ignore the
   registry and run the spec path even for jetted laws.

The differential-testing pattern: define a Law via ``#law``, register
a jet whose result *intentionally differs* from the spec body, then
verify the answer changes when jets are toggled. This proves the flag
actually controls the dispatch.
"""

from __future__ import annotations

import pytest

from marduk import (
    App, Law, Nat, Pin, Val,
    evaluate,
    register_jet, lookup_jet, clear_jets,
    set_jets, jets_enabled,
)


PLAN = Pin(Nat(0))


def app(*xs: Val) -> Val:
    out = xs[0]
    for x in xs[1:]:
        out = App(out, x)
    return out


def make_identity_law() -> Val:
    """Identity law via the inner-op-1 construction primitive."""
    return evaluate(app(PLAN, app(Nat(1), Nat(1), Nat(0), Nat(1))))


def make_double_law() -> Val:
    """A doubler — body ``(0 (0 BPLAN_pin) inner)`` calling Add x x."""
    from marduk.runtime.strnat import str_nat
    bplan = Pin(Nat(66))
    add_name = Nat(str_nat("Add"))
    # body: (0 (0 BPLAN) (0 (0 (0 ADD_NAME) 1) 1))
    inner = App(App(Nat(0),
                    App(App(Nat(0), App(Nat(0), add_name)), Nat(1))),
                Nat(1))
    body = App(App(Nat(0), App(Nat(0), bplan)), inner)
    return evaluate(app(PLAN, app(Nat(1), Nat(1), Nat(0), body)))


@pytest.fixture(autouse=True)
def _reset_jets():
    """Each test starts with a clean registry and jets enabled."""
    clear_jets()
    set_jets(True)
    yield
    clear_jets()
    set_jets(True)


# ---------------------------------------------------------------------------
# Registration mechanics
# ---------------------------------------------------------------------------

class TestRegistry:

    def test_register_and_lookup(self):
        ident = make_identity_law()
        register_jet(ident, lambda x: x)
        fn = lookup_jet(ident)
        assert fn is not None

    def test_lookup_missing_returns_none(self):
        ident = make_identity_law()
        # No registration.
        assert lookup_jet(ident) is None

    def test_register_rejects_non_law(self):
        with pytest.raises(ValueError, match="expected a Law"):
            register_jet(Nat(0), lambda x: x)
        with pytest.raises(ValueError, match="expected a Law"):
            register_jet(Pin(Nat(0)), lambda x: x)

    def test_re_register_replaces_previous(self):
        ident = make_identity_law()
        register_jet(ident, lambda x: x)
        sentinel = Nat(99)
        register_jet(ident, lambda x: sentinel)
        assert lookup_jet(ident)(Nat(7)) is sentinel

    def test_clear_drops_registrations(self):
        ident = make_identity_law()
        register_jet(ident, lambda x: x)
        clear_jets()
        assert lookup_jet(ident) is None


# ---------------------------------------------------------------------------
# Dispatch — jets fire on saturated law evaluation
# ---------------------------------------------------------------------------

class TestDispatch:

    def test_jet_fires_on_saturation(self):
        """A registered jet runs in place of the spec body."""
        ident = make_identity_law()
        # Spec body returns the arg unchanged. Register a jet that
        # *intentionally returns a different value* so we can detect
        # which path ran. (The interpreter would return Nat(7); the
        # jet returns Nat(999).)
        register_jet(ident, lambda _x: Nat(999))
        result = evaluate(App(ident, Nat(7)))
        assert result.type == "nat" and result.nat == 999

    def test_jet_args_arrive_in_order(self):
        """Multi-arg laws: the jet sees args in declaration order."""
        # K combinator (arity 2) — body returns $1 (first arg).
        k = evaluate(app(PLAN, app(Nat(1), Nat(2), Nat(0), Nat(1))))
        seen = []
        def k_jet(a, b):
            seen.append((a, b))
            return a
        register_jet(k, k_jet)
        result = evaluate(app(k, Nat(7), Nat(99)))
        assert seen == [(Nat(7), Nat(99))]
        assert result.type == "nat" and result.nat == 7

    def test_jet_via_pinned_law_also_fires(self):
        """A Pin around the jetted law still routes through the jet —
        the jet check sees the inner Law value."""
        ident = make_identity_law()
        register_jet(ident, lambda _x: Nat(999))
        # Wrap in a pin so X enters via the pin'd-law arm.
        pin_ident = Pin(ident)
        result = evaluate(App(pin_ident, Nat(7)))
        assert result.type == "nat" and result.nat == 999


# ---------------------------------------------------------------------------
# Flag — set_jets(False) forces the spec path
# ---------------------------------------------------------------------------

class TestFlag:

    def test_default_is_enabled(self):
        # Note: the autouse fixture calls set_jets(True) at start, but
        # the module-level default is also True. Verify.
        assert jets_enabled() is True

    def test_disabling_skips_jet_dispatch(self):
        """With jets disabled, the spec path runs even when a jet is
        registered. The K combinator's body returns $1 (first arg);
        the jet (deliberately wrong) returns Nat(999). Differential
        check: jets-on returns 999, jets-off returns 7."""
        k = evaluate(app(PLAN, app(Nat(1), Nat(2), Nat(0), Nat(1))))
        register_jet(k, lambda _a, _b: Nat(999))

        # Default (jets on): jet wins.
        assert jets_enabled() is True
        v_jetted = evaluate(app(k, Nat(7), Nat(99)))
        assert v_jetted.nat == 999

        # Re-evaluate the same form fresh under jets-off to see the
        # spec body run.
        set_jets(False)
        try:
            v_spec = evaluate(app(k, Nat(7), Nat(99)))
            assert v_spec.nat == 7
        finally:
            set_jets(True)

    def test_lookup_returns_none_when_disabled(self):
        ident = make_identity_law()
        register_jet(ident, lambda x: x)
        assert lookup_jet(ident) is not None
        set_jets(False)
        try:
            assert lookup_jet(ident) is None
        finally:
            set_jets(True)
        # And re-enabled, we see it again.
        assert lookup_jet(ident) is not None


# ---------------------------------------------------------------------------
# Differential — jet result must equal spec result for a correct jet
# ---------------------------------------------------------------------------

class TestDifferential:
    """A jet whose implementation matches the spec body should produce
    the same answer regardless of the flag. This is the test you'd
    extend when adding a new jet to a real codebase."""

    def test_correct_jet_matches_spec(self):
        # Doubler: spec body computes Add x x; jet does the same in
        # native Python.
        doubler = make_double_law()

        def doubler_jet(x):
            evaluate(x)
            return Nat(x.nat * 2)

        register_jet(doubler, doubler_jet)

        # Build the same call twice — once jetted, once spec-only —
        # and verify the answers match.
        v1 = evaluate(App(doubler, Nat(21)))
        set_jets(False)
        try:
            v2 = evaluate(App(doubler, Nat(21)))
        finally:
            set_jets(True)

        assert v1.type == "nat" and v2.type == "nat"
        assert v1.nat == v2.nat == 42
