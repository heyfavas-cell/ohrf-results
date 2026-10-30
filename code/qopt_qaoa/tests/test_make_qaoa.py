import json
import re
from pathlib import Path

import pytest

from spikes.qopt_qaoa import frozen, make_qaoa

HERE = Path(__file__).resolve().parents[1]


def test_the_sets_have_the_frozen_sizes():
    dev, held = make_qaoa.cases("dev"), make_qaoa.cases("held_out")
    assert len(dev) == len(frozen.SIZES) * frozen.DEV_PER_SIZE == 36
    assert len(held) == len(frozen.SIZES) * frozen.HELD_OUT_POOL_PER_SIZE == 324
    assert {c.kind for c in held} == set(frozen.GRAPH_KINDS)
    assert {(c.size, c.kind, c.depth) for c in held} == {
        (n, k, p) for n in frozen.SIZES for k in frozen.GRAPH_KINDS for p in frozen.DEPTHS}


def test_a_circuit_is_a_pure_function_of_its_case():
    case = make_qaoa.cases("held_out")[17]
    assert make_qaoa.generate(case) == make_qaoa.generate(case)


def test_no_two_circuits_share_a_graph_and_every_qubit_has_an_edge():
    seen = set()
    for case in make_qaoa.cases("dev") + make_qaoa.cases("held_out"):
        edges = make_qaoa.graph_of(case)
        key = (case.size, tuple(sorted(edges)))
        assert key not in seen, case.name
        seen.add(key)
        assert {q for e in edges for q in e} == set(range(case.size)), case.name


def test_regular_kinds_have_the_right_degree():
    for case in make_qaoa.cases("held_out"):
        if case.kind.startswith("regular"):
            degree = int(case.kind[-1])
            counts = [0] * case.size
            for a, b in make_qaoa.graph_of(case):
                counts[a] += 1
                counts[b] += 1
            assert set(counts) == {degree}, case.name


def test_the_text_is_one_register_qelib1_with_the_expected_cx_count():
    for case in make_qaoa.cases("held_out")[::13]:
        text = make_qaoa.generate(case)
        assert text.count("qreg") == 1 and "measure" not in text
        assert sum(1 for l in text.splitlines() if l.startswith("cx ")) == 2 * len(make_qaoa.graph_of(case)) * case.depth
        gates = {l.split("(")[0].split()[0] for l in text.splitlines()[3:] if l.strip()}
        assert gates <= {"h", "rz", "rx", "cx"}, gates


def test_every_tool_reader_accepts_a_circuit():
    from pytket.qasm import circuit_from_qasm_str
    from qiskit import QuantumCircuit
    import pyzx as zx
    text = make_qaoa.generate(make_qaoa.cases("dev")[5])
    assert QuantumCircuit.from_qasm_str(text).num_qubits
    assert circuit_from_qasm_str(text).n_qubits
    assert zx.Circuit.from_qasm(text).qubits


def test_the_two_sets_share_no_hash_and_the_committed_files_match_the_manifests():
    hashes = {}
    for name in ("dev", "held_out"):
        manifest = json.loads((HERE / f"{name}.json").read_text(encoding="utf-8"))
        assert len(manifest) == len(make_qaoa.cases(name))
        for case in make_qaoa.cases(name):
            entry = manifest[case.name]
            path = HERE / "circuits" / name / f"{case.name}.qasm"
            assert make_qaoa.text_hash(path.read_text(encoding="utf-8")) == entry["sha"]
            assert make_qaoa.text_hash(make_qaoa.generate(case)) == entry["sha"]
            assert (entry["size"], entry["kind"], entry["depth"]) == (case.size, case.kind, case.depth)
        hashes[name] = {e["sha"] for e in manifest.values()}
    assert not hashes["dev"] & hashes["held_out"]


def test_angles_stay_in_the_frozen_range():
    lo, hi = frozen.ANGLE_RANGE
    for case in make_qaoa.cases("dev")[:6]:
        angles = [float(m) for m in re.findall(r"rz\(([-0-9.e]+)\)", make_qaoa.generate(case))]
        assert angles and all(2 * lo - 1e-9 <= a <= 2 * hi + 1e-9 for a in angles)


def test_the_pool_has_324_circuits_and_a_seeded_order_that_does_not_depend_on_sizes():
    pool = make_qaoa.cases("held_out")
    assert len(pool) == 324 == len({c.name for c in pool})
    order = make_qaoa.run_order()
    assert order == make_qaoa.run_order() and sorted(c.name for c in order) == sorted(c.name for c in pool)
    manifest = json.loads((HERE / "held_out.json").read_text(encoding="utf-8"))
    assert sorted(e["order"] for e in manifest.values()) == list(range(324))
    assert [c.name for c in order[:3]] == [n for n, e in sorted(manifest.items(), key=lambda kv: kv[1]["order"])][:3]


def test_any_first_n_of_the_run_order_is_balanced_over_size_and_kind():
    from collections import Counter
    order = make_qaoa.run_order()
    strata = {(c.size, c.kind) for c in order}
    assert len(strata) == 27
    for n in (1, 26, 27, 28, 54, 100, 108, 150, 323, 324):
        counts = Counter((c.size, c.kind) for c in order[:n])
        full = [counts.get(s, 0) for s in strata]
        assert max(full) - min(full) <= 1, n
    assert {c.name for c in order[:27]} and len({(c.size, c.kind) for c in order[:27]}) == 27
    assert order == make_qaoa.run_order()
