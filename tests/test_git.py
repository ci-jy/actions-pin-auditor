"""Git-backed features against throwaway local repositories (no network)."""
import subprocess

import pytest

from actpin import gitops
from actpin.tags import diff_snapshots, take_snapshot


def sh(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture()
def upstream(tmp_path):
    d = tmp_path / "up"
    d.mkdir()
    sh("init", "-q", "-b", "main", cwd=d)
    sh("config", "user.email", "t@example.com", cwd=d)
    sh("config", "user.name", "t", cwd=d)
    sh("config", "uploadpack.allowFilter", "true", cwd=d)
    sh("config", "uploadpack.allowAnySHA1InWant", "true", cwd=d)
    (d / ".github" / "workflows").mkdir(parents=True)
    (d / ".github" / "workflows" / "ci.yml").write_text("jobs:\n  a:\n    steps:\n      - uses: o/r@v1\n")
    (d / "sub").mkdir()
    (d / "sub" / "action.yml").write_text("runs:\n  using: node20\n  main: x.js\n")
    (d / "big.bin").write_text("x" * 10000)
    sh("add", "-A", cwd=d)
    sh("commit", "-qm", "one", cwd=d)
    sh("tag", "v1", cwd=d)
    sh("tag", "-a", "v1.0.0", "-m", "annotated", cwd=d)
    good = sh("rev-parse", "HEAD", cwd=d)
    (d / "f").write_text("2")
    sh("add", "-A", cwd=d)
    sh("commit", "-qm", "two", cwd=d)
    mid = sh("rev-parse", "HEAD", cwd=d)
    (d / "f").write_text("3")
    sh("add", "-A", cwd=d)
    sh("commit", "-qm", "three", cwd=d)
    # A commit that is in the object store but on no branch or tag: what a
    # fork commit looks like when fetched through the parent repository.
    sh("checkout", "-q", "--detach", cwd=d)
    (d / "evil").write_text("curl | sh")
    sh("add", "-A", cwd=d)
    sh("commit", "-qm", "evil", cwd=d)
    evil = sh("rev-parse", "HEAD", cwd=d)
    sh("checkout", "-q", "main", cwd=d)
    return d, good, mid, evil


def test_ls_remote_peels_annotated_tags(upstream):
    d, good, _, _ = upstream
    tags = gitops.tag_map(str(d))
    assert tags["v1"] == good and tags["v1.0.0"] == good


def test_reachability_and_impostor(upstream, tmp_path):
    d, good, mid, evil = upstream
    c = gitops.ReachabilityChecker(tmp_path / "reach")
    assert c.is_reachable(str(d), good)       # tag tip
    assert c.is_reachable(str(d), mid)        # inside branch history, not a tip
    assert not c.is_reachable(str(d), evil)   # impostor
    assert not c.is_reachable(str(d), "f" * 40)


def test_sparse_blobless_fetch(upstream, tmp_path):
    d, *_ = upstream
    files = gitops.fetch_repo_files(f"file://{d}", tmp_path / "clone")
    assert set(files) == {".github/workflows/ci.yml", "sub/action.yml"}
    assert not (tmp_path / "clone" / "big.bin").exists()


def test_snapshot_and_tag_move(upstream):
    d, good, mid, _ = upstream
    before = take_snapshot([str(d)])
    sh("tag", "-f", "v1", mid, cwd=d)
    after = take_snapshot([str(d)])
    moved = diff_snapshots(before, after)["moved"]
    assert [(m["tag"], m["old"], m["new"]) for m in moved] == [("v1", good, mid)]
