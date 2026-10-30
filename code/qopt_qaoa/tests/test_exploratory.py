import itertools

from spikes.qopt_qaoa import develop, exploratory, passes, worker

TEXT = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncx q[0],q[1];\ncx q[0],q[1];\ncx q[0],q[1];\n'
ONE = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncx q[0],q[1];\n'


def test_the_exploratory_passes_are_three_and_none_is_in_the_pool_or_borrows_its_name():
    pool_names = set(passes.pool())
    names = set(exploratory.pool())
    assert len(names) == 3 and names.isdisjoint(pool_names) and all(n.startswith("x-") for n in names)


def test_the_pool_itself_has_no_exploratory_name():
    assert not any(n.startswith("x-") for n in passes.pool())


def test_a_passes_spec_for_the_exploratory_pool_runs_those_passes_and_no_others(tmp_path, monkeypatch):
    monkeypatch.setattr(exploratory, "pool", lambda: {"x-one": lambda t, s: ONE})
    spec = {"job": "passes", "case": "dev-6-x", "set": "dev", "out_dir": str(tmp_path), "pool": "exploratory"}
    result = worker.run_passes(spec, clock=itertools.count(0.0, 1.0).__next__, start_text=(TEXT, TEXT))
    assert [r["pass"] for r in result["rows"]] == ["x-one"] and result["rows"][0]["cx"] == 1


def test_passes_jobs_can_name_the_exploratory_pool_and_the_default_is_the_real_pool():
    assert all(j["pool"] == "exploratory" for j in develop.passes_jobs(pool="exploratory"))
    assert all("pool" not in j for j in develop.passes_jobs())
