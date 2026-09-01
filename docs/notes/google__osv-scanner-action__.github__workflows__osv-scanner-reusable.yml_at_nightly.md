# Draft note to the maintainers of `google/osv-scanner-action` (not sent)

`google/osv-scanner-action/.github/workflows/osv-scanner-reusable.yml@nightly` is reached from 2 of the scanned repositories. Inside it, these references are still mutable, so pinning the action does not pin what it runs:

- `google/osv-scanner-action/osv-reporter-action@nightly`
- `google/osv-scanner-action/osv-scanner-action@nightly`

Suggested patch (tags resolved with `git ls-remote`; the version is kept as a trailing comment so Dependabot and Renovate keep updating it):

```diff
--- a/.github/workflows/osv-scanner-reusable.yml
+++ b/.github/workflows/osv-scanner-reusable.yml
@@ -93,7 +93,7 @@
           path: "./"
       - name: "Run scanner"
         id: "scan"
-        uses: google/osv-scanner-action/osv-scanner-action@nightly
+        uses: google/osv-scanner-action/osv-scanner-action@933759f76f6d9db420e5adc9f59ef5825a5696ec # nightly
         env:
           GOTOOLCHAIN: auto
         with:
@@ -118,7 +118,7 @@
             exit 1
           fi
       - name: "Run osv-scanner-reporter"
-        uses: google/osv-scanner-action/osv-reporter-action@nightly
+        uses: google/osv-scanner-action/osv-reporter-action@933759f76f6d9db420e5adc9f59ef5825a5696ec # nightly
         with:
           scan-args: |-
             --output=${{ inputs.matrix-property }}${{ inputs.results-file-name }}
```

Affected scanned repositories: `google/osv-scanner`, `ossf/osv-schema`
