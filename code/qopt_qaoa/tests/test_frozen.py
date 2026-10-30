import importlib.metadata as md
import re
from pathlib import Path

from spikes.qopt_qaoa import frozen

HERE = Path(__file__).resolve().parents[1]
PLAN = HERE.parents[1] / "docs" / "plans" / "P0e-qaoa-explore.md"


def test_the_plan_carries_the_frozen_parameters_verbatim():
    text = (HERE / "frozen.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    plan = PLAN.read_text(encoding="utf-8").replace("\r\n", "\n")
    block = re.search(r"## Frozen parameters.*?```python\n(.*?)```", plan, re.S).group(1)
    assert text == block


def test_the_pinned_tools_are_the_installed_ones():
    for name, version in frozen.TOOL_PINS.items():
        assert md.version(name) == version, name


def test_the_budgets_and_caps_are_consistent():
    assert frozen.B_SHORT_S < frozen.B_LONG_S
    assert frozen.DEV_CAP_S + frozen.HELD_OUT_CAP_S <= frozen.COMPUTE_CAP_S
    assert frozen.WORKERS_DEFAULT <= frozen.WORKERS_IDLE_MAX == 3
    assert frozen.RUN_CAP_S <= frozen.COMPUTE_CAP_S
