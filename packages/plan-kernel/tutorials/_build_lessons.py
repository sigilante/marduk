#!/usr/bin/env python3
"""Build the tutorial notebooks.

Each ``LESSON_NN`` constant below is a list of ``(kind, body)`` cell
descriptors — ``kind`` is ``"md"`` or ``"code"``. The script runs every
code cell through ``PlanKernelEvaluator`` and writes the resulting
notebook with captured outputs. Re-run after the kernel changes
behaviour to refresh the committed outputs.

Usage::

    python3 tutorials/_build_lessons.py            # build all lessons
    python3 tutorials/_build_lessons.py 01 02      # build only specific lessons
"""

from __future__ import annotations

import os
import sys
from typing import Any

import nbformat
from nbformat import v4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from plan_kernel.evaluator import PlanKernelEvaluator


# ---------------------------------------------------------------------------
# Lesson 01 — Numbers and pins
# ---------------------------------------------------------------------------

LESSON_01: list[tuple[str, str]] = [
    ("md", """# 01 — Numbers and pins

PLAN starts with one kind of value: the natural number. Type a nat, \
see it back.

This notebook teaches the smallest set of building blocks: bare nats, \
BPLAN arithmetic primitives, and pins. It assumes you have the \
`plan-kernel` Jupyter kernel installed and selected (``python -m \
plan_kernel install``).
"""),

    ("md", "## Bare nats\n\n"
           "A bare nat is the number itself. The kernel echoes it back."),
    ("code", "42"),
    ("code", "0"),
    ("code", "1024"),

    ("md", "## Arithmetic via BPLAN\n\n"
           "PLAN proper has just three opcodes (Pin, Law, Elim). "
           "Arithmetic, comparison, and the rest of the usual primitives "
           "live in **BPLAN** — named operations dispatched via the "
           "pinned-nat dispatcher `<66>`. The surface syntax is "
           "``(OpName arg1 arg2 ...)``."),
    ("code", "(Add 2 3)"),
    ("code", "(Mul 7 6)"),
    ("code", "(Sub 10 3)"),
    ("code", "(Inc 41)"),

    ("md", "Compositions work the way you'd expect:"),
    ("code", "(Add (Mul 2 3) (Inc 4))"),

    ("md", "Saturating subtraction — `Sub` clamps at zero rather than "
           "going negative (PLAN nats are unsigned):"),
    ("code", "(Sub 3 10)"),

    ("md", "## Comparison\n\n"
           "Booleans in PLAN are encoded as nats: `1` is true, `0` is "
           "false. `Eq`, `Lt`, `Gt`, etc. return one of those."),
    ("code", "(Eq 5 5)"),
    ("code", "(Lt 3 7)"),
    ("code", "(Gt 3 7)"),

    ("md", "## Pins\n\n"
           "A **pin** wraps a value. The notation `<v>` means \"a pin \"\n"
           "around v\". You construct one with `#pin`:"),
    ("code", "(#pin 5)"),

    ("md", "Pins are how PLAN does content addressing — two pins around "
           "structurally equal values are interchangeable. They're also "
           "how you mark a value as \"finished, don't recompute\". "
           "Most of the time you'll see them wrapping laws (the next "
           "lesson)."),

    ("md", "## What's next\n\n"
           "Lesson 02 introduces **laws** — PLAN's representation of a "
           "function. You'll define an identity law, a doubler, and the "
           "K combinator, and start composing them."),
]


# ---------------------------------------------------------------------------
# Lesson 02 — Laws
# ---------------------------------------------------------------------------

LESSON_02: list[tuple[str, str]] = [
    ("md", """# 02 — Laws

A **law** is PLAN's representation of a callable function. Three \
components: a name (any nat — usually a string-encoded one), an \
arity (how many arguments before saturation), and a body (an \
expression that computes the result).
"""),

    ("md", "## Surface syntax: `#law`\n\n"
           "The macro `#law` constructs a law:\n\n"
           "```\n"
           '(#law "name" (self arg1 arg2 ...) body)\n'
           "```\n\n"
           "* The string after `#law` is the law's display name.\n"
           "* The signature `(self arg1 ...)` declares the parameter "
           "names. `self` is the law itself (slot 0); `arg1` is slot 1, "
           "and so on.\n"
           "* The body is an expression that can reference slots by name."),

    ("md", "### Identity\n\n"
           "Returning the argument unchanged:"),
    ("code", '(#law "id" (id x) x)'),

    ("md", "Apply it to a value:"),
    ("code", '((#law "id" (id x) x) 42)'),

    ("md", "## `#bind` — give a law a name\n\n"
           "Inline laws are noisy. `#bind` ties a name in the top-level "
           "environment so subsequent cells can use it:"),
    ("code", '(#bind id (#law "id" (id x) x))'),
    ("code", "(id 99)"),

    ("md", "Bound names are visible across cells. `%env` shows them:"),
    ("code", "%env"),

    ("md", "## A doubler\n\n"
           "Two-argument body: just call `Add` with the same input twice."),
    ("code", '(#bind double (#law "double" (double x) (Add x x)))'),
    ("code", "(double 21)"),

    ("md", "## The K combinator\n\n"
           "`K a b = a` — return the first argument, ignore the second. "
           "Useful as a constant function and in encoding booleans."),
    ("code", '(#bind k (#law "k" (k a b) a))'),
    ("code", "(k 7 99)"),

    ("md", "## Composition\n\n"
           "Functions compose by application. Define `quad` as `double` "
           "applied to `double`:"),
    ("code", '(#bind quad (#law "quad" (quad x) (double (double x))))'),
    ("code", "(quad 5)"),

    ("md", "## Pinning a law\n\n"
           "`#pin` wraps a law in a Pin. The arity stays the same — "
           "applying a pinned law works identically to applying the law "
           "directly. Pins are how you mark a value as \"finalized for "
           "sharing.\""),
    ("code", '(#bind sq (#pin (#law "sq" (sq n) (Mul n n))))'),
    ("code", "(sq 9)"),

    ("md", "## What's next\n\n"
           "Lesson 03 introduces `Elim` — PLAN's pattern matcher. It's "
           "a six-armed eliminator that dispatches on whether the input "
           "is a Pin, Law, App, zero-nat, or successor-nat. It's the "
           "primitive every conditional, case, or fold-like operation "
           "is built from."),
]


# ---------------------------------------------------------------------------
# Lesson 03 — Elim and cases
# ---------------------------------------------------------------------------

LESSON_03: list[tuple[str, str]] = [
    ("md", """# 03 — Elim and case dispatchers

`Elim` is PLAN's pattern matcher. It takes six handlers — one per \
shape of value — plus the value to dispatch on, and it picks the \
right handler based on the value's type.
"""),

    ("md", "## Anatomy of `Elim`\n\n"
           "Surface syntax:\n\n"
           "```\n"
           "(Elim p l a z m o)\n"
           "```\n\n"
           "* `p` — handler for **Pin**: applied to the pin's inner.\n"
           "* `l` — handler for **Law**: applied to (name, arity, body).\n"
           "* `a` — handler for **App**: applied to (head, tail).\n"
           "* `z` — handler for **zero**: returned directly.\n"
           "* `m` — handler for **successor n>0**: applied to n-1.\n"
           "* `o` — the value to dispatch on.\n\n"
           "The handler arms are just normal PLAN values; the `Elim` "
           "primitive picks one based on `o`'s shape and applies it."),

    ("md", "### A simple use: zero-check\n\n"
           "Use `Elim`'s `z` arm for the zero case and ignore everything "
           "else. (`k` is from lesson 02 — it's the constant-function "
           "pattern. Re-bind it here so this lesson stands alone.)"),
    ("code", '(#bind k (#law "k" (k a b) a))'),
    ("code", '(#bind is_zero (#law "is_zero" (is_zero n)\n'
             '  (Elim 0 0 0 1 (k 0) n)))'),
    ("code", "(is_zero 0)"),
    ("code", "(is_zero 5)"),

    ("md", "Reading the body: when `n` is `0`, return `1`. When `n` is "
           "a successor (any nat > 0), apply `(k 0)` to `n-1` — that "
           "discards the predecessor and yields `0`. The Pin/Law/App "
           "handlers are placeholders since `n` is always a nat here."),

    ("md", "## `Case2`..`Case16` — small dispatchers\n\n"
           "For matching a nat against a small set of values, BPLAN "
           "provides shortcuts. `Case2` picks branch_0 if the index is 0, "
           "fallback otherwise:"),
    ("code", "(Case2 0 100 999)"),
    ("code", "(Case2 1 100 999)"),
    ("code", "(Case2 50 100 999)"),

    ("md", "`Case3` adds a second indexed branch:"),
    ("code", '(Case3 0 "first" "second" "fallback")'),
    ("code", '(Case3 1 "first" "second" "fallback")'),
    ("code", '(Case3 2 "first" "second" "fallback")'),

    ("md", "(The strings are encoded as nats — that's why the cell "
           "shows numbers. Plan Asm doesn't have a separate string type; "
           "`\"foo\"` is shorthand for the nat whose little-endian bytes "
           "decode as `\"foo\"`.)"),

    ("md", "## Encoding booleans with laws\n\n"
           "Church-style booleans use two-arg laws — `T a b = a`, "
           "`F a b = b`. Then `(b x y)` is \"if b then x else y\"."),
    ("code", '(#bind T (#pin (#law "T" (T a b) a)))'),
    ("code", '(#bind F (#pin (#law "F" (F a b) b)))'),
    ("code", "(T 100 999)"),
    ("code", "(F 100 999)"),

    ("md", "Logical AND: `And p q = (p q F)` — if `p` is true, return "
           "`q`; else return `F`."),
    ("code", '(#bind And (#pin (#law "And" (And p q) (p q F))))'),
    ("code", "(And T T 100 999)"),
    ("code", "(And T F 100 999)"),

    ("md", "## What's next\n\n"
           "Lesson 04 introduces **recursion**. The signature's `self` "
           "name lets a law refer to itself, which is how you build "
           "factorial, fibonacci, and the rest of the usual recursive "
           "shapes."),
]


# ---------------------------------------------------------------------------
# Lesson 04 — Recursion
# ---------------------------------------------------------------------------

LESSON_04: list[tuple[str, str]] = [
    ("md", """# 04 — Recursion

A law's signature names `self` (slot 0) — the law itself. References \
to that name in the body produce self-application, and that's how \
recursion works in PLAN. No special `fix` operator: just refer to \
yourself.
"""),

    ("md", "## Factorial\n\n"
           "`fact n = if n < 2 then 1 else n * fact(n - 1)`."),
    ("code", '(#bind fact (#pin (#law "fact" (fact n)\n'
             '  (If (Lt n 2) 1\n'
             '      (Mul n (fact (Sub n 1)))))))'),
    ("code", "(fact 0)"),
    ("code", "(fact 1)"),
    ("code", "(fact 5)"),
    ("code", "(fact 10)"),

    ("md", "Reading the body:\n\n"
           "* `(Lt n 2)` is the base condition.\n"
           "* `(If c t e)` returns `t` if `c` is non-zero, else `e`.\n"
           "* The recursive arm `(Mul n (fact (Sub n 1)))` calls `fact` "
           "directly — no special syntax for self-reference."),

    ("md", "## Fibonacci\n\n"
           "Naive recursion — each call branches into two:"),
    ("code", '(#bind fib (#pin (#law "fib" (fib n)\n'
             '  (If (Lt n 2) n\n'
             '      (Add (fib (Sub n 1)) (fib (Sub n 2)))))))'),
    ("code", "(fib 0)"),
    ("code", "(fib 1)"),
    ("code", "(fib 8)"),
    ("code", "(fib 12)"),

    ("md", "## A note on depth\n\n"
           "The Marduk runtime evaluates by Python recursion. A "
           "self-recursive law of depth N takes O(N) Python stack "
           "frames (with a multiplier for evaluator bookkeeping). "
           "Toy examples like `(fib 12)` work fine; `(fib 30)` will "
           "exhaust the stack on default Python settings.\n\n"
           "Production-grade depth handling is forward work — see the "
           "Marduk roadmap for native trampolining and jet support."),

    ("md", "## A summing function\n\n"
           "Tail-recursive shape: `sum n = sum_acc 0 n` where "
           "`sum_acc acc n` adds `n` into `acc` and recurses on `n-1`."),
    ("code", '(#bind sum_acc (#pin (#law "sum_acc" (sum_acc acc n)\n'
             '  (If (Eq n 0) acc\n'
             '      (sum_acc (Add acc n) (Sub n 1))))))'),
    ("code", "(sum_acc 0 10)"),
    ("code", "(sum_acc 0 100)"),

    ("md", "## What's next\n\n"
           "You've now seen each major construct: nats and BPLAN "
           "primitives, laws, pins, `Elim` and case dispatchers, and "
           "recursion. From here, real PLAN code is just composition "
           "of these — define data shapes via Pin-of-Law constructor "
           "discipline, drive computations through Elim, and let the "
           "self-recursive laws do the work.\n\n"
           "For language reference see "
           "[`vendor/reaver/doc/plan-spec.txt`](https://github.com/xocore-tech/PLAN) "
           "(the formal small-step semantics) and "
           "[`vendor/reaver/src/hs/Plan.hs`](https://github.com/xocore-tech/PLAN) "
           "(the production runtime, including the full BPLAN op set)."),
]


# ---------------------------------------------------------------------------
# Notebook synthesis
# ---------------------------------------------------------------------------

LESSONS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "01": ("01-numbers-and-pins.ipynb",   LESSON_01),
    "02": ("02-laws.ipynb",               LESSON_02),
    "03": ("03-elim-and-cases.ipynb",     LESSON_03),
    "04": ("04-recursion.ipynb",          LESSON_04),
}


def _render_outputs(text: str | None, html: str | None,
                    execution_count: int) -> list[Any]:
    if text is None and html is None:
        return []
    data: dict[str, Any] = {}
    if text is not None:
        data["text/plain"] = text
    if html is not None:
        data["text/html"] = html
    return [v4.new_output("execute_result", data=data,
                          execution_count=execution_count, metadata={})]


def build_lesson(filename: str, cells: list[tuple[str, str]]) -> str:
    nb = v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "name": "plan-kernel",
        "display_name": "PLAN",
        "language": "plan",
    }
    nb.metadata["language_info"] = {
        "name": "plan",
        "mimetype": "text/x-plan",
        "file_extension": ".plan",
        "pygments_lexer": "lisp",
    }

    evaluator = PlanKernelEvaluator()
    exec_count = 0

    for kind, body in cells:
        if kind == "md":
            nb.cells.append(v4.new_markdown_cell(
                body, id=f"md-{len(nb.cells):02d}"
            ))
            continue
        exec_count += 1
        result = evaluator.eval_cell(body)
        if result.error is not None:
            print(f"WARN: cell {exec_count} errored: {result.error}",
                  file=sys.stderr)
        outputs = _render_outputs(
            result.value_text, result.value_html,
            execution_count=exec_count,
        )
        cell = v4.new_code_cell(
            source=body, outputs=outputs, id=f"code-{exec_count:02d}"
        )
        cell["execution_count"] = exec_count
        nb.cells.append(cell)

    out_path = os.path.join(os.path.dirname(__file__), filename)
    with open(out_path, "w") as f:
        nbformat.write(nb, f)
    return out_path


def main(argv: list[str]) -> int:
    selectors = argv[1:] if len(argv) > 1 else list(LESSONS.keys())
    for sel in selectors:
        if sel not in LESSONS:
            print(f"unknown lesson {sel!r}; expected one of "
                  f"{sorted(LESSONS)}", file=sys.stderr)
            return 1
    for sel in selectors:
        filename, cells = LESSONS[sel]
        path = build_lesson(filename, cells)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
