#!/usr/bin/env python3
"""Plot the public-repo scan summary to docs/scan.png."""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main(summary=ROOT / "results" / "summary.json", out=ROOT / "docs" / "scan.png"):
    s = json.loads(Path(summary).read_text())
    passing = s["direct_policy_pass"]
    exposed = s["direct_pass_but_transitive_unpinned"]
    fig, ax = plt.subplots(figsize=(8, 3.4), dpi=130)
    labels = ["Direct SHA-pin policy\n(what GitHub checks)", "actpin\n(transitive closure)"]
    ax.barh(labels, [passing, passing - exposed], color=["#2e7d32", "#2e7d32"], label="clean")
    ax.barh(labels, [0, exposed], left=[passing, passing - exposed], color="#c62828",
            label="runs an unpinned transitive action or image")
    ax.text(passing + 0.5, 0, "0 flagged", va="center")
    ax.text(passing + 0.5, 1, f"{exposed} flagged", va="center", color="#c62828", fontweight="bold")
    ax.set_xlim(0, passing * 1.25)
    ax.invert_yaxis()
    ax.set_xlabel(f"Repos that pass direct SHA pinning (of {s['repos_with_workflows']} scanned with workflows)")
    ax.set_title(f"{exposed} of {passing} directly-pinned repos still run unpinned code transitively",
                 fontsize=11)
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
