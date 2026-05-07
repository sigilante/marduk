"""Plan Asm reader.

Port of `vendor/reaver/src/hs/PlanAssembler.hs` lines 32-114 (the
`parse` / `pseq` / `parseMany` block). Output is a PLAN ``Val`` — using
the constructors from ``marduk.runtime.plan`` — not a separate surface AST.
This matches PlanAssembler's semantics: parsing and macroexpansion both
operate on PLAN values.

The Haskell ``A`` constructor takes a vector of args; our Python ``A`` is
binary, so an n-arg array becomes a left-associated chain. Encoding rules:

- ``(...)``       → ``array(xs)`` = head ``N 0`` + args
- ``[...]``       → ``array([N "#brak"] + xs)``
- ``{...}``       → ``array([N "#curl"] + xs)``
- ``"foo"``       → ``natE(strNat "foo")`` = ``A(N 1, N (strNat "foo"))``
- bare nat lit    → ``natE n`` = ``A(N 1, N n)``
- bare symbol     → ``N (strNat sym)``
- ``sym(...)`` /  ``sym"..."`` (no whitespace) → ``array [N "#juxt", v, body]``

``;`` starts a line comment that runs to the next ``\\n``. Tabs and CRs are
intentionally treated as symbol characters, matching upstream.
"""

from .runtime.plan import A, N, str_nat


__all__ = ["ParseError", "parse", "parse_many"]


class ParseError(Exception):
    """Raised when Plan Asm input is malformed.

    Carries 1-indexed ``line`` and ``col`` of the offending position in the
    source text.
    """

    def __init__(self, message: str, line: int, col: int):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(f"line {line} col {col}: {message}")


# ---------------------------------------------------------------------------
# Constructors (mirror PlanAssembler's natE/strE/symE/listE/curlE/brakE).
# ---------------------------------------------------------------------------

def _array(xs):
    """``adt 0 xs``. ``[]`` → ``N(0)``; non-empty → left-associated ``A`` chain."""
    if not xs:
        return N(0)
    val = N(0)
    for x in xs:
        val = A(val, x)
    return val


def _list_e(xs):
    return _array(xs)


def _brak_e(xs):
    return _array([N(str_nat("#brak"))] + xs)


def _curl_e(xs):
    return _array([N(str_nat("#curl"))] + xs)


def _juxt_e(v, body):
    return _array([N(str_nat("#juxt")), v, body])


def _nat_e(n):
    return A(N(1), N(n))


def _str_e(s):
    return _nat_e(str_nat(s))


def _sym_e(s):
    return N(str_nat(s))


# ---------------------------------------------------------------------------
# Character categories.
# ---------------------------------------------------------------------------

_GAP = "GAP"
_SYM = "SYM"
_STR = "STR"
_END = "END"
# NEST is encoded as a tuple ("NEST", make_fn).


def _cat(c: str):
    if c == "(":
        return ("NEST", _list_e)
    if c == "[":
        return ("NEST", _brak_e)
    if c == "{":
        return ("NEST", _curl_e)
    if c == ")" or c == "]" or c == "}":
        return _END
    if c == "\n" or c == " " or c == ";":
        return _GAP
    if c == '"':
        return _STR
    return _SYM


def _is_closer(c: str) -> bool:
    return c == ")" or c == "]" or c == "}"


def _is_gap(c: str) -> bool:
    return c == " " or c == "\n" or c == ";"


def _is_sym_char(c: str) -> bool:
    return _cat(c) == _SYM


# ---------------------------------------------------------------------------
# Cursor — string + position with line/col derivation for errors.
# ---------------------------------------------------------------------------

class _Cursor:
    __slots__ = ("text", "pos")

    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def at_eof(self) -> bool:
        return self.pos >= len(self.text)

    def peek(self):
        return None if self.at_eof() else self.text[self.pos]

    def take(self) -> str:
        c = self.text[self.pos]
        self.pos += 1
        return c

    def line_col(self):
        """1-indexed (line, col) of ``self.pos``."""
        last_nl = self.text.rfind("\n", 0, self.pos)
        col = self.pos - last_nl  # last_nl == -1 → col = pos + 1
        line = self.text.count("\n", 0, self.pos) + 1
        return line, col

    def error(self, msg: str):
        line, col = self.line_col()
        raise ParseError(msg, line, col)


# ---------------------------------------------------------------------------
# Parser.
# ---------------------------------------------------------------------------

def _eat(cur: _Cursor) -> None:
    """Skip gaps and ``;``-line-comments."""
    while not cur.at_eof():
        c = cur.peek()
        if c == ";":
            while not cur.at_eof() and cur.peek() != "\n":
                cur.take()
        elif c == " " or c == "\n":
            cur.take()
        else:
            break


def _parse(cur: _Cursor):
    _eat(cur)
    if cur.at_eof():
        cur.error("eof")
    c = cur.peek()
    cat = _cat(c)
    if cat == _STR:
        cur.take()
        return _parse_string(cur)
    if isinstance(cat, tuple) and cat[0] == "NEST":
        cur.take()
        return _pseq(cur, cat[1])
    if cat == _SYM:
        return _parse_symbol(cur)
    cur.error(f"unexpected: {c!r}")


def _parse_string(cur: _Cursor):
    """Caller has consumed the opening ``"``. Read body, expect closing ``"``."""
    start = cur.pos
    while not cur.at_eof() and cur.peek() != '"':
        cur.take()
    if cur.at_eof():
        cur.error("unterminated string")
    body = cur.text[start:cur.pos]
    cur.take()  # closing "
    return _str_e(body)


def _parse_symbol(cur: _Cursor):
    start = cur.pos
    while not cur.at_eof() and _is_sym_char(cur.peek()):
        cur.take()
    s = cur.text[start:cur.pos]
    if s and all(c.isdigit() for c in s):
        v = _nat_e(int(s))
    else:
        v = _sym_e(s)
    if not cur.at_eof():
        nxt = cur.peek()
        cat = _cat(nxt)
        if isinstance(cat, tuple) and cat[0] == "NEST":
            cur.take()
            return _juxt_e(v, _pseq(cur, cat[1]))
        if cat == _STR:
            cur.take()
            return _juxt_e(v, _parse_string(cur))
    return v


def _pseq(cur: _Cursor, mk):
    """Caller has consumed the opening bracket. Parse forms until the closer."""
    items = []
    while True:
        _eat(cur)
        if cur.at_eof():
            cur.error("eof in list")
        c = cur.peek()
        if _is_closer(c):
            cur.take()
            return mk(items)
        item = _parse(cur)
        items.append(item)
        if not cur.at_eof():
            nxt = cur.peek()
            if not _is_gap(nxt) and not _is_closer(nxt):
                cur.error("bad list")


# ---------------------------------------------------------------------------
# Public surface.
# ---------------------------------------------------------------------------

def parse(text: str):
    """Parse a single Plan Asm form from ``text`` and return its ``Val``.

    Trailing content after the form is ignored (use :func:`parse_many` for a
    sequence).
    """
    cur = _Cursor(text)
    return _parse(cur)


def parse_many(text: str):
    """Parse a sequence of top-level Plan Asm forms. Returns a list of ``Val``."""
    cur = _Cursor(text)
    items = []
    _eat(cur)
    while not cur.at_eof():
        items.append(_parse(cur))
        _eat(cur)
    return items
