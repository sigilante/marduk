"""BPLAN named-primitive dispatch (outer ``<66>``).

Mirrors the ``op 66 [...]`` cases in ``vendor/reaver/src/hs/Plan.hs``:
the saturated form ``(<66> (name args...))`` looks up ``name`` in the op
table and runs the corresponding Python implementation.

Coverage in this module is the **pure** subset of Reaver's BPLAN ops:
arithmetic, comparison, boolean, bit/byte manipulation, fixed-width
truncation, value introspection, the small Case2..Case16 dispatchers,
and the named aliases for the three core constructions (Pin / Law /
Elim). Effects (Throw, Trace, Save, Load, Read, Write, Try, Up,
DeepSeq, Equal) and collection ops (Row, Rep, Slice, Weld, Ix, …) are
not implemented yet — calling them raises ``NotImplementedError`` with
the op name and string-nat encoding for diagnosis.

Adding an op: register it with ``@op("Name", arity)`` and write a small
function that takes the args list (length matches ``arity``) and returns
a ``Val``. The function is responsible for forcing args it needs to
inspect — most arithmetic/comparison ops force via ``_nat`` which calls
``E`` and treats non-nats as zero (matching Reaver's ``nat`` accessor).
"""

from __future__ import annotations

from typing import Callable

from .core import (
    Val, Hol, Nat, Pin, App, Law,
    E, F, A, N, S, C,
    PlanError,
)
from .strnat import nat_str


# ---------------------------------------------------------------------------
# Op table
# ---------------------------------------------------------------------------

OpFn = Callable[[list[Val]], Val]
OPS: dict[str, tuple[int, OpFn]] = {}


def op(name: str, arity: int):
    """Register a BPLAN op under ``name`` with the given ``arity``."""
    def reg(fn: OpFn) -> OpFn:
        OPS[name] = (arity, fn)
        return fn
    return reg


def dispatch(arg: Val) -> Val:
    """Entry point from ``core.S`` for outer opcode 66.

    ``arg`` is the saturated argument; its App spine is
    ``(name_nat, ...args)``. The first element is forced and decoded as
    a UTF-8 string; the rest are passed to the registered op function.
    """
    parts = arg.spine
    if not parts:
        raise PlanError(("BPLAN: empty arg spine", arg))
    name_v = parts[0]
    E(name_v)
    if name_v.type != "nat":
        raise PlanError(("BPLAN: op-name slot is not a nat", name_v))
    name = nat_str(name_v.nat)
    entry = OPS.get(name)
    if entry is None:
        raise NotImplementedError(
            f"BPLAN op {name!r} (nat {name_v.nat}) not implemented"
        )
    expected_arity, fn = entry
    actual = len(parts) - 1
    if actual != expected_arity:
        raise PlanError((
            f"BPLAN op {name!r}: expected {expected_arity} args, got {actual}",
            parts[1:],
        ))
    return fn(parts[1:])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nat(v: Val) -> int:
    """Force ``v`` to WHNF and return its int. Non-nats coerce to 0,
    matching Reaver's ``nat`` accessor (``N(x:@) = x; N_ = 0``)."""
    E(v)
    return v.nat if v.type == "nat" else 0


def _bool(b: bool) -> Val:
    """PLAN-encoded boolean: ``Nat(1)`` for true, ``Nat(0)`` for false."""
    return Nat(1) if b else Nat(0)


def _is_zero(v: Val) -> bool:
    """``v == N 0`` after forcing — Reaver's truthiness predicate (the
    ``If``/``Or``/``And`` ops compare against ``N 0`` exactly)."""
    E(v)
    return v.type == "nat" and v.nat == 0


# ---------------------------------------------------------------------------
# Core construction aliases (named versions of the inner-op-0/1/2 dispatch)
# ---------------------------------------------------------------------------

@op("Pin", 1)
def _bp_pin(args):
    i, = args
    E(i)
    return Pin(i)


@op("Law", 3)
def _bp_law(args):
    a, m, b = args
    E(a)
    arity = N(a)
    if arity.nat == 0:
        raise PlanError(("BPLAN Law: arity 0 is not a law",))
    E(b)
    # Match core's spine-force discipline.
    from .core import B
    B(arity.nat, arity.nat, Hol(), b, b)
    return Law(N(m), arity, b)


@op("Elim", 6)
def _bp_elim(args):
    p, l, ap, z, m, o = args
    E(o)
    return C(p, l, ap, z, m, o)


# ---------------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------------

@op("Inc", 1)
def _inc(args):
    return Nat(_nat(args[0]) + 1)


@op("Dec", 1)
def _dec(args):
    n = _nat(args[0])
    return Nat(0 if n == 0 else n - 1)


@op("Add", 2)
def _add(args):
    return Nat(_nat(args[0]) + _nat(args[1]))


@op("Sub", 2)
def _sub(args):
    x, y = _nat(args[0]), _nat(args[1])
    # Reaver's saturating subtraction: ``if y >= x then 0 else x - y``.
    # The Plan.hs source has the operands swapped (a Reaver-side bug?);
    # we follow the spec convention "Sub x y = max(0, x-y)".
    return Nat(0 if y > x else x - y)


@op("Mul", 2)
def _mul(args):
    return Nat(_nat(args[0]) * _nat(args[1]))


@op("Div", 2)
def _div(args):
    x, y = _nat(args[0]), _nat(args[1])
    return Nat(0 if y == 0 else x // y)


@op("Mod", 2)
def _mod(args):
    x, y = _nat(args[0]), _nat(args[1])
    return Nat(0 if y == 0 else x % y)


@op("Rsh", 2)
def _rsh(args):
    return Nat(_nat(args[0]) >> _nat(args[1]))


@op("Lsh", 2)
def _lsh(args):
    return Nat(_nat(args[0]) << _nat(args[1]))


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

@op("Eq", 2)
def _eq(args):
    return _bool(_nat(args[0]) == _nat(args[1]))


@op("Ne", 2)
def _ne(args):
    return _bool(_nat(args[0]) != _nat(args[1]))


@op("Lt", 2)
def _lt(args):
    return _bool(_nat(args[0]) < _nat(args[1]))


@op("Le", 2)
def _le(args):
    return _bool(_nat(args[0]) <= _nat(args[1]))


@op("Gt", 2)
def _gt(args):
    return _bool(_nat(args[0]) > _nat(args[1]))


@op("Ge", 2)
def _ge(args):
    return _bool(_nat(args[0]) >= _nat(args[1]))


@op("Cmp", 2)
def _cmp(args):
    x, y = _nat(args[0]), _nat(args[1])
    if x < y:
        return Nat(0)
    if x == y:
        return Nat(1)
    return Nat(2)


# ---------------------------------------------------------------------------
# Boolean / control
# ---------------------------------------------------------------------------

@op("Truth", 1)
def _truth(args):
    return _bool(not _is_zero(args[0]))


@op("Or", 2)
def _or(args):
    x, y = args
    return y if _is_zero(x) else x


@op("And", 2)
def _and(args):
    x, y = args
    return Nat(0) if _is_zero(x) else y


@op("If", 3)
def _if(args):
    c, t, e = args
    return e if _is_zero(c) else t


@op("Ifz", 3)
def _ifz(args):
    c, t, e = args
    return t if _is_zero(c) else e


# ---------------------------------------------------------------------------
# Bit / byte manipulation
# ---------------------------------------------------------------------------

@op("Test", 2)
def _test(args):
    i, n = _nat(args[0]), _nat(args[1])
    return _bool((n >> i) & 1)


@op("Set", 2)
def _set(args):
    i, n = _nat(args[0]), _nat(args[1])
    return Nat(n | (1 << i))


@op("Clear", 2)
def _clear(args):
    i, n = _nat(args[0]), _nat(args[1])
    return Nat(n & ~(1 << i))


@op("Bex", 1)
def _bex(args):
    return Nat(1 << _nat(args[0]))


@op("Nib", 2)
def _nib(args):
    ni, n = _nat(args[0]), _nat(args[1])
    return Nat((n >> (4 * ni)) & 0xF)


@op("Load8", 2)
def _load8(args):
    ni, n = _nat(args[0]), _nat(args[1])
    return Nat((n >> (8 * ni)) & 0xFF)


@op("Store8", 3)
def _store8(args):
    i, b, n = _nat(args[0]), _nat(args[1]) & 0xFF, _nat(args[2])
    off = 8 * i
    top = off + 8
    high = (n >> top) << top
    low = n & ((1 << off) - 1) if off else 0
    mid = (b & 0xFF) << off
    return Nat(high | mid | low)


@op("Trunc", 2)
def _trunc(args):
    w, x = _nat(args[0]), _nat(args[1])
    return Nat(x & ((1 << w) - 1)) if w > 0 else Nat(0)


@op("Trunc8", 1)
def _trunc8(args):
    return Nat(_nat(args[0]) & 0xFF)


@op("Trunc16", 1)
def _trunc16(args):
    return Nat(_nat(args[0]) & 0xFFFF)


@op("Trunc32", 1)
def _trunc32(args):
    return Nat(_nat(args[0]) & 0xFFFFFFFF)


@op("Trunc64", 1)
def _trunc64(args):
    return Nat(_nat(args[0]) & 0xFFFFFFFFFFFFFFFF)


@op("Bits", 1)
def _bits(args):
    n = _nat(args[0])
    return Nat(n.bit_length())


@op("Bytes", 1)
def _bytes(args):
    n = _nat(args[0])
    return Nat((n.bit_length() + 7) // 8)


# ---------------------------------------------------------------------------
# Value introspection
# ---------------------------------------------------------------------------

@op("Type", 1)
def _type(args):
    v = args[0]
    E(v)
    return Nat({"pin": 1, "law": 2, "app": 3, "nat": 0}.get(v.type, 0))


@op("IsPin", 1)
def _is_pin(args):
    v = args[0]
    E(v)
    return _bool(v.type == "pin")


@op("IsLaw", 1)
def _is_law(args):
    v = args[0]
    E(v)
    return _bool(v.type == "law")


@op("IsApp", 1)
def _is_app(args):
    v = args[0]
    E(v)
    return _bool(v.type == "app")


@op("IsNat", 1)
def _is_nat(args):
    v = args[0]
    E(v)
    return _bool(v.type == "nat")


@op("Nat", 1)
def _to_nat(args):
    return Nat(_nat(args[0]))


@op("Arity", 1)
def _arity(args):
    v = args[0]
    E(v)
    if v.type == "law":
        return Nat(v.args.nat)
    return Nat(0)


@op("Name", 1)
def _name(args):
    v = args[0]
    E(v)
    if v.type == "law":
        return v.name
    return Nat(0)


@op("Body", 1)
def _body(args):
    v = args[0]
    E(v)
    if v.type == "law":
        return v.body
    return Nat(0)


@op("Unpin", 1)
def _unpin(args):
    v = args[0]
    E(v)
    if v.type == "pin":
        return v.item
    return Nat(0)


# ---------------------------------------------------------------------------
# Sequencing / strict apply
# ---------------------------------------------------------------------------

@op("Seq", 2)
def _seq(args):
    x, y = args
    E(x)
    return y


@op("Seq2", 3)
def _seq2(args):
    x, y, z = args
    E(x); E(y)
    return z


@op("Seq3", 4)
def _seq3(args):
    a, b, c, d = args
    E(a); E(b); E(c)
    return d


@op("Sap", 2)
def _sap(args):
    f, x = args
    E(x)
    out = App(f, x)
    E(out)
    return out


@op("Sap2", 3)
def _sap2(args):
    f, x, y = args
    E(x); E(y)
    out = App(App(f, x), y)
    E(out)
    return out


@op("Force", 1)
def _force_op(args):
    F(args[0])
    return args[0]


# ---------------------------------------------------------------------------
# Hd: head-of-app accessor
# ---------------------------------------------------------------------------

@op("Hd", 1)
def _hd(args):
    v = args[0]
    E(v)
    if v.type == "app":
        # Reaver's Hd returns the App's f (innermost head). For a multi-arg
        # spine (((f a) b) c), this is f — i.e. spine[0].
        return v.spine[0]
    return v


# ---------------------------------------------------------------------------
# Small Case dispatchers (Case2..Case16)
#
# Pattern: op 66 ["CaseN", x, branch_0, branch_1, ..., branch_{N-2}, fb]
# where x is a nat. Returns branch_x if 0 <= x < N-1 else fb.
# ---------------------------------------------------------------------------

def _make_small_case(n: int):
    def _case(args):
        x_v = args[0]
        branches = args[1:-1]   # length n - 1
        fb = args[-1]
        x = _nat(x_v)
        if 0 <= x < n - 1:
            return branches[x]
        return fb
    return _case


for _n in range(2, 17):
    OPS[f"Case{_n}"] = (_n + 1, _make_small_case(_n))
