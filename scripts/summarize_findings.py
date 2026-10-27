"""Summarise a full trace into findings/ for review. Run after `fallout trace`.

Usage: summarize_findings.py LEDGER OUT_DIR [RW_CSV [PUBTYPES_JSON]]. With the Retraction
Watch CSV, the summary also counts trials in the population that the ledger has not
reached; with the PubMed publication types too, that population is `--population trials`.
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

from fallout.retractions import load_selection_data, read_records, select_population

ledger = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

syn = [e for e in ledger["edges"] if e["class"] in ("systematic_review", "meta_analysis", "guideline")]
after = [e for e in syn if e["cited_after_retraction"]]
# Publication dates can be year-only or lag acceptance, so also count a margin.
after_180 = [e for e in after if (e["days_after_retraction"] or 0) > 180]

def count(edges, key):
    return dict(Counter(key(e) for e in edges).most_common())


def inclusion(e):
    """Inclusion verdict, with strength for included_evidence, or "not checked"."""
    inc = e.get("inclusion") or {}
    v = inc.get("verdict", "not checked")
    return f"{v}:{inc['strength']}" if v == "included_evidence" and inc.get("strength") else v


ASSESSED = ("included_evidence", "excluded", "cited_outside_results", "reference_only", "reference_not_found")


def inclusion_summary(edges):
    assessed = [e for e in edges if (e.get("inclusion") or {}).get("verdict") in ASSESSED]
    inc = [e for e in assessed if e["inclusion"]["verdict"] == "included_evidence"]
    table = [e for e in inc if e["inclusion"].get("strength") == "table"]
    return {
        "by_verdict": count(edges, inclusion),
        "full_text_read": len(assessed),
        "included_evidence": len(inc),
        "included_evidence_from_table": len(table),
        "distinct_syntheses_full_text_read": len({e["citing"]["openalex_id"] for e in assessed}),
        "distinct_syntheses_with_included_evidence": len({e["citing"]["openalex_id"] for e in inc}),
        "distinct_syntheses_with_table_evidence": len({e["citing"]["openalex_id"] for e in table}),
        "trials_with_table_evidence": len({e["trial"] for e in table}),
    }

summary = {
    "generated_at": ledger.get("generated_at"),
    "trials": dict(Counter(t.get("status") for t in ledger["trials"].values())),
    "trials_by_selection": dict(Counter(t.get("selected_by") or "article_type" for t in ledger["trials"].values()).most_common()),
    "trial_errors": dict(Counter((t.get("error") or "")[:80] for t in ledger["trials"].values() if t.get("status") == "error").most_common(10)),
    # Trials that hit trace --max-citing: OpenAlex may hold more citing works than the ledger.
    "trials_citing_may_be_truncated": sum(1 for t in ledger["trials"].values() if t.get("citing_may_be_truncated")),
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
    "inclusion_all_synthesis_citations": inclusion_summary(syn),
    "inclusion_after_retraction": inclusion_summary(after),
    "inclusion_more_than_180d_after": inclusion_summary(after_180),
    "after_retraction_by_publication_year": dict(sorted(Counter((e["citing"]["publication_date"] or "")[:4] for e in after).items())),
}
if len(sys.argv) > 3:
    pubtypes, signals = load_selection_data(sys.argv[4]) if len(sys.argv) > 4 else (None, None)
    selected = select_population(read_records(sys.argv[3]), "trials" if pubtypes is not None else "clinical-study",
                                 pubtypes, abstract_signals=signals)
    population = {t.key for t in selected}
    summary["population"] = "trials" if pubtypes is not None else "clinical-study"
    summary["population_by_selection"] = dict(Counter(t.selected_by for t in selected).most_common())
    summary["trials_in_population"] = len(population)
    summary["trials_untraced"] = len(population - ledger["trials"].keys())
    # Errored trials are retried on the next run, so they are not finished either.
    summary["trials_pending_retry"] = sum(1 for t in ledger["trials"].values() if t.get("status") == "error")
(out / "summary.json").write_text(json.dumps(summary, indent=2))

fields = ["trial", "class", "class_confidence", "days_after_retraction", "citing_doi", "citing_openalex_id", "citing_publication_date",
          "citing_title", "inclusion_verdict", "inclusion_strength", "inclusion_signals", "inclusion_source"]
with open(out / "syntheses_citing_after_retraction.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for e in sorted(after, key=lambda e: -(e["days_after_retraction"] or 0)):
        c = e["citing"]
        w.writerow({"trial": e["trial"], "class": e["class"], "class_confidence": e["class_confidence"],
                    "days_after_retraction": e["days_after_retraction"], "citing_doi": c["doi"],
                    "citing_openalex_id": c["openalex_id"], "citing_publication_date": c["publication_date"],
                    "citing_title": c["title"], "inclusion_verdict": (e.get("inclusion") or {}).get("verdict"),
                    "inclusion_strength": (e.get("inclusion") or {}).get("strength"),
                    "inclusion_signals": "; ".join((e.get("inclusion") or {}).get("signals") or []),
                    "inclusion_source": (e.get("inclusion") or {}).get("source")})
print(json.dumps(summary, indent=2))
