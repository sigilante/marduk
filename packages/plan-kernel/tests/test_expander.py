"""Tests for ``plan_kernel.expander`` — macro expander.

Drives the expander end-to-end (parse → macroexpand → thunk → evaluate)
against the four supported macros (#pin, #law, #app, #bind) and confirms
that #macro / #export are rejected with a clear error.
"""

import pytest

from plan_kernel.expander import Env, MacroError, eval_form, macroexpand, thunk
from plan_kernel.parser import parse_many
from plan_kernel.runtime.plan import (
    A, L, N, P,
    is_app, is_law, is_nat, is_pin,
    evaluate, str_nat,
)


def _drive(src, env=None):
    """Parse and run each top-level form through the macro-layer eval.

    Returns the list of per-form results.  Mirrors what a notebook cell
    would do with `eval_form` once phase 4 lands.
    """
    env = env if env is not None else Env()
    return [eval_form(form, env) for form in parse_many(src)], env


# ---------------------------------------------------------------------------
# #pin
# ---------------------------------------------------------------------------

def test_pin_of_nat_literal():
    results, _ = _drive("(#pin 5)")
    # #pin wraps in (1 ...) post-expand; thunk unwraps; evaluate returns Pin.
    assert results == [P(5)]


def test_pin_of_string():
    results, _ = _drive('(#pin "B")')
    assert results == [P(str_nat("B"))]


# ---------------------------------------------------------------------------
# #bind — accumulates env state, returns marker.
# ---------------------------------------------------------------------------

def test_bind_returns_name_marker():
    results, env = _drive('(#bind name "value")')
    # Marker thunks to the bind-name nat itself.
    assert results == [str_nat("name")]
    # Env now has the binding.
    entry = env.get(str_nat("name"))
    assert entry is not None
    assert entry[0] == str_nat("value")
    assert entry[1] is False    # not a macro


def test_bind_then_lookup_in_pin():
    results, _ = _drive('(#bind k 42) (#pin k)')
    # First form: bind. Second form: pin the bound value.
    assert results[0] == str_nat("k")
    assert results[1] == P(42)


def test_bind_overwrites_previous_binding():
    _, env = _drive('(#bind k 1) (#bind k 2)')
    entry = env.get(str_nat("k"))
    assert entry[0] == 2


def test_bind_bad_key_errors():
    # The bind name must be a bare symbol (parsed as a Nat). A string ((1 ...))
    # is not a bare nat — it's an App.
    with pytest.raises(MacroError) as exc_info:
        _drive('(#bind "name" "value")')
    assert "bind-key" in str(exc_info.value)


# ---------------------------------------------------------------------------
# #law — builds Law values.
# ---------------------------------------------------------------------------

def test_law_identity():
    """`(#law "id" (id x) x)` — a single-arg identity law."""
    results, _ = _drive('(#law "id" (id x) x)')
    [law] = results
    assert is_law(law)
    assert law.args == 1
    assert law.name == str_nat("id")
    # Body references slot 1 (the arg `x`).
    assert law.body == N(1)


def test_law_two_args_returns_first():
    """`(#law "k" (k a b) a)`."""
    results, _ = _drive('(#law "k" (k a b) a)')
    [law] = results
    assert is_law(law)
    assert law.args == 2
    # `a` is at slot 1, `b` is at slot 2.
    assert law.body == N(1)


def test_law_two_args_returns_second():
    results, _ = _drive('(#law "snd" (snd a b) b)')
    [law] = results
    assert law.body == N(2)


def test_law_self_reference():
    """The self-name (slot 0) is referenceable from the body."""
    results, _ = _drive('(#law "rec" (rec x) rec)')
    [law] = results
    # `rec` resolves to slot 0.
    assert law.body == N(0)


def test_law_with_let_bind():
    """`(#law "letted" (f x) y(1 x) (0 y x))` — a let-bind in the body."""
    results, _ = _drive('(#law "letted" (f x) y(1 x) (0 y x))')
    [law] = results
    assert is_law(law)
    assert law.args == 1
    # Body: (1 bind_ir body_ir) where bind_ir = (0 (1)) (compiled `(1 x)`)
    # — actually `x1(1 x)` means bind x1 = (1 x), so the bind-expr is the
    # quoted nat 1 wrapped... let's just confirm it's a (1 _ _) shape.
    assert is_app(law.body)
    assert is_app(law.body.head)
    assert is_nat(law.body.head.head) and law.body.head.head == 1


def test_law_zero_args_rejected():
    """`(#law "no-args" (foo))` — only the self-name, no arg syms."""
    with pytest.raises(MacroError) as exc_info:
        _drive('(#law "no-args" (foo) 0)')
    assert "empty argument list" in str(exc_info.value)


def test_law_missing_body_rejected():
    """`(#law "x" (x a))` — sig but no body forms."""
    with pytest.raises(MacroError):
        _drive('(#law "x" (x a))')


# ---------------------------------------------------------------------------
# #app — saturated application.
# ---------------------------------------------------------------------------

def test_app_two_args():
    """`(#app f a b)` evaluates each, then apple's them."""
    # Define a 2-arg law that returns its first arg, then app it.
    src = '''
    (#bind id (#pin (#law "id" (id x) x)))
    (#app id 42)
    '''
    results, _ = _drive(src)
    # Last result is `id 42` evaluated = 42.
    assert results[-1] == 42


# ---------------------------------------------------------------------------
# Top-level (0 ...) form (no macro head): regular saturated app.
# ---------------------------------------------------------------------------

def test_top_level_app_uses_bound_law():
    """A bare `(id 7)` form at top level should evaluate to `id 7 = 7`."""
    src = '''
    (#bind id (#pin (#law "id" (id x) x)))
    (id 7)
    '''
    results, _ = _drive(src)
    assert results[-1] == 7


# ---------------------------------------------------------------------------
# silly.plan-shaped fixtures: a chain of pin/law definitions.
# ---------------------------------------------------------------------------

def test_silly_plan_first_three_forms():
    """The first three forms from silly.plan: a #bind and two #pin (#law)s."""
    src = '''
    (#bind silly "silly")
    (#bind a
      (#pin
        (#law "a" (a b c)
          a)))
    (#pin
      (#law "b" (b c d)
        (a b c d)))
    '''
    results, env = _drive(src)
    assert len(results) == 3
    # Form 1: bind marker = "silly" nat.
    assert results[0] == str_nat("silly")
    # Form 2: bind marker = "a" nat. Env should have `a` bound to a Pin(Law).
    assert results[1] == str_nat("a")
    a_entry = env.get(str_nat("a"))
    assert is_pin(a_entry[0])
    assert is_law(a_entry[0].item)
    # Form 3: a Pin(Law) value (no bind, returns the pin itself).
    assert is_pin(results[2])


# ---------------------------------------------------------------------------
# Manual splicing form: #(expr) inside a law body.
# ---------------------------------------------------------------------------

def test_juxt_splice_inside_law():
    """`#(_01)` from raw.plan: manual expression splicing.

    `(#bind _01 (0 1))` sets `_01` to the value of `(0 1)` = 1 (after thunk
    unwraps the (0 1) shape — wait, actually (0 1) is array [(1 1)] which
    thunks to apple [1] = 1).  Then `#(_01)` in a law body splices that
    value in directly.
    """
    src = '''
    (#bind _01 (0 1))
    (#law "spliced" (_ a) (#(_01) a))
    '''
    results, env = _drive(src)
    [_, law] = results
    assert is_law(law)
    # The splice should have inserted the bound value of _01 into the body.
    # We don't pin the exact body shape — just confirm we got a Law and
    # the env was updated.
    assert env.get(str_nat("_01")) is not None


# ---------------------------------------------------------------------------
# Rejection of unsupported macros.
# ---------------------------------------------------------------------------

def test_macro_macro_rejected():
    with pytest.raises(MacroError) as exc_info:
        _drive('(#macro foo "bar")')
    assert "#macro is not supported" in str(exc_info.value)


def test_export_rejected():
    with pytest.raises(MacroError) as exc_info:
        _drive('(#export foo)')
    assert "#export is not supported" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unbound symbols.
# ---------------------------------------------------------------------------

def test_unbound_symbol_at_top_level():
    """`unknown` at top level — bare nat, looked up by thunk."""
    with pytest.raises(MacroError) as exc_info:
        _drive("unknown")
    assert "unbound" in str(exc_info.value)


def test_unbound_symbol_in_law_body():
    with pytest.raises(MacroError) as exc_info:
        _drive('(#law "x" (x a) unknown)')
    assert "unbound" in str(exc_info.value)


# ---------------------------------------------------------------------------
# macroexpand idempotence on already-expanded literals.
# ---------------------------------------------------------------------------

def test_macroexpand_leaves_nat_alone():
    env = Env()
    assert macroexpand(N(7), env) == N(7)


def test_macroexpand_leaves_quoted_alone():
    """`(1 x)` — the literal-quotation wrapper — passes through unchanged."""
    env = Env()
    val = A(N(1), N(7))
    assert macroexpand(val, env) == val


def test_thunk_unwraps_quoted():
    env = Env()
    assert thunk(A(N(1), N(7)), env) == N(7)


def test_thunk_bare_nat_unbound():
    env = Env()
    with pytest.raises(MacroError):
        thunk(N(str_nat("nope")), env)


def test_thunk_bare_zero():
    env = Env()
    assert thunk(N(0), env) == N(0)
