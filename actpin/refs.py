"""Parsing and classification of `uses:` references."""
from __future__ import annotations

import re
from dataclasses import dataclass

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHORT_SHA = re.compile(r"^[0-9a-f]{7,39}$")
VERSIONISH = re.compile(r"^v?\d+(\.\d+)*([-.+].*)?$")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")

# Pin states
PINNED = "pinned"          # full 40-char commit SHA or image digest
MUTABLE_TAG = "tag"        # looks like a version tag (v4, v1.2.3)
MUTABLE_BRANCH = "branch"  # anything else (main, master, release/x)
SHORT = "short-sha"        # abbreviated SHA: rejected by GitHub's policy, ambiguous
DOCKER_TAG = "docker-tag"  # docker://image:tag without digest
LOCAL = "local"            # ./path inside the same repository

UNPINNED_STATES = {MUTABLE_TAG, MUTABLE_BRANCH, SHORT, DOCKER_TAG}


@dataclass(frozen=True)
class UsesRef:
    """One `uses:` (or docker `image:`) value."""

    raw: str
    kind: str            # "action", "reusable", "docker", "local"
    owner: str = ""
    repo: str = ""
    path: str = ""       # sub-path inside the repository ('' for root)
    ref: str = ""        # git ref or docker tag/digest

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}" if self.owner else ""

    @property
    def state(self) -> str:
        return pin_state(self)

    @property
    def unpinned(self) -> bool:
        return self.state in UNPINNED_STATES

    def __str__(self) -> str:
        return self.raw


def parse_uses(value: str) -> UsesRef | None:
    """Parse a `uses:` string. Returns None for values that are not references
    (expressions, empty strings)."""
    v = str(value).strip()
    if not v or "${{" in v:
        return None
    if v.startswith("docker://"):
        return UsesRef(raw=v, kind="docker", ref=v[len("docker://"):])
    if v.startswith("./") or v.startswith("../"):
        return UsesRef(raw=v, kind="local", path=v[2:].strip("/") if v.startswith("./") else v)
    if "@" not in v:
        return None
    target, ref = v.rsplit("@", 1)
    parts = target.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    owner, repo, sub = parts[0], parts[1], "/".join(parts[2:])
    kind = "reusable" if re.search(r"(^|/)\.github/workflows/[^/]+\.ya?ml$", sub) else "action"
    return UsesRef(raw=v, kind=kind, owner=owner, repo=repo, path=sub, ref=ref)


def parse_image(value: str) -> UsesRef | None:
    """Parse the `runs.image` of a Docker action."""
    v = str(value).strip()
    if v.startswith("docker://"):
        return UsesRef(raw=v, kind="docker", ref=v[len("docker://"):])
    return None  # Dockerfile builds from the (already-resolved) action repo


def pin_state(u: UsesRef) -> str:
    if u.kind == "local":
        return LOCAL
    if u.kind == "docker":
        return PINNED if DIGEST.search(u.ref) else DOCKER_TAG
    if FULL_SHA.match(u.ref):
        return PINNED
    if SHORT_SHA.match(u.ref):
        return SHORT
    if VERSIONISH.match(u.ref):
        return MUTABLE_TAG
    return MUTABLE_BRANCH
