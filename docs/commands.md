# Commands

Run everything as `python3 -m actpin <command>`.

| Command | What it does |
|---|---|
| `scan [PATH]` | Resolve a checkout's workflows transitively and print each unpinned link with its path |
| `scan --repos FILE --limit N --out DIR` | Scan public repos (sparse blobless clones) and write `summary.json`, `scan.json` and `sarif/` |
| `snapshot --repo o/r --out snap.json` | Record tag to commit maps with `git ls-remote` |
| `diff-tags old.json new.json` | List tags whose commit changed between two snapshots |
| `fix [PATH]` | Rewrite `owner/repo@v4` to `owner/repo@<sha> # v4`, keeping existing comments |
| `replay FIXTURE` | Replay a recorded incident fixture |

## scan

- `path` (default `.`): checkout to scan when `--repos` is not given.
- `--repos FILE`: file with one `owner/repo` per line.
- `--limit N`: only scan the first N repos from the list (0 means all).
- `--out DIR` (default `results/`): output directory for a multi-repo scan.
- `--workers N` (default 6): parallel clones.
- `--check-impostors`: verify every SHA pin is reachable from an upstream branch or tag. Slow, since it clones each action's commit graph.
- `--sarif FILE`: write SARIF 2.1.0 for a single checkout.
- `--json FILE`: write the per-repo summary record.
- `--fail-on none|transitive|any` (default `none`): exit 1 if there are transitive findings (or impostors), or any findings at all.

## snapshot

- `--repo owner/repo`: repeatable.
- `--repos FILE`: one `owner/repo` per line.
- `--from-scan results/scan.json`: snapshot every action repo seen in a scan.
- `--out FILE`: required.

Annotated tags are peeled to the commit they point at.

## diff-tags

- `old`, `new`: snapshot files.
- `--json FILE`: write the full diff.
- `-v`: also list added and deleted tags.

Exits 1 if any tag moved.

## fix

- `path` (default `.`).
- `--out FILE`: write a unified patch instead of printing it.
- `--write`: rewrite files in place.

References that can't be resolved with `git ls-remote` are reported on stderr and left alone.

## replay

- `fixture`: directory such as `fixtures/tj-actions-2025`.
- `--expect-detected`: exit 1 if any expected detection is missed.
- `--live`: re-check reachability of the malicious commits over the network.
- `--json FILE`: write the replay result.

## Cache

Fetched action files and reachability clones go in `$ACTPIN_CACHE`, or `$XDG_CACHE_HOME/actpin` (default `~/.cache/actpin`).

## CI

`.github/workflows/actpin.yml` runs the auditor on this repository and uploads the SARIF to GitHub code scanning.

## Regenerating outputs

After a scan, `python3 scripts/plot_results.py && python3 scripts/build_report.py` rebuilds `docs/scan.png`, `docs/index.html` and `docs/notes/`. `python3 scripts/record_tj_fixture.py` re-records the replay fixture.
