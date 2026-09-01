#!/usr/bin/env python3
"""Validate results/summary.json from a public-repo scan."""
import argparse
import json
import sys

REQUIRED = ["repos_requested", "repos_scanned", "repos_failed", "direct_policy_pass",
            "direct_pass_but_transitive_unpinned", "github_policy_flags_in_those_repos",
            "total_transitive_unpinned_links"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("summary")
    p.add_argument("--min-repos", type=int, default=100)
    a = p.parse_args()
    s = json.load(open(a.summary))
    errors = [f"missing key {k}" for k in REQUIRED if k not in s]
    if not errors:
        if s["repos_scanned"] < a.min_repos:
            errors.append(f"only {s['repos_scanned']} repos scanned (< {a.min_repos})")
        if s["direct_pass_but_transitive_unpinned"] > s["direct_policy_pass"]:
            errors.append("exposed repos exceed repos passing the direct policy")
        if s["github_policy_flags_in_those_repos"] != 0:
            errors.append("repos counted as passing the direct policy have direct findings")
        if len(s.get("direct_pass_but_transitive_unpinned_repos", [])) != s["direct_pass_but_transitive_unpinned"]:
            errors.append("repo list does not match count")
    if errors:
        print("FAIL: " + "; ".join(errors))
        return 1
    print(f"OK: {s['repos_scanned']} repos scanned; {s['direct_pass_but_transitive_unpinned']} of "
          f"{s['direct_policy_pass']} that pass direct SHA pinning still run an unpinned transitive "
          f"action or image ({s['total_transitive_unpinned_links']} unpinned transitive links in total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
