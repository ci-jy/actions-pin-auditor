# Draft note to the maintainers of `ossf/scorecard-action` (not sent)

`ossf/scorecard-action@2d1146689b8cda280b9bc96326124645441f03bc` is reached from 34 of the scanned repositories. Inside it, these references are still mutable, so pinning the action does not pin what it runs:

- `docker://ghcr.io/ossf/scorecard-action:v2.4.4`

Container images cannot be pinned with `git ls-remote`; pin them by digest, e.g. `docker://ghcr.io/org/image@sha256:<digest>`.

Affected scanned repositories: `PowerShell/PowerShell`, `argoproj/argo-cd`, `cert-manager/cert-manager`, `docker/compose`, `electron/electron`, `etcd-io/etcd`, `expressjs/express`, `external-secrets/external-secrets`, `falcosecurity/falco`, `fluxcd/flux2`, `google/osv-scanner`, `goreleaser/goreleaser`, `guacsec/guac`, `helm/helm`, `jaegertracing/jaeger`, `kyverno/kyverno`, `microsoft/TypeScript`, `nodejs/node`, `nodejs/undici`, `numpy/numpy`, `open-policy-agent/gatekeeper`, `open-policy-agent/opa`, `open-telemetry/opentelemetry-collector`, `open-telemetry/opentelemetry-go`, `open-telemetry/opentelemetry-js`, `open-telemetry/opentelemetry-python`, `ossf/scorecard`, `prometheus/prometheus`, `sigstore/cosign`, `sigstore/fulcio`, `sigstore/rekor`, `sigstore/sigstore`, `sigstore/sigstore-python`, `tektoncd/pipeline`
