# Draft note to the maintainers of `slsa-framework/slsa-github-generator` (not sent)

`slsa-framework/slsa-github-generator/.github/actions/generate-builder@v2.1.0` is reached from 7 of the scanned repositories. Inside it, these references are still mutable, so pinning the action does not pin what it runs:

- `slsa-framework/slsa-github-generator/.github/actions/secure-builder-checkout@v2.1.0`

Suggested patch (tags resolved with `git ls-remote`; the version is kept as a trailing comment so Dependabot and Renovate keep updating it):

```diff
--- a/.github/actions/generate-builder/action.yml
+++ b/.github/actions/generate-builder/action.yml
@@ -62,7 +62,7 @@
   using: "composite"
   steps:
     - name: Checkout builder repository
-      uses: slsa-framework/slsa-github-generator/.github/actions/secure-builder-checkout@v2.1.0
+      uses: slsa-framework/slsa-github-generator/.github/actions/secure-builder-checkout@f7dd8c54c2067bafc12ca7a55595d5ee9b75204a # v2.1.0
       with:
         repository: ${{ inputs.repository }}
         ref: ${{ inputs.ref }}
```

Affected scanned repositories: `argoproj/argo-cd`, `fluxcd/flux2`, `google/osv-scanner`, `guacsec/guac`, `jaegertracing/jaeger`, `kyverno/kyverno`, `ossf/scorecard`
