# Replay fixture: tj-actions/changed-files and reviewdog/action-setup (March 2025)

Recorded by `scripts/record_tj_fixture.py` from public data (git ls-remote,
commits-only clones, raw.githubusercontent.com).

| File | Contents |
|---|---|
| `incident.json` | Compromised repos, malicious commits, sources, and the exposures the replay must find |
| `tags-before.json` | Tag -> commit maps for both repos, limited to tags that existed before the attack, as published today (the maintainers restored them). `reviewdog/action-setup@v1` is set to v1.3.0 (`3f401fe`), the latest v1.x at the time |
| `tags-after.json` | The attack state: every `tj-actions/changed-files` tag re-pointed to `0e58ed86` (CVE-2025-30066) and `reviewdog/action-setup@v1` re-pointed to `f0d342d2` (CVE-2025-30154) |
| `reachability.json` | Live check of both malicious commits against upstream branches and tags: neither is reachable (impostor commits). GitHub no longer serves either object |
| `repos/` | Real action metadata: `tj-actions/eslint-changed-files` v25.3.0 (what `v25` pointed at in March 2025, a composite action using `reviewdog/action-setup@v1` and `tj-actions/changed-files@v45`), `reviewdog/action-setup` v1.3.0, `tj-actions/changed-files` v45.0.7 |
| `victims/tj-actions-changed-files` | The real `test.yml` of tj-actions/changed-files at v45.0.7, which calls `tj-actions/eslint-changed-files@v25`: the path that leaked the bot token |
| `victims/direct-tag-user` | Minimal consumer using `tj-actions/changed-files@v45` |
| `victims/fully-pinned-user` | Consumer that SHA-pins every direct reference, yet reaches both compromised tags through the pinned composite action |

The malicious commits' contents are not included; detection relies on the tag
moves, their targets being unreachable from upstream refs, and the `uses:` paths.
