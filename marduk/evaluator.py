"""Cell-level driver.

``MardukEvaluator`` ties parser → expander → runtime together with a
notebook-scoped ``Env``. ``eval_cell(source)`` returns a ``CellResult`` that
the kernel layer (phase 8) translates into a Jupyter MIME bundle.

Phase 4 scope: parse, expand, thunk, evaluate; bind-only cells produce
summary lines; per-stage exceptions become structured error envelopes;
Python's recursion limit is bumped while evaluating so user-level recursion
gets a reasonable shot before tripping ``RecursionError``.

Deferred to later phases:
- ``%backend`` / ``%reset`` / ``%env`` magics — phase 6.
- BPLAN op prelude auto-loading — phase 7.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from .expander import Env, MacroError, macroexpand, thunk
from .parser import ParseError, parse_many
from .render import render_value
from .runtime.plan import (
    is_nat,
    nat_str, str_nat,
    evaluate,
    _unapp,
)


__all__ = ["CellResult", "MardukEvaluator"]


_BIND_NAT = str_nat("#bind")


# ---------------------------------------------------------------------------
# CellResult — public output shape (mirrors gallowglass's kernel).
# ---------------------------------------------------------------------------

@dataclass
class CellResult:
    """Result of evaluating one cell.

    Exactly one of ``value_text`` / ``error`` is populated for non-silent
    cells. ``decls_only=True`` indicates a silent cell (empty source, or all
    forms were silent assignments with no displayable summary).
    """

    value_text: str | None = None
    value_html: str | None = None
    error: dict | None = None
    decls_only: bool = False


# ---------------------------------------------------------------------------
# Internal error envelope — same shape as gallowglass's ``_error_envelope``.
# ---------------------------------------------------------------------------

def _error_envelope(stage: str, err: Exception) -> dict:
    loc = None
    if isinstance(err, ParseError):
        loc = {"file": None, "line": err.line, "col": err.col}
    return {
        "stage": stage,
        "message": str(err),
        "type": type(err).__name__,
        "loc": loc,
    }


def _stage_for(err: Exception) -> str:
    if isinstance(err, ParseError):
        return "parse"
    if isinstance(err, MacroError):
        return "expand"
    if isinstance(err, RecursionError):
        return "runtime"
    return "internal"


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

def _pretty_nat(n) -> str:
    if not isinstance(n, int):
        return repr(n)
    s = nat_str(n)
    if s and not s.startswith("<nat:"):
        return s
    return str(n)


def _is_bind_form(form) -> bool:
    """Structurally check whether ``form`` is a ``(#bind ...)`` macro call."""
    parts = _unapp(form)
    return (
        len(parts) >= 2
        and is_nat(parts[0]) and parts[0] == 0
        and is_nat(parts[1]) and parts[1] == _BIND_NAT
    )




# ---------------------------------------------------------------------------
# MardukEvaluator.
# ---------------------------------------------------------------------------

class MardukEvaluator:
    """Stateful Marduk evaluator.

    Owns a notebook-scoped ``Env``. ``eval_cell(source)`` parses, expands,
    and evaluates one cell, returning a ``CellResult``. Side-effects from
    ``#bind`` accumulate across cells.

    Parameters
    ----------
    env
        A pre-existing ``Env`` to use; if ``None``, a fresh empty one is
        created. Useful when the kernel needs to share an env across
        instances or pre-load a prelude.
    backend
        Either ``"evaluate"`` (formal Python evaluator, default) or
        ``"bevaluate"`` (jet-aware, faster for arithmetic). Phase 6's
        ``%backend`` magic switches this at cell granularity.
    """

    def __init__(self, env: Env | None = None, backend: str = "evaluate"):
        self.env = env if env is not None else Env()
        self._set_backend(backend)

    # ------------------------------------------------------------------
    # Public entry points.
    # ------------------------------------------------------------------

    def eval_cell(self, source: str) -> CellResult:
        if not source.strip():
            return CellResult(decls_only=True)

        try:
            forms = parse_many(source)
        except ParseError as e:
            return CellResult(error=_error_envelope("parse", e))
        except Exception as e:    # pragma: no cover — defensive
            return CellResult(error=_error_envelope("internal", e))

        if not forms:
            return CellResult(decls_only=True)

        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, 200_000))
        try:
            return self._evaluate_forms(forms)
        except (MacroError, RecursionError) as e:
            return CellResult(error=_error_envelope(_stage_for(e), e))
        except Exception as e:
            return CellResult(error=_error_envelope("internal", e))
        finally:
            sys.setrecursionlimit(old_limit)

    def reset(self) -> None:
        """Clear all bindings. (Prelude reload happens in phase 7.)"""
        self.env.reset()

    @property
    def backend_name(self) -> str:
        return self._backend_name

    # ------------------------------------------------------------------
    # Internals.
    # ------------------------------------------------------------------

    def _set_backend(self, name: str) -> None:
        if name == "evaluate":
            self._backend = evaluate
            self._backend_name = name
            return
        if name == "bevaluate":
            # Resolved on first use (lazy import — bplan pulls in jet
            # registration code we don't need until selected).
            from .runtime.bplan import bevaluate
            self._backend = bevaluate
            self._backend_name = name
            return
        raise ValueError(
            f"unknown backend: {name!r} (expected 'evaluate' or 'bevaluate')"
        )

    def _eval_one(self, form):
        """Run one form through expand → thunk → backend."""
        expanded = macroexpand(form, self.env)
        thunked = thunk(expanded, self.env)
        return self._backend(thunked)

    def _evaluate_forms(self, forms) -> CellResult:
        bind_summaries: list[str] = []
        last_value = None
        last_was_bind = False

        for form in forms:
            is_bind = _is_bind_form(form)
            result = self._eval_one(form)
            if is_bind:
                bind_summaries.append(f"bind {_pretty_nat(result)}")
            else:
                last_value = result
            last_was_bind = is_bind

        # Trailing-bind cells (and all-binds cells) display the bind summary
        # block; expression-cells display their final value.
        if last_was_bind:
            if not bind_summaries:
                return CellResult(decls_only=True)    # pragma: no cover
            return CellResult(value_text="\n".join(bind_summaries))

        text, html = render_value(last_value)
        return CellResult(value_text=text, value_html=html)
