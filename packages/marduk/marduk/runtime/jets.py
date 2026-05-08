"""Optional jet overlay for the Marduk runtime.

A **jet** is a native Python implementation registered against a
specific PLAN ``Law`` value. When the spec-faithful interpreter
(``X`` → ``B`` → ``L`` → ``R``) is about to evaluate a saturated law,
it first checks the jet registry; if the law has a registered jet,
the runtime calls the Python function instead of walking the body.
The result must be the same; jets are a performance shortcut, never
a correctness mechanism.

Jets are **opt-in**:

* The global flag :func:`set_jets` toggles the entire mechanism.
  When disabled, jets are never consulted — every law evaluation
  goes through the spec-faithful path. Default: enabled.
* A law without a registered jet always runs the spec path
  regardless of the flag.

The two-path discipline matters because the spec-faithful interpreter
is the correctness oracle. Differential testing (run the same
program with and without jets, expect identical results) is the
canonical way to validate a jet's implementation. Disable jets via
``set_jets(False)`` to force the spec path even when jets are
registered.

The registry keys laws by Python object identity (``id(law.box)``).
Two laws built from the same Plan Asm source are *different* Val
objects with *different* ids, so a jet registered for one won't fire
for the other. This matches how jets work in real systems: register
once at construction time, use repeatedly. ``_KEEPALIVE`` holds a
strong reference to every registered law so the box can't be GC'd
and have its memory reused — that would silently misroute later
laws to the stale jet.
"""

from __future__ import annotations

from typing import Callable

from .core import Val


__all__ = [
    # Registry
    "register_jet", "register_named_jet", "lookup_jet", "clear_jets",
    # Flag
    "set_jets", "jets_enabled",
    # Type alias
    "JetFn",
]


# A jet function takes the saturated args (in argument order, NOT
# including the law itself) and returns a ``Val``. Args arrive in
# whatever WHNF state the spine had when ``X`` saw the saturation —
# the jet is responsible for forcing what it needs to inspect, the
# same way BPLAN op implementations do.
JetFn = Callable[..., Val]


_REGISTRY: dict[int, JetFn] = {}
_KEEPALIVE: list[Val] = []
_JETS_ENABLED: bool = True

# Content-addressed jet registry keyed by (name_nat, arity, body_hash).
# Jets registered here are looked up by Law content rather than Val
# identity. This is stable across bevaluate() calls: the same Law always
# has the same name nat, arity, and body structure regardless of which
# Python Val object was produced by the converter.
#
# The body hash distinguishes Laws that share name and arity — for
# example, Core.Text.Prim.text_len and text_nat both declare name
# "text_field" with arity 1. The body hash is computed at registration
# and at lookup using repr(law.body), which produces the same output for
# the same PLAN body structure regardless of which Val objects it used.
#
# _NAMED_KEYS is a fast filter: (name_nat, arity) → True for any
# registered jet. Most Law saturations will miss here in O(1) without
# computing a body hash.
_BODY_REGISTRY: dict[tuple[int, int, int], JetFn] = {}
_NAMED_KEYS: set[tuple[int, int]] = set()


def set_jets(enabled: bool) -> None:
    """Enable or disable the jet overlay globally.

    With ``enabled=False``, every law evaluation runs the
    spec-faithful path regardless of registration state. Useful for
    correctness testing and for benchmarking the spec path without
    rebuilding without jets.
    """
    global _JETS_ENABLED
    _JETS_ENABLED = bool(enabled)


def jets_enabled() -> bool:
    """Return whether the jet overlay is currently enabled."""
    return _JETS_ENABLED


def register_jet(law: Val, fn: JetFn) -> None:
    """Register ``fn`` as the native implementation of ``law`` by Val identity.

    ``law`` must be a Marduk ``Val`` of type ``"law"``. ``fn`` will
    be called with the law's saturated arguments (positional, in
    declaration order) and must return a ``Val``. The jet's result
    must equal the spec-path result for the same inputs — the
    runtime trusts but does not verify this.

    Calling ``register_jet`` for a law that already has a jet replaces
    the previous registration.
    """
    if not isinstance(law, Val) or law.type != "law":
        raise ValueError(f"register_jet: expected a Law value, got {law!r}")
    _REGISTRY[id(law.box)] = fn
    _KEEPALIVE.append(law)


def register_named_jet(name_nat: int, arity: int, fn: JetFn,
                        body_hash: int) -> None:
    """Register ``fn`` as the native implementation for the Law whose
    name encodes to ``name_nat``, arity is ``arity``, and body hashes to
    ``body_hash``.

    Unlike ``register_jet``, this does not key on Val identity. The key
    is (name_nat, arity, body_hash) — all three derived from Law content
    that is stable across bevaluate() calls. The body hash uses
    ``hash(repr(law.body))`` which produces the same value for the same
    PLAN structure across calls within a single Python process (hash
    randomisation applies per-process, not per-call).

    Follows Sol's principle that jet matching is a codegen-time concern
    driven by content, not a runtime identity lookup.
    """
    _BODY_REGISTRY[(name_nat, arity, body_hash)] = fn
    _NAMED_KEYS.add((name_nat, arity))


def lookup_jet(law: Val) -> JetFn | None:
    """Return the registered jet for ``law``, or ``None``.

    Three-tier lookup:
    1. Identity registry (``id(law.box)``) — fast, used for Val-identity
       registrations from ``register_jet``.
    2. Named-key fast filter — O(1) set membership test to avoid
       computing a body hash for laws that definitely have no jet.
    3. Body-content registry (``(name_nat, arity, body_hash)``) — exact
       match when a law's name+arity is in the filtered set.

    Honours the global flag — if ``jets_enabled()`` is ``False``,
    always returns ``None`` so the runtime falls through to the spec path.
    """
    if not _JETS_ENABLED:
        return None
    if not isinstance(law, Val):
        return None
    fn = _REGISTRY.get(id(law.box))
    if fn is not None:
        return fn
    if law.type != "law" or law.name.type != "nat" or law.args.type != "nat":
        return None
    key2 = (law.name.nat, law.args.nat)
    if key2 not in _NAMED_KEYS:
        return None
    return _BODY_REGISTRY.get((law.name.nat, law.args.nat, hash(repr(law.body))))


def clear_jets() -> None:
    """Drop every registered jet. The keepalive list is also cleared,
    so registered laws become eligible for GC again. Mostly useful in
    tests to keep registrations from leaking across cases."""
    _REGISTRY.clear()
    _KEEPALIVE.clear()
    _BODY_REGISTRY.clear()
    _NAMED_KEYS.clear()
