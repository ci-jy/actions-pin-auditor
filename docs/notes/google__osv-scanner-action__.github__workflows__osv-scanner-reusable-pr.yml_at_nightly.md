# Draft note to the maintainers of `google/osv-scanner-action` (not sent)

`google/osv-scanner-action/.github/workflows/osv-scanner-reusable-pr.yml@nightly` is reached from 2 of the scanned repositories. Inside it, these references are still mutable, so pinning the action does not pin what it runs:

- `google/osv-scanner-action/osv-reporter-action@nightly`
- `google/osv-scanner-action/osv-scanner-action@nightly`

Suggested patch (tags resolved with `git ls-remote`; the version is kept as a trailing comment so Dependabot and Renovate keep updating it):

```diff
--- a/.github/workflows/osv-scanner-reusable-pr.yml
+++ b/.github/workflows/osv-scanner-reusable-pr.yml
@@ -86,7 +86,7 @@
           git submodule update --recursive
       - name: "Run scanner on existing code"
         id: "scan-old"
-        uses: google/osv-scanner-action/osv-scanner-action@nightly
+        uses: google/osv-scanner-action/osv-scanner-action@933759f76f6d9db420e5adc9f59ef5825a5696ec # nightly
         env:
           GOTOOLCHAIN: auto
         continue-on-error: true
@@ -102,7 +102,7 @@
           git submodule update --recursive
       - name: "Run scanner on new code"
         id: "scan-new"
-        uses: google/osv-scanner-action/osv-scanner-action@nightly
+        uses: google/osv-scanner-action/osv-scanner-action@933759f76f6d9db420e5adc9f59ef5825a5696ec # nightly
         env:
           GOTOOLCHAIN: auto
         with:
@@ -140,7 +140,7 @@
           fi
           exit "${status}"
       - name: "Run osv-scanner-reporter"
-        uses: google/osv-scanner-action/osv-reporter-action@nightly
+        uses: google/osv-scanner-action/osv-reporter-action@933759f76f6d9db420e5adc9f59ef5825a5696ec # nightly
         with:
           scan-args: |-
             --output=${{ inputs.matrix-property }}${{ inputs.results-file-name }}
```

Affected scanned repositories: `google/osv-scanner`, `ossf/osv-schema`
