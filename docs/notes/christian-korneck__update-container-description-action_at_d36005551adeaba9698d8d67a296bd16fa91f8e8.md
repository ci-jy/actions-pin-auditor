# Draft note to the maintainers of `christian-korneck/update-container-description-action` (not sent)

`christian-korneck/update-container-description-action@d36005551adeaba9698d8d67a296bd16fa91f8e8` is reached from 3 of the scanned repositories. Inside it, these references are still mutable, so pinning the action does not pin what it runs:

- `docker://docker.io/chko/docker-pushrm:1`

Container images cannot be pinned with `git ls-remote`; pin them by digest, e.g. `docker://ghcr.io/org/image@sha256:<digest>`.

Affected scanned repositories: `prometheus/alertmanager`, `prometheus/node_exporter`, `prometheus/prometheus`
