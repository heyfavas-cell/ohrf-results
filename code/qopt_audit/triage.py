"""Triage: find outputs that differ from their input, reduce them, and sort known issues from new candidates.

QCEC cannot decide many large outputs (the `unverified` rows). A statevector on a seeded random product state is a
concrete witness: if the two circuits give different states by more than float noise, the output is wrong on that input.
A witnessed difference is only a lead. It counts under the kill rule once the reduced reproducer, which QCEC can
decide, meets every evidence condition (docs/plans/P0b-audit-spike.md).

python -m spikes.qopt_audit.triage <run-dir> <findings-dir> [--limit N]

Every triage record carries `observed_at` (from the run log) and `triaged_at`, so the time from seeing a case to
knowing it is wrong is on file. A case that needs a person is given a filing clock that starts when it was seen.
"""
from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from spikes.qopt_audit import frozen
from spikes.qopt_audit.oracle import Observation, observe
from spikes.qopt_audit.reduce import compact, ddmin_gates, gate_count
from spikes.qopt_audit.tools import run_tool

WITNESS_MIN = 1e-11  # infidelity far above float noise (about 1e-15) and below any real approximation cutoff
# Qiskit's two-qubit peephole pass drops rotations below about pi/2^15 even with approximation_degree=1.0.
KNOWN_FAMILIES = {"qiskit": ("Qiskit/qiskit#16864", 2e-4)}
PARAMS = re.compile(r"^\s*[a-z0-9]+\(([^)]*)\)")
FILE_WITHIN_H = 72  # a lead that needs a person is due upstream this long after it was seen (not a frozen parameter)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Triage:
    kind: str  # the oracle's kind for the reduced reproducer
    reduced: str
    gap: float
    duplicate_of: str | None
    observation: Observation


def witness_gap(original: str, output: str, *, seed: int = 1) -> float:
    """1 - |<a|b>|^2 for both circuits applied to one seeded random product state (global phase ignored)."""
    import numpy as np
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector
    a, b = QuantumCircuit.from_qasm_str(original), QuantumCircuit.from_qasm_str(output)
    if a.num_qubits != b.num_qubits:
        return 1.0
    rng = np.random.default_rng(seed)
    prep = QuantumCircuit(a.num_qubits)
    for qubit in range(a.num_qubits):
        prep.u(*rng.uniform(0.0, 2 * np.pi, 3), qubit)
    sa, sb = Statevector.from_instruction(prep.compose(a)), Statevector.from_instruction(prep.compose(b))
    return float(max(0.0, 1.0 - abs(np.vdot(sa.data, sb.data)) ** 2))


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


def triage_circuit(original: str, tool: str, fn: Callable[[str], str], *, workdir: Path) -> Triage | None:
    """None when the output has no witness. Otherwise the reduced reproducer, its classification and any known issue."""
    try:
        gap = witness_gap(original, fn(original))
    except Exception:
        return None
    if gap <= WITNESS_MIN:
        return None

    def differs(text: str) -> bool:
        try:
            return witness_gap(text, fn(text)) > WITNESS_MIN
        except Exception:
            return False

    reduced = compact(ddmin_gates(original, differs))
    observation = observe(reduced, tool, fn, workdir=workdir, gates=gate_count(reduced))
    duplicate = None
    family = KNOWN_FAMILIES.get(tool)
    if family and tiny_angle_only(reduced, family[1]):
        duplicate = family[0]
    return Triage(observation.kind, reduced, witness_gap(reduced, fn(reduced)), duplicate, observation)


def _signature(tool: str, result: Triage) -> str:
    return tool + ":" + "|".join(sorted(set(re.findall(r"^\s*([a-z0-9]+)", result.reduced.split("qreg", 1)[1].split("\n", 1)[1], re.M))))


def needs_attention(entry: dict) -> bool:
    """True when a triage record needs a person: a witnessed lead that no known issue explains.

    The founder's call. This body flags wrong outputs and oracle disagreements (a lead on the checker itself) with no
    duplicate. It leaves out `within_tolerance`, although the tolerance table under-measures what Qiskit drops (F-029),
    so a new signature there may still be a bug upstream would accept.
    """
    return bool(entry.get("witness")) and entry.get("duplicate_of") is None and \
        entry.get("kind") in ("wrong_output", "oracle_disagreement")


def attention_record(entry: dict) -> dict:
    """The filing clock for one record: due FILE_WITHIN_H after it was seen (after triage, for rows logged unstamped)."""
    seen, triaged = entry.get("observed_at"), entry.get("triaged_at")
    start = datetime.fromisoformat(seen or triaged)
    lag = (datetime.fromisoformat(triaged) - start).total_seconds() / 3600 if seen and triaged else None
    return {"key": entry["key"], "kind": entry.get("kind"), "signature": entry.get("signature"),
            "observed_at": seen, "triaged_at": triaged,
            "due_by": (start + timedelta(hours=FILE_WITHIN_H)).isoformat(timespec="seconds"),
            "lag_h": None if lag is None else round(lag, 2)}


def triage_run(run_dir: Path, findings: Path, *, limit: int = 10 ** 9,
               triage: Callable[..., Triage | None] = triage_circuit,
               now: Callable[[], str] = utc_now) -> list[dict]:
    """Triage every undecided or failed row not triaged yet; return the records written in this pass."""
    rows = [json.loads(l) for p in sorted(run_dir.glob("shard-*/log.jsonl")) for l in p.read_text("utf-8").splitlines()]
    todo = [r for r in rows if r["kind"] in ("unverified", "wrong_output", "oracle_disagreement")]
    written: list[dict] = []
    findings.mkdir(parents=True, exist_ok=True)
    (findings / "work").mkdir(exist_ok=True)
    for row in todo[:limit]:
        folder = findings / row["key"].replace(":", "_")
        if (folder / "triage.json").exists():
            continue
        circuit = next(run_dir.glob(f"shard-*/circuits/{row['case_kind']}-{row['case']}-{row['seed']}.qasm"))
        text = circuit.read_text("utf-8")
        result = triage(text, row["tool"], lambda t, tool=row["tool"]: run_tool(tool, t), workdir=findings / "work")
        folder.mkdir(parents=True, exist_ok=True)
        stamps = {"observed_at": row.get("observed_at"), "triaged_at": now()}
        if result is None:
            entry = {"key": row["key"], "witness": False, **stamps}
            (folder / "triage.json").write_text(json.dumps(entry), "utf-8")
            written.append(entry)
            continue
        (folder / "input.qasm").write_text(text, "utf-8", newline="\n")
        (folder / "reduced.qasm").write_text(result.reduced, "utf-8", newline="\n")
        entry = {
            "key": row["key"], "witness": True, "kind": result.kind, "gap": result.gap,
            "signature": _signature(row["tool"], result), "duplicate_of": result.duplicate_of,
            "reduced_gates": gate_count(result.reduced), "qcec": result.observation.qcec,
            "second_opinion": result.observation.second_opinion, "distance": result.observation.distance, **stamps}
        (folder / "triage.json").write_text(json.dumps(entry, indent=2), "utf-8")
        written.append(entry)
    return written


def main(argv: list[str] | None = None) -> int:
    run_dir, findings = Path(argv[0] if argv else sys.argv[1]), Path(argv[1] if argv else sys.argv[2])
    limit = int(argv[argv.index("--limit") + 1]) if argv and "--limit" in argv else 10 ** 9
    seen: dict[str, str] = {}
    for entry in triage_run(run_dir, findings, limit=limit):
        if entry["witness"]:
            seen.setdefault(entry["signature"], entry["key"])
    print(f"{len(seen)} distinct reduced signatures")
    for sig, key in seen.items():
        print(sig, "<-", key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
