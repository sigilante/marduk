"""Macro expander for Plan Asm.

Port of ``vendor/reaver/src/hs/PlanAssembler.hs`` lines 158-306 (Macro
enum, ``expand1``, ``macroexpand``, ``thunk``, ``lawExp``, ``compileExpr``).

Surface macros supported in the Plan Asm subset: ``#pin``, ``#law``,
``#app``, ``#bind``. ``#macro`` and ``#export`` are recognized but
rejected — they require module-loading semantics that don't make sense
in a notebook (per PLAN's "Out of scope" notes). User-defined macros
(which are created by ``#macro``) are therefore also unsupported.

The expander is shape-preserving: a ``Val`` from the parser comes in, a
``Val`` ready for ``thunk`` + runtime evaluation comes out.
``macroexpand`` walks ``(0 head args...)`` forms; ``expand1`` produces
the (1 ...)-wrapped expansions that ``thunk`` then unwraps before runtime
evaluation.

Lifted from ``packages/plan-kernel/plan_kernel/expander.py`` (which itself
ports PlanAssembler.hs); the changes here are translating from
plan-kernel's runtime API (raw Python ints for nats, separate ``A``/``L``/``P``
classes) to Marduk's runtime API (a single ``Val`` cell type, accessed via
``.type``/``.nat``/``.head``/``.tail``).
"""

from __future__ import annotations

from ..runtime import App, Hol, Law, Nat, Pin, Val, evaluate
from ..runtime.strnat import nat_str, str_nat


__all__ = [
    "Env",
    "MacroError",
    "macroexpand",
    "thunk",
    "eval_form",
]


# Builtin macro head-symbol nats.
_PIN_NAT    = str_nat("#pin")
_LAW_NAT    = str_nat("#law")
_BIND_NAT   = str_nat("#bind")
_MACRO_NAT  = str_nat("#macro")
_APP_NAT    = str_nat("#app")
_EXPORT_NAT = str_nat("#export")
_JUXT_NAT   = str_nat("#juxt")
_HASH_NAT   = str_nat("#")

# Macro identifiers.
_PIN    = "PIN"
_LAW    = "LAW"
_BIND   = "BIND"
_MACRO  = "MACRO"
_APP    = "APP"
_EXPORT = "EXPORT"

_BUILTIN_MACRO_NAMES = {
    _PIN_NAT:    _PIN,
    _LAW_NAT:    _LAW,
    _BIND_NAT:   _BIND,
    _MACRO_NAT:  _MACRO,
    _APP_NAT:    _APP,
    _EXPORT_NAT: _EXPORT,
}


class MacroError(Exception):
    """Raised when macro expansion or thunking fails."""


# ---------------------------------------------------------------------------
# Env — top-level mutable environment.
# ---------------------------------------------------------------------------

class Env:
    """Top-level environment.

    Maps name nats (raw Python ints) to ``(value, is_macro)`` tuples.
    ``#bind`` adds entries with ``is_macro=False``; ``#macro`` would add
    ``is_macro=True`` entries but the kernel rejects ``#macro``, so all
    entries are values.
    """

    def __init__(self):
        self._d: dict[int, tuple] = {}

    def get(self, key: int):
        """Return ``(value, is_macro)`` or ``None``."""
        return self._d.get(key)

    def put(self, key: int, val: Val, is_macro: bool = False) -> None:
        self._d[key] = (val, is_macro)

    def reset(self) -> None:
        self._d.clear()

    def names(self) -> list[int]:
        return list(self._d.keys())

    def __contains__(self, key: int) -> bool:
        return key in self._d


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

def _is_nat(v: Val) -> bool:
    return v.type == "nat"


def _is_app(v: Val) -> bool:
    return v.type == "app"


def _array(xs: list[Val]) -> Val:
    """``adt 0 xs``. Empty → ``Nat(0)``; non-empty → left-folded App chain."""
    if not xs:
        return Nat(0)
    v = Nat(0)
    for x in xs:
        v = App(v, x)
    return v


def _apple(xs: list[Val]) -> Val:
    """``apple xs``: ``[]→Nat(0)``, ``[a]→a``, else left-fold App over args."""
    if not xs:
        return Nat(0)
    out = xs[0]
    for x in xs[1:]:
        out = App(out, x)
    return out


def _list_elems(ctx: str, v: Val) -> list[Val]:
    """Extract args from ``(0 args...)``. Errors if ``v`` isn't that shape."""
    parts = v.spine
    if parts and _is_nat(parts[0]) and parts[0].nat == 0:
        return parts[1:]
    raise MacroError(f"{ctx}: expected list: {v!r}")


def _law_quote(x: Val) -> Val:
    """``lawQuote x = array [x]`` — i.e. ``(0 x)``."""
    return _array([x])


def _pretty_nat(n: int) -> str:
    """Best-effort display for diagnostics."""
    s = nat_str(n)
    if s and not s.startswith("<nat:"):
        return s
    return str(n)


# ---------------------------------------------------------------------------
# Macro resolution.
# ---------------------------------------------------------------------------

def _resolve_macro(head: Val, locals_dict: dict[int, int], env: Env):
    """Determine whether ``head`` (the head sym of a ``(0 head args...)``
    form) names a macro that should expand.

    Locals shadow env. An env entry with ``is_macro=False`` is a plain
    bound value, not a macro. Builtin macro names only fire when the
    symbol is neither in locals nor in env.
    """
    if not _is_nat(head):
        return None
    s = head.nat
    if s in locals_dict:
        return None
    entry = env.get(s)
    if entry is not None:
        _val, is_macro = entry
        if is_macro:
            raise MacroError(
                f"user macros are not supported (symbol: {_pretty_nat(s)!r})"
            )
        return None
    return _BUILTIN_MACRO_NAMES.get(s)


# ---------------------------------------------------------------------------
# macroexpand.
# ---------------------------------------------------------------------------

def macroexpand(val: Val, env: Env, locals_dict: dict[int, int] | None = None) -> Val:
    """Expand all macros in ``val`` against ``env``.

    ``locals_dict`` is a ``{name_nat: slot_index}`` map of in-scope law
    locals (self, args, binds). Macros named by a local symbol are NOT
    expanded — the local reference wins.
    """
    if locals_dict is None:
        locals_dict = {}
    parts = val.spine
    if not parts:
        return val

    # Special: (0 #juxt # x) inside a law body — recurse on x but preserve
    # the splicing wrapper so compileExpr can spot it later.
    if (
        locals_dict
        and len(parts) == 4
        and _is_nat(parts[0]) and parts[0].nat == 0
        and _is_nat(parts[1]) and parts[1].nat == _JUXT_NAT
        and _is_nat(parts[2]) and parts[2].nat == _HASH_NAT
    ):
        x_expanded = macroexpand(parts[3], env, locals_dict)
        return _array([Nat(_JUXT_NAT), Nat(_HASH_NAT), x_expanded])

    # General (0 head args...) form.
    if _is_nat(parts[0]) and parts[0].nat == 0:
        xs = parts[1:]
        if not xs:
            return val
        head = xs[0]
        mac = _resolve_macro(head, locals_dict, env)
        if mac is None:
            expanded = [macroexpand(x, env, locals_dict) for x in xs]
            return _array(expanded)
        new_v = _expand1(mac, val, env)
        return macroexpand(new_v, env, locals_dict)

    # Not a (0 ...) form — leave alone.
    return val


# ---------------------------------------------------------------------------
# expand1 — single macro step.
# ---------------------------------------------------------------------------

def _expand1(mac: str, val: Val, env: Env) -> Val:
    elems = _list_elems("expand1", val)
    # elems[0] is the head sym (the macro name); elems[1:] are the macro args.

    if mac == _PIN:
        if len(elems) != 2:
            raise MacroError(f"#pin: bad form: {val!r}")
        return App(Nat(1), Pin(_eval(elems[1], env)))

    if mac == _LAW:
        if len(elems) < 4:
            raise MacroError(f"#law: bad form: {val!r}")
        tag, sig, forms = elems[1], elems[2], elems[3:]
        return App(Nat(1), _law_exp(tag, sig, forms, env))

    if mac == _BIND:
        if len(elems) != 3:
            raise MacroError(f"#bind: bad form: {val!r}")
        nm = elems[1]
        if not _is_nat(nm):
            raise MacroError(f"#bind: bad bind-key: {nm!r}")
        result = _eval(elems[2], env)
        env.put(nm.nat, result, is_macro=False)
        return App(Nat(1), Nat(nm.nat))

    if mac == _APP:
        if len(elems) < 1:
            raise MacroError(f"#app: bad form: {val!r}")
        exprs = elems[1:]
        vs = [_eval(e, env) for e in exprs]
        return App(Nat(1), evaluate(_apple(vs)))

    if mac == _MACRO:
        raise MacroError(
            "#macro is not supported "
            "(user macros require module-loading semantics)"
        )

    if mac == _EXPORT:
        raise MacroError(
            "#export is not supported "
            "(notebooks have no module to export to)"
        )

    raise MacroError(f"bad-form: unknown macro {mac!r}")


# ---------------------------------------------------------------------------
# thunk — convert macro-expanded form to a value ready for runtime evaluate.
# ---------------------------------------------------------------------------

def thunk(top: Val, env: Env) -> Val:
    """Mirror PlanAssembler's ``thunk``.

    * ``Nat(0)`` (bare) → ``Nat(0)``
    * ``(1 x)`` → ``x`` (unwraps the macro-layer's literal-quotation)
    * bare ``Nat(n)`` (n != 0) → look up in env, error if unbound
    * ``(0 args...)`` → ``apple`` of recursively-thunked args
    """
    parts = top.spine

    if len(parts) == 1 and _is_nat(parts[0]) and parts[0].nat == 0:
        return Nat(0)

    if len(parts) == 2 and _is_nat(parts[0]) and parts[0].nat == 1:
        return parts[1]

    if len(parts) == 1 and _is_nat(parts[0]):
        n = parts[0].nat
        entry = env.get(n)
        if entry is None:
            raise MacroError(f"expr: unbound: {_pretty_nat(n)}")
        return entry[0]

    args = _list_elems("thunk", top)
    return _apple([thunk(a, env) for a in args])


# ---------------------------------------------------------------------------
# Macro-layer eval: expand >> thunk >> runtime evaluate.
# ---------------------------------------------------------------------------

def _eval(val: Val, env: Env) -> Val:
    return evaluate(thunk(macroexpand(val, env), env))


def eval_form(val: Val, env: Env) -> Val:
    """Public entry: full macro-layer evaluation pipeline (expand → thunk →
    evaluate)."""
    return _eval(val, env)


# ---------------------------------------------------------------------------
# law_exp — build a Law from (#law tag sig binds... body).
# ---------------------------------------------------------------------------

def _law_exp(tag_form: Val, sig_form: Val, forms: list[Val], env: Env) -> Val:
    if not forms:
        raise MacroError("law: missing body")
    body_src = forms[-1]
    bind_forms = forms[:-1]

    tag = _eval(tag_form, env)

    sig_args = _list_elems("sig", sig_form)
    if not sig_args:
        raise MacroError("sig: empty signature")
    arg_nats = []
    for s in sig_args:
        if not _is_nat(s):
            raise MacroError(f"arg-name: bad: {s!r}")
        arg_nats.append(s.nat)
    self_name = arg_nats[0]
    arg_syms = arg_nats[1:]
    n_args = len(arg_syms)
    if n_args == 0:
        raise MacroError("empty argument list")

    binds = [_parse_bind(bf) for bf in bind_forms]
    bind_names = [b[0] for b in binds]
    bind_exprs = [b[1] for b in binds]

    locals_dict: dict[int, int] = {self_name: 0}
    for i, an in enumerate(arg_syms, start=1):
        locals_dict[an] = i
    for i, bn in enumerate(bind_names, start=n_args + 1):
        locals_dict[bn] = i

    bind_exps = [macroexpand(e, env, locals_dict) for e in bind_exprs]
    body_exp = macroexpand(body_src, env, locals_dict)
    bind_irs = [_compile_expr(locals_dict, e, env) for e in bind_exps]
    body_ir = _compile_expr(locals_dict, body_exp, env)

    body = body_ir
    for bind_ir in reversed(bind_irs):
        body = App(App(Nat(1), bind_ir), body)

    # Construct the Law via Marduk's smart constructor. Match the runtime
    # spine-force discipline so the body is evaluated consistently.
    arity = Nat(n_args)
    from ..runtime.core import B
    B(n_args, n_args, Hol(), body, body)
    return Law(tag, arity, body)


def _parse_bind(v: Val) -> tuple[int, Val]:
    elems = _list_elems("bind", v)
    if (len(elems) == 3
        and _is_nat(elems[0]) and elems[0].nat == _JUXT_NAT
        and _is_nat(elems[1])):
        return (elems[1].nat, elems[2])
    raise MacroError(f"law: bad bind: {v!r}")


# ---------------------------------------------------------------------------
# compile_expr — build the law-body IR.
# ---------------------------------------------------------------------------

def _compile_expr(locals_dict: dict[int, int], val: Val, env: Env) -> Val:
    # Nat 0 → (0 0)
    if _is_nat(val) and val.nat == 0:
        return _law_quote(Nat(0))

    # (1 x) → (0 x)  (quoted literal)
    if _is_app(val) and _is_nat(val.head) and val.head.nat == 1:
        return _law_quote(val.tail)

    # Bare nat → local slot, env constant, or unbound.
    if _is_nat(val):
        s = val.nat
        if s in locals_dict:
            return Nat(locals_dict[s])
        entry = env.get(s)
        if entry is not None:
            return App(Nat(0), entry[0])
        raise MacroError(f"law: unbound: {_pretty_nat(s)}")

    # (0 args...) form.
    if _is_app(val):
        parts = val.spine
        if parts and _is_nat(parts[0]) and parts[0].nat == 0:
            xs = parts[1:]
            # Manual splicing: (0 #juxt # expr).
            if (len(xs) == 3
                and _is_nat(xs[0]) and xs[0].nat == _JUXT_NAT
                and _is_nat(xs[1]) and xs[1].nat == _HASH_NAT):
                return _eval(xs[2], env)
            if not xs:
                return _law_quote(Nat(0))
            f = xs[0]
            as_ = xs[1:]
            f_ir = _compile_expr(locals_dict, f, env)
            as_irs = [_compile_expr(locals_dict, a, env) for a in as_]
            result = f_ir
            for a in as_irs:
                result = _array([result, a])
            return result

    raise MacroError(f"compile_expr: unhandled value: {val!r}")
