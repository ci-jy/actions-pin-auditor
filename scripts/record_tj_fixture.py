#!/usr/bin/env python3
"""Record the tj-actions/reviewdog replay fixture from public data.

Network: git ls-remote, commits-only bare clones and raw.githubusercontent.com.
Re-running overwrites fixtures/tj-actions-2025/{tags-*.json,reachability.json,repos/,victims/}.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from actpin import gitops  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "tj-actions-2025"
CHANGED = "tj-actions/changed-files"
SETUP = "reviewdog/action-setup"
ESLINT = "tj-actions/eslint-changed-files"
MAL_CHANGED = "0e58ed8671d6b60d0890c21b07f8835ace038e67"   # CVE-2025-30066
MAL_SETUP = "f0d342d24037bb11d26b9bd8496e0808ba32e9ec"     # CVE-2025-30154
SETUP_V130 = "3f401fe1d58fe77e10d665ab713057375e39b887"    # v1.3.0, last v1.x before 2025-03-11
ESLINT_V2530 = "74f98653675512158746d3136cd2d9326fbfb6e1"  # v25.3.0, what v25 pointed at in March 2025
CHANGED_V4507 = "a284dc1814e3fd07f2e34267fc8f81227ed29fb8"  # v45.0.7 (restored)


def raw(slug, ref, path):
    url = f"https://raw.githubusercontent.com/{slug}/{ref}/{path}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "actpin"}),
                                timeout=30) as r:
        return r.read().decode()


def tags_before(slug: str, cutoff: str, work: Path) -> dict[str, str]:
    d = work / slug.replace("/", "__")
    gitops.git("clone", "--quiet", "--bare", "--filter=tree:0", gitops.repo_url(slug), str(d), timeout=600)
    out = gitops.git("for-each-ref", "refs/tags",
                     "--format=%(refname:short) %(objectname) %(*objectname) %(creatordate:short)",
                     cwd=d)
    tags = {}
    for line in out.splitlines():
        parts = line.split()
        name, obj, date = parts[0], parts[-2] if len(parts) == 4 else parts[1], parts[-1]
        if date < cutoff:
            tags[name] = obj  # peeled commit for annotated tags
    return dict(sorted(tags.items()))


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def main():
    work = Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
    changed = tags_before(CHANGED, "2025-03-14", work)
    setup = tags_before(SETUP, "2025-03-11", work)
    setup["v1"] = SETUP_V130
    before = {"note": "Tags that existed before the attack, as published today (restored "
                      "after the incident). reviewdog/action-setup@v1 is set to v1.3.0, the "
                      "latest v1.x release at the time.",
              "repos": {CHANGED: changed, SETUP: dict(sorted(setup.items()))}}
    after = {"note": "State during the attack windows reported by CISA, Wiz and StepSecurity: "
                     "every tj-actions/changed-files tag re-pointed to the malicious commit "
                     "(2025-03-14/15) and reviewdog/action-setup@v1 re-pointed "
                     "(2025-03-11 18:42-20:31 UTC).",
             "repos": {CHANGED: {t: MAL_CHANGED for t in changed},
                       SETUP: {**before["repos"][SETUP], "v1": MAL_SETUP}}}
    write(OUT / "tags-before.json", json.dumps(before, indent=1) + "\n")
    write(OUT / "tags-after.json", json.dumps(after, indent=1) + "\n")

    checker = gitops.ReachabilityChecker(work / "reach")
    reach = {"note": "Live reachability of the malicious commits from upstream branches/tags.",
             "repos": {CHANGED: {MAL_CHANGED: checker.is_reachable(CHANGED, MAL_CHANGED)},
                       SETUP: {MAL_SETUP: checker.is_reachable(SETUP, MAL_SETUP)}}}
    write(OUT / "reachability.json", json.dumps(reach, indent=1) + "\n")

    eslint_yml = raw(ESLINT, ESLINT_V2530, "action.yml")
    files = {
        f"repos/{ESLINT}/v25/action.yml": eslint_yml,
        f"repos/{ESLINT}/{ESLINT_V2530}/action.yml": eslint_yml,
        f"repos/{SETUP}/v1/action.yml": raw(SETUP, SETUP_V130, "action.yml"),
        f"repos/{CHANGED}/v45/action.yml": raw(CHANGED, CHANGED_V4507, "action.yml"),
        "victims/tj-actions-changed-files/.github/workflows/test.yml":
            raw(CHANGED, CHANGED_V4507, ".github/workflows/test.yml"),
        "victims/direct-tag-user/.github/workflows/ci.yml": DIRECT_VICTIM,
        "victims/fully-pinned-user/.github/workflows/lint.yml": PINNED_VICTIM,
    }
    for rel, text in files.items():
        write(OUT / rel, text)
    print(f"recorded fixture in {OUT}")


DIRECT_VICTIM = """\
# Typical consumer: references tj-actions/changed-files by major version tag.
name: ci
on: [pull_request]
jobs:
  changes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
      - uses: tj-actions/changed-files@v45
        id: changed
      - run: echo "${{ steps.changed.outputs.all_changed_files }}"
"""

PINNED_VICTIM = f"""\
# Every direct reference is a full SHA, so a direct SHA-pinning policy passes.
# The pinned composite action still pulls reviewdog/action-setup@v1 and
# tj-actions/changed-files@v45 by tag.
name: lint
on: [pull_request]
jobs:
  eslint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
      - uses: tj-actions/eslint-changed-files@{ESLINT_V2530} # v25.3.0
        with:
          config_path: .eslintrc.json
"""

if __name__ == "__main__":
    main()
