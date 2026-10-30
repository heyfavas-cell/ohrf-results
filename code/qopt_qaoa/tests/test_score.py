import random

from spikes.qopt_qaoa import frozen, score
from spikes.qopt_qaoa.score import LONG, SHORT, Row


def table(n=60, guoq=0.85, cand=0.85, cand_short=None, star=1.0, star_short=None, seed=3, noise=0.01, input_cx=200):
    """Rows whose counts follow the given ratios to the input, with a little seeded noise."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        def at(ratio):
            return max(1, round(input_cx * ratio * (1 + rng.uniform(-noise, noise))))
        g = at(guoq)
        rows.append(Row(f"c{i}", input_cx, {SHORT: g, LONG: g},
                        {SHORT: at(cand if cand_short is None else cand_short), LONG: at(cand)},
                        {SHORT: at(star if star_short is None else star_short), LONG: at(star)}))
    return rows


def test_a_candidate_clearly_better_than_guoq_and_the_single_pass_passes():
    r = score.decide(table(guoq=0.9, cand=0.8, star=0.95))
    assert r["outcome"] == "pass" and r["pass_q"] and r["Q"]["gain"] >= 0.01 and r["Q"]["gain_lower"] > 0


def test_equal_to_guoq_at_the_long_budget_alone_is_a_null():
    r = score.decide(table(guoq=0.85, cand=0.85, cand_short=0.9, star=1.0))
    assert r["outcome"] == "null" and not r["pass_q"]


def test_a_gain_under_one_percent_is_not_a_pass_however_tight_the_interval():
    r = score.decide(table(guoq=0.85, cand=0.8445, cand_short=0.9, star=1.0, noise=0.001))
    assert 0 < r["Q"]["gain"] < frozen.GAIN_MIN and r["outcome"] == "null"


def test_matching_guoq_at_the_short_budget_passes_the_time_test():
    r = score.decide(table(guoq=0.85, cand=0.83, cand_short=0.85, star=1.0))
    assert r["pass_t"] and r["outcome"] == "pass"
    assert not r["pass_q"] or r["Q"]["gain"] >= 0.01


def test_worse_than_one_percent_at_the_short_budget_fails_the_time_test():
    r = score.decide(table(guoq=0.85, cand=0.85, cand_short=0.88, star=1.0))
    assert not r["pass_t"] and r["outcome"] == "null"


def test_a_win_that_one_existing_pass_already_gives_is_single_pass_not_pass():
    r = score.decide(table(guoq=0.9, cand=0.8, star=0.8))
    assert not r["pass_q"] and r["outcome"] == "single-pass"
    r = score.decide(table(guoq=0.9, cand=0.8, star=0.8))
    assert r["star_vs_guoq_long"]["gain"] > 0.01


def test_pass_takes_precedence_over_single_pass_when_the_candidate_beats_the_single_pass_too():
    r = score.decide(table(guoq=0.9, cand=0.75, star=0.85))
    assert r["outcome"] == "pass" and r["star_vs_guoq_long"]["gain"] > 0.01


def test_an_unverified_output_scores_the_input_on_both_sides():
    rows = [Row("a", 100, {LONG: None, SHORT: None}, {LONG: 80, SHORT: 80}, {LONG: None, SHORT: None}),
            Row("b", 100, {LONG: 90, SHORT: 90}, {LONG: None, SHORT: None}, {LONG: 100, SHORT: 100})]
    assert score.pairs(rows, ("guoq", LONG), ("cand", LONG)) == [(100, 80), (90, 100)]
    assert score.verified_shares(rows)["guoq@300"] == 0.5 and score.verified_shares(rows)["star@15"] == 0.5


def test_a_low_verified_share_is_flagged_and_the_verified_only_row_is_reported():
    rows = table(n=20)
    for r in rows[:8]:
        r.cand[LONG] = None
    out = score.decide(rows)
    assert out["below_verified_floor"] and out["verified_only_Q"]["n"] == 12


def test_the_smallest_findable_gain_shrinks_with_the_sample():
    small = score.smallest_gain([(100, 90), (100, 105), (100, 80), (100, 99)])
    big = score.smallest_gain([(100, 90), (100, 105), (100, 80), (100, 99)] * 25)
    assert big < small and score.smallest_gain([(100, 90)]) is None


def test_equal_quality_at_the_short_budget_is_the_time_pass_even_with_no_gain_at_the_long_one():
    r = score.decide(table(guoq=0.85, cand=0.85, star=1.0))
    assert r["pass_t"] and not r["pass_q"] and r["outcome"] == "pass"
