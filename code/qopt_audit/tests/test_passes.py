from spikes.qopt_audit.passes import AFTER_PIPELINE, first_breaking_pass, trace

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
SWAPPED = HEAD + "qreg q[3];\nx q[0];\nh q[2];\nswap q[0],q[1];\nswap q[1],q[2];\nrz(0.3) q[1];\ncx q[1],q[0];\n"
TINY = HEAD + "qreg q[2];\nh q[0];\nh q[1];\ncu1(9.6e-05) q[0],q[1];\nh q[0];\n"


def test_an_elided_swap_breaks_the_operator_only_for_a_probe_blind_to_the_layout():
    assert first_breaking_pass(SWAPPED, layout_aware=False) == "ElidePermutations"
    assert first_breaking_pass(SWAPPED, layout_aware=True) is None


def test_the_known_tiny_controlled_phase_drop_is_named_with_or_without_the_layout():
    assert first_breaking_pass(TINY, layout_aware=False) == "TwoQubitPeepholeOptimization"
    assert first_breaking_pass(TINY, layout_aware=True) == "TwoQubitPeepholeOptimization"


def test_a_swap_does_not_hide_a_later_drop_from_the_layout_aware_probe():
    both = SWAPPED.replace("qreg q[3];\n", "qreg q[3];\nh q[0];\nh q[1];\ncu1(9.6e-05) q[0],q[1];\nh q[0];\n")
    assert first_breaking_pass(both, layout_aware=False) == "ElidePermutations"
    assert first_breaking_pass(both, layout_aware=True) == "TwoQubitPeepholeOptimization"


def test_the_trace_ends_with_the_final_output_of_the_audit_pipeline():
    steps = trace(SWAPPED, layout_aware=True)
    assert steps[-1][0] == AFTER_PIPELINE and steps[-1][1] < 1e-9
