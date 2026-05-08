"""Smoke test: each tutorial notebook re-evaluates cleanly via the kernel.

Each tutorial is run cell-by-cell through ``PlanKernelEvaluator``. The
committed notebook output is compared against what the live evaluator
produces — a mismatch means either the notebook needs regeneration
(``python tutorials/_build_lessons.py``) or the kernel's behaviour
drifted in a user-visible way. Both worth catching before merge.
"""

from __future__ import annotations

import json
import os
import unittest

from plan_kernel.evaluator import PlanKernelEvaluator


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TUTORIALS_DIR = os.path.join(REPO_ROOT, "plan-kernel", "tutorials")


def _load_notebook(name: str) -> dict:
    path = os.path.join(TUTORIALS_DIR, name)
    with open(path) as f:
        return json.load(f)


def _code_cells(nb: dict):
    """Yield ``(index, source, recorded_text_output)`` for each code cell."""
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue
        src = cell["source"]
        if isinstance(src, list):
            src = "".join(src)
        outputs = cell.get("outputs", [])
        text_out = ""
        if outputs:
            data = outputs[0].get("data", {})
            text_out = data.get("text/plain", "")
            if isinstance(text_out, list):
                text_out = "".join(text_out)
        yield i, src, text_out


class _TutorialNotebookTestMixin:
    """Shared assertions for one notebook's cell-by-cell behaviour.

    Subclasses set ``NOTEBOOK`` (the .ipynb filename). The test methods
    walk every code cell in the notebook and check (a) it evaluates
    without raising and (b) its committed text/plain output matches
    what the live evaluator produces.
    """

    NOTEBOOK: str = ""

    @classmethod
    def _load(cls):
        return _load_notebook(cls.NOTEBOOK)

    def test_cells_execute_without_error(self):
        nb = self._load()
        ev = PlanKernelEvaluator()
        for idx, src, _expected in _code_cells(nb):
            result = ev.eval_cell(src)
            self.assertIsNone(
                result.error,
                f"{self.NOTEBOOK} cell {idx} errored: {result.error}\n"
                f"source:\n{src}",
            )

    def test_cell_outputs_match_recorded(self):
        nb = self._load()
        ev = PlanKernelEvaluator()
        for idx, src, expected in _code_cells(nb):
            result = ev.eval_cell(src)
            actual = result.value_text or ""
            self.assertEqual(
                actual, expected,
                f"{self.NOTEBOOK} cell {idx} output drift:\n"
                f"  expected: {expected!r}\n"
                f"  actual:   {actual!r}\n"
                f"  source:\n{src}\n"
                f"(re-run `python tutorials/_build_lessons.py` to "
                f"regenerate the committed outputs)",
            )


class TestLesson01NumbersAndPins(_TutorialNotebookTestMixin, unittest.TestCase):
    NOTEBOOK = "01-numbers-and-pins.ipynb"


class TestLesson02Laws(_TutorialNotebookTestMixin, unittest.TestCase):
    NOTEBOOK = "02-laws.ipynb"


class TestLesson03ElimAndCases(_TutorialNotebookTestMixin, unittest.TestCase):
    NOTEBOOK = "03-elim-and-cases.ipynb"


class TestLesson04Recursion(_TutorialNotebookTestMixin, unittest.TestCase):
    NOTEBOOK = "04-recursion.ipynb"


if __name__ == "__main__":
    unittest.main()
