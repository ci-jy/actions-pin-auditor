"""SARIF 2.1.0 output for GitHub code scanning."""
from __future__ import annotations

from . import __version__
from .graph import Resolution

RULES = {
    "APN001": ("unpinned-direct", "Action reference in this repository is not pinned to a full commit SHA",
               "error"),
    "APN002": ("unpinned-transitive",
               "A pinned action or reusable workflow pulls in an unpinned action", "error"),
    "APN003": ("impostor-commit",
               "Pinned SHA is not reachable from any branch or tag of the upstream repository",
               "error"),
    "APN004": ("tag-moved", "A referenced tag now points at a different commit", "warning"),
}


def _rule_for(f) -> str:
    return "APN002" if f.transitive else "APN001"


def to_sarif(res: Resolution, impostors: list[dict] | None = None,
             moved_tags: list[dict] | None = None) -> dict:
    results = []
    for f in res.findings:
        rid = _rule_for(f)
        chain = " -> ".join(f.path)
        if f.transitive:
            msg = (f"`{f.use.ref.raw}` ({f.use.ref.state}) is pulled in transitively via {chain}. "
                   "Pinning the direct reference does not pin this action.")
        else:
            msg = f"`{f.use.ref.raw}` uses a mutable {f.use.ref.state} reference; pin it to a full SHA."
        results.append(_result(rid, msg, f.root.path, f.root_line or 1))
    for imp in impostors or []:
        results.append(_result("APN003",
                               f"`{imp['uses']}`: commit {imp['sha']} is not on any branch or tag of "
                               f"{imp['repo']} (possible impostor commit from a fork). Path: "
                               + " -> ".join(imp.get("path", [])),
                               imp.get("root", ".github/workflows"), imp.get("root_line", 1) or 1))
    for m in moved_tags or []:
        results.append(_result("APN004",
                               f"{m['repo']}@{m['tag']} moved from {m['old']} to {m['new']}",
                               m.get("root", ".github/workflows"), m.get("root_line", 1) or 1))
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "actpin",
                "version": __version__,
                "informationUri": "https://github.com/",
                "rules": [{"id": rid, "name": name, "shortDescription": {"text": text},
                           "defaultConfiguration": {"level": level}}
                          for rid, (name, text, level) in RULES.items()],
            }},
            "results": results,
        }],
    }


def _result(rule_id: str, message: str, uri: str, line: int) -> dict:
    return {
        "ruleId": rule_id,
        "level": RULES[rule_id][2],
        "message": {"text": message},
        "locations": [{"physicalLocation": {
            "artifactLocation": {"uri": uri},
            "region": {"startLine": max(1, int(line))},
        }}],
    }
