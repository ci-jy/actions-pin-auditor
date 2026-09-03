# Results

From `results/summary.json`. The repo list (`data/repos.txt`) is weighted toward security-focused and cloud-native projects, which pin actions more often. Each repo is scanned at its default branch at scan time.

## 100-repo scan

| Measure | Value |
|---|---|
| Repos scanned (with workflows) | 100 (98) |
| Pass direct SHA-pin policy | 56 |
| ...of which run an unpinned transitive action or image | 28 |
| ...via a mutable action or workflow ref | 5 |
| ...via a mutable container image tag inside a pinned action | 24 |
| Direct-policy findings in those 28 repos | 0 |
| Repos with any transitive unpinned link (pinned or not) | 61 |
| Direct `uses:` references / unpinned | 12,940 / 1,041 |
| Unpinned transitive links | 213 |
| Remote action and workflow files resolved | 2,605 |
| Deepest chain | 4 hops |

The 5 and 24 overlap: a repo can have both kinds of link.

## Impostor check (opt-in run)

From `results/impostor_check.json`. 2,022 SHA pins were checked for reachability. Two were not on any upstream branch or tag: `pnpm/action-setup@c5ba7f78` and `dtolnay/rust-toolchain@29eef336`, both inside third-party reusable workflows. An unreachable SHA isn't proof of an attack. Commits orphaned by a force-push or a deleted branch look the same, and these two are most likely that.

## Most common transitive links

| Inside | Mutable reference | Repos |
|---|---|---|
| `ossf/scorecard-action` | `docker://ghcr.io/ossf/scorecard-action:v2.4.4` | 35 |
| `slsa-framework/slsa-github-generator/.github/actions/generate-builder` | `.../secure-builder-checkout@v2.1.0` | 7 |
| `slsa-framework/slsa-github-generator` generic SLSA3 workflow | `.../detect-workflow-js@v2.1.0` and 3 more | 6 |

## tj-actions/reviewdog replay

`fixtures/tj-actions-2025/` holds the real tag histories, the real `eslint-changed-files` composite action and the real `changed-files` CI workflow (see its README). The malicious code itself is not included. The pre-attack value of `reviewdog/action-setup@v1` is taken as v1.3.0, the latest v1.x at the time.

| Check | Result |
|---|---|
| 359 `tj-actions/changed-files` tags and `reviewdog/action-setup@v1` moved | detected (360 moves) |
| `0e58ed86` and `f0d342d2` not on any upstream branch or tag | both flagged as impostor commits |
| Direct `@v45` user exposed | depth 1 |
| Fully SHA-pinned user exposed via pinned `eslint-changed-files` | depth 2, to both compromised tags |
| `tj-actions/changed-files` CI exposed to `reviewdog/action-setup@v1` | depth 2 |
