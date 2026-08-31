"""Fetchers return the metadata file behind a remote `uses:` reference.

* RawFetcher reads public files from raw.githubusercontent.com (no token) and
  caches them on disk.
* DirFetcher reads a recorded tree laid out as <root>/<owner>/<repo>/<ref>/<path>.
* DictFetcher serves an in-memory mapping (used by tests).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .refs import UsesRef


def candidate_paths(u: UsesRef) -> list[str]:
    if u.kind == "reusable":
        return [u.path]
    base = f"{u.path}/" if u.path else ""
    return [f"{base}action.yml", f"{base}action.yaml"]


class Fetcher:
    def get_file(self, slug: str, ref: str, path: str) -> str | None:  # pragma: no cover
        raise NotImplementedError

    def load(self, u: UsesRef) -> tuple[str, str] | None:
        """Return (path, text) of the action.yml / reusable workflow, or None."""
        for p in candidate_paths(u):
            text = self.get_file(u.slug, u.ref, p)
            if text is not None:
                return p, text
        return None


class DictFetcher(Fetcher):
    def __init__(self, files: dict[tuple[str, str, str], str]):
        self.files = files
        self.calls = 0

    def get_file(self, slug, ref, path):
        self.calls += 1
        return self.files.get((slug, ref, path))


class DirFetcher(Fetcher):
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)

    def get_file(self, slug, ref, path):
        f = self.root / slug / ref / path
        return f.read_text() if f.is_file() else None


class RawFetcher(Fetcher):
    BASE = "https://raw.githubusercontent.com"

    def __init__(self, cache_dir: str | os.PathLike, timeout: float = 20.0):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._lock = threading.Lock()
        self.requests = 0

    def _key(self, slug, ref, path) -> Path:
        h = hashlib.sha256(f"{slug}@{ref}:{path}".encode()).hexdigest()
        return self.cache / h[:2] / f"{h}.json"

    def get_file(self, slug, ref, path):
        key = self._key(slug, ref, path)
        if key.is_file():
            try:
                return json.loads(key.read_text())["text"]
            except (ValueError, KeyError):
                pass
        url = f"{self.BASE}/{slug}/{ref}/{path}"
        text = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "actpin"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    text = r.read().decode("utf-8", "replace")
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    break
                time.sleep(1 + attempt * 2)
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(1 + attempt * 2)
        else:
            return None  # network failure: do not cache
        with self._lock:
            self.requests += 1
            key.parent.mkdir(parents=True, exist_ok=True)
            tmp = key.with_suffix(f".{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps({"url": url, "text": text}))
            tmp.replace(key)
        return text
