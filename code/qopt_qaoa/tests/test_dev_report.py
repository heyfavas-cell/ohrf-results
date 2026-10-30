import json
import math

from spikes.qopt_qaoa import dev_report


def pass_obs(case, input_cx, rows):
    return {"kind": "passes", "case": case, "input_cx": input_cx, "passes": rows}


def row(name, cx, seconds, verified=True, seed=1):
    return {"pass": name, "seed": seed, "cx": cx, "seconds": seconds, "verified": verified, "file": "f"}


def test_a_pass_slower_than_the_budget_or_unverified_scores_the_input_and_the_best_pass_ranks_first():
    obs = [pass_obs("dev-6-a", 100, [row("fast", 90, 1), row("slow", 50, 100), row("bad", 10, 1, verified=False)]),
           pass_obs("dev-8-b", 100, [row("fast", 90, 1), row("slow", 50, 100), row("bad", 10, 1, verified=False)])]
    table = dev_report.star_table(obs)
    assert [t["pass"] for t in table[15]][0] == "fast" and table[15][0]["gain"] == 0.1
    assert table[300][0]["pass"] == "slow" and table[300][0]["gain"] == 0.5
    assert {t["pass"]: t["verified_share"] for t in table[15]}["bad"] == 0.0


def test_passes_with_the_same_gain_are_ordered_by_name_so_s_star_is_the_first_by_name():
    rows = [row("b-pass", 90, 1), row("a-pass", 90, 1), row("c-pass", 100, 1)]
    for order in (rows, list(reversed(rows))):
        table = dev_report.star_table([pass_obs("dev-6-a", 100, order), pass_obs("dev-8-b", 100, order)])
        assert [t["pass"] for t in table[15]] == ["a-pass", "b-pass", "c-pass"]


def test_the_seeded_pass_takes_seeds_while_their_time_fits_and_keeps_the_best():
    rows = [row("q-level3", 90, 6, seed=1), row("q-level3", 80, 6, seed=2), row("q-level3", 70, 6, seed=3)]
    assert dev_report.pass_effective(rows, "q-level3", 15, 100) == 80  # two seeds fit in 15 s
    assert dev_report.pass_effective(rows, "q-level3", 300, 100) == 70
    assert dev_report.pass_effective(rows, "q-level3", 5, 100) is None


def test_guoq_runs_are_listed_per_circuit_and_budget_in_repeat_order_and_the_spread_is_pooled():
    def g(case, rep, cx, ok=True):
        return {"kind": "guoq", "case": case, "budget": 300, "rep": rep, "output_cx": cx, "verified": ok}

    obs = [g("dev-6-a", 1, 90), g("dev-6-a", 0, 100), g("dev-6-a", 2, 95), g("dev-8-b", 0, 50), g("dev-8-b", 1, 50),
           g("dev-8-b", 2, None, ok=False)]
    assert dev_report.guoq_cx(obs)[("dev-6-a", 300)] == [100, 90, 95]
    spread = dev_report.repeat_spread(obs)
    assert spread["circuits"] == 2 and spread["circuits_that_differ"] == 1 and spread["pooled_sd_log"] > 0


def test_shares_by_size_and_compute_hours():
    assert dev_report.shares_by_size([("dev-6-a", True), ("dev-6-b", False), ("dev-8-c", True)]) == {6: "1/2", 8: "1/1"}
    hours = dev_report.compute_hours([{"phase": "dev", "seconds": 3600}, {"phase": "note", "seconds": 0},
                                      {"phase": "dev", "seconds": 1800}])
    assert hours == {"dev": 1.5, "note": 0.0, "total": 1.5}


def test_a_held_out_circuit_in_the_same_folder_never_reaches_the_development_report(tmp_path):
    dev = [{"kind": "guoq", "case": "dev-6-a", "budget": 15, "rep": 0, "output_cx": 9, "verified": True, "input_cx": 10},
           {"kind": "guoq", "case": "held_out-6-a", "budget": 15, "rep": 0, "output_cx": 1, "verified": True, "input_cx": 10}]
    (tmp_path / "observations.jsonl").write_text("\n".join(json.dumps(o) for o in dev) + "\n", encoding="utf-8")
    text = dev_report.render(tmp_path)
    assert "1 circuits, geometric-mean ratio to input 0.9000" in text
    assert [o["case"] for o in dev_report.dev_only(dev)] == ["dev-6-a"]


def test_the_report_renders_from_run_files(tmp_path):
    def search(case, b, cx):
        return {"kind": "search", "config": "base", "case": case, "budget": b, "cx": cx, "verified": cx is not None,
                "input_cx": 100}

    def guoq(case, b, cx):
        return {"kind": "guoq", "case": case, "budget": b, "rep": 0, "output_cx": cx, "verified": True, "input_cx": 100}

    obs = []
    for case, g15, g300, c15, c300 in [("dev-6-a", 95, 94, 96, 92), ("dev-8-b", 97, 96, 98, 97), ("dev-10-c", 90, 89, 91, 90)]:
        obs += [guoq(case, 15, g15), guoq(case, 300, g300), search(case, 15, c15), search(case, 300, c300),
                pass_obs(case, 100, [row("p", 99, 1)])]
    (tmp_path / "observations.jsonl").write_text("\n".join(json.dumps(o) for o in obs) + "\n", encoding="utf-8")
    (tmp_path / "runs.jsonl").write_text(json.dumps({"batch": "b", "phase": "dev", "seconds": 7200}) + "\n", encoding="utf-8")
    text = dev_report.render(tmp_path)
    assert "no outcome is decided" in text and "proposed S*" in text and "Search config `base` (3 circuits)" in text
    assert "'dev': 2.0" in text and not math.isnan(dev_report.geomean([1.0, 2.0]))
