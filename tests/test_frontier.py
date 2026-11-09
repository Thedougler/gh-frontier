"""Hermetic tests for gh-frontier's ordering, filtering and topo logic.

Run: uv run --with pytest pytest -q
"""

import importlib.machinery
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).parent
loader = importlib.machinery.SourceFileLoader("gh_frontier", str(HERE.parent / "gh-frontier"))
spec = importlib.util.spec_from_loader("gh_frontier", loader)
gf = importlib.util.module_from_spec(spec)
loader.exec_module(gf)


def load_issues():
    raw = json.loads((HERE / "fixtures" / "issues.json").read_text())
    return gf.compute_stats(gf.normalize(raw["nodes"], ["P0", "P1", "P2", "P3"], "P2"))


@pytest.fixture()
def issues():
    return load_issues()


def sel(issues, **kw):
    labels = kw.get("labels", [])
    exclude = kw.get("exclude", [])
    unassigned = kw.get("unassigned", False)
    priorities = kw.get("priorities", [])
    return {n: i for n, i in issues.items()
            if gf.matches(i, labels, exclude, unassigned, priorities)}


def test_frontier_excludes_blocked(issues):
    got = [i["number"] for i in gf.order_issues(sel(issues, labels=["ready"]), gf.parse_sort("priority,number"), [])
           if not i["blocked_by_open"]]
    # 5 blocked by 4; 6 blocked by 5; 10-12 cycle members each blocked
    assert got == [1, 2, 7, 4, 3]


def test_priority_then_number_order(issues):
    got = [i["number"] for i in gf.order_issues(sel(issues, labels=["ready"]), gf.parse_sort("priority,number"), [])]
    assert got == [1, 2, 7, 4, 3, 5, 6]  # 8-12 lack the ready label

def test_per_tier_keeps_the_oldest_of_each_tier_and_counts_the_rest():
    records = [{"number": n, "priority": p} for n, p in
               [(1, "P0"), (4, "P0"), (9, "P0"), (2, "P1"), (3, "P2"), (5, "P2"), (8, "P2")]]
    kept, omitted = gf.per_tier(records, 2)
    assert [r["number"] for r in kept] == [1, 4, 2, 3, 5]
    assert omitted == {"P0": 1, "P2": 1}



def test_default_priority_p2(issues):
    assert issues[3]["priority"] == "P2"
    assert issues[5]["priority"] == "P2"


def test_closed_blocker_does_not_block(issues):
    assert issues[2]["blocked_by_open"] == []
    assert issues[2]["blocked_by_closed"] == [9]
    assert issues[2]["depth"] == 0


def test_depth(issues):
    assert issues[6]["depth"] == 2  # 6 <- 5 <- 4
    assert issues[5]["depth"] == 1
    assert issues[4]["depth"] == 0  # 4 is a blocker, blocked by no one


def test_unblocks_transitive(issues):
    assert issues[4]["unblocks"] == 2  # 5 and 6
    assert issues[5]["unblocks"] == 1
    assert issues[6]["unblocks"] == 0


def test_blocks_back_edges(issues):
    assert issues[4]["blocks"] == [5]
    assert issues[5]["blocks"] == [6]


def test_sort_unblocks_desc(issues):
    got = [i["number"] for i in gf.order_issues(sel(issues, labels=["ready"]), gf.parse_sort("unblocks,number"), [])]
    assert got[0] == 4  # unblocks 2


def test_sort_newest_first(issues):
    got = [i["number"] for i in gf.order_issues(sel(issues, labels=["ready"]), gf.parse_sort("newest"), [])]
    assert got == [7, 6, 5, 4, 3, 2, 1]  # only ready-labelled issues


def test_sort_updated(issues):
    got = [i["number"] for i in gf.order_issues(sel(issues, labels=["ready"]), gf.parse_sort("updated"), [])]
    assert got == sorted(got, key=lambda n: issues[n]["updated_at"], reverse=True)


def test_sort_depth(issues):
    got = [i["number"] for i in gf.order_issues(sel(issues, labels=["ready"]), gf.parse_sort("depth,number"), [])]
    assert got[:4] == [1, 2, 3, 4]  # depth 0 ties broken by number


def test_label_and_semantics(issues):
    got = sel(issues, labels=["P0", "ready"])
    assert set(got) == {1, 2, 7}


def test_exclude_label(issues):
    got = sel(issues, labels=["ready"], exclude=["needs-info"])
    assert 8 not in got


def test_unassigned_filter(issues):
    got = sel(issues, labels=["ready"], unassigned=True)
    assert 7 not in got
    assert 1 in got


def test_priority_filter(issues):
    got = sel(issues, labels=["ready"], priorities=["P0"])
    assert set(got) == {1, 2, 7}


def test_topological_order_respects_edges(issues):
    got = sel(issues, labels=["ready"])
    order = gf.topological_order(list(got.values()), gf.sort_key(gf.parse_sort("priority,number"), []))
    pos = {n: i for i, n in enumerate(order)}
    assert pos[4] < pos[5] < pos[6]  # blockers before blocked


def test_cycle_detected_with_path(issues):
    got = sel(issues)  # all open
    with pytest.raises(gf.CliError) as e:
        gf.topological_order(list(got.values()), gf.sort_key(gf.parse_sort("priority,number"), []))
    assert e.value.exit_code == gf.EXIT_CYCLE
    assert "#10 -> #11 -> #12 -> #10" in str(e.value) or "#10" in str(e.value)
    assert e.value.fix  # actionable fix present


def test_parse_sort_rejects_unknown():
    with pytest.raises(gf.CliError) as e:
        gf.parse_sort("priority,bogus")
    assert e.value.exit_code == gf.EXIT_USAGE


def test_json_record_shape(issues):
    i = issues[4]
    for key in ("number", "title", "priority", "labels", "assignees", "blocked_by_open",
                "blocked_by_closed", "blocks", "unblocks", "depth", "created_at", "updated_at", "url", "parent"):
        assert key in i
