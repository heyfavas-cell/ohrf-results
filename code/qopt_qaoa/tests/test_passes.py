import importlib.metadata as md

import pytest

from spikes.qopt_p0.harness import cx_count
from spikes.qopt_qaoa import oracle, passes
from spikes.qopt_qaoa.tests import stuck_pyzx

# a throwaway 4-qubit ring, in neither set
EDGES = [(0, 1), (1, 2), (2, 3), (3, 0)]
BODY = "".join(f"cx q[{a}],q[{b}];\nrz(0.7) q[{b}];\ncx q[{a}],q[{b}];\n" for a, b in EDGES)
RING = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[4];\n' + "h q[0];\n" + BODY + "rx(0.9) q[1];\n" + BODY


@pytest.fixture(scope="module")
def pool():
    walled = passes.WalledPyzx()
    yield passes.pool(walled)
    walled.stop()


def test_the_pool_has_the_planned_entries_and_the_pins_hold():
    names = set(passes.pool())
    assert {"q-linear-functions", "q-peephole-2q", "q-level3", "t-peephole", "t-peephole-swaps", "t-greedy-pauli",
            "z-full-reduce", "z-clifford-simp"} <= names
    assert len(names) == 7 + 9 + 2
    assert md.version("pytket") == "2.18.4" and md.version("pyzx") == "0.10.7"


def test_every_pass_gives_a_basis_circuit_that_qcec_proves_equivalent_or_raises(pool, tmp_path):
    outcomes = {}
    for name, fn in pool.items():
        try:
            out = fn(RING, 1)
        except Exception as exc:  # a pass that cannot read this circuit is skipped by the search
            outcomes[name] = f"raised {type(exc).__name__}"
            continue
        assert {l.split()[0].split("(")[0] for l in out.splitlines()[3:] if l.strip()} <= {"cx", "rz", "sx", "x"}, name
        v = oracle.verdict(RING, out, workdir=tmp_path, recheck=lambda *a, **k: "not_run")
        assert v.verified, (name, v)
        outcomes[name] = cx_count(out)
    assert sum(isinstance(v, int) for v in outcomes.values()) >= 12, outcomes


def test_a_pyzx_call_past_its_wall_is_killed_and_the_next_call_starts_a_fresh_worker():
    w = passes.WalledPyzx(wall_s=1, serve=stuck_pyzx.serve)
    try:
        with pytest.raises(TimeoutError):
            w.call("full_reduce", RING)
        assert w._proc is None
    finally:
        w.stop()
    real = passes.WalledPyzx(wall_s=60)
    try:
        assert "qreg" in real.call("full_reduce", RING)
    finally:
        real.stop()


def test_no_pass_refuses_a_circuit_in_the_pool_basis(pool):
    """A pass that raises on every basis circuit is not in the pool (t-greedy-pauli did, until it was given a gate set
    it accepts first); only a tool failure on a particular circuit may raise."""
    start = passes.to_basis(RING)
    refused = {}
    for name, fn in pool.items():
        try:
            fn(start, 1)
        except Exception as exc:
            refused[name] = f"{type(exc).__name__}: {str(exc)[:80]}"
    assert refused == {}
