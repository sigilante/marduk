"""Tests for ``plan_kernel.evaluator`` — cell-level driver.

Drives ``PlanKernelEvaluator.eval_cell`` end-to-end against representative cell
shapes (silent, expression, bind-only, mixed) and confirms the error
envelopes for each pipeline stage. The placeholder structural renderer used
in phase 4 emits decimal nats and structural ``(fun arg)`` / ``<pin>`` /
``{name arity body}`` forms — phase 5's renderer will replace it.
"""

import pytest

from plan_kernel.evaluator import CellResult, PlanKernelEvaluator
from plan_kernel.expander import Env
from plan_kernel.runtime.plan import str_nat


# ---------------------------------------------------------------------------
# Silent cells.
# ---------------------------------------------------------------------------

def test_empty_source_is_silent():
    ev = PlanKernelEvaluator()
    assert ev.eval_cell("") == CellResult(decls_only=True)


def test_whitespace_only_source_is_silent():
    ev = PlanKernelEvaluator()
    assert ev.eval_cell("   \n  \t").decls_only is True


def test_comment_only_source_is_silent():
    ev = PlanKernelEvaluator()
    result = ev.eval_cell("; just a comment\n;; and another")
    assert result.decls_only is True


# ---------------------------------------------------------------------------
# Expression cells.
# ---------------------------------------------------------------------------

def test_single_nat_literal():
    ev = PlanKernelEvaluator()
    result = ev.eval_cell("42")
    assert result.value_text == "42"
    assert result.error is None


def test_zero_literal():
    ev = PlanKernelEvaluator()
    assert ev.eval_cell("0").value_text == "0"


def test_identity_law_applied():
    """`(#bind id (#pin (#law "id" (id x) x))) (id 7)` should display 7."""
    ev = PlanKernelEvaluator()
    result = ev.eval_cell(
        '(#bind id (#pin (#law "id" (id x) x))) (id 7)'
    )
    assert result.value_text == "7"
    assert result.error is None


def test_k_combinator():
    """`K x y = x` — first arg is returned."""
    ev = PlanKernelEvaluator()
    result = ev.eval_cell(
        '(#bind k (#pin (#law "k" (k a b) a))) (k 3 99)'
    )
    assert result.value_text == "3"


def test_k_combinator_second_form():
    """`(#law "snd" (snd a b) b)` returns its second arg."""
    ev = PlanKernelEvaluator()
    result = ev.eval_cell(
        '(#bind snd (#pin (#law "snd" (snd a b) b))) (snd 3 99)'
    )
    assert result.value_text == "99"


# ---------------------------------------------------------------------------
# Bind summaries.
# ---------------------------------------------------------------------------

def test_single_bind_returns_summary():
    ev = PlanKernelEvaluator()
    result = ev.eval_cell('(#bind a 1)')
    assert result.value_text == "bind a"
    assert result.error is None


def test_multiple_binds_return_multiline_summary():
    ev = PlanKernelEvaluator()
    result = ev.eval_cell('(#bind a 1) (#bind b 2) (#bind c 3)')
    assert result.value_text == "bind a\nbind b\nbind c"


def test_trailing_bind_shows_summary_not_expression():
    """`(id 7) (#bind k 5)` — last form is a bind, so the cell shows summary."""
    ev = PlanKernelEvaluator()
    result = ev.eval_cell(
        '(#bind id (#pin (#law "id" (id x) x))) '
        '(id 7) (#bind k 5)'
    )
    # Two bind summaries: id and k.
    assert result.value_text == "bind id\nbind k"


def test_bind_then_expression_shows_value():
    """`(#bind k 5) k` — last form is non-bind, so the value displays."""
    ev = PlanKernelEvaluator()
    result = ev.eval_cell('(#bind k 5) k')
    assert result.value_text == "5"


# ---------------------------------------------------------------------------
# Env accumulation across cells.
# ---------------------------------------------------------------------------

def test_env_accumulates_across_cells():
    ev = PlanKernelEvaluator()
    r1 = ev.eval_cell('(#bind id (#pin (#law "id" (id x) x)))')
    assert r1.value_text == "bind id"
    # Cell 2 references the binding from cell 1.
    r2 = ev.eval_cell('(id 42)')
    assert r2.value_text == "42"


def test_reset_clears_env():
    ev = PlanKernelEvaluator()
    ev.eval_cell('(#bind k 5)')
    assert str_nat("k") in ev.env
    ev.reset()
    assert str_nat("k") not in ev.env


def test_external_env_is_used():
    env = Env()
    env.put(str_nat("answer"), 42)
    ev = PlanKernelEvaluator(env=env)
    result = ev.eval_cell("answer")
    assert result.value_text == "42"


# ---------------------------------------------------------------------------
# Pin / Law structural display via the placeholder renderer.
# ---------------------------------------------------------------------------

def test_pin_renders_with_angle_brackets():
    ev = PlanKernelEvaluator()
    result = ev.eval_cell("(#pin 5)")
    assert result.value_text == "<5>"


def test_law_renders_with_curly_braces():
    """Just confirm the placeholder shape — phase 5 prettifies."""
    ev = PlanKernelEvaluator()
    result = ev.eval_cell('(#law "id" (id x) x)')
    # The body (slot 1) renders as "1"; tag is the strNat of "id".
    assert result.value_text.startswith("{")
    assert result.value_text.endswith("}")
    assert " 1 1}" in result.value_text   # arity 1, body N(1)


# ---------------------------------------------------------------------------
# Error envelopes.
# ---------------------------------------------------------------------------

def test_parse_error_returns_envelope():
    ev = PlanKernelEvaluator()
    result = ev.eval_cell('"unterminated')
    assert result.error is not None
    assert result.error["stage"] == "parse"
    assert "unterminated string" in result.error["message"]
    assert result.error["loc"]["line"] == 1
    assert result.value_text is None


def test_expand_error_returns_envelope():
    ev = PlanKernelEvaluator()
    result = ev.eval_cell("undefined_symbol")
    assert result.error is not None
    assert result.error["stage"] == "expand"
    assert "unbound" in result.error["message"]


def test_macro_export_rejected_with_envelope():
    ev = PlanKernelEvaluator()
    result = ev.eval_cell("(#export foo)")
    assert result.error is not None
    assert result.error["stage"] == "expand"
    assert "#export" in result.error["message"]


def test_partial_eval_keeps_prior_binds():
    """If form 3 errors, forms 1-2's binds should still be in env."""
    ev = PlanKernelEvaluator()
    result = ev.eval_cell(
        '(#bind a 1) (#bind b 2) undefined_symbol'
    )
    assert result.error is not None
    # The earlier binds took effect even though the cell errored.
    assert str_nat("a") in ev.env
    assert str_nat("b") in ev.env


def test_parse_error_does_not_mutate_env():
    """If parse fails, no form runs, no env mutation."""
    ev = PlanKernelEvaluator()
    ev.eval_cell('(#bind a 1)')   # establish baseline
    result = ev.eval_cell('"unterminated')
    assert result.error is not None
    # `a` from the prior cell remains; the failed cell didn't touch the env.
    assert str_nat("a") in ev.env


# ---------------------------------------------------------------------------
# Backend selection.
# ---------------------------------------------------------------------------

def test_backend_default_is_evaluate():
    ev = PlanKernelEvaluator()
    assert ev.backend_name == "evaluate"


def test_backend_bevaluate_selectable():
    ev = PlanKernelEvaluator(backend="bevaluate")
    assert ev.backend_name == "bevaluate"
    # Should evaluate identically for jet-free programs.
    result = ev.eval_cell("42")
    assert result.value_text == "42"


def test_backend_unknown_rejected():
    with pytest.raises(ValueError, match="unknown backend"):
        PlanKernelEvaluator(backend="reaver")
