# actpin

In a scan of 100 public repositories, 56 passed a direct SHA-pin policy, and 28 of those 56 still ran unpinned code through the actions they call. actpin is the Python CLI that found them. It follows every GitHub Actions `uses:` reference through composite actions, reusable workflows and Docker actions, and reports each tag, branch or image tag it reaches, together with the chain of files that leads there.

The case I kept testing against is the tj-actions/changed-files compromise (CVE-2025-30066). It started with `reviewdog/action-setup@v1`, which wasn't in the victim's workflow at all. It came in through a composite action. GitHub's SHA-pinning policy only looks at what a workflow writes directly, so a repo can pin everything and still be exposed.

![28 of 56 directly-pinned repos still run unpinned code transitively](docs/scan.png)

## Trying it

```bash
pip install -r requirements.txt
python3 -m actpin scan --repos data/repos.txt --limit 100 --out results/
python3 -m actpin replay fixtures/tj-actions-2025 --expect-detected
```

The scan takes about a minute and needs no API token. It writes `results/summary.json`, `results/scan.json` and a SARIF file per repo. To check your own checkout, run `python3 -m actpin scan .` from its root. The replay rebuilds the tj-actions incident from recorded tag histories and real action files. Part of its output:

```
victim fully-pinned-user: direct SHA-pin policy PASS, 2 exposure(s)
  depth 2: .github/workflows/lint.yml -> tj-actions/eslint-changed-files@74f98653... -> reviewdog/action-setup@v1
  depth 2: .github/workflows/lint.yml -> tj-actions/eslint-changed-files@74f98653... -> tj-actions/changed-files@v45
```

That victim pins every action it uses by SHA. The policy passes, and it still reaches both compromised tags two hops down. The replay also catches all 360 moved tags and flags both malicious commits as impostors.

There are also `snapshot`, `diff-tags` and `fix` commands, plus a browser report in [docs/index.html](docs/index.html) and drafted (unsent) notes to upstream maintainers in [docs/notes/](docs/notes/).

Every command and flag: [docs/commands.md](docs/commands.md)
Full scan numbers and replay checks: [docs/results.md](docs/results.md)

## What surprised me in the scan

I expected the transitive problem to be mostly composite actions calling other actions by tag. It mostly wasn't. In 24 of the 28 exposed repos the weak link is a container image tag inside an action that is itself pinned. One link, `ossf/scorecard-action` running `docker://ghcr.io/ossf/scorecard-action:v2.4.4`, shows up in 35 repos on its own. A commit SHA can't fix that. The image needs a digest.

The repo list leans toward security and cloud-native projects, which pin more often than most. A random sample would probably look worse.

## How it works

Each repo is fetched with a shallow blobless clone and a sparse checkout of `.github/` and every `action.yml`, so only the metadata comes down. Remote action files are read from `raw.githubusercontent.com` and cached on disk.

The resolver walks the reference graph breadth-first and expands each file-at-a-ref once. That keeps cycles from looping and gives the shortest path to every finding. Getting this exactly right was harder than it sounds, so the walk is checked against a slow brute-force enumeration on 400 Hypothesis-generated graphs with loops, missing actions and mixed ref kinds. The two agree on all of them.

Impostor commits were the strangest part. GitHub serves fork commits through the parent repo, so `owner/repo@<sha>` can run code that never landed in that repo. To check, actpin takes a commits-only bare clone and asks git whether any branch or tag contains the SHA, with lazy fetching turned off so git can't quietly download the missing commit and make it look fine.

Internals, SARIF rules and tests: [docs/internals.md](docs/internals.md)

## Known gaps

- Mutable tags are flagged by pattern. Whether a tag actually moved is only known if you compare two `snapshot`s, so a scheduled snapshot job would be the obvious next step.
- Impostor checks clone each pinned action's history, so they're opt-in (`--check-impostors`). The two unreachable SHAs the opt-in run found are most likely orphaned by a force-push, not attacks.
- Dockerfile `FROM` images, expressions in `uses:` and JavaScript actions that download code at runtime are not inspected.
- The scan is a snapshot of each default branch, so rerunning it gives slightly different numbers.

Project period: 2026-08-31 to 2026-09-07.
