"""Resolve the transitive closure of `uses:` references.

A *unit* is one YAML file that can contain references: a workflow, a
composite/Docker action.yml, or a reusable workflow. Units owned by the scanned
repository are *local*; units fetched from other repositories are *remote*.
Edges go from a unit to every reference it contains. The resolver walks the
graph breadth-first, so each unit is expanded once (cycles terminate) and the
path recorded for every finding is a shortest one.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import yaml

from .fetch import Fetcher
from .refs import UsesRef, parse_image, parse_uses


def is_workflow_path(path: str) -> bool:
    return path.endswith((".yml", ".yaml")) and ".github/workflows/" in f"/{path}"


@dataclass(frozen=True)
class Unit:
    origin: str   # "local" or "remote"
    slug: str     # owner/repo for remote, '' for local
    ref: str      # git ref for remote, '' for local
    path: str     # file path inside the repository

    def label(self) -> str:
        if self.origin == "local":
            return self.path
        sub = f"/{self.path}" if self.path else ""
        return f"{self.slug}{sub}@{self.ref}"

    @property
    def is_workflow(self) -> bool:
        return is_workflow_path(self.path)


@dataclass(frozen=True)
class Use:
    ref: UsesRef
    line: int     # 1-based line in the containing unit, 0 if unknown


@dataclass
class Finding:
    """An unpinned link: `use` appears inside `parent`, reached via `path`."""

    parent: Unit
    use: Use
    path: tuple[str, ...]          # labels: root unit ... parent, then the uses string
    root: Unit
    root_line: int                 # line of the first hop inside the root unit

    @property
    def depth(self) -> int:
        """1 = written in a repo-owned file; >1 = pulled in through a remote unit."""
        return len(self.path) - 1

    @property
    def transitive(self) -> bool:
        return self.parent.origin == "remote"

    def to_dict(self) -> dict:
        return {
            "uses": self.use.ref.raw,
            "state": self.use.ref.state,
            "in": self.parent.label(),
            "transitive": self.transitive,
            "path": list(self.path),
            "root": self.root.path,
            "root_line": self.root_line,
        }


@dataclass
class Resolution:
    roots: list[Unit]
    units: dict[Unit, list[Use]] = field(default_factory=dict)
    dist: dict[Unit, int] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    unresolved: list[tuple[Unit, Use]] = field(default_factory=list)
    missing: list[Unit] = field(default_factory=list)
    edges: list[tuple[Unit, Use, Unit | None]] = field(default_factory=list)

    @property
    def direct_uses(self) -> list[tuple[Unit, Use]]:
        return [(u, x) for u, uses in self.units.items() if u.origin == "local" for x in uses]

    @property
    def direct_policy_pass(self) -> bool:
        """GitHub's SHA-pin policy view: every reference written in the repo's
        own files is a full SHA (or local / digest-pinned)."""
        return not any(x.ref.unpinned for _, x in self.direct_uses)

    @property
    def transitive_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.transitive]

    @property
    def direct_findings(self) -> list[Finding]:
        return [f for f in self.findings if not f.transitive]


def extract_uses(text: str, is_action: bool = False) -> list[Use]:
    """All `uses:` values in a workflow / action YAML, with line numbers.
    For action.yml also the `runs.image` of Docker actions."""
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError:
        return []
    out: list[Use] = []

    def walk(n, parent_key=None):
        if isinstance(n, yaml.MappingNode):
            for k, v in n.value:
                key = k.value if isinstance(k, yaml.ScalarNode) else None
                if key == "uses" and isinstance(v, yaml.ScalarNode):
                    r = parse_uses(v.value)
                    if r:
                        out.append(Use(r, v.start_mark.line + 1))
                elif (key == "image" and parent_key == "runs" and is_action
                      and isinstance(v, yaml.ScalarNode)):
                    r = parse_image(v.value)
                    if r:
                        out.append(Use(r, v.start_mark.line + 1))
                else:
                    walk(v, key)
        elif isinstance(n, yaml.SequenceNode):
            for v in n.value:
                walk(v, parent_key)

    if node is not None:
        walk(node)
    return out


class LocalRepo:
    """Files of the scanned repository: {path: text}."""

    def __init__(self, files: dict[str, str]):
        self.files = files

    def workflows(self) -> list[str]:
        return sorted(p for p in self.files
                      if p.startswith(".github/workflows/") and p.count("/") == 2
                      and p.endswith((".yml", ".yaml")))

    def resolve_local(self, u: UsesRef) -> str | None:
        p = u.path.strip("/")
        if p.endswith((".yml", ".yaml")) and p in self.files and "/.github/workflows/" in f"/{p}":
            return p
        for name in ("action.yml", "action.yaml"):
            cand = f"{p}/{name}" if p else name
            if cand in self.files:
                return cand
        return None


def resolve(local: LocalRepo, fetcher: Fetcher, roots: list[str] | None = None,
            max_units: int = 5000) -> Resolution:
    root_units = [Unit("local", "", "", p) for p in (roots if roots is not None else local.workflows())]
    res = Resolution(roots=root_units)
    # Breadth-first: parent pointer gives a shortest path to every unit.
    prev: dict[Unit, tuple[Unit, Use] | None] = {}
    first_hop: dict[Unit, tuple[Unit, int]] = {}
    q: deque[Unit] = deque()
    for r in root_units:
        if r not in prev:
            prev[r] = None
            res.dist[r] = 0
            first_hop[r] = (r, 0)
            q.append(r)

    def path_to(u: Unit) -> list[str]:
        out = []
        cur: Unit | None = u
        while cur is not None:
            p = prev[cur]
            if p is None:
                out.append(cur.label())
                break
            out.append(p[1].ref.raw)
            cur = p[0]
        return out[::-1]

    while q:
        unit = q.popleft()
        if len(res.units) >= max_units:
            break
        text = _load(local, fetcher, unit)
        if text is None and unit.origin == "remote":
            res.missing.append(unit)
        is_action = not unit.is_workflow
        uses = extract_uses(text, is_action=is_action) if text is not None else []
        res.units[unit] = uses
        for use in uses:
            hop = first_hop[unit] if unit not in root_units else (unit, use.line)
            if use.ref.unpinned:
                res.findings.append(Finding(parent=unit, use=use,
                                            path=tuple(path_to(unit) + [use.ref.raw]),
                                            root=hop[0], root_line=hop[1]))
            child = _child(local, unit, use)
            res.edges.append((unit, use, child))
            if child is None:
                if use.ref.kind in ("action", "reusable") or (
                        use.ref.kind == "local" and unit.origin == "local"):
                    res.unresolved.append((unit, use))
                continue
            if child not in prev:
                prev[child] = (unit, use)
                res.dist[child] = res.dist[unit] + 1
                first_hop[child] = hop
                q.append(child)
    return res


def _child(local: LocalRepo, unit: Unit, use: Use) -> Unit | None:
    r = use.ref
    if r.kind == "local":
        if unit.origin != "local":
            # `./x` inside a remote action points at the caller's workspace, not the
            # action repository; it cannot be resolved statically.
            return None
        p = local.resolve_local(r)
        return Unit("local", "", "", p) if p else None
    if r.kind in ("action", "reusable"):
        return Unit("remote", r.slug, r.ref, r.path)  # path resolved lazily on load
    return None


def _load(local: LocalRepo, fetcher: Fetcher, unit: Unit) -> str | None:
    if unit.origin == "local":
        return local.files.get(unit.path)
    kind = "reusable" if unit.is_workflow else "action"
    owner, repo = unit.slug.split("/", 1)
    got = fetcher.load(UsesRef(raw="", kind=kind, owner=owner, repo=repo, path=unit.path, ref=unit.ref))
    return got[1] if got else None
