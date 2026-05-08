"""Differential tests: same Plan Asm program, two runtimes, equal output.

For each fixture, this:

  1. Evaluates against Marduk via :func:`marduk.asm.eval_form` after
     loading the BPLAN prelude — Marduk's spec-faithful + jet path.
  2. Writes the same Plan Asm text to a temp directory along with
     ``boot.plan`` from the vendored Reaver checkout, runs Reaver's
     ``plan-assembler`` driver with a ``(Trace (Lsh main 32) 0)``
     trailer, and parses the traced integer back out.
  3. Asserts the two integers are equal.

This catches divergence between Marduk and the canonical Reaver
runtime on real programs. Skip-gated: tests pass through if Reaver
isn't reachable (no nix/cabal, or no vendored checkout). CI runs them
via Nix; local dev typically doesn't.

Conventions:

* Each fixture's ``main`` is a ``Nat`` — Reaver only knows how to
  serialize nats cleanly via ``Trace``.
* We trace ``(Lsh main 32)`` to dodge Reaver's ``showVal`` quirk
  where small nats (in the ASCII byte range) get pretty-printed as
  quoted strings rather than decimals. The shift forces the low bits
  to zero, which can never be a printable string. We right-shift
  back to recover the original value.
* Prelude wrappers come from :mod:`marduk.asm.prelude`. Reaver's
  ``boot.plan`` provides the equivalent — both runtimes have
  ``Add``/``Mul``/``If``/etc. visible without further setup.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest

from marduk.asm import Env, eval_form, parse_many, load_prelude


# ---------------------------------------------------------------------------
# Reaver discovery & skip gating
# ---------------------------------------------------------------------------

# When this package lives at gallowglass/vendor/marduk/packages/marduk/,
# Reaver is at gallowglass/vendor/reaver/. Walk four levels up from
# packages/marduk/tests/ to reach gallowglass/, then into vendor/reaver.
PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GALLOWGLASS_ROOT = os.path.abspath(os.path.join(PKG_ROOT, "..", "..", "..", ".."))
REAVER_DIR = os.environ.get(
    "REAVER_DIR",
    os.path.join(GALLOWGLASS_ROOT, "vendor", "reaver"),
)
BOOT_PLAN = os.path.join(REAVER_DIR, "src", "plan", "boot.plan")


def _reaver_available() -> tuple[bool, str]:
    """Return ``(available, reason)``. Reaver needs a vendored checkout
    plus either ``nix`` (preferred — uses the project flake) or a bare
    ``cabal`` on PATH."""
    if not os.path.isdir(REAVER_DIR):
        return False, f"{REAVER_DIR} not present (set REAVER_DIR or run tools/vendor.sh upstream)"
    if not os.path.isfile(BOOT_PLAN):
        return False, f"{BOOT_PLAN} not present — Reaver checkout incomplete"
    if shutil.which("nix") is None and shutil.which("cabal") is None:
        return False, "neither nix nor cabal on PATH"
    return True, ""


_AVAIL, _SKIP_REASON = _reaver_available()
requires_reaver = unittest.skipUnless(
    _AVAIL, _SKIP_REASON or "reaver unavailable"
)


# ---------------------------------------------------------------------------
# Marduk + Reaver invocation helpers
# ---------------------------------------------------------------------------

def _marduk_eval(plan_text: str, value_name: str = "main") -> int:
    """Run ``plan_text`` through Marduk; look up ``value_name`` in the
    resulting env; return its nat value."""
    env = Env()
    load_prelude(env)
    for form in parse_many(plan_text):
        eval_form(form, env)
    from marduk.runtime.strnat import str_nat
    entry = env.get(str_nat(value_name))
    if entry is None:
        raise AssertionError(
            f"Marduk: {value_name!r} not bound after evaluating fixture"
        )
    val, _is_macro = entry
    if val.type != "nat":
        raise AssertionError(
            f"Marduk: {value_name!r} is not a nat, got type={val.type!r}"
        )
    return val.nat


_TAIL_DECIMAL_PAIR_RE = re.compile(r"(\d+)\s*\n0\s*\n*\Z")


def _parse_traced_int(reaver_output: str) -> int:
    """Pull the trace value off Reaver's output tail.

    Reaver writes binding-name noise on every load, then ``(Trace v 0)``
    prints ``<value>\\n0\\n``. Anchoring at end-of-output is more robust
    than first-match.
    """
    m = _TAIL_DECIMAL_PAIR_RE.search(reaver_output)
    if m is None:
        raise AssertionError(
            "expected `<value>\\n0\\n` tail in Reaver output (value may be "
            f"in byte range and string-formatted by showVal):\n{reaver_output!r}"
        )
    return int(m.group(1))


def _run_reaver(plan_text: str, module: str = "demo", timeout: int = 120) -> str:
    """Write ``plan_text`` + ``boot.plan`` into a tempdir, run
    ``plan-assembler``, return stdout+stderr decoded.

    Uses ``nix develop`` when available (matches Reaver's flake), else
    falls back to bare ``cabal``."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, f"{module}.plan"), "w") as f:
            f.write(plan_text)
        shutil.copy(BOOT_PLAN, os.path.join(tmpdir, "boot.plan"))
        if shutil.which("nix") is not None:
            cmd = ["nix", "develop", "--command", "cabal", "run", "-v0",
                   "plan-assembler", "--", tmpdir, module]
        else:
            cmd = ["cabal", "run", "-v0",
                   "plan-assembler", "--", tmpdir, module]
        result = subprocess.run(
            cmd, cwd=REAVER_DIR, capture_output=True, timeout=timeout,
        )
    return (result.stdout + result.stderr).decode("utf-8", errors="replace")


_SHIFT = 32  # Lsh by this much to force decimal output past the ASCII range


def _reaver_eval(plan_text: str, value_name: str = "main") -> int:
    """Append a ``(Trace (Lsh <main> 32) 0)`` driver, run Reaver, parse
    back the int, right-shift to recover the original value."""
    trailer = f"\n(Trace (Lsh {value_name} {_SHIFT}) 0)\n"
    full = "@boot\n" + plan_text + trailer
    out = _run_reaver(full)
    try:
        shifted = _parse_traced_int(out)
    except AssertionError as e:
        raise AssertionError(
            f"{e}\n--- emitted plan text ---\n{full}"
        ) from None
    return shifted >> _SHIFT


# ---------------------------------------------------------------------------
# Fixtures + assertion
# ---------------------------------------------------------------------------

@requires_reaver
class TestMardukReaverEquivalence(unittest.TestCase):
    """For each fixture, Marduk and Reaver agree on ``main : Nat``.

    Fixtures kept compact: the goal is *coverage* of language features,
    not depth in any one. Nats are kept above 256 so Reaver's
    ``showVal`` definitely renders them as decimals (the ``Lsh 32``
    trick covers smaller values too, but the > 256 convention also
    keeps the raw fixture readable as a number)."""

    def _assert_equiv(self, plan_text: str, value_name: str = "main"):
        marduk = _marduk_eval(plan_text, value_name)
        reaver = _reaver_eval(plan_text, value_name)
        self.assertEqual(
            marduk, reaver,
            f"Marduk/Reaver divergence on {value_name!r}: "
            f"marduk={marduk} reaver={reaver}\n"
            f"--- source ---\n{plan_text}",
        )

    # --- arithmetic --------------------------------------------------------

    def test_basic_arithmetic(self):
        """Literal arithmetic: 1000 + 234 = 1234."""
        self._assert_equiv("(#bind main (Add 1000 234))")

    def test_nested_arithmetic(self):
        """Nested operations: (10 * 100) + 7 = 1007."""
        self._assert_equiv("(#bind main (Add (Mul 10 100) 7))")

    def test_subtraction_saturates(self):
        """Saturating sub: (Sub 500 1000) = 0."""
        self._assert_equiv("(#bind main (Add 500 (Sub 500 1000)))")

    # --- conditionals ------------------------------------------------------

    def test_if_then_branch(self):
        """If with truthy condition picks `t`."""
        self._assert_equiv("(#bind main (If 1 1234 9999))")

    def test_if_else_branch(self):
        """If with zero condition picks `e`."""
        self._assert_equiv("(#bind main (If 0 9999 1234))")

    # --- comparison --------------------------------------------------------

    def test_lt_true(self):
        """Lt yields 1 (then If picks the high branch)."""
        self._assert_equiv("(#bind main (If (Lt 5 10) 12345 0))")

    def test_lt_false(self):
        """Lt yields 0 (If picks the low branch)."""
        self._assert_equiv("(#bind main (If (Lt 10 5) 0 67890))")

    # --- user-defined laws -------------------------------------------------

    def test_simple_law(self):
        """User-defined doubler applied to a nat."""
        self._assert_equiv("""
            (#bind double (#pin (#law "double" (double n) (Add n n))))
            (#bind main (double 678))
        """)

    def test_law_composition(self):
        """A doubler and a squarer composed: square(double(15)) = 900."""
        self._assert_equiv("""
            (#bind double (#pin (#law "double" (double n) (Add n n))))
            (#bind square (#pin (#law "square" (square n) (Mul n n))))
            (#bind main (square (double 15)))
        """)

    # --- recursion ---------------------------------------------------------

    def test_factorial_small(self):
        """5! = 120."""
        self._assert_equiv("""
            (#bind fact (#pin (#law "fact" (fact n)
              (If (Lt n 2) 1
                  (Mul n (fact (Sub n 1)))))))
            (#bind main (fact 5))
        """)

    def test_accumulator_sum(self):
        """sum 1..50 = 1275."""
        self._assert_equiv("""
            (#bind sum (#pin (#law "sum" (sum acc n)
              (If (Eq n 0) acc
                  (sum (Add acc n) (Sub n 1))))))
            (#bind main (sum 0 50))
        """)
