# Draft note to the maintainers of `slsa-framework/slsa-github-generator` (not sent)

`slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v2.1.0` is reached from 6 of the scanned repositories. Inside it, these references are still mutable, so pinning the action does not pin what it runs:

- `slsa-framework/slsa-github-generator/.github/actions/detect-workflow-js@v2.1.0`
- `slsa-framework/slsa-github-generator/.github/actions/generate-builder@v2.1.0`
- `slsa-framework/slsa-github-generator/.github/actions/secure-builder-checkout@v2.1.0`
- `slsa-framework/slsa-github-generator/.github/actions/secure-download-artifact@v2.1.0`

Suggested patch (tags resolved with `git ls-remote`; the version is kept as a trailing comment so Dependabot and Renovate keep updating it):

```diff
--- a/.github/workflows/generator_generic_slsa3.yml
+++ b/.github/workflows/generator_generic_slsa3.yml
@@ -121,7 +121,7 @@
       - name: Detect the generator ref
         id: detect
         continue-on-error: true
-        uses: slsa-framework/slsa-github-generator/.github/actions/detect-workflow-js@v2.1.0
+        uses: slsa-framework/slsa-github-generator/.github/actions/detect-workflow-js@f7dd8c54c2067bafc12ca7a55595d5ee9b75204a # v2.1.0
 
       - name: Final outcome
         id: final
@@ -156,7 +156,7 @@
       - name: Generate builder
         id: generate-builder
         continue-on-error: true
-        uses: slsa-framework/slsa-github-generator/.github/actions/generate-builder@v2.1.0
+        uses: slsa-framework/slsa-github-generator/.github/actions/generate-builder@f7dd8c54c2067bafc12ca7a55595d5ee9b75204a # v2.1.0
         with:
           repository: "${{ needs.detect-env.outputs.repository }}"
           ref: "${{ needs.detect-env.outputs.ref }}"
@@ -189,7 +189,7 @@
         id: download-file
         continue-on-error: true
         if: inputs.base64-subjects-as-file != ''
-        uses: slsa-framework/slsa-github-generator/.github/actions/secure-download-artifact@v2.1.0
+        uses: slsa-framework/slsa-github-generator/.github/actions/secure-download-artifact@f7dd8c54c2067bafc12ca7a55595d5ee9b75204a # v2.1.0
         with:
           name: "${{ steps.metadata.outputs.artifact_name }}"
           path: "${{ steps.metadata.outputs.filename }}"
@@ -269,7 +269,7 @@
       - name: Checkout builder repository
         id: checkout-builder
         continue-on-error: true
-        uses: slsa-framework/slsa-github-generator/.github/actions/secure-builder-checkout@v2.1.0
+        uses: slsa-framework/slsa-github-generator/.github/actions/secure-builder-checkout@f7dd8c54c2067bafc12ca7a55595d5ee9b75204a # v2.1.0
         with:
           repository: "${{ needs.detect-env.outputs.repository }}"
           ref: "${{ needs.detect-env.outputs.ref }}"
```

Affected scanned repositories: `argoproj/argo-cd`, `fluxcd/flux2`, `google/osv-scanner`, `guacsec/guac`, `jaegertracing/jaeger`, `ossf/scorecard`
