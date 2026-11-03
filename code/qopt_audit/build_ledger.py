"""Build the findings ledger (findings/ledger.jsonl) from triage's records: one row per witnessed case.

Two steps, so the ledger can be rebuilt exactly from what was measured:

    python -m spikes.qopt_audit.build_ledger collect <findings> <notes.json> --latest-python <python>
    python -m spikes.qopt_audit.build_ledger build <findings> <notes.json> <ledger.jsonl>

`collect` runs in the pinned environment and measures what each row needs, writing it to the notes: two QCEC
decisions on the reduced reproducer, each in a fresh worker (`oracle._decide`); the alternating checker as second
opinion; the first pass after which the operator differs (blind to the layout, as the verdict's ledger was built);
the dense distance; the witness at the pins and, through `--latest-python`, on the latest Qiskit. It fills only what
the notes lack, so it resumes, and notes measured earlier are kept. `build` reads nothing else and runs no tool.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from spikes.qopt_audit import frozen
from spikes.qopt_audit.ledger import Finding, dump

ISSUES = {"TwoQubitPeepholeOptimization": ("Qiskit/qiskit#16864", "https://github.com/Qiskit/qiskit/issues?q="
                                           "TwoQubitPeepholeOptimization+approximation_degree"),
          "CommutativeCancellation": ("Qiskit/qiskit#17315",
                                      "https://github.com/Qiskit/qiskit/issues?q=CommutativeCancellation+small")}
CHANGED = 1e-9  # the oracle's floor for a distance that is not float noise


def _folder(findings: Path, key: str) -> Path:
    return Path(findings) / "spike" / key.replace(":", "_")


def witnessed(findings: Path) -> list[dict]:
    """Every triage record with a witness, in key order."""
    records = (json.loads(p.read_text(encoding="utf-8")) for p in Path(findings).glob("spike/*/triage.json"))
    return sorted((r for r in records if r["witness"]), key=lambda r: r["key"])


def _qubits(qasm: str) -> int:
    return sum(int(m) for m in re.findall(r"qreg\s+\w+\[(\d+)\]", qasm))


def row(record: dict, reduced: str, note: dict) -> Finding:
    tool = record["key"].rsplit(":", 1)[1]
    distance = record["distance"] if record.get("distance") is not None else note["distance"]
    gates = record["reduced_gates"]
    duplicate, search = ISSUES.get(note["pass"], (None, None))
    return Finding(
        id=record["key"], cls="wrong_output", tool=tool, reproducer_gates=gates, reproducer_qubits=_qubits(reduced),
        distance=distance, tolerance_ok=distance is None or distance > gates * frozen.TOLERANCE[tool],
        proved_twice=note["answers"] == ["not_equivalent"] * frozen.CONFIRM_RUNS,
        second_opinion_ok=note["alternating"] == "not_equivalent" and (distance is None or distance > CHANGED),
        reproduces_latest=note["pinned_gap"] > _witness_min() and note["latest_gap"] > _witness_min(),
        lead=False, duplicate_of=duplicate, search_url=search, filed=None, accepted=None, url=None)


def _witness_min() -> float:
    from spikes.qopt_audit.triage import WITNESS_MIN
    return WITNESS_MIN


def build(findings: Path, notes: Path, ledger: Path) -> int:
    cases = json.loads(Path(notes).read_text(encoding="utf-8"))["cases"]
    rows = [row(r, (_folder(findings, r["key"]) / "reduced.qasm").read_text(encoding="utf-8"), cases[r["key"]])
            for r in witnessed(findings)]
    dump(rows, Path(ledger))
    return len(rows)


def _default_tool(tool: str, text: str) -> str:
    from spikes.qopt_audit.tools import run_tool
    return run_tool(tool, text)


def latest_gaps(findings: Path, keys: list[str]) -> dict:
    """The witness on each reduced reproducer with whatever Qiskit this interpreter has."""
    import qiskit
    from spikes.qopt_audit.triage import witness_gap
    gaps = {}
    for key in keys:
        text = (_folder(findings, key) / "reduced.qasm").read_text(encoding="utf-8")
        gaps[key] = witness_gap(text, _default_tool(key.rsplit(":", 1)[1], text))
    return {"qiskit": qiskit.__version__, "gaps": gaps}


def collect(findings: Path, notes: Path, *, latest_python: str, tool=_default_tool) -> dict:
    from spikes.qopt_audit.oracle import _alternating, _decide, _distance
    from spikes.qopt_audit.passes import first_breaking_pass
    from spikes.qopt_audit.triage import witness_gap
    from spikes.qopt_p0 import verify
    notes = Path(notes)
    data = json.loads(notes.read_text(encoding="utf-8")) if notes.exists() else {"qiskit_latest": None, "cases": {}}
    work = notes.parent / "work"  # beside the notes: the findings folder is only read
    work.mkdir(parents=True, exist_ok=True)
    filled = 0
    try:
        for record in witnessed(findings):
            note = data["cases"].setdefault(record["key"], {})
            reduced = (_folder(findings, record["key"]) / "reduced.qasm").read_text(encoding="utf-8")
            out = tool(record["key"].rsplit(":", 1)[1], reduced)
            before = len(note)
            if "answers" not in note:
                note["answers"] = []
                for _ in range(frozen.CONFIRM_RUNS):
                    verify._WORKER.stop()  # a fresh worker process for every decision
                    note["answers"].append(_decide(reduced, out, workdir=work)[0])
            if "alternating" not in note:
                note["alternating"] = _alternating(reduced, out, workdir=work)
            note.setdefault("pass", first_breaking_pass(reduced, layout_aware=False))
            note.setdefault("triage_kind", record["kind"])
            if "distance" not in note:
                note["distance"] = _distance(reduced, out)
            if "pinned_gap" not in note:
                note["pinned_gap"] = witness_gap(reduced, out)
            filled += len(note) > before
    finally:
        verify._WORKER.stop()
    missing = [k for k, n in data["cases"].items() if "latest_gap" not in n]
    if missing:
        result = subprocess.run([latest_python, "-W", "ignore", "-m", "spikes.qopt_audit.build_ledger", "latest",
                                 str(findings), *missing], capture_output=True, text=True, check=True)
        latest = json.loads(result.stdout)
        data["qiskit_latest"] = latest["qiskit"]
        for key, gap in latest["gaps"].items():
            data["cases"][key]["latest_gap"] = gap
    notes.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
    return {"cases": len(data["cases"]), "filled": filled, "latest": len(missing)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("collect", "build", "latest"))
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--latest-python", default="")
    args = parser.parse_args(argv)
    if args.step == "collect":
        print(collect(Path(args.paths[0]), Path(args.paths[1]), latest_python=args.latest_python))
    elif args.step == "build":
        print(build(Path(args.paths[0]), Path(args.paths[1]), Path(args.paths[2])), "rows")
    else:
        print(json.dumps(latest_gaps(Path(args.paths[0]), args.paths[1:])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
