"""Summarise a full trace into findings/ for review. Run after `fallout trace`."""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ledger = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

syn = [e for e in ledger["edges"] if e["class"] in ("systematic_review", "meta_analysis", "guideline")]
after = [e for e in syn if e["cited_after_retraction"]]
# Publication dates can be year-only or lag acceptance, so also count a margin.
after_180 = [e for e in after if (e["days_after_retraction"] or 0) > 180]

def count(edges, key):
    return dict(Counter(key(e) for e in edges).most_common())

summary = {
    "generated_at": ledger.get("generated_at"),
    "trials": dict(Counter(t.get("status") for t in ledger["trials"].values())),
    "trial_errors": dict(Counter((t.get("error") or "")[:80] for t in ledger["trials"].values() if t.get("status") == "error").most_common(10)),
    "trials_by_retraction_year": dict(sorted(Counter((t.get("retraction_date") or "")[:4] for t in ledger["trials"].values()).items())),
    "citing_edges": len(ledger["edges"]),
    "synthesis_edges": len(syn),
    "synthesis_edges_by_class": count(syn, lambda e: e["class"]),
    "synthesis_edges_by_confidence": count(syn, lambda e: e["class_confidence"]),
    "synthesis_edges_after_retraction": len(after),
    "synthesis_edges_after_retraction_by_class": count(after, lambda e: e["class"]),
    "synthesis_edges_more_than_180d_after": len(after_180),
    "distinct_syntheses_citing_after_retraction": len({e["citing"]["openalex_id"] for e in after}),
    "distinct_syntheses_citing_more_than_180d_after": len({e["citing"]["openalex_id"] for e in after_180}),
    "trials_cited_by_a_synthesis": len({e["trial"] for e in syn}),
    "trials_cited_by_a_synthesis_after_retraction": len({e["trial"] for e in after}),
    "after_retraction_by_publication_year": dict(sorted(Counter((e["citing"]["publication_date"] or "")[:4] for e in after).items())),
}
(out / "summary.json").write_text(json.dumps(summary, indent=2))

fields = ["trial", "class", "class_confidence", "days_after_retraction", "citing_doi", "citing_openalex_id", "citing_publication_date", "citing_title"]
with open(out / "syntheses_citing_after_retraction.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for e in sorted(after, key=lambda e: -(e["days_after_retraction"] or 0)):
        c = e["citing"]
        w.writerow({"trial": e["trial"], "class": e["class"], "class_confidence": e["class_confidence"],
                    "days_after_retraction": e["days_after_retraction"], "citing_doi": c["doi"],
                    "citing_openalex_id": c["openalex_id"], "citing_publication_date": c["publication_date"],
                    "citing_title": c["title"]})
print(json.dumps(summary, indent=2))
