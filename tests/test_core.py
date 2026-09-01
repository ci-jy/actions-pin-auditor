import json
import subprocess
import sys
from pathlib import Path

import pytest

from actpin.fetch import DictFetcher
from actpin.fix import pin_text, unified_patch
from actpin.graph import LocalRepo, extract_uses, resolve
from actpin.refs import parse_uses
from actpin.replay import replay
from actpin.sarif import to_sarif
from actpin.tags import diff_snapshots

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
SHA2 = "b" * 40


@pytest.mark.parametrize("value,kind,state", [
    (f"actions/checkout@{SHA}", "action", "pinned"),
    ("actions/checkout@v4", "action", "tag"),
    ("actions/checkout@v4.2.1", "action", "tag"),
    ("actions/checkout@main", "action", "branch"),
    ("actions/checkout@11bd719", "action", "short-sha"),
    ("github/codeql-action/upload-sarif@v3", "action", "tag"),
    ("org/repo/.github/workflows/build.yml@v1", "reusable", "tag"),
    (f"org/repo/.github/workflows/build.yml@{SHA}", "reusable", "pinned"),
    ("./.github/actions/setup", "local", "local"),
    ("docker://alpine:3.19", "docker", "docker-tag"),
    ("docker://alpine@sha256:" + "c" * 64, "docker", "pinned"),
])
def test_parse_and_classify(value, kind, state):
    u = parse_uses(value)
    assert u.kind == kind and u.state == state


def test_parse_rejects_non_refs():
    assert parse_uses("${{ matrix.action }}") is None
    assert parse_uses("checkout") is None


def test_subpath_action():
    u = parse_uses("github/codeql-action/upload-sarif@v3")
    assert (u.slug, u.path, u.ref) == ("github/codeql-action", "upload-sarif", "v3")


def test_extract_uses_lines_and_docker_image():
    text = "runs:\n  using: docker\n  image: 'docker://alpine:3'\n"
    assert [(x.ref.raw, x.line) for x in extract_uses(text, is_action=True)] == [("docker://alpine:3", 3)]
    wf = "jobs:\n  a:\n    uses: o/r/.github/workflows/x.yml@v1\n  b:\n    steps:\n      - uses: o/s@v2\n"
    assert [(x.ref.raw, x.line) for x in extract_uses(wf)] == [
        ("o/r/.github/workflows/x.yml@v1", 3), ("o/s@v2", 6)]
    assert extract_uses("{{ not yaml") == []


def _pinned_repo():
    local = {".github/workflows/ci.yml":
             f"jobs:\n  a:\n    steps:\n      - uses: org/composite@{SHA} # v1\n"
             f"  b:\n    uses: org/shared/.github/workflows/w.yml@{SHA2}\n"}
    files = {
        ("org/composite", SHA, "action.yml"):
            "runs:\n  using: composite\n  steps:\n    - uses: actions/setup-node@v4\n"
            f"    - uses: org/docker@{SHA}\n",
        ("org/docker", SHA, "action.yml"): "runs:\n  using: docker\n  image: docker://img:latest\n",
        ("org/shared", SHA2, ".github/workflows/w.yml"):
            "on: workflow_call\njobs:\n  x:\n    steps:\n      - uses: org/composite@main\n",
        ("org/composite", "main", "action.yml"): "runs:\n  using: node20\n  main: index.js\n",
    }
    return LocalRepo(local), DictFetcher(files)


def test_direct_pinned_repo_still_has_transitive_findings():
    local, fetcher = _pinned_repo()
    res = resolve(local, fetcher)
    assert res.direct_policy_pass
    got = {(f.use.ref.raw, f.depth) for f in res.transitive_findings}
    assert got == {("actions/setup-node@v4", 2), ("docker://img:latest", 3), ("org/composite@main", 2)}
    f = next(f for f in res.findings if f.use.ref.raw == "docker://img:latest")
    assert f.path == (".github/workflows/ci.yml", f"org/composite@{SHA}", f"org/docker@{SHA}",
                      "docker://img:latest")
    assert f.root_line == 4  # SARIF points at the first hop in the repo's own workflow
    assert ("actions/setup-node", "v4") in {(u.slug, u.ref) for u in res.missing}


def test_local_composite_counts_as_direct():
    local = LocalRepo({
        ".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - uses: ./.github/actions/x\n",
        ".github/actions/x/action.yml": "runs:\n  using: composite\n  steps:\n    - uses: o/r@v1\n",
    })
    res = resolve(local, DictFetcher({}))
    assert not res.direct_policy_pass
    assert [f.transitive for f in res.findings] == [False]


def test_sarif_shape():
    local, fetcher = _pinned_repo()
    s = to_sarif(resolve(local, fetcher),
                 impostors=[{"repo": "o/r", "sha": SHA, "uses": f"o/r@{SHA}", "path": []}])
    assert s["version"] == "2.1.0"
    run = s["runs"][0]
    rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert {r["ruleId"] for r in run["results"]} == {"APN002", "APN003"}
    for r in run["results"]:
        assert r["ruleId"] in rule_ids
        loc = r["locations"][0]["physicalLocation"]
        assert loc["region"]["startLine"] >= 1 and loc["artifactLocation"]["uri"]


def test_fix_keeps_comments_and_quotes():
    text = ("steps:\n"
            "  - uses: actions/checkout@v4\n"
            "  - uses: 'actions/setup-node@v4.1.0'   # keep me\n"
            f"  - uses: actions/cache@{SHA} # v4.2.0\n"
            "  - uses: ./local\n"
            "  - uses: unknown/thing@v9\n")
    shas = {("actions/checkout", "v4"): SHA, ("actions/setup-node", "v4.1.0"): SHA2}
    new, changes = pin_text(text, lambda s, r: shas.get((s, r)))
    assert f"  - uses: actions/checkout@{SHA} # v4\n" in new
    assert f"  - uses: 'actions/setup-node@{SHA2}'   # keep me\n" in new
    assert f"  - uses: actions/cache@{SHA} # v4.2.0\n" in new
    assert "  - uses: unknown/thing@v9\n" in new
    assert [c["status"] for c in changes] == ["pinned", "pinned", "unresolved"]
    patch = unified_patch(".github/workflows/ci.yml", text, new)
    assert patch.startswith("--- a/.github/workflows/ci.yml")
    assert unified_patch("x", text, text) == ""


def test_diff_snapshots():
    old = {"repos": {"o/r": {"v1": SHA, "v2": SHA, "gone": SHA}, "o/only-old": {"v1": SHA}}}
    new = {"repos": {"o/r": {"v1": SHA2, "v2": SHA, "v3": SHA}}}
    d = diff_snapshots(old, new)
    assert d["moved"] == [{"repo": "o/r", "tag": "v1", "old": SHA, "new": SHA2}]
    assert [a["tag"] for a in d["added"]] == ["v3"]
    assert [a["tag"] for a in d["deleted"]] == ["gone"]


def test_replay_detects_tj_actions_chain():
    r = replay(ROOT / "fixtures" / "tj-actions-2025")
    assert r["detected"], [c for c in r["checks"] if not c["ok"]]
    pinned = r["victims"]["fully-pinned-user"]
    assert pinned["direct_policy_pass"]
    paths = [e["path"] for e in pinned["exposures"]]
    assert any(p[-1] == "reviewdog/action-setup@v1" and "eslint-changed-files" in p[1] for p in paths)
    assert all(e["impostor"] for v in r["victims"].values() for e in v["exposures"])


def test_cli_replay_and_diff(tmp_path):
    run = lambda *a: subprocess.run([sys.executable, "-m", "actpin", *a], cwd=ROOT,
                                    capture_output=True, text=True)
    p = run("replay", "fixtures/tj-actions-2025", "--expect-detected")
    assert p.returncode == 0 and "DETECTED" in p.stdout
    fx = ROOT / "fixtures" / "tj-actions-2025"
    p = run("diff-tags", str(fx / "tags-before.json"), str(fx / "tags-after.json"),
            "--json", str(tmp_path / "d.json"))
    assert p.returncode == 1 and "MOVED   reviewdog/action-setup@v1" in p.stdout
    assert len(json.loads((tmp_path / "d.json").read_text())["moved"]) > 300


def test_check_summary_script(tmp_path):
    s = {"repos_requested": 3, "repos_scanned": 3, "repos_failed": 0, "direct_policy_pass": 2,
         "direct_pass_but_transitive_unpinned": 1, "direct_pass_but_transitive_unpinned_repos": ["a/b"],
         "github_policy_flags_in_those_repos": 0, "total_transitive_unpinned_links": 4}
    f = tmp_path / "s.json"
    f.write_text(json.dumps(s))
    cmd = [sys.executable, str(ROOT / "scripts" / "check_summary.py"), str(f)]
    assert subprocess.run(cmd + ["--min-repos", "3"], capture_output=True).returncode == 0
    assert subprocess.run(cmd + ["--min-repos", "4"], capture_output=True).returncode == 1
