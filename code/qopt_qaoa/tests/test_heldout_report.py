import json

from spikes.qopt_qaoa import heldout_report

STAR = "q-1q-decompose"
CFG = {"s_star": {"15": STAR, "300": STAR}, "search": {"id": "wide"}, "n_heldout": {"n": 3, "s": 0.05}}


def arms(case, batch="held-1", g15=95, g300=90, c15=96, c300=92, star=100, verified=True, lead=None):
    base = {"batch": batch, "case": case, "input_cx": 100}
    return [
        {**base, "kind": "guoq", "budget": 15, "rep": 0, "output_cx": g15, "verified": True, "timed_out": False,
         "exit_code": 0, "overhead_s": 1.0, "wall_s": 16.0},
        {**base, "kind": "guoq", "budget": 300, "rep": 0, "output_cx": g300, "verified": True, "timed_out": False,
         "exit_code": 0, "overhead_s": 2.0, "wall_s": 302.0},
        {**base, "kind": "search", "config": "wide", "budget": 15, "cx": c15, "verified": verified, "leads": []},
        {**base, "kind": "search", "config": "wide", "budget": 300, "cx": c300, "verified": True,
         "leads": [lead] if lead else []},
        {**base, "kind": "passes", "passes": [{"pass": STAR, "seed": 1, "cx": star, "seconds": 0.01, "verified": True,
                                               "file": "f"}], "leads": []},
    ]


def obs():
    out = []
    for case in ("held_out-6-a", "held_out-8-b", "held_out-10-c"):
        out += arms(case)
    out += arms("dev-6-z", batch="dev")  # a development circuit in the same folder is never counted
    return out


def test_a_batch_summary_counts_arms_verified_ratios_and_leads_for_that_batch_only():
    text = heldout_report.batch_summary(obs() + arms("held_out-12-d", batch="held-2", verified=False,
                                                    lead={"lead_kind": "wrong_output"}), "held-1", CFG)
    assert "held-1" in text and "3 circuits" in text
    assert "guoq@300: 3/3 verified, ratio 0.9000" in text and "cand@15: 3/3 verified, ratio 0.9600" in text
    assert "leads: 0" in text and "held_out-12-d" not in text and "dev-6-z" not in text


def refusal(job, utc):
    return {"job": job, "refused_utc": utc, "reason": "free memory 9.0 GB is under 8 GB plus the 1.3 GB reserve"}


def test_memory_waits_are_the_time_between_a_jobs_first_refusal_and_its_start_and_only_for_that_batch():
    records = [dict(o, job=f"held-1-{i}", start_utc="2026-10-29T10:00:00+00:00") for i, o in enumerate(obs()[:3])]
    refusals = [refusal("held-1-0", "2026-10-29T09:50:00+00:00"), refusal("held-1-0", "2026-10-29T09:55:00+00:00"),
                refusal("held-1-1", "2026-10-29T09:58:00+00:00"), refusal("held-2-0", "2026-10-29T01:00:00+00:00")]
    waits = heldout_report.memory_waits(records, refusals, "held-1")
    assert waits == {"jobs_that_waited": 2, "refusals": 3, "total_wait_s": 720.0, "max_wait_s": 600.0}


def test_progress_gives_held_out_hours_the_projection_and_the_reserve_and_total_headroom(tmp_path):
    cfg = dict(CFG, n_heldout={"n": 6, "s": 0.05})
    records = [dict(o, batch="held-1") for o in obs()[:15]]  # three circuits, all arms, in batch held-1
    (tmp_path / "observations.jsonl").write_text("\n".join(json.dumps(o) for o in records) + "\n", encoding="utf-8")
    (tmp_path / "runs.jsonl").write_text(
        json.dumps({"batch": "dev-x", "phase": "dev", "seconds": 7200}) + "\n"
        + json.dumps({"batch": "held-1", "phase": "held_out", "seconds": 3 * 3600}) + "\n", encoding="utf-8")
    p = heldout_report.progress(tmp_path, cfg)
    assert p["held_out_hours_used"] == 3.0 and p["circuits_done"] == 3 and p["circuits_planned"] == 6
    assert p["projected_held_out_hours"] == 6.0 and p["projected_total_hours"] == 8.0
    assert p["held_out_cap_hours"] == 12 and p["reserve_hours"] == 8 and p["total_cap_hours"] == 30


def test_a_summary_does_not_decide_the_outcome():
    assert "outcome" not in heldout_report.batch_summary(obs(), "held-1", CFG).lower()


def test_the_final_report_decides_once_on_the_held_out_rows_and_adds_the_verified_only_row(tmp_path):
    records = obs() + arms("held_out-12-d", batch="held-2", verified=False)
    (tmp_path / "observations.jsonl").write_text("\n".join(json.dumps(o) for o in records) + "\n", encoding="utf-8")
    (tmp_path / "runs.jsonl").write_text(json.dumps({"batch": "held-1", "phase": "held_out", "seconds": 3600}) + "\n",
                                         encoding="utf-8")
    text = heldout_report.final(tmp_path, CFG)
    assert "outcome: " in text and "circuits with every arm: 4 of 3 planned" in text
    assert "verified-only" in text and "'held_out': 1.0" in text
    assert "dev-6-z" not in text
