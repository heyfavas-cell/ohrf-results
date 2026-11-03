from datetime import date

from spikes.qopt_audit.ledger import Finding, counts_as_wrong_output, verdict

D0 = date(2026, 10, 14)


def f(**kw):
    base = dict(id="x", cls="wrong_output", tool="qiskit", reproducer_gates=12, reproducer_qubits=3, distance=0.3,
                tolerance_ok=True, proved_twice=True, second_opinion_ok=True, reproduces_latest=True, lead=False,
                duplicate_of=None, search_url=None, filed=None, accepted=None, url=None)
    base.update(kw)
    return Finding(**base)


def test_one_clean_small_wrong_output_passes_alone():
    assert verdict([f()], day0=D0, today=date(2026, 10, 20)) == "pass"


def test_a_tiny_rotation_dropped_within_tolerance_never_passes():
    assert verdict([f(tolerance_ok=False)], day0=D0, today=date(2026, 10, 28)) == "fallback"


def test_a_wrong_output_over_fifty_gates_does_not_pass_by_itself():
    assert verdict([f(reproducer_gates=51)], day0=D0, today=date(2026, 10, 28)) == "fallback"


def test_two_accepted_wrong_output_issues_pass_even_when_large():
    a = dict(reproducer_gates=90, search_url="u", filed=date(2026, 10, 20), accepted=date(2026, 10, 27))
    assert verdict([f(id="a", **a), f(id="b", **a)], day0=D0, today=date(2026, 10, 28)) == "pass"


def test_crash_and_reader_issues_never_count_however_many_are_accepted():
    a = dict(search_url="u", filed=date(2026, 10, 20), accepted=date(2026, 10, 27))
    crashes = [f(id=str(i), cls=c, **a) for i, c in enumerate(["crash", "reader", "crash"])]
    assert verdict(crashes, day0=D0, today=date(2026, 10, 28)) == "fallback"


def test_an_issue_filed_after_day_ten_or_without_a_search_link_does_not_count():
    late = dict(search_url="u", filed=date(2026, 10, 25), accepted=date(2026, 10, 27), reproducer_gates=90)
    nolink = dict(search_url=None, filed=date(2026, 10, 20), accepted=date(2026, 10, 27), reproducer_gates=90)
    assert verdict([f(id="a", **late), f(id="b", **nolink)], day0=D0, today=date(2026, 10, 28)) == "fallback"


def test_a_lead_a_duplicate_or_an_unreproduced_finding_does_not_count():
    assert not counts_as_wrong_output(f(lead=True))
    assert not counts_as_wrong_output(f(duplicate_of="qiskit#123"))
    assert not counts_as_wrong_output(f(reproduces_latest=False))
    assert not counts_as_wrong_output(f(proved_twice=False))
    assert not counts_as_wrong_output(f(second_opinion_ok=False))


def test_before_day_fourteen_an_unmet_rule_is_open_and_after_it_is_a_fallback():
    assert verdict([], day0=D0, today=date(2026, 10, 20)) == "open"
    assert verdict([], day0=D0, today=date(2026, 10, 28)) == "fallback"
