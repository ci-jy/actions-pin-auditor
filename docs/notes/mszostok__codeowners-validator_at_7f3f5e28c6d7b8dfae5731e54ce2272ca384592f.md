# Draft note to the maintainers of `mszostok/codeowners-validator` (not sent)

`mszostok/codeowners-validator@7f3f5e28c6d7b8dfae5731e54ce2272ca384592f` is reached from 2 of the scanned repositories. Inside it, these references are still mutable, so pinning the action does not pin what it runs:

- `docker://ghcr.io/mszostok/codeowners-validator:v0.7.4`

Container images cannot be pinned with `git ls-remote`; pin them by digest, e.g. `docker://ghcr.io/org/image@sha256:<digest>`.

Affected scanned repositories: `grafana/grafana`, `nodejs/node`
