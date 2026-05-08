"""Spec-faithful PLAN core.

A direct translation of ``vendor/reaver/doc/plan-spec.txt`` into Python.
The spec's 21 lines of small-step rewrite rules become a dozen small
functions over a single ``Val`` cell type that supports update-in-place
via ``Val.box``. The box indirection IS the thunk mechanism — letrec, Y,
fix, and cyclic environments work because evaluation can update a cell's
contents while other references to it observe the new value (and detect
loops via the ``Hol`` sentinel).

Origin: this file is a modernization of Sol's 270-line proof-of-concept
preserved verbatim at gallowglass/``vendor/death-to-the-corporation-old-plan.py``.
The structural ideas — the Val cell, the spec rules I/A/N/R/L/B/C/P/S/X/F/E
named after the spec letters, and the cyclic update via box mutation —
are Sol's. The deltas vs the proof-of-concept reflect how PLAN's ABI has
moved since:

  1.  **Pinned-nat dispatch.** Bare nats are no longer opcodes; they have
      arity 0 (data only). The PLAN dispatcher is the pinned-nat ``<o>``,
      arity 1, applied to a single argument whose App spine encodes
      ``(inner-op, ...args)``. Outer ``<0>`` is core PLAN; ``<66>`` is
      BPLAN; ``<82>`` is RPLAN. The proof-of-concept's bare-nat dispatch
      collapses three abstractions (which is why it worked, but couldn't
      grow into BPLAN/RPLAN cleanly).
  2.  **Three core opcodes** instead of five. Inner opcode 0 is Pin
      construction, 1 is Law construction, 2 is Elim. The proof-of-concept
      had five (Law, Elim, Case-on-nat, Inc, Pin); the latter three moved
      into BPLAN.
  3.  **Pin items reduce to WHNF, not full normal form.** Per spec rule
      ``S0(0 i) = Ei; <i>`` (force i with E, not F). The proof-of-concept
      used F.
  4.  **Law spines are forced on construction via B**, not full normal
      form. Per spec rule ``Jamb = Eb; Baa0bb; {a m b}`` — the B/L
      side-effects walk the body's let-binding spine, forcing each
      continuation and value to WHNF without recursing into pin contents.
      Where the proof-of-concept calls ``F(b)``, this implementation
      calls ``B(a, a, Hol(), b, b)`` and discards the return value.

BPLAN (outer ``<66>``) and RPLAN (outer ``<82>``) primitives are not yet
implemented in this core. Calling into them raises ``NotImplementedError``;
they ride on top via a separate primop table in a subsequent commit.
"""

from __future__ import annotations

from typing import Any


__all__ = [
    "Val",
    "Hol", "Nat", "Pin", "App", "Law",
    "evaluate", "force",
    "PlanError", "PlanLoop",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class PlanError(Exception):
    """Raised when a PLAN form crashes (stuck state, malformed args)."""


class PlanLoop(PlanError):
    """Raised when evaluation enters an unproductive loop on a hole.

    Spec rule ``E<> = E<>`` — forcing a hole forces a hole forever. Python
    cannot represent that literally, so we raise instead. Productive cycles
    (where the hole gets updated to a real value before being re-entered)
    are fine; only re-entering a hole that was never updated counts as a
    loop.
    """


# ---------------------------------------------------------------------------
# Val — the universal cell type
#
# A Val carries one field, ``box``, which is a single-element list holding
# the actual data tuple. Two Vals share state when they share a box. The
# ``update(other)`` method points self at other's box AND mutates self's
# box's contents to match — this dual update is what lets the cyclic
# letrec construction in L work: the slot reachable from old references
# AND the slot reachable from new references both observe the new value.
# ---------------------------------------------------------------------------

class Val:
    """A PLAN value cell.

    The constructor takes the raw data form (an int for a nat, a tuple of
    length 0/1/2/3 for hol/pin/app/law) and wraps it in a one-element list
    so that ``update`` can mutate-in-place.
    """

    __slots__ = ("box",)
    __match_args__ = ("val",)

    def __init__(self, val: Any) -> None:
        self.box = [val]

    def update(self, other: "Val") -> None:
        """Replace self's contents with other's, in a way that aliases of
        either Val see the new value. Used by E (when stepping a saturated
        app cyclically updates its own cell) and by L (when a letrec slot
        gets its computed binding installed)."""
        self.box[0] = other.box[0]
        self.box = other.box

    # ---- Attribute accessors driven by the data shape ------------------

    @property
    def val(self) -> Any:
        return self.box[0]

    @property
    def type(self) -> str:
        v = self.box[0]
        if isinstance(v, int):
            return "nat"
        # tuples of length 0, 1, 2, 3 → hol, pin, app, law
        return ("hol", "pin", "app", "law")[len(v)]

    # nat
    @property
    def nat(self) -> int:
        return self.box[0]

    # pin
    @property
    def item(self) -> "Val":
        return self.box[0][0]

    # app
    @property
    def head(self) -> "Val":
        return self.box[0][0]

    @property
    def tail(self) -> "Val":
        return self.box[0][1]

    # law
    @property
    def name(self) -> "Val":
        return self.box[0][0]

    @property
    def args(self) -> "Val":
        return self.box[0][1]

    @property
    def body(self) -> "Val":
        return self.box[0][2]

    @property
    def id(self) -> int:
        """Identity of the underlying box. Two Vals share identity iff they
        share state — i.e., updating one updates the other."""
        return id(self.box)

    # ---- Spine flattening ----------------------------------------------

    @property
    def spine(self) -> list["Val"]:
        """Flatten an App spine into ``[head, *args]``. Non-App values
        return ``[self]``. Mirrors Reaver's ``unapp`` (Types.hs:44)."""
        out = []
        cur = self
        while cur.type == "app":
            out.append(cur.tail)
            cur = cur.head
        out.append(cur)
        out.reverse()
        return out

    # ---- Equality and display ------------------------------------------

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Val):
            return self.val == other.val
        # Convenience: a nat-typed Val compares equal to a Python int with
        # matching value. This makes ``some_val == 0`` and similar idioms
        # work without unpacking ``.nat`` everywhere. Non-nat types still
        # return NotImplemented so integer comparison stays type-safe.
        if isinstance(other, int) and self.type == "nat":
            return self.nat == other
        return NotImplemented

    def __hash__(self) -> int:
        # Vals are mutable cells; hashing by identity is the only sane choice.
        return id(self.box)

    def __repr__(self) -> str:
        t = self.type
        v = self.val
        if t == "nat":
            return repr(v)
        if t == "hol":
            return "<>"
        if t == "pin":
            return f"<{v[0]!r}>"
        if t == "law":
            return f"{{{v[0]!r} {v[1]!r} {v[2]!r}}}"
        if t == "app":
            return f"({' '.join(repr(x) for x in self.spine)})"
        return f"<unknown:{t}>"


# ---------------------------------------------------------------------------
# Smart constructors
# ---------------------------------------------------------------------------

def Hol() -> Val:
    """A hole — empty cell. Forcing it raises ``PlanLoop`` unless something
    updates it first. Used by L for letrec slots and by E for cyclic
    self-update during saturated-app stepping."""
    return Val(())


def Nat(i: int) -> Val:
    if not isinstance(i, int) or i < 0:
        raise PlanError(f"Nat: expected non-negative int, got {i!r}")
    return Val(i)


def Pin(item: Val) -> Val:
    return Val((item,))


def App(f: Val, x: Val) -> Val:
    return Val((f, x))


def Law(name: Val, arity: Val, body: Val) -> Val:
    return Val((name, arity, body))


# ---------------------------------------------------------------------------
# Spec rules: I, A, N, R, L, B, C, P, S, X, F, E
#
# Naming follows plan-spec.txt; module-level public names (``evaluate``,
# ``force``) wrap E and F.
# ---------------------------------------------------------------------------

# Spec table for nat arity. Pin'd-nat (``<o>``) has arity 1 regardless of o
# (per ``A<i> = 1``), but the outer dispatcher distinguishes opcodes by o's
# value. Bare nats are data — arity 0 — and never directly saturate.
#
# We don't need a literal arity table for nats; A returns 0 for them.

def I(f: Val, o: Val, n: int) -> Val:
    """Index into a list (App spine) by reverse position.

    ``I f o n`` walks ``o`` ``n`` Apps deep on the head side and returns
    the tail at that depth, falling back to ``f`` if the spine is shorter
    than ``n`` and bottoms out on a non-App.

    Mirrors spec ``I0(e x) = x; In(e x) = I(n-1)e; In_ = 0``."""
    while n > 0:
        if o.type == "app":
            o = o.head
            n -= 1
        else:
            return f
    return o.tail if o.type == "app" else o


def A(o: Val) -> int:
    """Arity. Mirrors spec arity table:

      A(f x)     = max(0, Af - 1)        -- App: head's arity decremented
      A{a m b}   = a                     -- Law: stored arity
      A<{a m b}> = a                     -- Pin'd Law: same
      A<i>       = 1                     -- Pin'd anything else: 1
      A@         = 0                     -- Hole: 0
      A(nat)     = 0                     -- bare nats are data

    The App case clamps at 0 rather than going negative; per Plan.hs's
    ``arity (A f xs) = if af==0 then 0 else af - length xs`` an over-applied
    head doesn't go negative — it's stuck."""
    t = o.type
    if t == "app":
        af = A(o.head)
        return 0 if af == 0 else af - 1
    if t == "pin":
        inner = o.item
        if inner.type == "law":
            return inner.args.nat
        return 1
    if t == "law":
        return o.args.nat
    if t == "hol":
        raise PlanLoop("arity of hole")
    # nat
    return 0


def N(o: Val) -> Val:
    """Cast to nat — force ``o`` to WHNF and return it if it's a nat,
    else 0. Mirrors spec ``N(x:@) = x; N_ = 0``."""
    E(o)
    return o if o.type == "nat" else Nat(0)


def R(n: int, e: Val, b: Val) -> Val:
    """Reduce a body ``b`` under environment ``e`` of size ``n``.

    Spec rules:

      Rne(b:@) | b<=n = I(n-b)e               -- de Bruijn ref
      Rne(0 f x)      = Ef; Ex; (Rnef Rnex)   -- apply
      Rne(0 x)        = Ex; x                 -- quote (suppress reduction)
      Rnex            = x                     -- otherwise pass through
    """
    if b.type == "nat" and b.nat <= n:
        return I(b, e, n - b.nat)

    parts = b.spine
    # Apply: (0 f x) — exactly 3 parts, head is nat 0
    if (len(parts) == 3
            and parts[0].type == "nat" and parts[0].nat == 0):
        f, x = parts[1], parts[2]
        return App(R(n, e, f), R(n, e, x))
    # Quote: (0 x) — exactly 2 parts, head is nat 0
    if (len(parts) == 2
            and parts[0].type == "nat" and parts[0].nat == 0):
        return parts[1]
    # Anything else: pass through unchanged
    return b


def L(i: int, n: int, e: Val, x: Val) -> Val:
    """Process let-bindings in a law body, in cyclic order.

    For each ``(1 v b)`` form encountered, force v's reduction under the
    current env, install it into slot ``n - i`` (which started life as a
    hole when B set up the env), and recurse on b. When the form is no
    longer ``(1 v b)``, recursively reduce it as the law's terminal body.

    Spec:

      Line(1 v b) = Ev; Iie#Rnev; L(i+1)neb
      Linex       = Rnex
    """
    parts = x.spine
    if (len(parts) == 3
            and parts[0].type == "nat" and parts[0].nat == 1):
        v, b = parts[1], parts[2]
        # The slot we wrote during B's descent. The constant 999 is a
        # never-used fallback — I should never bottom out at the ``f``
        # arg here because the slot exists.
        I(Nat(999), e, n - i).update(R(n, e, v))
        return L(i + 1, n, e, b)
    return R(n, e, x)


def B(a: int, n: int, e: Val, b: Val, x: Val) -> Val:
    """Build the let-binding env for a law body.

    Walks the spine of ``x``; for each ``(1 _ k)`` form, increments n,
    extends e with a fresh Hol (the slot for the binding's value, to be
    filled by L), and recurses on k. When the form bottoms out, hands off
    to L which fills the slots in cyclic order.

    Spec:

      Baneb(1 _ k) = Ek; Ba(n+1)(e <>)bk
      Banebx       = Laneb
    """
    parts = x.spine
    if (len(parts) == 3
            and parts[0].type == "nat" and parts[0].nat == 1):
        _v, k = parts[1], parts[2]
        # Spec forces k to WHNF here; in our representation x is already
        # the structure we walk and k is just a sub-Val we dereference,
        # so the Ek is implicit (we'll evaluate any sub-form as we hit it).
        return B(a, n + 1, App(e, Hol()), b, k)
    return L(a + 1, n, e, b)


def C(p: Val, l: Val, ap: Val, z: Val, m: Val, o: Val) -> Val:
    """The unified eliminator (PLAN's ``Elim``).

    Dispatches on ``o``'s type; in each case applies the matching handler
    to o's components. Spec:

      Cp____<i>     = p i           -- pin (any pin'd val): unwrap
      C_l___{a m b} = l a m b       -- law: explode header + body
      C__a__(x e)   = a x e         -- app: explode head + tail
      C___z_0       = z             -- nat zero: just z
      C____m(o:@)   = m (o-1)       -- nat succ: predecessor under m
    """
    t = o.type
    if t == "pin":
        return App(p, o.item)
    if t == "law":
        return App(App(App(l, o.name), o.args), o.body)
    if t == "app":
        return App(App(ap, o.head), o.tail)
    if t == "nat":
        if o.nat == 0:
            return z
        return App(m, Nat(o.nat - 1))
    raise PlanLoop("eliminator on hole")


def S(o: int, arg: Val) -> Val:
    """Outer dispatch. ``o`` is the pinned-nat opcode (0 = core, 66 = BPLAN,
    82 = RPLAN). ``arg`` is the saturated argument, an App spine of the
    form ``(inner-op ...args)``.

    Core PLAN (``<0>``) has three inner opcodes:

      S0(0 i)           = Ei; <i>           -- Pin construction
      S0(1 a m b)       = Ea; J(Na+1)mb     -- Law construction
      S0(2 p l a z m o) = Eo; Cplazmo       -- Elim
    """
    if o == 0:
        parts = arg.spine
        if not parts or parts[0].type != "nat":
            raise PlanError(("S0: malformed arg (head is not a nat)", arg))
        inner = parts[0].nat
        rest = parts[1:]
        if inner == 0:
            if len(rest) != 1:
                raise PlanError(("S0(Pin): expected 1 arg", rest))
            i = rest[0]
            E(i)
            return Pin(i)
        if inner == 1:
            if len(rest) != 3:
                raise PlanError(("S0(Law): expected 3 args", rest))
            a_arg, m_arg, b_arg = rest
            E(a_arg)
            arity = N(a_arg)
            if arity.nat == 0:
                raise PlanError(("S0(Law): arity 0 is not a law", arg))
            E(b_arg)
            # Spine-force the body via B with a hole-only env. The B/L
            # side-effects force each let-binding's continuation (in B)
            # and value (in L) to WHNF. Per spec ``Jamb = Eb; Baa0bb;
            # {a m b}`` — the return value of B is discarded; only the
            # forcing side-effects matter at construction time.
            B(arity.nat, arity.nat, Hol(), b_arg, b_arg)
            return Law(N(m_arg), arity, b_arg)
        if inner == 2:
            if len(rest) != 6:
                raise PlanError(("S0(Elim): expected 6 args", rest))
            p, l, ap, z, m, o_arg = rest
            E(o_arg)
            return C(p, l, ap, z, m, o_arg)
        raise PlanError(("S0: unknown inner opcode", inner, arg))
    if o == 66:
        # Lazy import: bplan.py imports from core, so the import at module
        # top would cycle. The first real call lands the table.
        from . import bplan
        return bplan.dispatch(arg)
    if o == 82:
        raise NotImplementedError(
            "RPLAN op 82: implemented in marduk.runtime.rplan (not yet wired)"
        )
    raise PlanError(("S: unknown outer opcode", o))


def X(k: Val, e: Val) -> Val:
    """Execute a step on a saturated form.

    ``e`` is the saturated App (the whole expression that just hit arity 0).
    ``k`` is a walking pointer into ``e`` that descends through the App
    spine and any pin layers to find the leaf head — a pinned nat (the
    PLAN dispatcher), a pinned law, or a bare law.

    Spec:

      Xe(<o:@> x) = Ex; Sox          -- pinned nat dispatcher
      Xe(f x)     = Xef              -- App: descend into f
      Xe{a m b}   = Baaebb           -- bare law: build env + run body
      Xe<{a m b}> = Baaebb           -- pinned law: same
    """
    while True:
        t = k.type
        if t == "app":
            k = k.head
            continue
        if t == "pin":
            inner = k.item
            if inner.type == "nat":
                # ``<o>`` saturates with one arg; that arg is e.tail
                # (e is App(<o>, arg) at saturation).
                arg = e.tail
                E(arg)
                return S(inner.nat, arg)
            if inner.type == "law":
                return B(inner.args.nat, inner.args.nat, e,
                         inner.body, inner.body)
            raise PlanError(("X: pin'd non-nat-non-law in head", k))
        if t == "law":
            return B(k.args.nat, k.args.nat, e, k.body, k.body)
        if t == "hol":
            raise PlanLoop("X: hole in head position")
        # bare nat — saturated bare-nat shouldn't occur because A(nat)=0,
        # so an App over a bare nat has arity 0 from the start and never
        # enters the saturation path. If we arrive here something else has
        # gone wrong upstream.
        raise PlanError(("X: bare nat in head; should not reach here", k, e))


def F(o: Val) -> Val:
    """Force to full normal form along the App spine.

    Forces o to WHNF, then if it's an App, recursively forces head and
    tail. Pin contents and Law bodies remain opaque — F does NOT recurse
    into them. Spec:

      Fo (App case): F head; F tail
      Fo (else): just E(o)
    """
    E(o)
    if o.type == "app":
        F(o.head)
        F(o.tail)
    return o


def E(o: Val) -> Val:
    """Evaluate to weak head normal form.

    Spec:

      E<>        = E<>          -- hole forces forever (we raise instead)
      E(o:(f x)) = Ef; Ho(Af)   -- App: force head, then handle saturation
      Eo         = o            -- already WHNF

    Where ``Ho`` is:

      Ho1 = o#Xoo; Eo           -- arity-1 (saturated): cyclic update + re-E
      Hoa = o                   -- not yet saturated: no-op
    """
    t = o.type
    if t == "hol":
        raise PlanLoop("E: hole encountered")
    if t == "app":
        E(o.head)
        if A(o.head) == 1:
            # The cyclic update: o's box becomes whatever X(o,o) produces,
            # AND any other Val sharing this box sees the update too.
            o.update(X(o, o))
            E(o)
    return o


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(o: Val) -> Val:
    """Force ``o`` to weak head normal form (WHNF). Same as the spec's E.

    Mutates ``o`` in place: a saturated App will be replaced by its
    reduction, with that update visible through any other Val that
    shares ``o``'s box.
    """
    return E(o)


def force(o: Val) -> Val:
    """Force ``o`` to full normal form along the App spine.

    Pin contents and Law bodies remain opaque — force does NOT recurse
    into them. For deep-force-into-pins behaviour, use a separate walker.
    """
    return F(o)
