# Internals

## Fetching

`git clone --depth 1 --filter=blob:none --no-checkout` plus a non-cone sparse checkout of `/.github/` and every `action.yml` downloads only metadata files. Remote `action.yml` files and reusable workflows come from `raw.githubusercontent.com` without a token and are cached on disk. Nothing uses the REST API, so there are no rate limits to worry about and it works in locked-down CI.

## Graph walk

`actpin/graph.py` parses each YAML file with line numbers and walks the reference graph breadth-first. Each unit (a file at a ref) is expanded once, so cycles terminate, and parent pointers give a shortest path for every finding.

`./` inside a remote action refers to the caller's workspace, not the action repo, so it is recorded as unresolvable rather than guessed.

## Direct vs transitive

References in the repo's own workflows and its local composite actions count as direct. That is what a direct SHA-pin policy checks. References inside remote units are transitive. A repo counts as exposed only if every direct reference is a full SHA and some transitive link is not. Counting local composite actions as direct makes the exposed number conservative: a repo whose local action uses `@v4` is counted as failing the policy, not as exposed.

A pinned action whose `runs.image` is `docker://...:tag` runs whatever that tag points at today. Those links are reported separately because the fix is an image digest, not a commit SHA. Dockerfile-based actions are treated as pinned by the action SHA; their `FROM` images are not inspected.

## Impostor commits

GitHub serves fork commits through the parent repository, so `owner/repo@<sha>` can run code that never landed in `owner/repo`. `ReachabilityChecker` first matches the SHA against `ls-remote` tips, then takes a commits-only (`--filter=tree:0`) bare clone and runs `git for-each-ref --contains`. Lazy fetching is disabled so the promisor remote can't supply the missing commit behind the scenes.

## Tag mutation

`snapshot` records tag to commit maps (annotated tags peeled) and `diff-tags` reports tags that kept their name but changed commit.

## SARIF rules

| Rule | Meaning |
|---|---|
| `APN001` | Unpinned direct reference |
| `APN002` | Unpinned transitive reference, with the full chain in the message, anchored on the first hop's line |
| `APN003` | Impostor commit |
| `APN004` | Moved tag |

## Tests

```bash
python3 -m pytest -q
python3 scripts/check_summary.py results/summary.json --min-repos 100
```

- `tests/test_properties.py`: Hypothesis generates graphs of composite, reusable-workflow and Docker actions with arbitrary edges (cycles, self-loops, duplicates), ref kinds (SHA, tag, branch, short SHA), missing actions and local composite actions. It renders them to YAML, runs the resolver, and compares distances, findings and every reported path against a brute-force enumeration of all simple paths over the specification, not the YAML. It runs 400 examples. A fixed example covers a deep path that a depth-first walk would find before the short one.
- `tests/test_git.py`: real git repos on disk for annotated-tag peeling, sparse blobless fetch, tag moves, and an impostor commit that is in the object store but on no ref.
- `tests/test_core.py`: ref classification, YAML line numbers, direct vs transitive, SARIF shape, pin-fix comment preservation, the replay and the CLI.
