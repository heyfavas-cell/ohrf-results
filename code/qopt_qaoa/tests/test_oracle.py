from spikes.qopt_qaoa import frozen, oracle

BASE = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\n'
ORIG = BASE + "h q[0];\ncu1(0.0001) q[0],q[1];\nh q[0];\n"
DROPPED = BASE + "h q[0];\nh q[0];\n"


class Scripted:
    """An Outcome stub: answers by the checker config used; a list is consumed in order."""

    def __init__(self, default, alternating="equivalent", zx="probably_not_equivalent"):
        self.table = {"default": default, "alternating": alternating, "zx": zx}
        self.calls = []

    def __call__(self, original, candidate, *, workdir, timeout_s, hard_wall_s=0, config=None):
        key = "default" if config is None else ("zx" if config.get("run_zx_checker") else "alternating")
        self.calls.append(key)
        value = self.table[key]
        return value.pop(0) if isinstance(value, list) else value


def test_a_decided_default_answer_is_kept(tmp_path):
    run = Scripted("equivalent")
    assert oracle.decide(ORIG, ORIG, workdir=tmp_path, run=run) == ("equivalent", "default")
    assert run.calls == ["default"]


def test_an_undecided_default_answer_is_re_decided_once_by_the_alternating_checker(tmp_path):
    run = Scripted("no_information", alternating="equivalent_up_to_global_phase")
    assert oracle.decide(ORIG, ORIG, workdir=tmp_path, run=run) == ("equivalent_up_to_global_phase", "alternating")
    assert run.calls == ["default", "alternating"]


def test_a_wall_or_a_parse_failure_is_not_re_waited(tmp_path):
    for answer in ("hard_timeout", "strict_parse", "not_equivalent"):
        run = Scripted(answer)
        assert oracle.decide(ORIG, ORIG, workdir=tmp_path, run=run)[0] == answer and run.calls == ["default"]


def test_a_3_11_contradiction_makes_a_verified_output_unverified(tmp_path):
    run = Scripted("equivalent")
    ok = oracle.verdict(ORIG, ORIG, workdir=tmp_path, run=run, recheck=lambda *a, **k: "equivalent")
    bad = oracle.verdict(ORIG, ORIG, workdir=tmp_path, run=run, recheck=lambda *a, **k: "not_equivalent")
    unsure = oracle.verdict(ORIG, ORIG, workdir=tmp_path, run=run, recheck=lambda *a, **k: "no_information")
    assert ok.verified and not bad.verified and bad.contradicted and unsure.verified


def test_an_undecided_answer_is_never_verified_and_skips_the_recheck(tmp_path):
    called = []
    v = oracle.verdict(ORIG, ORIG, workdir=tmp_path, run=Scripted("probably_equivalent", alternating="no_information"),
                       recheck=lambda *a, **k: called.append(1) or "equivalent")
    assert not v.verified and not called


def test_the_witness_keeps_every_state_and_sees_a_dropped_cu1_on_some_state():
    gaps = oracle.witness(ORIG, DROPPED)
    assert set(gaps) == {"random-11", "random-12", "random-13", "basis-zeros", "basis-bits"}
    assert oracle.witnessed(gaps)
    assert not oracle.witnessed(oracle.witness(ORIG, ORIG))
    assert oracle.witness(ORIG, BASE.replace("[2]", "[3]")) == {"width": 1.0}


def test_a_disagreeing_confirmation_is_an_oracle_disagreement(tmp_path):
    run = Scripted(["not_equivalent", "equivalent"])
    lead = oracle.classify(ORIG, DROPPED, workdir=tmp_path, run=run, fresh=lambda: None)
    assert lead.kind == "oracle_disagreement" and lead.confirmations == 1


def test_zx_agreement_makes_a_wrong_output_and_zx_silence_a_disagreement(tmp_path):
    for zx, kind in (("probably_not_equivalent", "wrong_output"), ("not_equivalent", "wrong_output"),
                     ("no_information", "oracle_disagreement")):
        lead = oracle.classify(ORIG, DROPPED, workdir=tmp_path, run=Scripted("not_equivalent", zx=zx),
                               fresh=lambda: None)
        assert lead.kind == kind and lead.confirmations == frozen.CONFIRM_RUNS


def test_an_equivalent_pair_is_no_lead(tmp_path):
    assert oracle.classify(ORIG, ORIG, workdir=tmp_path, run=Scripted("equivalent"), fresh=lambda: None) is None


def test_the_zx_second_opinion_sees_a_dropped_cu1_on_the_real_checker(tmp_path):
    """P0c: the random-state simulation cannot see this; the ZX checker alone answered probably_not_equivalent."""
    for _ in range(3):
        assert oracle.second_opinion(ORIG, DROPPED, workdir=tmp_path) in oracle.ZX_AGREES
    assert oracle.second_opinion(ORIG, ORIG, workdir=tmp_path) not in oracle.ZX_AGREES


def test_the_recheck_runs_qcec_3_11_in_its_own_interpreter(tmp_path, monkeypatch):
    import os
    import pytest
    path = os.environ.get("QCEC_LATEST_PYTHON")
    if not path:
        pytest.skip("QCEC_LATEST_PYTHON names no QCEC 3.11.0 interpreter")
    assert oracle.recheck_latest(ORIG, ORIG, workdir=tmp_path) in ("equivalent", "equivalent_up_to_global_phase")
    assert oracle.recheck_latest(ORIG, DROPPED, workdir=tmp_path) != "recheck_error"
    monkeypatch.delenv("QCEC_LATEST_PYTHON")
    assert oracle.recheck_latest(ORIG, ORIG, workdir=tmp_path) == "not_run"
