"""Triage of a batch the moment it is logged (D-156): known duplicates, leads that need a person, the 72 hour clock.

A lead never counts toward the rule. Nothing is posted upstream from here (D-157): a lead goes to the founder with
a filing draft due 72 hours after it was seen.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from spikes.qopt_qaoa import frozen

# issue -> (pool step that breaks first, largest rotation it drops); the audit's match rule (pass name plus shape)
KNOWN = {"Qiskit/qiskit#16864": ("q-peephole-2q", 2e-4), "Qiskit/qiskit#17315": ("q-commutative-cancel", 2e-4)}
PARAMS = re.compile(r"^\s*[a-z0-9_]+\(([^)]*)\)")


def _value(expr: str) -> float:
    cleaned = expr.strip().replace("pi", repr(math.pi))
    if not re.fullmatch(r"[0-9eE+\-*/(). ]+", cleaned):
        raise ValueError(f"not a plain angle: {expr!r}")
    return float(eval(cleaned, {"__builtins__": {}}))  # noqa: S307  (characters checked above)


def tiny_angle_only(qasm: str, cutoff: float) -> bool:
    """True when every gate parameter is within `cutoff` of a multiple of 2*pi, and there is at least one."""
    seen = False
    for line in qasm.splitlines():
        match = PARAMS.match(line)
        if match is None:
            continue
        for arg in match.group(1).split(","):
            turns = _value(arg) / (2 * math.pi)
            if abs(turns - round(turns)) * 2 * math.pi > cutoff:
                return False
            seen = True
    return seen


def match_known(breaking_step: str | None, reduced_qasm: str) -> str | None:
    for issue, (step, cutoff) in KNOWN.items():
        if breaking_step == step and tiny_angle_only(reduced_qasm, cutoff):
            return issue
    return None


def first_breaking_step(original: str, path: tuple[str, ...], passes: dict, verifies: Callable[[str], bool],
                        seed: int = 1) -> str | None:
    """Replay a proposal's path one step at a time; the first step after which the state no longer verifies."""
    text = original
    for name in path:
        text = passes[name](text, seed)
        if not verifies(text):
            return name
    return None


def lead_record(key: str, kind: str, *, seen: datetime, witnessed: bool, duplicate_of: str | None, **extra) -> dict:
    return {"key": key, "kind": kind, "seen_utc": seen.isoformat(),
            "due_by": (seen + timedelta(hours=frozen.DUE_BY_HOURS)).isoformat(), "witness": witnessed,
            "duplicate_of": duplicate_of, **extra}


def needs_attention(rec: dict) -> bool:
    """A witnessed lead that no known issue explains: a wrong output, an oracle disagreement, an output QCEC 3.11.0
    contradicts, or a tool that crashed on a valid input."""
    return rec.get("duplicate_of") is None and (
        (rec["kind"] in ("wrong_output", "oracle_disagreement") and rec.get("witness"))
        or rec["kind"] in ("recheck_contradiction", "tool_crash"))


def triage_batch(records: list[dict], attention: Path) -> list[dict]:
    """Append the records that need a person to `attention.jsonl`, once each, and return the new ones."""
    attention = Path(attention)
    have = {json.loads(l)["key"] for l in attention.read_text(encoding="utf-8").splitlines() if l.strip()} \
        if attention.exists() else set()
    new = [r for r in records if needs_attention(r) and r["key"] not in have]
    if new:
        with attention.open("a", encoding="utf-8") as handle:
            handle.writelines(json.dumps(r) + "\n" for r in new)
    return new


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
