from spikes.qopt_qaoa import search

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\n'


def circ(cx: int, extra: int = 0) -> str:
    return HEAD + "cx q[0],q[1];\n" * cx + "rz(0.1) q[0];\n" * extra


class FakeClock:
    """Each call to the clock advances time; each pass call advances it by `cost`."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def timed(clock, cost, fn):
    def run(text, seed):
        clock.t += cost
        return fn(text, seed)
    return run


def drop_one(text, seed):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("cx "):
            return "\n".join(lines[:i] + lines[i + 1:]) + "\n"
    raise ValueError("nothing to drop")


def test_the_search_finds_the_best_sequence_and_proposes_distinct_states_best_first():
    clock = FakeClock()
    passes = {"drop": timed(clock, 1, drop_one), "pad": timed(clock, 1, lambda t, s: t + "rz(0.2) q[1];\n")}
    r = search.search(circ(5), passes, 1000, clock=clock, max_steps=6)
    assert r.proposals[0].cx == 0 and r.proposals[0].path.count("drop") == 5
    assert len({p.qasm for p in r.proposals}) == len(r.proposals) <= 5
    assert [(p.cx, p.gates) for p in r.proposals] == sorted((p.cx, p.gates) for p in r.proposals)


def test_the_original_is_always_a_proposal_so_a_useless_pool_loses_nothing():
    clock = FakeClock()
    r = search.search(circ(3), {"noop": timed(clock, 1, lambda t, s: t)}, 100, clock=clock)
    assert [p.path for p in r.proposals] == [()] and r.proposals[0].cx == 3


def test_the_search_stops_starting_passes_at_the_budget_and_logs_the_overrun():
    clock = FakeClock()
    passes = {"drop": timed(clock, 4, drop_one)}
    r = search.search(circ(50), passes, 10, clock=clock, max_steps=50)
    assert r.calls == 3 and r.elapsed_s == 12 and r.overrun_s == 2


def test_a_failing_pass_is_counted_and_skipped():
    clock = FakeClock()
    passes = {"bad": timed(clock, 1, lambda t, s: 1 / 0), "drop": timed(clock, 1, drop_one)}
    r = search.search(circ(2), passes, 100, clock=clock)
    assert r.errors["bad"] >= 1 and r.proposals[0].cx == 0


def test_seeded_passes_see_a_new_seed_on_every_restart():
    clock, seeds = FakeClock(), []

    def seeded(text, seed):
        clock.t += 1
        seeds.append(seed)
        return text + f"rz({seed}.5) q[0];\n"

    search.search(circ(1), {"s": seeded}, 40, clock=clock, max_steps=1)
    assert len(set(seeds)) > 3


def test_choose_takes_the_first_verified_proposal_and_none_is_a_loss():
    clock = FakeClock()
    r = search.search(circ(3), {"drop": timed(clock, 1, drop_one)}, 100, clock=clock)
    best, tried = search.choose(r, lambda q: search.cx_count(q) >= 2)
    assert best.cx == 2 and tried >= 2
    none, tried = search.choose(r, lambda q: False)
    assert none is None and tried == len(r.proposals)
