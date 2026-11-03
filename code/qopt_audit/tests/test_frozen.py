from pathlib import Path

from spikes.qopt_audit import frozen
from spikes.qopt_audit.tolerance import largest_drop

HERE = Path(__file__).resolve().parents[1]
PLAN = HERE.parents[1] / "docs" / "plans" / "P0b-audit-spike.md"


def test_the_plan_carries_the_frozen_parameters_verbatim():
    text = (HERE / "frozen.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert text.strip() in PLAN.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_the_compute_and_worker_caps_are_the_registered_ones():
    assert frozen.COMPUTE_CAP_S == 30 * 3600 and frozen.RUN_CAP_S == 4 * 3600 and frozen.WORKERS == 3
    assert frozen.DECIDE_DAY == 14 and frozen.FILE_BY_DAY == 10 and frozen.REDUCED_MAX_GATES == 50


def test_the_installed_tools_are_the_pinned_ones():
    from importlib.metadata import PackageNotFoundError, version
    for name, pin in frozen.TOOL_PINS.items():
        try:
            assert version(name) == pin, name
        except PackageNotFoundError:
            assert name == "mqt.bench", name  # only needed to write the base circuits once


def test_no_pinned_tool_drops_more_than_its_recorded_tolerance():
    for tool in frozen.TOOLS:
        assert largest_drop(tool) <= frozen.TOLERANCE[tool], tool


def test_the_boundary_angles_cover_tiny_quarter_turn_and_binary_fraction_values():
    values = set(frozen.BOUNDARY_ANGLES)
    assert 9.6e-05 in values and 1e-12 in values
    assert any(abs(v - 3.141592653589793 / 2) < 1e-15 for v in values)
    assert any(abs(v - 2 * 3.141592653589793 / 4096) < 1e-18 for v in values)
