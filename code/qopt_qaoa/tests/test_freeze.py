import hashlib
import json
from datetime import datetime, timedelta, timezone

from spikes.qopt_qaoa import freeze, frozen, passes

T0 = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def stamp(seconds):
    return (T0 + timedelta(seconds=seconds)).isoformat()


def guoq(case, budget, seconds, cx=90):
    return {"kind": "guoq", "case": case, "budget": budget, "rep": 0, "input_cx": 100, "output_cx": cx, "verified": True,
            "start_utc": stamp(0), "end_utc": stamp(seconds)}


def search(case, budget, seconds, cx=95, config="wide"):
    return {"kind": "search", "config": config, "case": case, "budget": budget, "input_cx": 100, "cx": cx, "verified": True,
            "start_utc": stamp(0), "end_utc": stamp(seconds)}


def passes_obs(case, star_seconds=0.01):
    return {"kind": "passes", "case": case, "input_cx": 100,
            "passes": [{"pass": "q-1q-decompose", "seed": 1, "cx": 100, "seconds": star_seconds, "verified": True,
                        "file": "f"}]}


def obs_for(case, g15=20, g300=310, s15=18, s300=250, cx=95):
    return [guoq(case, 15, g15), guoq(case, 300, g300), search(case, 15, s15, cx=cx), search(case, 300, s300, cx=cx),
            passes_obs(case)]


def test_worker_seconds_per_circuit_sums_the_four_job_times_and_the_star_pass_for_both_budgets():
    obs = obs_for("dev-6-a") + obs_for("dev-8-b", g15=30)
    per = freeze.worker_seconds_per_circuit(obs, config="wide", star="q-1q-decompose")
    assert per == ((20 + 310 + 18 + 250 + 0.02) + (30 + 310 + 18 + 250 + 0.02)) / 2


def test_n_heldout_is_the_cap_when_the_cost_makes_the_cap_smaller_than_the_need():
    cfg = freeze.build(obs_for("dev-6-a") + obs_for("dev-8-b", cx=88) + obs_for("dev-10-c", cx=96),
                       config={"id": "wide", "beam": 8, "max_steps": 10, "proposals": 5, "order": None, "seed": 1},
                       star={"15": "q-1q-decompose", "300": "q-1q-decompose"})
    n = cfg["n_heldout"]
    assert n["n"] == min(max(n["needed"], frozen.HELD_OUT_MIN), n["cap"], 324)
    assert n["worker_seconds_per_circuit"] == 598.02 and n["circuits"] == 3
    assert n["cap"] == int(frozen.HELD_OUT_CAP_S * frozen.WORKERS_DEFAULT / 598.02)
    import math
    expect = round(1 - math.exp(-(1.96 + 0.8416) * n["s"] / math.sqrt(n["n"])), 6)
    assert n["smallest_gain_at_n"] == expect
    assert cfg["s_star"] =={"15": "q-1q-decompose", "300": "q-1q-decompose"}
    assert cfg["search"]["beam"] == 8 and cfg["pool"] == list(passes.pool())


def test_the_runs_are_the_first_n_of_the_stratified_order_and_balanced():
    names = freeze.run_names(120)
    assert len(names) == 120 and len(set(names)) == 120
    assert names == freeze.run_names(300)[:120]


def test_the_file_and_its_hash_are_written_and_the_hash_matches_the_bytes(tmp_path):
    cfg = {"b": 1, "a": [2, 3]}
    path = freeze.write(tmp_path / "search_config.json", cfg)
    digest = (tmp_path / "search_config.sha256").read_text(encoding="utf-8").split()[0]
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest() and json.loads(path.read_text(encoding="utf-8")) == cfg


def test_the_committed_config_names_the_pool_the_code_has_and_the_frozen_defaults_it_overrides():
    path = freeze.CONFIG_PATH
    if not path.exists():
        return
    cfg = json.loads(path.read_text(encoding="utf-8"))
    assert cfg["pool"] == list(passes.pool()) and cfg["n_heldout"]["n"] >= min(frozen.HELD_OUT_MIN, cfg["n_heldout"]["cap"])
    digest = path.with_suffix(".sha256").read_text(encoding="utf-8").split()[0]
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
