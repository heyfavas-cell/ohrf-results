from spikes.qopt_qaoa import frozen, sample


def test_the_floor_binds_when_the_spread_is_small():
    pairs = [(100, 100)] * 10
    r = sample.n_heldout(pairs, worker_seconds_per_circuit=700)
    assert r["needed"] <= 108 and r["n"] == 108 and r["floor_met"]


def test_a_large_spread_is_cut_by_the_cap_and_the_pool():
    pairs = [(100, 90), (100, 110), (100, 100), (100, 80)]
    cheap = sample.n_heldout(pairs, worker_seconds_per_circuit=1.0)
    assert cheap["n"] == sample.pool_size() == 324
    costly = sample.n_heldout(pairs, worker_seconds_per_circuit=700)
    assert costly["n"] == costly["cap"] == sample.n_cap(700)


def test_a_cap_under_the_floor_is_reported():
    r = sample.n_heldout([(100, 90), (100, 110)], worker_seconds_per_circuit=2000)
    assert r["n"] < frozen.HELD_OUT_MIN and not r["floor_met"]
