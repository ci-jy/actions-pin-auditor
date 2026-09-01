"""Tag -> SHA snapshots and mutation detection."""
from __future__ import annotations

import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import gitops


def take_snapshot(slugs: list[str], workers: int = 8, ls=gitops.tag_map) -> dict:
    repos: dict[str, dict[str, str]] = {}
    errors: dict[str, str] = {}

    def one(slug):
        try:
            return slug, ls(slug), None
        except gitops.GitError as e:
            return slug, None, str(e)

    with ThreadPoolExecutor(workers) as ex:
        for slug, tags, err in ex.map(one, sorted(set(slugs))):
            if tags is None:
                errors[slug] = err
            else:
                repos[slug] = dict(sorted(tags.items()))
    return {"taken_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "repos": repos, "errors": errors}


def load_snapshot(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text())
    return data if "repos" in data else {"repos": data}


def diff_snapshots(old: dict, new: dict) -> dict:
    """Compare two snapshots. A *moved* tag kept its name but now points at a
    different commit: the signature of the tj-actions and reviewdog attacks."""
    moved, added, deleted = [], [], []
    o, n = old["repos"], new["repos"]
    for slug in sorted(set(o) & set(n)):
        ot, nt = o[slug], n[slug]
        for tag in sorted(set(ot) | set(nt)):
            if tag in ot and tag in nt and ot[tag] != nt[tag]:
                moved.append({"repo": slug, "tag": tag, "old": ot[tag], "new": nt[tag]})
            elif tag in nt and tag not in ot:
                added.append({"repo": slug, "tag": tag, "new": nt[tag]})
            elif tag in ot and tag not in nt:
                deleted.append({"repo": slug, "tag": tag, "old": ot[tag]})
    return {"moved": moved, "added": added, "deleted": deleted,
            "repos_compared": len(set(o) & set(n))}
