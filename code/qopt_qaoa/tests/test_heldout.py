import json

import pytest

from spikes.qopt_qaoa import freeze, frozen, heldout

CFG = {"s_star": {"15": "q-1q-decompose", "300": "q-1q-decompose"},
       "search": {"id": "wide", "beam": 8, "max_steps": 10, "proposals": 5, "order": None, "seed": 1},
       "run_names": [f"held_out-{s}-regular3-p1-r{i}" for i in range(3) for s in (6, 22, 8, 20)]}


def anchor(**kw):
    base = {"status": "complete", "bitcoin_attestations": [{"block": 973556}], "files": {}}
    return {**base, **kw}


def write_anchor(tmp_path, **kw):
    path = tmp_path / "anchor.json"
    path.write_text(json.dumps(anchor(**kw)), encoding="utf-8")
    return path


def test_the_gate_opens_only_with_a_complete_anchor_a_matching_config_hash_and_the_freeze_tag(tmp_path):
    cfg_path = freeze.write(tmp_path / "search_config.json", CFG)
    heldout.gate(write_anchor(tmp_path), config_path=cfg_path, tag_exists=lambda t: t == "qaoa-freeze")
    with pytest.raises(heldout.Gate, match="anchor"):
        heldout.gate(write_anchor(tmp_path, status="pending Bitcoin confirmation"), config_path=cfg_path,
                     tag_exists=lambda t: True)
    with pytest.raises(heldout.Gate, match="Bitcoin"):
        heldout.gate(write_anchor(tmp_path, bitcoin_attestations=[]), config_path=cfg_path, tag_exists=lambda t: True)
    with pytest.raises(heldout.Gate, match="tag"):
        heldout.gate(write_anchor(tmp_path), config_path=cfg_path, tag_exists=lambda t: False)
    cfg_path.write_text(cfg_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(heldout.Gate, match="hash"):
        heldout.gate(write_anchor(tmp_path), config_path=cfg_path, tag_exists=lambda t: True)


def test_each_circuit_gets_the_five_frozen_arms_and_the_search_config_comes_from_the_frozen_file():
    jobs = heldout.jobs_for(["held_out-6-regular3-p1-r0"], CFG)
    assert [(j.get("kind", "guoq"), j["budget"]) for j in jobs if j.get("kind", "guoq") != "passes"] == [
        ("guoq", 300), ("search", 300), ("guoq", 15), ("search", 15)]
    star = [j for j in jobs if j.get("kind") == "passes"]
    assert len(star) == 1 and star[0]["names"] == ["q-1q-decompose"]
    assert all(j["set"] == "held_out" for j in jobs) and all(j["rep"] == 0 for j in jobs if "rep" in j)
    assert next(j for j in jobs if j.get("kind") == "search")["config"] == CFG["search"]


def test_blocks_keep_the_order_put_size_22_last_and_are_at_most_the_block_size():
    names = CFG["run_names"]
    blocks = heldout.blocks(names, size=4)
    flat = [n for b in blocks for n in b]
    assert sorted(flat) == sorted(names) and all(len(b) <= 4 for b in blocks)
    assert all("-22-" not in n for b in blocks[:-1] for n in b) and all("-22-" in n for n in blocks[-1])
    assert [n for n in flat if "-22-" not in n] == [n for n in names if "-22-" not in n]


def test_a_rerun_skips_the_jobs_already_logged_and_nothing_else():
    jobs = heldout.jobs_for(["held_out-6-regular3-p1-r0", "held_out-8-regular3-p1-r0"], CFG)
    done = [{"kind": "guoq", "case": "held_out-6-regular3-p1-r0", "budget": 300, "rep": 0},
            {"kind": "search", "case": "held_out-6-regular3-p1-r0", "budget": 15, "config": "wide"},
            {"kind": "passes", "case": "held_out-8-regular3-p1-r0"},
            {"kind": "guoq", "case": "held_out-8-regular3-p1-r0", "budget": 300, "rep": 1}]
    left = heldout.pending(jobs, done)
    assert len(left) == len(jobs) - 3
    assert not any(j["name"] == "held_out-6-regular3-p1-r0" and j.get("kind", "guoq") == "guoq" and j["budget"] == 300
                   for j in left)


def test_budgets_are_the_frozen_ones_for_the_held_out_set():
    assert {j["budget"] for j in heldout.jobs_for(["held_out-6-regular3-p1-r0"], CFG) if j.get("kind") != "passes"} == set(
        frozen.BUDGETS_S)
