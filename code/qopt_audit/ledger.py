"""The findings ledger and the pre-registered kill rule (docs/plans/P0b-audit-spike.md)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from datetime import date, timedelta
from pathlib import Path

from spikes.qopt_audit import frozen


@dataclass(frozen=True)
class Finding:
    id: str
    cls: str  # wrong_output, crash, reader, verifier, docs
    tool: str
    reproducer_gates: int
    reproducer_qubits: int
    distance: float | None
    tolerance_ok: bool
    proved_twice: bool
    second_opinion_ok: bool
    reproduces_latest: bool
    lead: bool
    duplicate_of: str | None
    search_url: str | None
    filed: date | None
    accepted: date | None
    url: str | None


def counts_as_wrong_output(f: Finding) -> bool:
    return (f.cls == "wrong_output" and f.proved_twice and f.second_opinion_ok and f.tolerance_ok
            and f.reproduces_latest and not f.lead and f.duplicate_of is None)


def _counts_toward_ii(f: Finding, day0: date) -> bool:
    return (counts_as_wrong_output(f) and f.search_url is not None and f.filed is not None
            and f.filed <= day0 + timedelta(days=frozen.FILE_BY_DAY) and f.accepted is not None
            and f.accepted <= day0 + timedelta(days=frozen.DECIDE_DAY))


def verdict(findings: list[Finding], *, day0: date, today: date) -> str:
    """pass, open (not met yet, before day 14) or fallback."""
    small = [f for f in findings if counts_as_wrong_output(f) and f.reproducer_gates <= frozen.REDUCED_MAX_GATES]
    if small or sum(_counts_toward_ii(f, day0) for f in findings) >= 2:
        return "pass"
    return "open" if today < day0 + timedelta(days=frozen.DECIDE_DAY) else "fallback"


def load(path: Path) -> list[Finding]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = json.loads(line)
            for key in ("filed", "accepted"):
                raw[key] = date.fromisoformat(raw[key]) if raw.get(key) else None
            out.append(Finding(**{f.name: raw.get(f.name) for f in fields(Finding)}))
    return out


def dump(findings: list[Finding], path: Path) -> None:
    rows = [{k: (v.isoformat() if isinstance(v, date) else v) for k, v in asdict(f).items()} for f in findings]
    Path(path).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")
