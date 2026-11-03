import re

import pytest

from spikes.qopt_audit.tolerance import largest_drop

ROTATION = re.compile(r"^(rz|rx)\(([^)]*)\) q\[\d+\];\n", re.M)


def deletes_rotations_up_to(cutoff):
    """A faulty tool that deletes every rz and rx whose angle is at most `cutoff` and leaves the rest as it is."""
    def tool(name, text, seed):
        return ROTATION.sub(lambda m: "" if abs(float(m.group(2))) <= cutoff else m.group(0), text)
    return tool


@pytest.mark.xfail(strict=True, reason="qasm2.dumps writes an angle below 1e-12 as 0, so the probe's own input loses "
                                       "cu1(1e-13) and largest_drop charges that to the tool")
def test_a_faithful_tool_drops_nothing(monkeypatch):
    monkeypatch.setattr("spikes.qopt_audit.tolerance.run_text", lambda name, text, seed: text)
    assert largest_drop("qiskit") == 0.0


@pytest.mark.xfail(strict=True, reason="P0c: deleting rz or rx moves the output by exactly eps/2 after the phase is "
                                       "removed, and largest_drop counts only a distance above 0.5 * eps")
def test_a_rotation_deleted_outright_is_measured(monkeypatch):
    monkeypatch.setattr("spikes.qopt_audit.tolerance.run_text", deletes_rotations_up_to(1e-6))
    assert largest_drop("qiskit") == pytest.approx(1e-6)
