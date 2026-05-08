"""Integration tests against the small PLAN programs in ``fixtures/``.

Each fixture is a complete Plan Asm cell — definitions plus a final
expression — that exercises one teaching point (combinators, arithmetic,
Elim, Church booleans). The tests load each, run it through
:class:`PlanKernelEvaluator`, and assert the expected final value.
"""

import pathlib

import pytest

from plan_kernel.evaluator import PlanKernelEvaluator


_FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _run(name: str) -> str:
    src = (_FIXTURES / f"{name}.plan").read_text()
    ev = PlanKernelEvaluator()
    result = ev.eval_cell(src)
    assert result.error is None, f"{name}: {result.error}"
    return result.value_text


@pytest.mark.parametrize("name,expected", [
    ("id",          "42"),    # I 42 = 42
    ("k",           "7"),     # K 7 99 = 7
    ("s",           "42"),    # S K K 42 = 42 (SKK is identity)
    ("arithmetic",  "7"),     # 1 + (2 * 3) = 7
    ("elim",        "1"),     # is_zero 0 = 1
    ("church_bool", "20"),    # And T F 10 20 = 20
])
def test_fixture_evaluates_to_expected(name, expected):
    assert _run(name) == expected
