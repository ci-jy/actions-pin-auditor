"""Replay a recorded tag-mutation incident against recorded victim repositories."""
from __future__ import annotations

import json
from pathlib import Path

from .fetch import DirFetcher
from .graph import LocalRepo, resolve
from .scan import read_local_files
from .tags import diff_snapshots, load_snapshot


def replay(fixture: str | Path, live_reachability: bool = False) -> dict:
    fx = Path(fixture)
    incident = json.loads((fx / "incident.json").read_text())
    diff = diff_snapshots(load_snapshot(fx / "tags-before.json"), load_snapshot(fx / "tags-after.json"))
    moved = {(m["repo"].lower(), m["tag"]): m for m in diff["moved"]}

    # Impostor check on every commit a tag was moved to.
    targets = sorted({(m["repo"], m["new"]) for m in diff["moved"]})
    if live_reachability:
        from .gitops import ReachabilityChecker
        import tempfile
        checker = ReachabilityChecker(tempfile.mkdtemp(prefix="reach-"))
        reach = {f"{r}@{s}": checker.is_reachable(r, s) for r, s in targets}
    else:
        rec = json.loads((fx / "reachability.json").read_text())["repos"]
        reach = {f"{r}@{s}": rec.get(r, {}).get(s) for r, s in targets}
    impostors = [k for k, v in reach.items() if v is False]

    fetcher = DirFetcher(fx / "repos")
    victims = {}
    for vdir in sorted(p for p in (fx / "victims").iterdir() if p.is_dir()):
        res = resolve(LocalRepo(read_local_files(vdir)), fetcher)
        exposures = []
        for f in res.findings:
            r = f.use.ref
            m = moved.get((r.slug.lower(), r.ref))
            if m:
                exposures.append({"repo": m["repo"], "tag": m["tag"], "old": m["old"], "new": m["new"],
                                  "impostor": f"{m['repo']}@{m['new']}" in impostors,
                                  "depth": f.depth, "path": list(f.path), "root": f.root.path,
                                  "root_line": f.root_line})
        victims[vdir.name] = {"direct_policy_pass": res.direct_policy_pass,
                              "exposures": exposures,
                              "unpinned_links": len(res.findings)}

    checks = []
    for c in incident["compromised"]:
        hit = [m for m in diff["moved"] if m["repo"] == c["repo"] and m["new"] == c["malicious_sha"]]
        checks.append({"check": f"tag move to malicious commit detected: {c['repo']}",
                       "ok": any(m["tag"] == c["tag"] for m in hit), "detail": f"{len(hit)} tags moved"})
        checks.append({"check": f"malicious commit flagged as impostor: {c['repo']}@{c['malicious_sha'][:12]}",
                       "ok": f"{c['repo']}@{c['malicious_sha']}" in impostors, "detail": ""})
    for e in incident["expected_exposures"]:
        v = victims.get(e["victim"], {"exposures": [], "direct_policy_pass": None})
        hits = [x for x in v["exposures"] if x["repo"] == e["repo"] and x["depth"] >= e["min_depth"]]
        ok = bool(hits) and ("direct_policy_pass" not in e or v["direct_policy_pass"] == e["direct_policy_pass"])
        checks.append({"check": f"{e['victim']} exposed to {e['repo']} (depth >= {e['min_depth']})",
                       "ok": ok, "detail": " -> ".join(hits[0]["path"]) if hits else "no path"})
    return {"incident": incident["name"], "moved_tags": len(diff["moved"]),
            "moved_by_repo": {r: sum(1 for m in diff["moved"] if m["repo"] == r)
                              for r in sorted({m["repo"] for m in diff["moved"]})},
            "impostors": impostors, "victims": victims, "checks": checks,
            "detected": all(c["ok"] for c in checks)}
