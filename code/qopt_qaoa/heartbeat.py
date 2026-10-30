"""The stall alarm (P0c, run change 5): a heartbeat file and an hourly check that puts one line in the sessions board.

The D-145 run stopped for 8 days and nobody noticed until a person looked. A scheduled task does not edit tracked
files, so the alarm line goes to the board only; the chat that sees it copies it into `docs/STATUS.md`.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from spikes.qopt_qaoa import frozen

MARK = "- STALL-ALARM (P0e)"
LINE = re.compile(r"^- STALL-ALARM \(P0e\).*\n?", re.M)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def write(path: Path, *, batch_end: datetime | None = None, triage_end: datetime | None = None) -> dict:
    path = Path(path)
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if batch_end is not None:
        state["batch_end_utc"] = batch_end.isoformat()
    if triage_end is not None:
        state["triage_end_utc"] = triage_end.isoformat()
    path.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return state


def stale(path: Path, now: datetime, *, hours: int = frozen.STALL_HOURS) -> list[str]:
    """Names of the clocks older than `hours`; a missing clock counts as stale."""
    state = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}
    out = []
    for key in ("batch_end_utc", "triage_end_utc"):
        if key not in state or now - datetime.fromisoformat(state[key]) > timedelta(hours=hours):
            out.append(key)
    return out


def check(path: Path, board: Path, *, now: datetime | None = None, run_open: bool = True) -> str | None:
    """Put or clear the alarm line in the board. Returns the line when the run is open and a clock is stale."""
    now = now or utc_now()
    board = Path(board)
    text = board.read_text(encoding="utf-8") if board.exists() else ""
    text = LINE.sub("", text)
    old = stale(path, now) if run_open else []
    line = None
    if old:
        state = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}
        line = (f"{MARK}: {', '.join(old)} older than {frozen.STALL_HOURS} h at {now.isoformat()}; "
                f"last batch end {state.get('batch_end_utc', 'never')}, last triage end {state.get('triage_end_utc', 'never')}")
        text = text.rstrip("\n") + "\n" + line + "\n"
    board.write_text(text, encoding="utf-8")
    return line
