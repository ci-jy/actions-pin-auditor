"""Scan local checkouts or lists of public repositories."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import gitops
from .fetch import Fetcher
from .graph import LocalRepo, Resolution, resolve
from .refs import PINNED, FULL_SHA
from .sarif import to_sarif


def read_local_files(root: str | os.PathLike) -> dict[str, str]:
    root = Path(root)
    files = {}
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if rel.parts[:1] == (".git",) or not p.is_file() or p.suffix not in (".yml", ".yaml"):
            continue
        if rel.parts[:1] == (".github",) or p.name in ("action.yml", "action.yaml"):
            files[rel.as_posix()] = p.read_text(errors="replace")
    return files


def find_impostors(res: Resolution, checker: gitops.ReachabilityChecker,
                   max_checks: int = 200) -> tuple[list[dict], int]:
    """Check every full-SHA pin in the graph against upstream branches/tags."""
    seen, out, checked = set(), [], 0
    for unit, use, _child in res.edges:
        r = use.ref
        if r.kind not in ("action", "reusable") or r.state != PINNED or not FULL_SHA.match(r.ref):
            continue
        key = (r.slug.lower(), r.ref)
        if key in seen or checked >= max_checks:
            continue
        seen.add(key)
        checked += 1
        try:
            ok = checker.is_reachable(r.slug, r.ref)
        except gitops.GitError:
            continue
        if not ok:
            out.append({"repo": r.slug, "sha": r.ref, "uses": r.raw, "in": unit.label()})
    return out, checked


def summarize_resolution(res: Resolution) -> dict:
    direct = res.direct_uses
    return {
        "workflows": len(res.roots),
        "direct_refs": len(direct),
        "direct_unpinned": sum(1 for _, x in direct if x.ref.unpinned),
        "direct_policy_pass": res.direct_policy_pass,
        "remote_units": sum(1 for u in res.units if u.origin == "remote"),
        "missing_units": [u.label() for u in res.missing],
        "max_depth": max(res.dist.values(), default=0),
        "transitive_unpinned": len(res.transitive_findings),
        "findings": [f.to_dict() for f in res.findings],
    }


def scan_repo(slug: str, fetcher: Fetcher, workdir: str | os.PathLike,
              checker: gitops.ReachabilityChecker | None = None) -> dict:
    t0 = time.time()
    rec: dict = {"repo": slug}
    d = Path(tempfile.mkdtemp(prefix="clone-", dir=workdir))
    try:
        files = gitops.fetch_repo_files(slug, d / "r")
        rec["commit"] = gitops.head_sha(d / "r")
    except gitops.GitError as e:
        rec.update(status="error", error=str(e))
        return rec
    finally:
        shutil.rmtree(d, ignore_errors=True)
    local = LocalRepo(files)
    if not local.workflows():
        rec.update(status="no-workflows")
        return rec
    res = resolve(local, fetcher)
    rec.update(status="ok", **summarize_resolution(res))
    if checker is not None:
        imps, n = find_impostors(res, checker)
        rec["impostor_checks"] = n
        rec["impostors"] = imps
    rec["sarif"] = to_sarif(res, impostors=rec.get("impostors"))
    rec["seconds"] = round(time.time() - t0, 2)
    return rec


def read_repo_list(path: str | os.PathLike) -> list[str]:
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line and line not in out:
            out.append(line)
    return out


def scan_many(slugs: list[str], fetcher: Fetcher, out_dir: str | os.PathLike,
              workers: int = 6, checker: gitops.ReachabilityChecker | None = None,
              log=lambda m: print(m, file=sys.stderr)) -> dict:
    out = Path(out_dir)
    (out / "sarif").mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="scan-"))
    records: dict[str, dict] = {}
    try:
        with ThreadPoolExecutor(workers) as ex:
            futs = {ex.submit(scan_repo, s, fetcher, work, checker): s for s in slugs}
            for i, fut in enumerate(as_completed(futs), 1):
                s = futs[fut]
                try:
                    rec = fut.result()
                except Exception as e:  # keep going; record the failure
                    rec = {"repo": s, "status": "error", "error": repr(e)}
                records[s] = rec
                log(f"[{i}/{len(slugs)}] {s}: {rec['status']}"
                    + (f" direct_pass={rec['direct_policy_pass']} transitive_unpinned="
                       f"{rec['transitive_unpinned']}" if rec["status"] == "ok" else ""))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    ordered = [records[s] for s in slugs]
    for rec in ordered:
        sarif = rec.pop("sarif", None)
        if sarif is not None:
            (out / "sarif" / f"{rec['repo'].replace('/', '__')}.sarif").write_text(
                json.dumps(sarif, indent=1))
    summary = build_summary(ordered)
    (out / "scan.json").write_text(json.dumps(ordered, indent=1))
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def build_summary(records: list[dict]) -> dict:
    ok = [r for r in records if r["status"] == "ok"]
    passing = [r for r in ok if r["direct_policy_pass"]]
    exposed = [r for r in passing if r["transitive_unpinned"] > 0]
    culprits: Counter = Counter()
    for r in ok:
        for f in {(f["in"].rsplit("@", 1)[0], f["uses"]) for f in r["findings"] if f["transitive"]}:
            culprits[f"{f[0]} -> {f[1]}"] += 1
    return {
        "repos_requested": len(records),
        "repos_scanned": len(ok) + sum(1 for r in records if r["status"] == "no-workflows"),
        "repos_with_workflows": len(ok),
        "repos_failed": sum(1 for r in records if r["status"] == "error"),
        "direct_policy_pass": len(passing),
        "direct_policy_fail": len(ok) - len(passing),
        "direct_pass_but_transitive_unpinned": len(exposed),
        "direct_pass_but_transitive_unpinned_repos": [r["repo"] for r in exposed],
        "github_policy_flags_in_those_repos": sum(r["direct_unpinned"] for r in exposed),
        "repos_with_any_transitive_unpinned": sum(1 for r in ok if r["transitive_unpinned"] > 0),
        "total_direct_refs": sum(r["direct_refs"] for r in ok),
        "total_direct_unpinned": sum(r["direct_unpinned"] for r in ok),
        "total_transitive_unpinned_links": sum(r["transitive_unpinned"] for r in ok),
        "total_remote_units_resolved": sum(r["remote_units"] for r in ok),
        "max_depth": max((r["max_depth"] for r in ok), default=0),
        "impostor_commits": sum(len(r.get("impostors", [])) for r in ok),
        "impostor_checks": sum(r.get("impostor_checks", 0) for r in ok),
        "top_transitive_unpinned": [{"link": k, "repos": v} for k, v in culprits.most_common(15)],
    }
