"""Thin wrappers around the git CLI: ls-remote, sparse blobless clones and
reachability checks. Works against any git URL, so tests use local repos."""
from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true"}


class GitError(RuntimeError):
    pass


def repo_url(slug_or_url: str) -> str:
    if "://" in slug_or_url or slug_or_url.startswith(("/", ".", "file:")):
        return slug_or_url
    return f"https://github.com/{slug_or_url}.git"


def git(*args: str, cwd: str | os.PathLike | None = None, timeout: float = 180,
        lazy_fetch: bool = True) -> str:
    env = GIT_ENV if lazy_fetch else {**GIT_ENV, "GIT_NO_LAZY_FETCH": "1"}
    try:
        p = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise GitError(f"git {args[0]} timed out") from e
    if p.returncode != 0:
        raise GitError(f"git {' '.join(args[:2])}: {p.stderr.strip()[:300]}")
    return p.stdout


def ls_remote(slug_or_url: str, timeout: float = 60) -> dict[str, str]:
    """Return {'refs/tags/v1': sha, 'refs/heads/main': sha}. Annotated tags are
    peeled to the commit they point at."""
    out = git("ls-remote", "--tags", "--heads", repo_url(slug_or_url), timeout=timeout)
    refs: dict[str, str] = {}
    peeled: dict[str, str] = {}
    for line in out.splitlines():
        sha, _, name = line.partition("\t")
        if name.endswith("^{}"):
            peeled[name[:-3]] = sha
        else:
            refs[name] = sha
    refs.update(peeled)
    return refs


def tag_map(slug_or_url: str) -> dict[str, str]:
    return {k[len("refs/tags/"):]: v for k, v in ls_remote(slug_or_url).items()
            if k.startswith("refs/tags/")}


def resolve_ref(slug_or_url: str, ref: str, refs: dict[str, str] | None = None) -> str | None:
    refs = refs if refs is not None else ls_remote(slug_or_url)
    return refs.get(f"refs/tags/{ref}") or refs.get(f"refs/heads/{ref}")


SPARSE_PATTERNS = ["/.github/", "action.yml", "action.yaml"]


def fetch_repo_files(slug_or_url: str, dest: str | os.PathLike, timeout: float = 240) -> dict[str, str]:
    """Shallow, blobless, sparse clone that downloads only workflow and action
    metadata files. Returns {path: text}."""
    dest = Path(dest)
    git("clone", "--quiet", "--depth", "1", "--filter=blob:none", "--no-checkout",
        repo_url(slug_or_url), str(dest), timeout=timeout)
    git("sparse-checkout", "set", "--no-cone", *SPARSE_PATTERNS, cwd=dest, timeout=timeout)
    git("checkout", "--quiet", cwd=dest, timeout=timeout)
    files: dict[str, str] = {}
    for p in dest.rglob("*"):
        if ".git" in p.relative_to(dest).parts[:1] or not p.is_file():
            continue
        rel = p.relative_to(dest).as_posix()
        if rel.startswith(".github/") or p.name in ("action.yml", "action.yaml"):
            if p.suffix in (".yml", ".yaml"):
                try:
                    files[rel] = p.read_text(errors="replace")
                except OSError:
                    pass
    return files


def head_sha(path: str | os.PathLike) -> str:
    return git("rev-parse", "HEAD", cwd=path).strip()


class ReachabilityChecker:
    """Decides whether a commit is reachable from any branch or tag of a
    repository. GitHub serves commits from forks through the parent repository
    (a shared object network), so `owner/repo@<sha>` can run code that never
    landed in owner/repo: an *impostor commit*.

    Strategy: a ref tip match from ls-remote settles most pins cheaply; otherwise
    take a commits-only (`--filter=tree:0`) bare clone of all branches and tags
    and ask git whether any ref contains the commit."""

    def __init__(self, workdir: str | os.PathLike):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self._refs: dict[str, dict[str, str]] = {}
        self._clones: dict[str, Path] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def refs(self, slug: str) -> dict[str, str]:
        if slug not in self._refs:
            self._refs[slug] = ls_remote(slug)
        return self._refs[slug]

    def _clone(self, slug: str) -> Path:
        if slug not in self._clones:
            d = self.workdir / slug.replace("/", "__").replace(":", "_")
            if not (d / "HEAD").exists():
                git("clone", "--quiet", "--bare", "--filter=tree:0", repo_url(slug), str(d),
                    timeout=600)
                git("fetch", "--quiet", "--filter=tree:0", "origin",
                    "+refs/tags/*:refs/tags/*", cwd=d, timeout=600)
            self._clones[slug] = d
        return self._clones[slug]

    def is_reachable(self, slug: str, sha: str) -> bool:
        slug = slug.lower()
        with self._guard:
            lock = self._locks.setdefault(slug, threading.Lock())
        with lock:
            return self._is_reachable(slug, sha)

    def _is_reachable(self, slug: str, sha: str) -> bool:
        if sha in set(self.refs(slug).values()):
            return True
        d = self._clone(slug)
        try:
            # No lazy fetch: the promisor remote would happily serve a fork commit.
            git("cat-file", "-e", f"{sha}^{{commit}}", cwd=d, lazy_fetch=False)
        except GitError:
            return False  # not in the history of any branch or tag
        out = git("for-each-ref", "--contains", sha, "--count=1", "--format=%(refname)",
                  "refs/heads", "refs/tags", cwd=d, lazy_fetch=False)
        return bool(out.strip())
