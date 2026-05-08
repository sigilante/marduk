"""Tests for ``plan_kernel.render`` — structural value renderer."""

import re

import pytest

from plan_kernel.render import render_value
from plan_kernel.runtime.plan import A, L, N, P, str_nat


# ---------------------------------------------------------------------------
# Atoms.
# ---------------------------------------------------------------------------

def test_nat_decimal():
    text, html = render_value(N(42))
    assert text == "42"
    assert "<span" in html
    assert ">42<" in html


def test_nat_zero():
    text, _ = render_value(N(0))
    assert text == "0"


def test_large_nat():
    text, _ = render_value(N(2 ** 64 + 17))
    # Decimal, not encoded.
    assert text.isdigit()
    assert text == str(2 ** 64 + 17)


# ---------------------------------------------------------------------------
# Pins.
# ---------------------------------------------------------------------------

def test_pin_of_nat():
    text, _ = render_value(P(5))
    assert text == "<5>"


def test_pin_of_pin():
    text, _ = render_value(P(P(N(7))))
    # Nested pins expand structurally (no Law collapse path here).
    assert text == "<<7>>"


def test_pin_of_law_pretty_collapses():
    """Default pretty=True: Pin(Law) renders as <{name…}>."""
    law = L(2, str_nat("foo"), N(1))
    text, _ = render_value(P(law))
    assert text == "<{'foo'…}>"


def test_pin_of_law_not_pretty_expands():
    law = L(2, str_nat("foo"), N(1))
    text, _ = render_value(P(law), pretty=False)
    # Full expansion: <{'foo' 2 1}>.
    assert text == "<{'foo' 2 1}>"


# ---------------------------------------------------------------------------
# Laws.
# ---------------------------------------------------------------------------

def test_law_with_decoded_name():
    law = L(1, str_nat("id"), N(1))
    text, _ = render_value(law)
    assert text == "{'id' 1 1}"


def test_law_with_zero_name_falls_back_to_decimal():
    """A name nat of 0 doesn't decode to printable UTF-8."""
    law = L(1, N(0), N(1))
    text, _ = render_value(law)
    assert text == "{0 1 1}"


def test_law_with_undecodable_name_falls_back_to_decimal():
    # 0xFF as a single byte isn't valid UTF-8 by itself.
    law = L(1, N(0xFF), N(1))
    text, _ = render_value(law)
    assert text == "{255 1 1}"


def test_law_with_complex_body():
    law = L(2, str_nat("k"), A(N(1), N(2)))
    text, _ = render_value(law)
    assert text == "{'k' 2 (1 2)}"


# ---------------------------------------------------------------------------
# Apps.
# ---------------------------------------------------------------------------

def test_app_simple():
    text, _ = render_value(A(N(0), N(1)))
    assert text == "(0 1)"


def test_app_nested_left():
    text, _ = render_value(A(A(N(0), N(1)), N(2)))
    assert text == "((0 1) 2)"


def test_app_nested_right():
    text, _ = render_value(A(N(0), A(N(1), N(2))))
    assert text == "(0 (1 2))"


# ---------------------------------------------------------------------------
# Depth bound.
# ---------------------------------------------------------------------------

def test_depth_bound_terminates():
    """A long App chain should hit the depth bound rather than recurse forever."""
    val = N(0)
    for _ in range(200):
        val = A(val, N(1))
    text, _ = render_value(val, max_depth=8)
    # The output must contain the ellipsis somewhere.
    assert "..." in text


def test_depth_bound_default_handles_modest_nesting():
    val = N(0)
    for _ in range(20):
        val = A(val, N(1))
    text, _ = render_value(val)
    # Nesting under the default bound should render fully.
    assert "..." not in text


# ---------------------------------------------------------------------------
# HTML output: well-formedness and content.
# ---------------------------------------------------------------------------

_SPAN_OPEN = re.compile(r'<span\b[^>]*>')
_SPAN_CLOSE = re.compile(r'</span>')


def _spans_balanced(html: str) -> bool:
    return len(_SPAN_OPEN.findall(html)) == len(_SPAN_CLOSE.findall(html))


def test_html_wraps_in_code_tag():
    _, html = render_value(N(1))
    assert html.startswith("<code")
    assert html.endswith("</code>")


def test_html_spans_balanced_for_each_shape():
    cases = [
        N(1),
        P(N(1)),
        L(1, str_nat("id"), N(1)),
        P(L(1, str_nat("id"), N(1))),       # pretty Pin(Law)
        A(N(0), N(1)),
        A(A(N(0), N(1)), L(1, str_nat("f"), N(1))),
    ]
    for val in cases:
        _, html = render_value(val)
        assert _spans_balanced(html), f"unbalanced spans for {val!r}: {html}"


def test_html_escapes_law_name_with_special_chars():
    """A law name containing characters that would break HTML must be escaped."""
    name_nat = str_nat("a<b>&c")
    law = L(1, name_nat, N(1))
    _, html = render_value(law)
    # The raw '<' in the name must be escaped to &lt; etc.
    assert "a&lt;b&gt;&amp;c" in html
    assert "<b>" not in html.replace('<b>', '', 0)  # no raw <b> tag from name


def test_html_nat_uses_nat_color_class():
    _, html = render_value(N(42))
    # The cyan style we picked.
    assert "color:#0097a7" in html


def test_html_brackets_use_muted_color():
    _, html = render_value(P(N(1)))
    # Pin brackets are muted gray.
    assert "color:#999" in html
    # And the actual `<` bracket is HTML-encoded.
    assert "&lt;" in html
    assert "&gt;" in html


# ---------------------------------------------------------------------------
# Misc.
# ---------------------------------------------------------------------------

def test_returns_two_strings():
    text, html = render_value(N(0))
    assert isinstance(text, str)
    assert isinstance(html, str)


def test_pretty_is_default_true():
    """Confirm Pin(Law) defaults to the collapsed form."""
    law = L(1, str_nat("x"), N(1))
    text_default, _ = render_value(P(law))
    text_explicit, _ = render_value(P(law), pretty=True)
    assert text_default == text_explicit
