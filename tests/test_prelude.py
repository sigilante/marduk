"""Tests for ``marduk.prelude`` and its integration with ``MardukEvaluator``.

The prelude auto-loads BPLAN op wrappers (Add, Sub, Mul, Inc, Dec, Eq, ...)
so that arithmetic and primitive ops work in cell 1 of a fresh notebook.
"""

import pytest

from marduk.evaluator import MardukEvaluator
from marduk.expander import Env, eval_form
from marduk.parser import parse_many
from marduk.prelude import PRELUDE_NAMES, load_prelude
from marduk.runtime.bplan_deps import ALL_DEPS
from marduk.runtime.plan import is_law, is_pin, str_nat


# ---------------------------------------------------------------------------
# load_prelude — direct.
# ---------------------------------------------------------------------------

def test_load_prelude_returns_name_set():
    env = Env()
    names = load_prelude(env)
    assert isinstance(names, set)
    assert all(isinstance(n, int) for n in names)


def test_load_prelude_covers_all_deps():
    env = Env()
    names = load_prelude(env)
    expected = {str_nat(n) for n, arity in ALL_DEPS.items() if arity >= 1}
    assert names == expected


def test_prelude_names_constant_matches_load():
    env = Env()
    names = load_prelude(env)
    assert names == set(PRELUDE_NAMES)


def test_each_prelude_entry_is_pin_of_law():
    env = Env()
    load_prelude(env)
    for name, arity in ALL_DEPS.items():
        if arity < 1:
            continue
        entry = env.get(str_nat(name))
        assert entry is not None, f"{name} not bound"
        val, is_macro = entry
        assert is_macro is False
        assert is_pin(val), f"{name} is not a Pin"
        assert is_law(val.val), f"{name} pin doesn't wrap a Law"
        assert val.val.arity == arity, f"{name} arity mismatch"


# ---------------------------------------------------------------------------
# Arithmetic — the headline outcome of phase 7.
# ---------------------------------------------------------------------------

def test_add_in_fresh_notebook():
    ev = MardukEvaluator()
    assert ev.eval_cell("(Add 2 3)").value_text == "5"


def test_sub_clamps_at_zero():
    """`_b_sub` returns 0 when y >= x; confirm that surfaces."""
    ev = MardukEvaluator()
    assert ev.eval_cell("(Sub 5 3)").value_text == "2"
    assert ev.eval_cell("(Sub 3 5)").value_text == "0"


def test_mul_div_mod():
    ev = MardukEvaluator()
    assert ev.eval_cell("(Mul 6 7)").value_text == "42"
    assert ev.eval_cell("(Div 22 7)").value_text == "3"
    assert ev.eval_cell("(Mod 22 7)").value_text == "1"


def test_inc_dec():
    ev = MardukEvaluator()
    assert ev.eval_cell("(Inc 41)").value_text == "42"
    assert ev.eval_cell("(Dec 42)").value_text == "41"
    # Dec of 0 is 0 (saturating).
    assert ev.eval_cell("(Dec 0)").value_text == "0"


def test_comparison():
    ev = MardukEvaluator()
    # Eq returns 0 / 1.
    assert ev.eval_cell("(Eq 3 3)").value_text == "1"
    assert ev.eval_cell("(Eq 3 4)").value_text == "0"


def test_nested_arithmetic():
    """`(Add 1 (Mul 2 3))` exercises arithmetic composition."""
    ev = MardukEvaluator()
    assert ev.eval_cell("(Add 1 (Mul 2 3))").value_text == "7"


def test_introspection_ops():
    ev = MardukEvaluator()
    assert ev.eval_cell("(IsNat 5)").value_text == "1"
    assert ev.eval_cell("(IsNat (#pin 0))").value_text == "0"
    assert ev.eval_cell("(IsPin (#pin 0))").value_text == "1"


# ---------------------------------------------------------------------------
# prelude=False opt-out.
# ---------------------------------------------------------------------------

def test_no_prelude_means_arithmetic_unbound():
    ev = MardukEvaluator(prelude=False)
    result = ev.eval_cell("(Add 2 3)")
    assert result.error is not None
    assert result.error["stage"] == "expand"
    assert "unbound" in result.error["message"]


def test_no_prelude_env_is_empty():
    ev = MardukEvaluator(prelude=False)
    assert ev.env.names() == []


# ---------------------------------------------------------------------------
# reset() preserves prelude.
# ---------------------------------------------------------------------------

def test_reset_preserves_prelude():
    ev = MardukEvaluator()
    # Bind a user name, then reset.
    ev.eval_cell("(#bind k 5)")
    ev.reset()
    # Arithmetic still works after reset.
    assert ev.eval_cell("(Add 1 1)").value_text == "2"
    # User name is gone.
    assert str_nat("k") not in ev.env


def test_magic_reset_preserves_prelude():
    ev = MardukEvaluator()
    ev.eval_cell("(#bind k 5)")
    ev.eval_cell("%reset")
    assert ev.eval_cell("(Add 1 1)").value_text == "2"


def test_no_prelude_reset_keeps_env_empty():
    ev = MardukEvaluator(prelude=False)
    ev.eval_cell("(#bind k 5)")
    ev.reset()
    assert ev.env.names() == []


# ---------------------------------------------------------------------------
# %env filters prelude names.
# ---------------------------------------------------------------------------

def test_env_magic_hides_prelude_by_default():
    """A fresh notebook's `%env` should display "(env empty)", not the
    prelude's ~30 entries."""
    ev = MardukEvaluator()
    result = ev.eval_cell("%env")
    assert result.value_text == "(env empty)"


def test_env_magic_shows_user_bindings_only():
    ev = MardukEvaluator()
    ev.eval_cell("(#bind alpha 1) (#bind beta 2)")
    result = ev.eval_cell("%env")
    assert result.value_text == "alpha, beta"


def test_env_no_prelude_shows_all_names():
    """With the prelude opt-out, %env should show whatever the user binds —
    including names like `Add` that would normally be prelude-shadowed."""
    ev = MardukEvaluator(prelude=False)
    ev.eval_cell('(#bind Add 0)')   # User redefines `Add`.
    result = ev.eval_cell("%env")
    assert result.value_text == "Add"


# ---------------------------------------------------------------------------
# User can shadow prelude names.
# ---------------------------------------------------------------------------

def test_user_bind_shadows_prelude():
    ev = MardukEvaluator()
    # Override Add to return 0 always.
    ev.eval_cell('(#bind Add (#pin (#law "Add" (Add a b) 0)))')
    result = ev.eval_cell("(Add 2 3)")
    assert result.value_text == "0"
