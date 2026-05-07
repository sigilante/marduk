"""Tests for ``marduk.parser`` — Plan Asm reader.

Covers the encoding rules from PlanAssembler.hs (nat/str/sym/list/brak/curl/
juxt), comments, whitespace, and error reporting (line+col).
"""

import pathlib

import pytest

from marduk.parser import ParseError, parse, parse_many
from marduk.runtime.plan import A, N, str_nat


# ---------------------------------------------------------------------------
# Helpers — match the encoding rules so tests state structure declaratively.
# ---------------------------------------------------------------------------

def array(xs):
    if not xs:
        return N(0)
    v = N(0)
    for x in xs:
        v = A(v, x)
    return v


def sym(s):
    return N(str_nat(s))


def nat_lit(n):
    return A(N(1), N(n))


def str_lit(s):
    return A(N(1), N(str_nat(s)))


def juxt(v, body):
    return array([sym("#juxt"), v, body])


# ---------------------------------------------------------------------------
# Empty / whitespace / comments.
# ---------------------------------------------------------------------------

def test_parse_many_empty():
    assert parse_many("") == []


def test_parse_many_whitespace_only():
    assert parse_many("   \n\n  ") == []


def test_parse_many_comments_only():
    assert parse_many("; foo\n;; bar baz\n") == []


def test_parse_eof_on_empty_raises():
    with pytest.raises(ParseError) as exc_info:
        parse("")
    assert "eof" in exc_info.value.message
    assert exc_info.value.line == 1
    assert exc_info.value.col == 1


# ---------------------------------------------------------------------------
# Atoms: nats, syms, strings.
# ---------------------------------------------------------------------------

def test_nat_literal_zero():
    assert parse_many("0") == [nat_lit(0)]


def test_nat_literal_multidigit():
    assert parse_many("42") == [nat_lit(42)]


def test_two_top_level_nats():
    assert parse_many("0 1") == [nat_lit(0), nat_lit(1)]


def test_symbol():
    assert parse_many("foo") == [sym("foo")]


def test_symbol_with_hash_prefix():
    # `#bind` is a symbol; the macro layer treats it specially, the parser
    # just sees a sym.
    assert parse_many("#bind") == [sym("#bind")]


def test_string():
    assert parse_many('"hello"') == [str_lit("hello")]


def test_empty_string():
    assert parse_many('""') == [str_lit("")]


def test_string_with_spaces():
    assert parse_many('"hello world"') == [str_lit("hello world")]


# ---------------------------------------------------------------------------
# Brackets: parens, brak, curl.
# ---------------------------------------------------------------------------

def test_empty_parens():
    # array []  →  N 0
    assert parse_many("()") == [N(0)]


def test_empty_brak():
    assert parse_many("[]") == [array([sym("#brak")])]


def test_empty_curl():
    assert parse_many("{}") == [array([sym("#curl")])]


def test_paren_list_of_syms():
    assert parse_many("(a b c)") == [array([sym("a"), sym("b"), sym("c")])]


def test_nested_parens():
    assert parse_many("(a (b c))") == [
        array([sym("a"), array([sym("b"), sym("c")])])
    ]


def test_paren_mixed_atoms():
    assert parse_many('(0 foo "bar")') == [
        array([nat_lit(0), sym("foo"), str_lit("bar")])
    ]


def test_brak_nonempty():
    assert parse_many("[a b]") == [array([sym("#brak"), sym("a"), sym("b")])]


def test_curl_nonempty():
    assert parse_many("{1 2}") == [
        array([sym("#curl"), nat_lit(1), nat_lit(2)])
    ]


# ---------------------------------------------------------------------------
# Juxtaposition: sym immediately followed by `(` or `"`.
# ---------------------------------------------------------------------------

def test_juxt_with_parens():
    # `foo(x)`  →  (0 #juxt foo (0 x))
    assert parse_many("foo(x)") == [juxt(sym("foo"), array([sym("x")]))]


def test_juxt_with_string():
    # `foo"x"`  →  (0 #juxt foo (1 strNat "x"))
    assert parse_many('foo"x"') == [juxt(sym("foo"), str_lit("x"))]


def test_juxt_inside_list():
    assert parse_many("(foo(x) y)") == [
        array([juxt(sym("foo"), array([sym("x")])), sym("y")])
    ]


def test_juxt_with_nat_head():
    # `42(x)` — head is a nat literal, juxt still applies.
    assert parse_many("42(x)") == [juxt(nat_lit(42), array([sym("x")]))]


def test_no_juxt_when_separated_by_space():
    # `foo (x)` is two top-level forms.
    assert parse_many("foo (x)") == [sym("foo"), array([sym("x")])]


def test_hash_paren_juxt_pattern():
    # `#(foo)` — the manual-expression-splicing form. Parser sees sym `#` then
    # `(foo)` — juxt.
    assert parse_many("#(foo)") == [juxt(sym("#"), array([sym("foo")]))]


# ---------------------------------------------------------------------------
# Comments interleaved with forms.
# ---------------------------------------------------------------------------

def test_line_comment_skips_rest_of_line():
    assert parse_many("; ignore me\n42") == [nat_lit(42)]


def test_comment_between_forms():
    assert parse_many("1\n; comment\n2") == [nat_lit(1), nat_lit(2)]


def test_comment_inside_list():
    assert parse_many("(a ; comment\n b)") == [array([sym("a"), sym("b")])]


# ---------------------------------------------------------------------------
# Single-form `parse()` accepts trailing content.
# ---------------------------------------------------------------------------

def test_parse_single_form_ignores_trailing():
    assert parse("foo bar") == sym("foo")


# ---------------------------------------------------------------------------
# Error cases — line+col reporting.
# ---------------------------------------------------------------------------

def test_unterminated_string():
    with pytest.raises(ParseError) as exc_info:
        parse_many('"hello')
    assert exc_info.value.message == "unterminated string"


def test_unterminated_string_in_list():
    # The string opens at col 4 of line 1. By the time we error, cur is at
    # EOF (line 1, col 11).
    with pytest.raises(ParseError) as exc_info:
        parse_many('(a "unterm')
    assert exc_info.value.message == "unterminated string"
    assert exc_info.value.line == 1


def test_eof_in_list():
    with pytest.raises(ParseError) as exc_info:
        parse_many("(")
    assert exc_info.value.message == "eof in list"


def test_eof_in_list_after_elements():
    with pytest.raises(ParseError) as exc_info:
        parse_many("(a b")
    assert exc_info.value.message == "eof in list"


def test_bad_list_no_separator():
    # `((a)b)` — after parsing inner `(a)`, the leftover starts with 'b',
    # which is non-gap non-closer in the outer list context.
    with pytest.raises(ParseError) as exc_info:
        parse_many("((a)b)")
    assert exc_info.value.message == "bad list"


def test_unexpected_closer_at_top_level():
    with pytest.raises(ParseError) as exc_info:
        parse_many(")")
    # Top-level closer trips the `_END` → `unexpected:` branch.
    assert "unexpected" in exc_info.value.message


def test_error_position_on_second_line():
    with pytest.raises(ParseError) as exc_info:
        parse_many("\n)")
    assert exc_info.value.line == 2
    assert exc_info.value.col == 1


# ---------------------------------------------------------------------------
# Round-trip against actual Reaver fixtures.
# ---------------------------------------------------------------------------

# The Reaver tree is Gallowglass-vendored, not vendored into Marduk. These
# tests are skipped if the upstream tree isn't available locally.
_REAVER_SRC = pathlib.Path(__file__).resolve().parents[2] / "reaver" / "src" / "plan"


def _has_reaver_fixtures() -> bool:
    return _REAVER_SRC.is_dir()


@pytest.mark.skipif(not _has_reaver_fixtures(),
                    reason="reaver source tree not present")
def test_silly_plan_parses():
    text = (_REAVER_SRC / "silly.plan").read_text()
    forms = parse_many(text)
    # silly.plan has 13 top-level forms (3 #binds + 5 (#law ...) shapes
    # + 5 wrapped pin/law + final (0 x y)).
    assert len(forms) > 0


@pytest.mark.skipif(not _has_reaver_fixtures(),
                    reason="reaver source tree not present")
def test_raw_plan_parses():
    text = (_REAVER_SRC / "raw.plan").read_text()
    forms = parse_many(text)
    assert len(forms) > 0


@pytest.mark.skipif(not _has_reaver_fixtures(),
                    reason="reaver source tree not present")
def test_silly_plan_first_form_shape():
    text = (_REAVER_SRC / "silly.plan").read_text()
    first = parse_many(text)[0]
    # First form is `(#bind silly "silly")`.
    expected = array([sym("#bind"), sym("silly"), str_lit("silly")])
    assert first == expected
