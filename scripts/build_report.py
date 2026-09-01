#!/usr/bin/env python3
"""Build docs/index.html (static browser report of the scan) and drafted,
unsent notes to maintainers of actions that pull in unpinned references."""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from actpin.cli import default_cache  # noqa: E402
from actpin.fetch import RawFetcher  # noqa: E402
from actpin.fix import ls_remote_resolver, pin_text, unified_patch  # noqa: E402
from actpin.graph import is_workflow_path  # noqa: E402

DOCS = ROOT / "docs"
MAX_NOTES = int(os.environ.get("ACTPIN_MAX_NOTES", "12"))


def split_label(label: str):
    target, ref = label.rsplit("@", 1)
    parts = target.split("/")
    return "/".join(parts[:2]), "/".join(parts[2:]), ref


def build_notes(scan: list[dict]) -> list[dict]:
    """Group transitive findings by the remote file that contains them."""
    by_unit: dict[str, dict] = defaultdict(lambda: {"repos": set(), "uses": set()})
    for rec in scan:
        for f in rec.get("findings", []):
            if f["transitive"]:
                by_unit[f["in"]]["repos"].add(rec["repo"])
                by_unit[f["in"]]["uses"].add((f["uses"], f["state"]))
    ranked = sorted(by_unit.items(), key=lambda kv: (-len(kv[1]["repos"]), kv[0]))[:MAX_NOTES]
    fetcher = RawFetcher(default_cache() / "raw")
    resolver = ls_remote_resolver()
    notes_dir = DOCS / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    for old in notes_dir.glob("*.md"):
        old.unlink()
    out = []
    for label, info in ranked:
        slug, sub, ref = split_label(label)
        paths = [sub] if is_workflow_path(sub) else [f"{sub}/action.yml" if sub else "action.yml",
                                                       f"{sub}/action.yaml" if sub else "action.yaml"]
        path, text = next(((p, t) for p in paths if (t := fetcher.get_file(slug, ref, p)) is not None),
                          (paths[0], None))
        patch = ""
        if text is not None:
            new, _ = pin_text(text, resolver)
            patch = unified_patch(path, text, new)
        images = sorted(u for u, s in info["uses"] if s == "docker-tag")
        refs = sorted(u for u, s in info["uses"] if s != "docker-tag")
        name = label.replace("/", "__").replace("@", "_at_")[:120] + ".md"
        lines = [
            f"# Draft note to the maintainers of `{slug}` (not sent)", "",
            f"`{label}` is reached from {len(info['repos'])} of the scanned repositories. "
            "Inside it, these references are still mutable, so pinning the "
            "action does not pin what it runs:", "",
            *[f"- `{u}`" for u in refs + images], "",
        ]
        if patch:
            lines += ["Suggested patch (tags resolved with `git ls-remote`; the version is kept as a "
                      "trailing comment so Dependabot and Renovate keep updating it):", "",
                      "```diff", patch.rstrip("\n"), "```", ""]
        if images:
            lines += ["Container images cannot be pinned with `git ls-remote`; pin them by digest, "
                      "e.g. `docker://ghcr.io/org/image@sha256:<digest>`.", ""]
        lines += ["Affected scanned repositories: " + ", ".join(f"`{r}`" for r in sorted(info["repos"])), ""]
        (notes_dir / name).write_text("\n".join(lines))
        out.append({"unit": label, "repos": len(info["repos"]), "note": f"notes/{name}",
                    "has_patch": bool(patch)})
    return out


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>actpin: transitive pinning report</title>
<style>
body{font:14px/1.45 system-ui,sans-serif;margin:2rem auto;max-width:1100px;padding:0 1rem;color:#222}
h1{margin-bottom:.2rem} .sub{color:#555;margin-top:0}
.cards{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}
.card{border:1px solid #ddd;border-radius:8px;padding:.7rem 1rem;min-width:150px}
.card b{display:block;font-size:1.6rem}
table{border-collapse:collapse;width:100%} td,th{border-bottom:1px solid #eee;padding:.35rem .4rem;text-align:left;vertical-align:top}
tr.repo{cursor:pointer} tr.repo:hover{background:#f6f6f6}
.pass{color:#2e7d32}.fail{color:#c62828}.warn{color:#b26a00;font-weight:600}
.chain{font:12px ui-monospace,monospace;background:#fafafa;padding:.3rem .5rem;margin:.2rem 0;border-left:3px solid #c62828}
.chain span{white-space:nowrap} .arrow{color:#999;margin:0 .3rem}
input,select{padding:.3rem;margin-right:.5rem}
</style></head><body>
<h1>Transitive SHA-pinning report</h1>
<p class="sub">Scan of __N__ public repositories with <code>actpin</code>. A repo passes the
<em>direct</em> SHA-pin policy when every <code>uses:</code> in its own workflows and local actions is a
full commit SHA. Rows marked <span class="warn">exposed</span> pass that policy yet run an unpinned action
or container image through a composite action, reusable workflow or Docker action. Click a row to see each chain.</p>
<div class="cards" id="cards"></div>
<p><input id="q" placeholder="filter repos"> <select id="f">
<option value="exposed">exposed only</option><option value="pass">passes direct policy</option>
<option value="all">all repos</option></select></p>
<table><thead><tr><th>Repository</th><th>Direct policy</th><th>Direct refs</th><th>Unpinned direct</th>
<th>Unpinned transitive</th><th>Max depth</th></tr></thead><tbody id="rows"></tbody></table>
<h2>Drafted maintainer notes (unsent)</h2><ul id="notes"></ul>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const S = D.summary, el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h !== undefined) e.innerHTML = h; return e; };
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
[[S.repos_scanned,'repos scanned'],[S.direct_policy_pass,'pass direct SHA pinning'],
 [S.direct_pass_but_transitive_unpinned,'of those still run unpinned code'],
 [S.github_policy_flags_in_those_repos,'direct-policy flags in those repos'],
 [S.total_transitive_unpinned_links,'unpinned transitive links']].forEach(([v,l]) => {
  const c = el('div','card'); c.append(el('b','',esc(v)), el('span','',esc(l))); cards.append(c); });
function render() {
  const q = document.getElementById('q').value.toLowerCase(), f = document.getElementById('f').value;
  rows.innerHTML = '';
  D.repos.filter(r => r.status === 'ok' && r.repo.toLowerCase().includes(q)
    && (f === 'all' || (f === 'pass' && r.direct_policy_pass) || (f === 'exposed' && r.exposed)))
   .forEach(r => {
    const tr = el('tr','repo');
    const pol = r.direct_policy_pass ? (r.exposed ? '<span class="warn">exposed</span>' : '<span class="pass">pass</span>') : '<span class="fail">fail</span>';
    tr.innerHTML = `<td><a href="https://github.com/${esc(r.repo)}">${esc(r.repo)}</a></td><td>${pol}</td><td>${r.direct_refs}</td><td>${r.direct_unpinned}</td><td>${r.transitive_unpinned}</td><td>${r.max_depth}</td>`;
    const det = el('tr'); det.style.display = 'none';
    const td = el('td'); td.colSpan = 6;
    r.chains.forEach(c => { const d = el('div','chain');
      d.innerHTML = c.path.map(h => `<span>${esc(h)}</span>`).join('<span class="arrow">&rarr;</span>') + ` <em>(${esc(c.state)})</em>`; td.append(d); });
    if (!r.chains.length) td.append(el('em','','no transitive findings'));
    det.append(td); tr.onclick = () => det.style.display = det.style.display ? '' : 'none';
    rows.append(tr, det); });
}
D.notes.forEach(n => { const li = el('li'); li.innerHTML = `<a href="${esc(n.note)}">${esc(n.unit)}</a>: used by ${n.repos} scanned repos${n.has_patch ? ', patch included' : ''}`; notes.append(li); });
q.oninput = render; f.onchange = render; render();
</script></body></html>
"""


def main():
    summary = json.loads((ROOT / "results" / "summary.json").read_text())
    scan = json.loads((ROOT / "results" / "scan.json").read_text())
    exposed = set(summary["direct_pass_but_transitive_unpinned_repos"])
    repos = []
    for r in scan:
        slim = {k: r.get(k) for k in ("repo", "status", "direct_policy_pass", "direct_refs",
                                       "direct_unpinned", "transitive_unpinned", "max_depth")}
        slim["exposed"] = r["repo"] in exposed
        slim["chains"] = [{"path": f["path"], "state": f["state"]} for f in r.get("findings", [])
                          if f["transitive"]]
        repos.append(slim)
    notes = build_notes(scan)
    data = json.dumps({"summary": summary, "repos": repos, "notes": notes}).replace("</", "<\\/")
    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(PAGE.replace("__N__", str(summary["repos_scanned"]))
                                     .replace("__DATA__", data))
    print(f"wrote docs/index.html and {len(notes)} notes")


if __name__ == "__main__":
    main()
