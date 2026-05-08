"""Tests for ``marduk.magics`` and the evaluator's magic dispatch.

Covers ``parse_magics`` standalone and the three magic semantics through
``MardukEvaluator.eval_cell``:

- ``%backend`` is per-cell (reverts).
- ``%reset`` is persistent.
- ``%env`` is read-only.
"""

import pytest

from marduk.evaluator import MardukEvaluator
from marduk.magics import MagicDirective, MagicError, parse_magics
from marduk.runtime.plan import str_nat


# ---------------------------------------------------------------------------
# parse_magics — pure parsing.
# ---------------------------------------------------------------------------

def test_parse_magics_empty():
    directives, body = parse_magics("")
    assert directives == []
    assert body == ""


def test_parse_magics_body_only():
    directives, body = parse_magics("(Add 2 3)")
    assert directives == []
    assert body == "(Add 2 3)"


def test_parse_magics_single():
    directives, body = parse_magics("%backend bevaluate\n42\n")
    assert directives == [MagicDirective(name="backend", args=["bevaluate"])]
    assert body == "42\n"


def test_parse_magics_no_args():
    directives, body = parse_magics("%env\n42")
    assert directives == [MagicDirective(name="env", args=[])]
    assert body == "42"


def test_parse_magics_multiple():
    directives, body = parse_magics(
        "%backend bevaluate\n%reset\n42\n"
    )
    assert [d.name for d in directives] == ["backend", "reset"]
    assert body == "42\n"


def test_parse_magics_blank_line_between():
    directives, body = parse_magics(
        "%backend bevaluate\n\n%env\n42"
    )
    assert [d.name for d in directives] == ["backend", "env"]
    assert body == "42"


def test_parse_magics_leading_blank_line_stays_in_body():
    """A blank line before any magic isn't part of a magic block."""
    directives, body = parse_magics("\n%backend bevaluate\n42")
    assert directives == []
    # Whole source preserved.
    assert body == "\n%backend bevaluate\n42"


def test_parse_magics_leading_comment_stays_in_body():
    """Comments above magics terminate the magic block (none parsed)."""
    directives, body = parse_magics("; comment\n%backend bevaluate\n42")
    assert directives == []
    assert body == "; comment\n%backend bevaluate\n42"


def test_parse_magics_bare_percent_is_body():
    directives, body = parse_magics("%\n42")
    assert directives == []
    assert body == "%\n42"


def test_parse_magics_mid_body_percent_stays_body():
    """A `%` line that appears after the body has started is body."""
    directives, body = parse_magics("42\n%backend bevaluate")
    assert directives == []
    assert body == "42\n%backend bevaluate"


def test_parse_magics_indented_magic_recognized():
    """Leading whitespace before `%` is tolerated."""
    directives, body = parse_magics("    %backend bevaluate\n42")
    assert [d.name for d in directives] == ["backend"]
    assert body == "42"


def test_magic_directive_line_property():
    d = MagicDirective(name="backend", args=["bevaluate"])
    assert d.line == "%backend bevaluate"
    d2 = MagicDirective(name="env", args=[])
    assert d2.line == "%env"


# ---------------------------------------------------------------------------
# %backend integration.
# ---------------------------------------------------------------------------

def test_backend_magic_switches_for_cell():
    ev = MardukEvaluator()
    assert ev.backend_name == "evaluate"
    result = ev.eval_cell("%backend bevaluate\n42")
    assert result.value_text == "42"
    # After cell, reverts to default.
    assert ev.backend_name == "evaluate"


def test_backend_magic_to_default():
    ev = MardukEvaluator(backend="bevaluate")
    result = ev.eval_cell("%backend evaluate\n42")
    assert result.value_text == "42"
    # Reverts to bevaluate (instance default).
    assert ev.backend_name == "bevaluate"


def test_backend_magic_unknown_value_errors():
    ev = MardukEvaluator()
    result = ev.eval_cell("%backend reaver\n42")
    assert result.error is not None
    assert result.error["stage"] == "magic"
    assert "unknown backend" in result.error["message"]
    # Backend unchanged.
    assert ev.backend_name == "evaluate"


def test_backend_magic_no_args_errors():
    ev = MardukEvaluator()
    result = ev.eval_cell("%backend\n42")
    assert result.error is not None
    assert result.error["stage"] == "magic"


def test_backend_magic_too_many_args_errors():
    ev = MardukEvaluator()
    result = ev.eval_cell("%backend evaluate bevaluate\n42")
    assert result.error is not None
    assert result.error["stage"] == "magic"


def test_backend_revert_after_error_in_body():
    """Backend reverts even if the body raises."""
    ev = MardukEvaluator()
    ev.eval_cell("%backend bevaluate\nundefined_symbol")
    assert ev.backend_name == "evaluate"


# ---------------------------------------------------------------------------
# %reset integration.
# ---------------------------------------------------------------------------

def test_reset_magic_clears_env():
    ev = MardukEvaluator()
    ev.eval_cell("(#bind a 1)")
    assert str_nat("a") in ev.env
    result = ev.eval_cell("%reset")
    # Silent — no body, no display output.
    assert result.decls_only is True
    assert str_nat("a") not in ev.env


def test_reset_persists_across_cells():
    ev = MardukEvaluator()
    ev.eval_cell("(#bind a 1)")
    ev.eval_cell("%reset")
    # New cell — env should still be empty.
    result = ev.eval_cell("a")
    assert result.error is not None
    assert result.error["stage"] == "expand"


def test_reset_with_args_errors():
    ev = MardukEvaluator()
    result = ev.eval_cell("%reset extra-arg")
    assert result.error is not None
    assert result.error["stage"] == "magic"


def test_reset_then_body_in_same_cell():
    ev = MardukEvaluator()
    ev.eval_cell("(#bind a 1)")
    result = ev.eval_cell("%reset\n(#bind b 2)\nb")
    assert str_nat("a") not in ev.env
    assert str_nat("b") in ev.env
    assert result.value_text == "2"


# ---------------------------------------------------------------------------
# %env integration.
# ---------------------------------------------------------------------------

def test_env_magic_empty():
    ev = MardukEvaluator()
    result = ev.eval_cell("%env")
    assert result.value_text == "(env empty)"


def test_env_magic_lists_names():
    ev = MardukEvaluator()
    ev.eval_cell("(#bind alpha 1) (#bind beta 2)")
    result = ev.eval_cell("%env")
    # Sorted, comma-separated.
    assert result.value_text == "alpha, beta"


def test_env_magic_with_body_prepends_output():
    ev = MardukEvaluator()
    ev.eval_cell("(#bind a 1)")
    result = ev.eval_cell("%env\n42")
    # Expected: "a\n42" (env listing then value).
    assert result.value_text == "a\n42"


def test_env_magic_with_args_errors():
    ev = MardukEvaluator()
    result = ev.eval_cell("%env extra")
    assert result.error is not None
    assert result.error["stage"] == "magic"


# ---------------------------------------------------------------------------
# Unknown magic.
# ---------------------------------------------------------------------------

def test_unknown_magic_errors():
    ev = MardukEvaluator()
    result = ev.eval_cell("%notamagic\n42")
    assert result.error is not None
    assert result.error["stage"] == "magic"
    assert "%notamagic" in result.error["message"]


# ---------------------------------------------------------------------------
# Multi-magic combos.
# ---------------------------------------------------------------------------

def test_reset_then_env_in_one_cell():
    ev = MardukEvaluator()
    ev.eval_cell("(#bind a 1)")
    result = ev.eval_cell("%reset\n%env")
    assert result.value_text == "(env empty)"


def test_backend_and_reset_in_one_cell():
    ev = MardukEvaluator()
    ev.eval_cell("(#bind a 1)")
    result = ev.eval_cell("%backend bevaluate\n%reset\n42")
    assert result.value_text == "42"
    assert str_nat("a") not in ev.env
    assert ev.backend_name == "evaluate"   # %backend reverted


def test_magic_block_followed_by_blank_line_then_body():
    ev = MardukEvaluator()
    result = ev.eval_cell("%env\n\n42")
    # %env on empty env gives "(env empty)", then 42.
    assert result.value_text == "(env empty)\n42"
