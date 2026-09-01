# Draft note to the maintainers of `slsa-framework/slsa-github-generator` (not sent)

`slsa-framework/slsa-github-generator/.github/workflows/generator_container_slsa3.yml@v2.1.0` is reached from 4 of the scanned repositories. Inside it, these references are still mutable, so pinning the action does not pin what it runs:

- `slsa-framework/slsa-github-generator/.github/actions/detect-workflow-js@v2.1.0`
- `slsa-framework/slsa-github-generator/.github/actions/generate-builder@v2.1.0`

Suggested patch (tags resolved with `git ls-remote`; the version is kept as a trailing comment so Dependabot and Renovate keep updating it):

```diff
--- a/.github/workflows/generator_container_slsa3.yml
+++ b/.github/workflows/generator_container_slsa3.yml
@@ -112,7 +112,7 @@
       - name: Detect the generator ref
         id: detect
         continue-on-error: true
-        uses: slsa-framework/slsa-github-generator/.github/actions/detect-workflow-js@v2.1.0
+        uses: slsa-framework/slsa-github-generator/.github/actions/detect-workflow-js@f7dd8c54c2067bafc12ca7a55595d5ee9b75204a # v2.1.0
 
       - name: Final outcome
         id: final
@@ -144,7 +144,7 @@
       - name: Generate builder
         id: generate-builder
         continue-on-error: true
-        uses: slsa-framework/slsa-github-generator/.github/actions/generate-builder@v2.1.0
+        uses: slsa-framework/slsa-github-generator/.github/actions/generate-builder@f7dd8c54c2067bafc12ca7a55595d5ee9b75204a # v2.1.0
         with:
           repository: "${{ needs.detect-env.outputs.repository }}"
           ref: "${{ needs.detect-env.outputs.ref }}"
```

Affected scanned repositories: `argoproj/argo-cd`, `fluxcd/flux2`, `guacsec/guac`, `kyverno/kyverno`
