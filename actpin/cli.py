"""Command-line interface: scan, snapshot, diff-tags, fix, replay."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from . import __version__, gitops
from .fetch import RawFetcher
from .fix import ls_remote_resolver, pin_text, unified_patch
from .graph import LocalRepo, resolve
from .replay import replay
from .sarif import to_sarif
from .scan import find_impostors, read_local_files, read_repo_list, scan_many, summarize_resolution
from .tags import diff_snapshots, load_snapshot, take_snapshot


def default_cache() -> Path:
    base = os.environ.get("ACTPIN_CACHE") or os.path.join(
        os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "actpin")
    return Path(base)


def cmd_scan(a) -> int:
    fetcher = RawFetcher(default_cache() / "raw")
    checker = gitops.ReachabilityChecker(default_cache() / "reach") if a.check_impostors else None
    if a.repos:
        slugs = read_repo_list(a.repos)[: a.limit or None]
        s = scan_many(slugs, fetcher, a.out, workers=a.workers, checker=checker)
        print(json.dumps({k: v for k, v in s.items() if not isinstance(v, list)}, indent=2))
        print(f"wrote {Path(a.out) / 'summary.json'}")
        return 0
    res = resolve(LocalRepo(read_local_files(a.path)), fetcher)
    imps = find_impostors(res, checker)[0] if checker else []
    rec = summarize_resolution(res)
    for f in res.findings:
        tag = "TRANSITIVE" if f.transitive else "direct"
        print(f"[{tag}] {f.use.ref.raw} ({f.use.ref.state})\n    " + " -> ".join(f.path))
    for i in imps:
        print(f"[IMPOSTOR] {i['uses']}: commit not on any branch or tag of {i['repo']}")
    print(f"\n{rec['workflows']} workflows, {rec['direct_refs']} direct refs "
          f"({rec['direct_unpinned']} unpinned), {rec['remote_units']} remote actions resolved, "
          f"{rec['transitive_unpinned']} unpinned transitive links, impostors: {len(imps)}; "
          f"direct SHA-pin policy: {'PASS' if res.direct_policy_pass else 'FAIL'}")
    if a.sarif:
        Path(a.sarif).write_text(json.dumps(to_sarif(res, impostors=imps), indent=1))
        print(f"wrote {a.sarif}")
    if a.json:
        Path(a.json).write_text(json.dumps(rec, indent=1))
    fail = {"none": False, "transitive": bool(res.transitive_findings) or bool(imps),
            "any": bool(res.findings) or bool(imps)}[a.fail_on]
    return 1 if fail else 0


def cmd_snapshot(a) -> int:
    slugs = list(a.repo or [])
    if a.repos:
        slugs += read_repo_list(a.repos)
    if a.from_scan:
        scan = json.loads(Path(a.from_scan).read_text())
        for rec in scan:
            for f in rec.get("findings", []):
                for hop in f["path"][1:]:
                    if "@" in hop and not hop.startswith(("./", "docker://")):
                        slugs.append("/".join(hop.split("@")[0].split("/")[:2]))
    snap = take_snapshot(sorted(set(slugs)))
    Path(a.out).write_text(json.dumps(snap, indent=1))
    print(f"snapshot of {len(snap['repos'])} repos ({len(snap['errors'])} errors) -> {a.out}")
    return 0


def cmd_diff(a) -> int:
    d = diff_snapshots(load_snapshot(a.old), load_snapshot(a.new))
    for m in d["moved"]:
        print(f"MOVED   {m['repo']}@{m['tag']}: {m['old'][:12]} -> {m['new'][:12]}")
    if a.verbose:
        for m in d["added"]:
            print(f"added   {m['repo']}@{m['tag']}")
        for m in d["deleted"]:
            print(f"deleted {m['repo']}@{m['tag']}")
    print(f"{len(d['moved'])} moved, {len(d['added'])} added, {len(d['deleted'])} deleted "
          f"across {d['repos_compared']} repos")
    if a.json:
        Path(a.json).write_text(json.dumps(d, indent=1))
    return 1 if d["moved"] else 0


def cmd_fix(a) -> int:
    root = Path(a.path)
    resolver = ls_remote_resolver()
    patches, total = [], 0
    for rel, text in sorted(read_local_files(root).items()):
        new, changes = pin_text(text, resolver)
        total += sum(c["status"] == "pinned" for c in changes)
        for c in changes:
            if c["status"] != "pinned":
                print(f"{rel}:{c['line']}: could not resolve {c['uses']}", file=sys.stderr)
        patches.append(unified_patch(rel, text, new))
        if a.write and new != text:
            (root / rel).write_text(new)
    patch = "".join(patches)
    if a.out:
        Path(a.out).write_text(patch)
        print(f"{total} references pinned; patch -> {a.out}", file=sys.stderr)
    else:
        sys.stdout.write(patch)
    return 0


def cmd_replay(a) -> int:
    r = replay(a.fixture, live_reachability=a.live)
    print(f"Replay: {r['incident']}")
    print(f"  moved tags: {r['moved_tags']} {r['moved_by_repo']}")
    print(f"  impostor commits: {', '.join(r['impostors']) or 'none'}")
    for name, v in r["victims"].items():
        print(f"  victim {name}: direct SHA-pin policy {'PASS' if v['direct_policy_pass'] else 'FAIL'}, "
              f"{len(v['exposures'])} exposure(s)")
        for e in v["exposures"]:
            print(f"    depth {e['depth']}: " + " -> ".join(e["path"]))
    for c in r["checks"]:
        print(f"  [{'ok' if c['ok'] else 'MISSED'}] {c['check']}" + (f"  ({c['detail']})" if c["detail"] else ""))
    print("DETECTED" if r["detected"] else "NOT DETECTED")
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1))
    return 0 if (r["detected"] or not a.expect_detected) else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="actpin", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan a checkout, or a list of public repos with --repos")
    s.add_argument("path", nargs="?", default=".")
    s.add_argument("--repos", help="file with one owner/repo per line")
    s.add_argument("--limit", type=int, default=0)
    s.add_argument("--out", default="results/")
    s.add_argument("--workers", type=int, default=6)
    s.add_argument("--check-impostors", action="store_true",
                   help="verify every SHA pin is reachable from upstream branches/tags")
    s.add_argument("--sarif")
    s.add_argument("--json")
    s.add_argument("--fail-on", choices=["none", "transitive", "any"], default="none")
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("snapshot", help="record tag -> SHA mappings")
    s.add_argument("--repo", action="append", help="owner/repo (repeatable)")
    s.add_argument("--repos", help="file with one owner/repo per line")
    s.add_argument("--from-scan", help="snapshot every action repo seen in results/scan.json")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_snapshot)

    s = sub.add_parser("diff-tags", help="flag tags whose target changed between snapshots")
    s.add_argument("old")
    s.add_argument("new")
    s.add_argument("--json")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_diff)

    s = sub.add_parser("fix", help="emit a patch pinning mutable refs to SHAs (keeps version comment)")
    s.add_argument("path", nargs="?", default=".")
    s.add_argument("--out")
    s.add_argument("--write", action="store_true", help="rewrite files in place")
    s.set_defaults(fn=cmd_fix)

    s = sub.add_parser("replay", help="replay a recorded incident fixture")
    s.add_argument("fixture")
    s.add_argument("--expect-detected", action="store_true")
    s.add_argument("--live", action="store_true", help="re-check reachability over the network")
    s.add_argument("--json")
    s.set_defaults(fn=cmd_replay)

    a = p.parse_args(argv)
    return a.fn(a)
