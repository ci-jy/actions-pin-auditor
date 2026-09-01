# Draft note to the maintainers of `slsa-framework/slsa-github-generator` (not sent)

`slsa-framework/slsa-github-generator/.github/actions/secure-download-artifact@v2.1.0` is reached from 6 of the scanned repositories. Inside it, these references are still mutable, so pinning the action does not pin what it runs:

- `slsa-framework/slsa-github-generator/.github/actions/compute-sha256@v2.1.0`

Suggested patch (tags resolved with `git ls-remote`; the version is kept as a trailing comment so Dependabot and Renovate keep updating it):

```diff
--- a/.github/actions/secure-download-artifact/action.yml
+++ b/.github/actions/secure-download-artifact/action.yml
@@ -85,7 +85,7 @@
 
     - name: Compute the hash
       id: compute
-      uses: slsa-framework/slsa-github-generator/.github/actions/compute-sha256@v2.1.0
+      uses: slsa-framework/slsa-github-generator/.github/actions/compute-sha256@f7dd8c54c2067bafc12ca7a55595d5ee9b75204a # v2.1.0
       with:
         path: "${{ steps.validate-path.outputs.file_path }}"
 
```

Affected scanned repositories: `argoproj/argo-cd`, `fluxcd/flux2`, `google/osv-scanner`, `guacsec/guac`, `jaegertracing/jaeger`, `ossf/scorecard`
