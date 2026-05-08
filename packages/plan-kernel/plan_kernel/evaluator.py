"""Cell-level driver.

``PlanKernelEvaluator`` ties parser → expander → runtime together with a
notebook-scoped ``Env``. ``eval_cell(source)`` returns a ``CellResult`` that
the kernel layer (phase 8) translates into a Jupyter MIME bundle.

Pipeline per cell: parse leading magics → apply them → parse_many on the
remaining body → for each form, macroexpand → thunk → backend evaluator.
Bind-only and trailing-bind cells produce ``bind <name>`` summary lines;
expression cells render the last form's value via ``plan_kernel.render``. Per-
stage exceptions become structured error envelopes; Python's recursion
limit is bumped to 200K so user-level recursion gets a fair shot.

Magic semantics:
- ``%backend NAME`` is per-cell — the backend reverts at end-of-cell.
- ``%reset`` is persistent — cleared bindings stay cleared.
- ``%env`` is read-only.

Deferred to phase 7: BPLAN op prelude auto-loading. ``%reset`` will
preserve the prelude once that lands.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from .expander import Env, MacroError, macroexpand, thunk
from .magics import MagicDirective, MagicError, parse_magics
from .parser import ParseError, parse_many
from .prelude import load_prelude
from .render import render_value
from .runtime.plan import (
    is_nat,
    nat_str, str_nat,
    evaluate,
    _unapp,
)


__all__ = ["CellResult", "PlanKernelEvaluator"]


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
    if isinstance(err, MagicError):
        return "magic"
    if isinstance(err, RecursionError):
        return "runtime"
    return "internal"


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

def _pretty_nat(n) -> str:
    # ``n`` may be a Marduk ``Val`` (post Phase E swap) or a raw int
    # (legacy callers). Normalize to int via ``.nat`` when needed.
    if hasattr(n, "type") and n.type == "nat":
        n = n.nat
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
        and is_nat(parts[0]) and parts[0].nat == 0
        and is_nat(parts[1]) and parts[1].nat == _BIND_NAT
    )




# ---------------------------------------------------------------------------
# PlanKernelEvaluator.
# ---------------------------------------------------------------------------

class PlanKernelEvaluator:
    """Stateful plan-kernel evaluator.

    Owns a notebook-scoped ``Env``. ``eval_cell(source)`` parses, expands,
    and evaluates one cell, returning a ``CellResult``. Side-effects from
    ``#bind`` accumulate across cells.

    Parameters
    ----------
    env
        A pre-existing ``Env`` to use; if ``None``, a fresh empty one is
        created. Useful when the kernel needs to share an env across
        instances.
    backend
        Either ``"evaluate"`` (formal Python evaluator, default) or
        ``"bevaluate"`` (jet-aware, faster for arithmetic). The
        ``%backend`` magic switches this at cell granularity.
    prelude
        If ``True`` (default), load the BPLAN op prelude into ``env`` so
        ``(Add 2 3)`` and friends work in cell 1. ``%reset`` reloads the
        prelude. Pass ``False`` for a fully empty env.
    """

    def __init__(self, env: Env | None = None, backend: str = "evaluate",
                 prelude: bool = True):
        self.env = env if env is not None else Env()
        self._set_backend(backend)
        self._prelude_loaded = bool(prelude)
        self._prelude_names: set[int] = set()
        if prelude:
            self._prelude_names = load_prelude(self.env)

    # ------------------------------------------------------------------
    # Public entry points.
    # ------------------------------------------------------------------

    def eval_cell(self, source: str) -> CellResult:
        if not source.strip():
            return CellResult(decls_only=True)

        directives, body = parse_magics(source)

        # Save backend state for cell-scoped %backend reverts. (env/reset
        # changes deliberately persist.)
        saved_backend = self._backend
        saved_backend_name = self._backend_name
        try:
            magic_outputs: list[str] = []
            try:
                for d in directives:
                    out = self._apply_magic(d)
                    if out is not None:
                        magic_outputs.append(out)
            except MagicError as e:
                return CellResult(error=_error_envelope("magic", e))

            return self._eval_body(body, magic_outputs)
        finally:
            self._backend = saved_backend
            self._backend_name = saved_backend_name

    def _eval_body(self, body: str, magic_outputs: list[str]) -> CellResult:
        if not body.strip():
            if magic_outputs:
                return CellResult(value_text="\n".join(magic_outputs))
            return CellResult(decls_only=True)

        try:
            forms = parse_many(body)
        except ParseError as e:
            return CellResult(error=_error_envelope("parse", e))
        except Exception as e:    # pragma: no cover — defensive
            return CellResult(error=_error_envelope("internal", e))

        if not forms:
            if magic_outputs:
                return CellResult(value_text="\n".join(magic_outputs))
            return CellResult(decls_only=True)

        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, 200_000))
        try:
            result = self._evaluate_forms(forms)
        except (MacroError, RecursionError) as e:
            return CellResult(error=_error_envelope(_stage_for(e), e))
        except Exception as e:
            return CellResult(error=_error_envelope("internal", e))
        finally:
            sys.setrecursionlimit(old_limit)

        if magic_outputs and result.value_text is not None:
            result.value_text = "\n".join(magic_outputs) + "\n" + result.value_text
        return result

    def reset(self) -> None:
        """Clear all user bindings. The prelude (if loaded) is reloaded."""
        self.env.reset()
        if self._prelude_loaded:
            self._prelude_names = load_prelude(self.env)

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

    def _apply_magic(self, d: MagicDirective) -> str | None:
        """Apply one magic directive. Returns optional display output."""
        if d.name == "backend":
            if len(d.args) != 1:
                raise MagicError(f"{d.line}: %backend takes exactly one argument")
            try:
                self._set_backend(d.args[0])
            except ValueError as e:
                raise MagicError(f"{d.line}: {e}") from e
            return None
        if d.name == "reset":
            if d.args:
                raise MagicError(f"{d.line}: %reset takes no arguments")
            self.reset()
            return None
        if d.name == "env":
            if d.args:
                raise MagicError(f"{d.line}: %env takes no arguments")
            user_names = sorted(
                _pretty_nat(n)
                for n in self.env.names()
                if n not in self._prelude_names
            )
            return ", ".join(user_names) if user_names else "(env empty)"
        raise MagicError(f"unknown magic: %{d.name}")

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
