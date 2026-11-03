import re
from pathlib import Path

from qiskit import QuantumCircuit

from spikes.qopt_audit import frozen
from spikes.qopt_audit.bases import load_bases
from spikes.qopt_audit.generate import boundary_variant, build, random_circuit, schedule

BASES = Path(__file__).resolve().parents[1] / "bases"


def test_a_random_circuit_is_a_pure_function_of_its_seed():
    assert random_circuit(7) == random_circuit(7)
    assert random_circuit(7) != random_circuit(8)


def test_random_circuits_parse_and_stay_in_the_registered_bounds():
    for seed in range(1, 40):
        text = random_circuit(seed)
        qc = QuantumCircuit.from_qasm_str(text)
        assert frozen.RANDOM_QUBITS[0] <= qc.num_qubits <= frozen.RANDOM_QUBITS[1]
        assert frozen.RANDOM_GATES[0] <= qc.size() <= frozen.RANDOM_GATES[1] + 5
        assert text.count("\nqreg ") == 1 and "measure" not in text and "creg" not in text


def test_random_circuits_use_only_standard_gates():
    allowed = {"u1", "u2", "u3", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "cx", "cz", "cy",
               "ch", "swap", "ccx", "crz", "cu1", "cu3"}
    for seed in range(1, 20):
        ops = {m.group(1) for m in re.finditer(r"^([a-z0-9]+)[ (]", random_circuit(seed), re.M)}
        assert ops - allowed <= {"OPENQASM", "include", "qreg"}


def test_the_forty_base_circuits_are_the_registered_grid():
    bases = load_bases(BASES)
    assert set(bases) == {f"{f}-{n}" for f in frozen.BASE_FAMILIES for n in frozen.BASE_SIZES}


def test_a_boundary_variant_keeps_the_gate_skeleton_and_moves_some_angles_to_boundary_values():
    base = load_bases(BASES)["qft-6"]
    changed = 0
    for seed in range(1, 30):
        variant = boundary_variant(base, seed)
        assert [re.sub(r"\([^)]*\)", "()", l) for l in variant.splitlines()] == \
               [re.sub(r"\([^)]*\)", "()", l) for l in base.splitlines()]
        changed += variant != base
    assert changed > 20
    assert "e-05" in "".join(boundary_variant(base, s) for s in range(1, 200))  # the PyZX lead's format appears


def test_the_schedule_alternates_is_deterministic_and_never_repeats():
    first = [c for _, c in zip(range(400), schedule())]
    assert first == [c for _, c in zip(range(400), schedule())]
    assert [c.kind for c in first[:4]] == ["random", "boundary", "random", "boundary"]
    assert len({(c.kind, c.name, c.seed) for c in first}) == 400
    assert [c for _, c in zip(range(10), schedule(start=390))] != first[:10]


def test_building_a_case_needs_nothing_but_the_case_and_the_bases():
    bases = load_bases(BASES)
    for case in [c for _, c in zip(range(8), schedule())]:
        assert build(case, bases) == build(case, bases)
