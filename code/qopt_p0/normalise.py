"""One QASM text for QCEC to read (D-113): anything QCEC could read differently from the strict reader is rejected.

QCEC honours the layout comments `// i` (initial layout) and `// o` (output permutation), so an output that drops a
SWAP behind `// o 1 0` is called equivalent. The spike charges no permutation, so any `// o` is rejected, and `// i`
is allowed only as the identity layout, which is dropped with every other comment.
"""
from __future__ import annotations

import re

COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
LAYOUT_MARK = re.compile(r"//[ \t]*([io])(?![^ \t\n])", re.I)  # a comment a layout reader could take for its own
INITIAL_LINE = re.compile(r"//[ \t]*i[ \t]+(\d+(?:[ \t]+\d+)*)[ \t]*")
QREG = re.compile(r"qreg\s+[A-Za-z_]\w*\[(\d+)\]\s*;")


class NormaliseError(ValueError):
    """The text could be read two ways; the output is not verified."""


def normalise(text: str) -> str:
    if "\r" in text:
        raise NormaliseError("a carriage return is not allowed: end every line with a line feed")
    initial: list[tuple[int, ...]] = []

    def visit(match: re.Match[str]) -> str:
        body, line = match.group(0), text.count("\n", 0, match.start()) + 1
        if body.startswith("/*"):
            if LAYOUT_MARK.search(body):
                raise NormaliseError(f"line {line}: a `// i` or `// o` comment inside a block comment")
            return "\n" * body.count("\n")
        mark = LAYOUT_MARK.match(body)
        if mark is None:
            return ""
        kind = mark.group(1).lower()
        if kind == "o":
            raise NormaliseError(f"line {line}: an output permutation `// o` is not allowed in the spike")
        ints = INITIAL_LINE.fullmatch(body)
        if ints is None:
            raise NormaliseError(f"line {line}: a malformed `// i` line: only integers may follow it")
        if text[text.rfind("\n", 0, match.start()) + 1:match.start()].strip():
            raise NormaliseError(f"line {line}: a `// i` comment must stand on its own line")
        if initial:
            raise NormaliseError(f"line {line}: more than one `// i` line")
        initial.append(tuple(int(part) for part in ints.group(1).split()))
        return ""

    clean = COMMENTS.sub(visit, text)
    if "/*" in clean:
        raise NormaliseError("a block comment is never closed")
    if initial:
        size = sum(int(m.group(1)) for m in QREG.finditer(clean))
        if initial[0] != tuple(range(size)):
            raise NormaliseError(f"the initial layout `// i` must be the identity for {size} qubits")
    return clean
