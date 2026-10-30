"""The QAOA MaxCut circuits of the explore track: python -m spikes.qopt_qaoa.make_qaoa <folder-of-the-track>.

A circuit is a pure function of its case (set, size, kind, depth) and `frozen.CIRCUIT_SEED`. Graphs are drawn in one
fixed order (held-out set first, then development) and a draw whose edge set an earlier circuit of the same size already
uses is redrawn from the next sub-seed, so no two circuits share a graph, within or across the sets.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from spikes.qopt_p0.harness import strip_measurements
from spikes.qopt_p0.make_circuits import QELIB1
from spikes.qopt_qaoa import folders, frozen

SETS = ("held_out", "dev")  # the drawing order


@dataclass(frozen=True)
class Case:
    set_name: str
    size: int
    kind: str
    depth: int
    replicate: int = 0

    @property
    def name(self) -> str:
        return f"{self.set_name}-{self.size}-{self.kind}-p{self.depth}-r{self.replicate}"

    @property
    def seed(self) -> int:
        key = f"{self.set_name}:{self.size}:{self.kind}:{self.depth}:{self.replicate}:{frozen.CIRCUIT_SEED}"
        return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


def cases(set_name: str) -> list[Case]:
    if set_name == "held_out":
        copies = frozen.HELD_OUT_POOL_PER_SIZE // (len(frozen.GRAPH_KINDS) * len(frozen.DEPTHS))
        return [Case(set_name, n, k, p, r) for n in frozen.SIZES for k in frozen.GRAPH_KINDS for p in frozen.DEPTHS
                for r in range(copies)]
    if set_name == "dev":  # four per size: every depth, the kind rotating with size and depth
        return [Case(set_name, n, frozen.GRAPH_KINDS[(i + p) % len(frozen.GRAPH_KINDS)], p)
                for i, n in enumerate(frozen.SIZES) for p in frozen.DEPTHS]
    raise ValueError(f"unknown set {set_name!r}")


def _draw(case: Case, sub_seed: int):
    import networkx as nx
    seed = case.seed + sub_seed
    if case.kind.startswith("regular"):
        return nx.random_regular_graph(int(case.kind[-1]), case.size, seed=seed)
    return nx.gnp_random_graph(case.size, frozen.ER_MEAN_DEGREE / (case.size - 1), seed=seed)


@lru_cache(maxsize=1)
def _graphs() -> dict[Case, tuple[tuple[int, int], ...]]:
    used: set[tuple[int, tuple]] = set()
    out = {}
    for set_name in SETS:
        for case in cases(set_name):
            for sub in range(100000):
                g = _draw(case, sub)
                edges = tuple(sorted(tuple(sorted(e)) for e in g.edges()))
                covered = {q for e in edges for q in e} == set(range(case.size))
                if covered and (case.size, edges) not in used:
                    used.add((case.size, edges))
                    out[case] = edges
                    break
            else:
                raise RuntimeError(f"no free graph for {case.name}")
    return out


def graph_of(case: Case) -> tuple[tuple[int, int], ...]:
    return _graphs()[case]


def generate(case: Case) -> str:
    from qiskit import QuantumCircuit, qasm2, transpile
    rng = random.Random(case.seed)
    lo, hi = frozen.ANGLE_RANGE
    layers = [(rng.uniform(lo, hi), rng.uniform(lo, hi)) for _ in range(case.depth)]
    qc = QuantumCircuit(case.size)
    qc.h(range(case.size))
    for gamma, beta in layers:
        for a, b in graph_of(case):
            qc.cx(a, b)
            qc.rz(2 * gamma, b)
            qc.cx(a, b)
        for q in range(case.size):
            qc.rx(2 * beta, q)
    return qasm2.dumps(transpile(qc, basis_gates=QELIB1, optimization_level=0))


def order_key(case: Case) -> str:
    """Ranks the circuits inside a stratum: a hash of the order seed and the circuit's name."""
    return hashlib.sha256(f"{frozen.HELD_OUT_ORDER_SEED}:{case.name}".encode()).hexdigest()


def stratum_key(case: Case) -> str:
    """Ranks the strata (size by kind) inside one round of the round-robin."""
    return hashlib.sha256(f"{frozen.HELD_OUT_ORDER_SEED}:{case.size}:{case.kind}".encode()).hexdigest()


def run_order(set_name: str = "held_out") -> list[Case]:
    """Round-robin over the strata (size by kind), seeded within each: any first N holds counts per stratum that
    differ by at most 1."""
    strata: dict[tuple[int, str], list[Case]] = {}
    for case in sorted(cases(set_name), key=order_key):
        strata.setdefault((case.size, case.kind), []).append(case)
    columns = sorted(strata.values(), key=lambda column: stratum_key(column[0]))
    return [column[k] for k in range(max(map(len, columns))) for column in columns if k < len(column)]


def text_hash(text: str) -> str:
    """The hash the P0 harness uses: sha256 of the text without measurements, barriers and creg lines."""
    return hashlib.sha256(strip_measurements(text).encode()).hexdigest()


def write_sets(root: Path) -> dict[str, int]:
    counts = {}
    for set_name in ("dev", "held_out"):
        folder = root / "circuits" / set_name
        folders.ensure_dir(folder)
        manifest = {}
        for case in cases(set_name):
            text = generate(case)
            (folder / f"{case.name}.qasm").write_text(text, encoding="utf-8", newline="\n")
            rank = {c: i for i, c in enumerate(run_order(set_name))}[case] if set_name == "held_out" else None
            manifest[case.name] = {"order": rank, "size": case.size, "kind": case.kind, "depth": case.depth, "seed": case.seed,
                                   "edges": len(graph_of(case)), "sha": text_hash(text)}
        (root / f"{set_name}.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                               encoding="utf-8", newline="\n")
        counts[set_name] = len(manifest)
    return counts


if __name__ == "__main__":
    print(write_sets(Path(sys.argv[1])))
