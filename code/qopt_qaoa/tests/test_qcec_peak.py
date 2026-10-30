from spikes.qopt_qaoa import qcec_peak


def test_the_sampler_keeps_the_largest_memory_threads_and_cores_it_saw():
    readings = iter([(1.0, 4, 100.0), (8.3, 20, 1200.0), (2.0, 6, 300.0)] + [(2.0, 6, 300.0)] * 200)
    value, peak = qcec_peak.measure(lambda: (__import__("time").sleep(0.2), "done")[1], probe=lambda: next(readings),
                                    interval=0.01)
    assert value == "done" and peak.private_gb == 8.3 and peak.threads == 20 and peak.cores == 12.0


def test_a_probe_that_fails_does_not_stop_the_measured_call():
    def probe():
        raise OSError("process gone")

    value, peak = qcec_peak.measure(lambda: 7, probe=probe, interval=0.01)
    assert value == 7 and peak.private_gb == 0.0


def test_the_table_takes_the_largest_peak_per_size_and_the_reserve_looks_a_size_up(tmp_path):
    rows = [{"size": 22, "private_gb": 8.3}, {"size": 22, "private_gb": 5.0}, {"size": 6, "private_gb": 0.2}]
    table = qcec_peak.table(rows)
    assert table == {6: 0.2, 22: 8.3}
    assert qcec_peak.reserve_for_size(table, 22) == 8.3 and qcec_peak.reserve_for_size(table, 8) == 0.2
    assert qcec_peak.reserve_for_size({}, 10) == 0.0
