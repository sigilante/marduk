"""Tests for marduk.asm — Plan Asm reader, expander, printer.

Three groups:

1. Reader-only — surface text → Val shape, no semantics.
2. Expander pipeline — eval_form with a bound prelude, end-to-end.
3. Printer round-trip — dump(parse(s)) reparses to an equivalent Val.
"""

from __future__ import annotations

import pytest

from marduk import App, Hol, Law, Nat, Pin, Val, evaluate
from marduk.asm import (
    Env,
    MacroError,
    ParseError,
    eval_form,
    parse,
    parse_many,
    dump,
    macroexpand,
    thunk,
)
from marduk.runtime.strnat import str_nat
from marduk.runtime.bplan import OPS as BPLAN_OPS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def app_chain(*xs: Val) -> Val:
    out = xs[0]
    for x in xs[1:]:
        out = App(out, x)
    return out


def make_bplan_law(name: str) -> Val:
    """Build a Law that wraps a BPLAN named op of the given name. The
    returned Law has the op's arity and a body that constructs
    ``(<66> (name arg1 ...))`` and evaluates it. Used to seed an Env
    with executable BPLAN bindings."""
    if name not in BPLAN_OPS:
        raise KeyError(f"unknown BPLAN op {name!r}")
    arity, _fn = BPLAN_OPS[name]
    bplan = Pin(Nat(66))
    name_nat = Nat(str_nat(name))
    # Inner spine in body syntax: ((quote name_nat) $1 $2 ...)
    # Each application is (0 head x); each constant is quoted via (0 v).
    # Build inner = name $1 $2 ... in body form.
    inner = App(Nat(0), name_nat)            # (0 name_nat) — quote
    for i in range(1, arity + 1):
        # Wrap inner as (0 inner $i) — apply
        inner = App(App(Nat(0), inner), Nat(i))
    # Wrap with bplan: (0 (0 bplan) inner) — apply BPLAN to the inner.
    bplan_q = App(Nat(0), bplan)             # (0 bplan)
    body = App(App(Nat(0), bplan_q), inner)
    return Law(Nat(str_nat(name)), Nat(arity), body)


def seed_env_with_bplan(env: Env, ops: list[str]) -> None:
    for op in ops:
        env.put(str_nat(op), make_bplan_law(op), is_macro=False)


def to_int(v: Val) -> int:
    assert v.type == "nat", f"expected nat, got {v}"
    return v.nat


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

class TestReader:

    def test_bare_nat(self):
        # Bare nat literal is wrapped as (1 n) per surface convention.
        v = parse("42")
        assert v.type == "app"
        assert v.head.nat == 1
        assert v.tail.nat == 42

    def test_bare_symbol(self):
        # Bare symbol is a Nat carrying the str_nat encoding.
        v = parse("foo")
        assert v.type == "nat"
        assert v.nat == str_nat("foo")

    def test_string_literal(self):
        # "foo" → (1 str_nat("foo")) — same shape as a nat literal.
        v = parse('"hi"')
        assert v.type == "app"
        assert v.head.nat == 1
        assert v.tail.nat == str_nat("hi")

    def test_paren_list(self):
        # (a b c) → (0 a b c) — a left-associated App spine over Nat(0).
        v = parse("(a b c)")
        parts = v.spine
        assert len(parts) == 4
        assert parts[0].nat == 0
        assert parts[1].nat == str_nat("a")
        assert parts[2].nat == str_nat("b")
        assert parts[3].nat == str_nat("c")

    def test_juxtaposition(self):
        # ``f(x)`` (no whitespace) → (0 #juxt f (0 x))
        v = parse("f(x)")
        parts = v.spine
        assert parts[0].nat == 0
        assert parts[1].nat == str_nat("#juxt")
        assert parts[2].nat == str_nat("f")

    def test_comments_and_whitespace(self):
        v = parse("""
            ; a comment
            (a  b  ; inner comment
             c)
        """)
        parts = v.spine
        assert len(parts) == 4

    def test_parse_many(self):
        forms = parse_many("1 2 3")
        assert len(forms) == 3
        assert forms[0].tail.nat == 1
        assert forms[2].tail.nat == 3

    def test_parse_error_carries_position(self):
        with pytest.raises(ParseError) as exc:
            parse("(a")  # unterminated
        assert exc.value.line == 1
        assert exc.value.col >= 2


# ---------------------------------------------------------------------------
# Expander pipeline
# ---------------------------------------------------------------------------

class TestExpander:

    def test_pin_macro(self):
        env = Env()
        seed_env_with_bplan(env, ["Add"])
        # (#pin (Add 2 3)) — pins the result of 2+3 = 5.
        result = eval_form(parse("(#pin (Add 2 3))"), env)
        assert result.type == "pin"
        assert result.item.type == "nat"
        assert result.item.nat == 5

    def test_bind_macro_stores_in_env(self):
        env = Env()
        seed_env_with_bplan(env, ["Add"])
        # (#bind x (Add 2 3))
        eval_form(parse("(#bind x (Add 2 3))"), env)
        assert str_nat("x") in env
        v, is_macro = env.get(str_nat("x"))
        assert is_macro is False
        assert v.type == "nat" and v.nat == 5

    def test_law_construction_and_application(self):
        env = Env()
        seed_env_with_bplan(env, ["Add"])
        # (#bind addtwo (#law "addtwo" (self n) (Add n 2)))
        eval_form(parse(
            '(#bind addtwo (#law "addtwo" (self n) (Add n 2)))'
        ), env)
        assert str_nat("addtwo") in env
        # (addtwo 5)
        result = eval_form(parse("(addtwo 5)"), env)
        assert to_int(result) == 7

    def test_nested_law_call(self):
        env = Env()
        seed_env_with_bplan(env, ["Add", "Mul"])
        eval_form(parse(
            '(#bind quad (#law "quad" (self n) (Mul n n)))'
        ), env)
        result = eval_form(parse("(quad 6)"), env)
        assert to_int(result) == 36

    def test_law_with_let_binding(self):
        env = Env()
        seed_env_with_bplan(env, ["Add"])
        # In-law bindings use juxt-form ``name(expr)`` — written without
        # whitespace between name and the parenthesized expression. The
        # ``#bind`` macro is for top-level bindings only.
        # (#law "f" (self x) y(Add x 1) (Add y y))
        eval_form(parse(
            '(#bind f (#law "f" (self x)'
            ' y(Add x 1) (Add y y)))'
        ), env)
        result = eval_form(parse("(f 3)"), env)
        # y = x + 1 = 4; result = y + y = 8.
        assert to_int(result) == 8

    def test_app_macro(self):
        env = Env()
        seed_env_with_bplan(env, ["Add"])
        # (#app Add 2 3) ≡ (Add 2 3) but evaluated immediately.
        result = eval_form(parse("(#app Add 2 3)"), env)
        assert to_int(result) == 5

    def test_unbound_symbol_errors(self):
        env = Env()
        with pytest.raises(MacroError, match="unbound"):
            eval_form(parse("(undefined_thing 1 2)"), env)

    def test_macro_export_rejected(self):
        env = Env()
        with pytest.raises(MacroError, match="#export is not supported"):
            eval_form(parse("(#export foo)"), env)


# ---------------------------------------------------------------------------
# Self-recursive law (the test that exercises knot-tying through asm)
# ---------------------------------------------------------------------------

class TestSelfRecursion:

    def test_factorial(self):
        env = Env()
        seed_env_with_bplan(env, ["Mul", "Sub", "If", "Lt"])
        # (#bind fact (#law "fact" (self n)
        #   (If (Lt n 2) 1 (Mul n (self (Sub n 1))))))
        eval_form(parse('''
            (#bind fact (#law "fact" (self n)
                (If (Lt n 2) 1
                    (Mul n (self (Sub n 1))))))
        '''), env)
        assert to_int(eval_form(parse("(fact 0)"), env)) == 1
        assert to_int(eval_form(parse("(fact 1)"), env)) == 1
        assert to_int(eval_form(parse("(fact 5)"), env)) == 120
        assert to_int(eval_form(parse("(fact 7)"), env)) == 5040


# ---------------------------------------------------------------------------
# Printer
# ---------------------------------------------------------------------------

class TestPrinter:

    def test_dump_nat(self):
        assert dump(Nat(42)) == "42"
        assert dump(Nat(0)) == "0"

    def test_dump_string_nat(self):
        # str_nat("hi") decodes back to "hi" via nat_str → printer emits "hi".
        assert dump(Nat(str_nat("hi"))) == '"hi"'

    def test_dump_pin(self):
        assert dump(Pin(Nat(7))) == "<7>"

    def test_dump_app_spine(self):
        v = app_chain(Nat(1), Nat(2), Nat(3))
        assert dump(v) == "(1 2 3)"

    def test_dump_law(self):
        # Law spec form: {name arity body}.
        l = Law(Nat(str_nat("id")), Nat(1), Nat(1))
        assert dump(l) == '{"id" 1 1}'

    def test_dump_hole(self):
        assert dump(Hol()) == "<>"

    def test_dump_truncates_at_max_depth(self):
        # Deeply nested App: 80 levels.
        v = Nat(0)
        for _ in range(80):
            v = App(v, Nat(1))
        out = dump(v, max_depth=10)
        assert "…" in out
