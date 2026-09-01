# Draft note to the maintainers of `ossf/scorecard-action` (not sent)

`ossf/scorecard-action@4eaacf0543bb3f2c246792bd56e8cdeffafb205a` is reached from 4 of the scanned repositories. Inside it, these references are still mutable, so pinning the action does not pin what it runs:

- `docker://ghcr.io/ossf/scorecard-action:v2.4.3`

Container images cannot be pinned with `git ls-remote`; pin them by digest, e.g. `docker://ghcr.io/org/image@sha256:<digest>`.

Affected scanned repositories: `anchore/grype`, `caddyserver/caddy`, `containerd/containerd`, `envoyproxy/envoy`
