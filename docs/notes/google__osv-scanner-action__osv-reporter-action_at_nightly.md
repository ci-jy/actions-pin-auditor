# Draft note to the maintainers of `google/osv-scanner-action` (not sent)

`google/osv-scanner-action/osv-reporter-action@nightly` is reached from 2 of the scanned repositories. Inside it, these references are still mutable, so pinning the action does not pin what it runs:

- `docker://ghcr.io/google/osv-scanner-action:nightly`

Container images cannot be pinned with `git ls-remote`; pin them by digest, e.g. `docker://ghcr.io/org/image@sha256:<digest>`.

Affected scanned repositories: `google/osv-scanner`, `ossf/osv-schema`
