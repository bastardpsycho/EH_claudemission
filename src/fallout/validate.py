"""Check the ledger against VITALITY Study I (Xu et al., BMJ 2025;389:e082068).

VITALITY screened forward citations of 1,330 retracted RCTs and verified, by full
text, which systematic reviews pooled them in a pairwise meta-analysis. That gives
a reference set Fallout can be measured against:

- population: how many VITALITY trials Fallout's Retraction Watch filter selects;
- recall: for each verified (trial, review) pair, whether the ledger holds that
  citation and labels the review a synthesis;
- review-level agreement: of the ledger's synthesis citations of VITALITY trials
  published before VITALITY's last search, how many are reviews VITALITY found
  pooling a retracted trial. If VITALITY's search was complete, this is an upper
  bound on how often "cites" means "pooled the cited trial in a pairwise
  meta-analysis"; reviews VITALITY missed push the true figure the other way.
  It is not the precision of Fallout's own "cites" claims.

Cochrane reviews have one DOI per version (``.pub2``, ``.pub3``...), and VITALITY
records one version. Matches are reported exactly and, separately, ignoring the
version; the second is generous, because an older version may not have pooled
the trial.

VITALITY files each review under one index trial, so a review that pooled several
retracted trials is listed against only one of them. Pairs are therefore checked
only for the index trial, and review-level agreement ignores which trial it is.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterable

from .classify import SYNTHESIS_CLASSES
from .retractions import Retraction

# Scopus forward citations were last updated on 21 November 2024 (Google Scholar 21 Nov–2 Dec 2024).
VITALITY_LAST_SEARCH = date(2024, 11, 21)

_COCHRANE_VERSION = re.compile(r"^(10\.1002/14651858\.[^.]+)\.pub\d+$")


def review_id(doi: str) -> str:
    """A DOI with any Cochrane version suffix removed."""
    m = _COCHRANE_VERSION.match(doi)
    return m.group(1) if m else doi


def load_vitality(directory: str | Path) -> tuple[dict[str, dict], list[dict]]:
    """Read vitality_trials.csv and vitality_inclusions.csv (see scripts/build_vitality_gold.py)."""
    d = Path(directory)
    with open(d / "vitality_trials.csv", encoding="utf-8", newline="") as f:
        trials = {}
        for row in csv.DictReader(f):
            row["dois"] = [x for x in [row["doi"], *row["other_dois"].split()] if x]
            trials[row["rct_id"]] = row
    with open(d / "vitality_inclusions.csv", encoding="utf-8", newline="") as f:
        pairs = list(csv.DictReader(f))
    return trials, pairs


def _ratio(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


def validate(
    ledger: dict,
    records: Iterable[Retraction],
    population: Iterable[Retraction],
    vitality_trials: dict[str, dict],
    pairs: list[dict],
    last_search: date = VITALITY_LAST_SEARCH,
) -> tuple[dict, list[dict]]:
    """Return a summary and one row per verified pair Fallout did not find as a synthesis citation."""
    pop_by_doi = {t.doi: t for t in population if t.doi}
    rw_by_doi: dict[str, list[Retraction]] = {}
    for r in records:
        if r.doi:
            rw_by_doi.setdefault(r.doi, []).append(r)

    # Map each VITALITY trial to a Fallout trial through any of its DOIs.
    fallout_key: dict[str, str] = {}
    selected_by: Counter = Counter()
    missing_reason: Counter = Counter()
    for rct_id, t in vitality_trials.items():
        hit = next((pop_by_doi[d] for d in t["dois"] if d in pop_by_doi), None)
        if hit:
            fallout_key[rct_id] = hit.key
            selected_by[hit.selected_by or "article_type"] += 1
        elif not t["dois"]:
            missing_reason["no DOI in VITALITY"] += 1
        else:
            rw = [r for d in t["dois"] for r in rw_by_doi.get(d, [])]
            if not rw:
                missing_reason["DOI not in Retraction Watch"] += 1
            elif not any("clinical study" in (a.lower() for a in r.article_types) for r in rw):
                missing_reason["RW type not Clinical Study, not added by PubMed type"] += 1
            else:
                missing_reason["excluded by nature or reinstatement"] += 1

    status = {k: v.get("status") for k, v in ledger["trials"].items()}
    by_trial: dict[str, dict[str, dict]] = {}
    by_trial_any_version: dict[str, dict[str, dict]] = {}
    review_dois_in_ledger = set()
    for e in ledger["edges"]:
        doi = e["citing"].get("doi")
        if doi:
            by_trial.setdefault(e["trial"], {})[doi] = e
            by_trial_any_version.setdefault(e["trial"], {})[review_id(doi)] = e
            review_dois_in_ledger.add(review_id(doi))

    # Recall over verified (index trial, review) pairs.
    found_cls: Counter = Counter()
    as_synthesis: Counter = Counter()  # keyed by whether the review DOI matched exactly
    outcome: Counter = Counter()
    missed = []
    for p in pairs:
        key = fallout_key.get(p["rct_id"])
        if not p["review_doi"]:
            outcome["review has no DOI"] += 1
            continue
        if key is None:
            outcome["trial not in Fallout population"] += 1
            continue
        if status.get(key) != "traced":
            outcome[f"trial {status.get(key) or 'not traced'}"] += 1
            continue
        edge = by_trial.get(key, {}).get(p["review_doi"])
        exact = edge is not None
        if edge is None:
            edge = by_trial_any_version.get(key, {}).get(review_id(p["review_doi"]))
        if edge is None:
            reason = "review cites other trials in ledger" if review_id(p["review_doi"]) in review_dois_in_ledger else "review not in ledger"
            outcome["checkable: citation not found"] += 1
            missed.append({**p, "fallout_trial": key, "reason": reason, "class": ""})
            continue
        outcome["checkable: citation found" if exact else "checkable: other Cochrane version found"] += 1
        found_cls[edge["class"]] += 1
        synthesis = edge["class"] in SYNTHESIS_CLASSES
        as_synthesis[exact] += synthesis
        if not synthesis:
            missed.append({**p, "fallout_trial": key, "reason": "found but classed as " + edge["class"], "class": edge["class"]})
    exact_found = outcome["checkable: citation found"]
    any_found = exact_found + outcome["checkable: other Cochrane version found"]
    checkable = any_found + outcome["checkable: citation not found"]

    # Review-level agreement on synthesis citations of VITALITY trials up to the last search.
    vitality_reviews = {p["review_doi"] for p in pairs if p["review_doi"]}
    vitality_review_ids = {review_id(d) for d in vitality_reviews}
    agree: Counter = Counter()
    agree_any: Counter = Counter()
    total: Counter = Counter()
    for key in set(fallout_key.values()):
        for doi, e in by_trial.get(key, {}).items():
            pub = e["citing"].get("publication_date")
            if e["class"] not in SYNTHESIS_CLASSES or not pub or date.fromisoformat(pub) > last_search:
                continue
            total[e["class"]] += 1
            agree[e["class"]] += doi in vitality_reviews
            agree_any[e["class"]] += review_id(doi) in vitality_review_ids

    index_trials = {p["rct_id"] for p in pairs}
    summary = {
        "reference": "VITALITY Study I, Xu et al. BMJ 2025;389:e082068; data https://osf.io/7eazq/ (CC BY 4.0)",
        "population": {
            "vitality_trials": len(vitality_trials),
            "in_fallout_population": len(fallout_key),
            "recall": _ratio(len(fallout_key), len(vitality_trials)),
            "in_fallout_population_by_selection": dict(selected_by.most_common()),
            "not_in_population_by_reason": dict(missing_reason.most_common()),
            "index_trials": len(index_trials),
            "index_trials_in_fallout_population": sum(1 for i in index_trials if i in fallout_key),
        },
        "pairs": {
            "verified_pairs": len(pairs),
            "by_outcome": dict(outcome.most_common()),
            "checkable": checkable,
            "citation_recall": _ratio(exact_found, checkable),
            "synthesis_recall": _ratio(as_synthesis[True], checkable),
            "citation_recall_any_cochrane_version": _ratio(any_found, checkable),
            "synthesis_recall_any_cochrane_version": _ratio(as_synthesis[True] + as_synthesis[False], checkable),
            "found_by_class": dict(found_cls.most_common()),
        },
        "review_level_agreement": {
            "last_search": last_search.isoformat(),
            "synthesis_citations_of_vitality_trials": sum(total.values()),
            "in_vitality_reviews": sum(agree.values()),
            "share": _ratio(sum(agree.values()), sum(total.values())),
            "in_vitality_reviews_any_cochrane_version": sum(agree_any.values()),
            "share_any_cochrane_version": _ratio(sum(agree_any.values()), sum(total.values())),
            "by_class": {c: {"citations": total[c], "in_vitality": agree[c], "share": _ratio(agree[c], total[c]),
                             "in_vitality_any_cochrane_version": agree_any[c],
                             "share_any_cochrane_version": _ratio(agree_any[c], total[c])}
                         for c in SYNTHESIS_CLASSES if total[c]},
        },
    }
    return summary, missed
