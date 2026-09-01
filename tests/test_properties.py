"""Property tests: the BFS resolver, fed YAML generated from a random action
graph, must agree with a brute-force enumeration of every simple path over the
graph specification itself."""
from __future__ import annotations

import hashlib
from collections import Counter

from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from actpin.fetch import DictFetcher
from actpin.graph import LocalRepo, resolve
from actpin.refs import UNPINNED_STATES, parse_uses

REF_KINDS = ["sha", "tag", "branch", "short"]
NODE_KINDS = ["composite", "reusable", "docker"]


def ref_for(i: int, kind: str) -> str:
    h = hashlib.sha1(str(i).encode()).hexdigest()
    return {"sha": h, "tag": f"v{i}", "branch": f"main-{i}", "short": h[:7]}[kind]


@st.composite
def graphs(draw):
    n = draw(st.integers(1, 7))
    nodes = []
    for i in range(n):
        nodes.append({
            "kind": draw(st.sampled_from(NODE_KINDS)),
            "ref": draw(st.sampled_from(REF_KINDS)),
            "missing": draw(st.booleans()) and draw(st.booleans()),  # ~25%
            "image_pinned": draw(st.booleans()),
        })
    # Arbitrary directed edges: cycles, self-loops and duplicates allowed.
    edges = draw(st.lists(st.tuples(st.integers(0, n - 1), st.integers(0, n - 1)),
                          min_size=n - 1, max_size=3 * n))
    roots = draw(st.lists(st.integers(0, n - 1), min_size=1, max_size=4))
    local_action = draw(st.lists(st.integers(0, n - 1), max_size=2))
    return nodes, edges, roots, local_action


def uses_string(i: int, node: dict) -> str:
    sub = "/.github/workflows/w.yml" if node["kind"] == "reusable" else ""
    return f"org/a{i}{sub}@{ref_for(i, node['ref'])}"


def label(i: int, node: dict) -> str:
    return uses_string(i, node)  # Unit.label() has the same shape for remote units


def render(nodes, edges, roots, local_action):
    files = {}
    children = {i: [j for a, j in edges if a == i] for i in range(len(nodes))}
    for i, node in enumerate(nodes):
        if node["missing"]:
            continue
        slug, ref = f"org/a{i}", ref_for(i, node["ref"])
        steps = "".join(f"      - uses: {uses_string(j, nodes[j])}\n" for j in children[i])
        if node["kind"] == "composite":
            body = "name: a\nruns:\n  using: composite\n  steps:\n" + (
                steps.replace("      - ", "    - ") or "    - run: true\n")
            files[(slug, ref, "action.yml")] = body
        elif node["kind"] == "docker":
            image = ("docker://alpine@sha256:" + "a" * 64) if node["image_pinned"] else "docker://alpine:3"
            # Docker actions have no steps; edges out of them are ignored.
            files[(slug, ref, "action.yml")] = f"name: d\nruns:\n  using: docker\n  image: '{image}'\n"
        else:
            body = "on: workflow_call\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n" + (
                steps or "      - run: true\n")
            files[(slug, ref, ".github/workflows/w.yml")] = body
    wf = "on: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n"
    wf += "".join(f"      - uses: {uses_string(j, nodes[j])}\n" for j in roots)
    local = {".github/workflows/ci.yml": wf}
    if local_action:
        wf += "      - uses: ./.github/actions/mine\n"
        local[".github/workflows/ci.yml"] = wf
        local[".github/actions/mine/action.yml"] = (
            "runs:\n  using: composite\n  steps:\n"
            + "".join(f"    - uses: {uses_string(j, nodes[j])}\n" for j in local_action))
    return local, files


def brute_force(nodes, edges, roots, local_action):
    """Enumerate every simple path from the root workflow; no visited-set
    shortcuts, no YAML."""
    def out_edges(u):
        if u == "ci":
            es = [("n", j) for j in roots] + ([("l", None)] if local_action else [])
            return es
        if u == "local":
            return [("n", j) for j in local_action]
        i = u
        node = nodes[i]
        if node["missing"]:
            return []
        if node["kind"] == "docker":
            return [("img", None)]
        return [("n", j) for a, j in edges if a == i]

    dist = {}
    def dfs(u, depth, on_path):
        dist[u] = min(dist.get(u, depth), depth)
        for kind, j in out_edges(u):
            v = j if kind == "n" else ("local" if kind == "l" else None)
            if v is None or v in on_path:
                continue
            dfs(v, depth + 1, on_path | {v})
    dfs("ci", 0, {"ci"})

    findings = Counter()
    for u, d in dist.items():
        for kind, j in out_edges(u):
            if kind == "n":
                raw = uses_string(j, nodes[j])
            elif kind == "img":
                raw = None if nodes[u]["image_pinned"] else "docker://alpine:3"
            else:
                raw = None
            if raw and parse_uses(raw).state in UNPINNED_STATES:
                findings[(u, raw, d + 1)] += 1
    return dist, findings


def unit_key(unit):
    if unit.origin == "local":
        return "ci" if unit.path.endswith("ci.yml") else "local"
    return int(unit.slug.split("/a")[1])


_COMPOSITE = {"kind": "composite", "ref": "tag", "missing": False, "image_pinned": True}


@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(graphs())
# A deep path that a depth-first walk would find before the short one.
@example(([_COMPOSITE] * 4, [(0, 3), (1, 2), (2, 3)], [0, 1], []))
def test_resolver_matches_brute_force(g):
    nodes, edges, roots, local_action = g
    local, files = render(*g)
    res = resolve(LocalRepo(local), DictFetcher(files))
    dist, expected = brute_force(*g)

    assert {unit_key(u): d for u, d in res.dist.items()} == dist
    got = Counter((unit_key(f.parent), f.use.ref.raw, f.depth) for f in res.findings)
    assert got == expected

    # Every reported path is a real chain of references starting at the workflow.
    for f in res.findings:
        assert f.path[0] == ".github/workflows/ci.yml"
        assert f.path[-1] == f.use.ref.raw
        assert len(f.path) == dist[unit_key(f.parent)] + 2
        for hop in f.path[1:-1]:
            if hop.startswith("./"):
                continue
            i = int(hop.split("/a")[1].split("/")[0].split("@")[0])
            assert hop == label(i, nodes[i])
    # The direct-policy verdict only looks at repo-owned files.
    direct = [j for j in roots + local_action]
    assert res.direct_policy_pass == all(nodes[j]["ref"] == "sha" for j in direct)


@settings(max_examples=50, deadline=None)
@given(st.integers(2, 40))
def test_long_cycle_terminates_and_expands_each_unit_once(n):
    files = {}
    for i in range(n):
        nxt = (i + 1) % n
        files[(f"org/a{i}", "v1", "action.yml")] = (
            f"runs:\n  using: composite\n  steps:\n    - uses: org/a{nxt}@v1\n")
    local = {".github/workflows/ci.yml": "jobs:\n  b:\n    steps:\n      - uses: org/a0@v1\n"}
    f = DictFetcher(files)
    res = resolve(LocalRepo(local), f)
    assert len([u for u in res.units if u.origin == "remote"]) == n
    assert max(res.dist.values()) == n
    assert len(res.findings) == n + 1  # n intra-cycle links + the direct one
