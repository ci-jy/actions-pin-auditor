"""Rewrite mutable `uses:` references to full SHAs, keeping the version as a
trailing comment (the convention Dependabot and Renovate understand)."""
from __future__ import annotations

import difflib
import re
from typing import Callable

from .refs import UNPINNED_STATES, parse_uses

USES_LINE = re.compile(
    r"^(?P<lead>\s*(?:-\s+)?uses:\s*)(?P<q>['\"]?)(?P<val>[^\s'\"#]+)(?P=q)(?P<rest>\s*(?:#.*)?)$")

Resolver = Callable[[str, str], "str | None"]  # (owner/repo, ref) -> sha


def pin_text(text: str, resolve: Resolver) -> tuple[str, list[dict]]:
    """Return the rewritten text and a list of the changes made / skipped."""
    out, changes = [], []
    for lineno, line in enumerate(text.splitlines(keepends=True), 1):
        body = line.rstrip("\r\n")
        nl = line[len(body):]
        m = USES_LINE.match(body)
        u = parse_uses(m.group("val")) if m else None
        if not u or u.kind not in ("action", "reusable") or u.state not in UNPINNED_STATES:
            out.append(line)
            continue
        sha = resolve(u.slug, u.ref)
        if not sha:
            changes.append({"line": lineno, "uses": u.raw, "status": "unresolved"})
            out.append(line)
            continue
        target = u.raw[: -len(u.ref)] + sha
        rest = m.group("rest")
        # Keep an existing comment; otherwise record the ref that was pinned.
        comment = rest if rest.strip().startswith("#") else f" # {u.ref}"
        out.append(f"{m.group('lead')}{m.group('q')}{target}{m.group('q')}{comment}{nl}")
        changes.append({"line": lineno, "uses": u.raw, "sha": sha, "status": "pinned"})
    return "".join(out), changes


def unified_patch(path: str, before: str, after: str) -> str:
    if before == after:
        return ""
    return "".join(difflib.unified_diff(before.splitlines(keepends=True),
                                        after.splitlines(keepends=True),
                                        fromfile=f"a/{path}", tofile=f"b/{path}"))


def ls_remote_resolver() -> Resolver:
    from . import gitops
    cache: dict[str, dict[str, str]] = {}

    def resolve(slug: str, ref: str) -> str | None:
        if slug not in cache:
            try:
                cache[slug] = gitops.ls_remote(slug)
            except gitops.GitError:
                cache[slug] = {}
        return gitops.resolve_ref(slug, ref, cache[slug])

    return resolve
