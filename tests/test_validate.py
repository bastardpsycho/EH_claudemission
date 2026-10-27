import csv
from datetime import date

from fallout.retractions import Retraction
from fallout.validate import load_vitality, review_id, validate


def rec(rid, doi, types=("Clinical Study",), nature="Retraction"):
    return Retraction(record_id=rid, title="", journal="", publisher="", article_types=list(types), nature=nature,
                      reasons=[], doi=doi, pmid=None, original_date=None, retraction_date=date(2020, 1, 1),
                      retraction_doi=None)


def edge(trial, doi, cls, pub="2022-01-01"):
    return {"trial": trial, "class": cls, "citing": {"doi": doi, "publication_date": pub}}


def write_vitality(tmp_path):
    with open(tmp_path / "vitality_trials.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rct_id", "doi", "other_dois", "retraction_date", "publication_date", "paper_mill"])
        w.writerow(["1", "10.1/a", "", "", "", ""])
        w.writerow(["2", "10.1/old", "10.1/b", "", "", ""])  # matched through its second DOI
        w.writerow(["3", "10.1/c", "", "", "", ""])          # labelled Research Article in RW
        w.writerow(["4", "10.1/zz", "", "", "", ""])         # not in RW
        w.writerow(["5", "", "", "", "", ""])
        w.writerow(["6", "10.1/e", "", "", "", ""])          # in population, not traced
    with open(tmp_path / "vitality_inclusions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rct_id", "srfile", "review_doi", "ma_rows", "replicated", "max_retracted_in_ma", "review_title"])
        w.writerow(["1", "1_1", "10.9/r1", "2", "2", "1", "found as MA"])
        w.writerow(["1", "1_2", "10.9/r2", "1", "1", "1", "found but classed other"])
        w.writerow(["2", "2_1", "10.9/r3", "1", "1", "2", "cites trial 1 only"])
        w.writerow(["2", "2_2", "10.9/r4", "1", "1", "1", "absent"])
        w.writerow(["2", "2_3", "10.1002/14651858.cd000001.pub2", "1", "1", "1", "Cochrane, other version in ledger"])
        w.writerow(["3", "3_1", "10.9/r5", "1", "1", "1", "trial outside population"])
        w.writerow(["6", "6_1", "10.9/r6", "1", "1", "1", "trial not traced"])
        w.writerow(["1", "1_3", "", "1", "0", "1", "no DOI"])


def test_validate_against_vitality(tmp_path):
    write_vitality(tmp_path)
    trials, pairs = load_vitality(tmp_path)
    assert trials["2"]["dois"] == ["10.1/old", "10.1/b"]
    records = [rec("a", "10.1/a"), rec("b", "10.1/b"), rec("c", "10.1/c", types=("Research Article",)), rec("e", "10.1/e")]
    population = [r for r in records if "Clinical Study" in r.article_types]
    ledger = {
        "trials": {"rw:a": {"status": "traced"}, "rw:b": {"status": "traced"}},
        "edges": [
            {**edge("rw:a", "10.9/r1", "meta_analysis"), "inclusion": {"verdict": "included_evidence", "strength": "table"}},
            # r1 pooled only its index trial (rct 1), so this citation by trial 2 is a negative.
            {**edge("rw:b", "10.9/r1", "meta_analysis"), "inclusion": {"verdict": "cited_outside_results"}},
            edge("rw:a", "10.9/r2", "other"),
            edge("rw:a", "10.9/r3", "systematic_review"),
            edge("rw:b", "10.9/x", "systematic_review"),                     # not a VITALITY review
            edge("rw:b", "10.1002/14651858.cd000001.pub3", "meta_analysis", pub="2023-01-01"),
            edge("rw:b", "10.9/late", "meta_analysis", pub="2025-06-01"),     # after VITALITY's last search
        ],
    }
    summary, missed = validate(ledger, records, population, trials, pairs)

    pop = summary["population"]
    assert pop["in_fallout_population"] == 3
    assert pop["in_fallout_population_by_selection"] == {"article_type": 3}
    # a, b and e (retracted 2020) are in VITALITY; all three population records are in the window.
    assert pop["selection_share_in_vitality"]["article_type"] == {"trials": 3, "in_vitality": 3, "share": 1.0}
    assert pop["not_in_population_by_reason"] == {
        "RW type not Clinical Study, not added by PubMed type": 1, "DOI not in Retraction Watch": 1, "no DOI in VITALITY": 1}
    assert pop["index_trials"] == 4 and pop["index_trials_in_fallout_population"] == 3

    pr = summary["pairs"]
    assert pr["by_outcome"] == {"checkable: citation found": 2, "checkable: citation not found": 2,
                                "checkable: other Cochrane version found": 1,
                                "review has no DOI": 1, "trial not in Fallout population": 1, "trial not traced": 1}
    assert pr["checkable"] == 5
    assert pr["citation_recall"] == 0.4 and pr["citation_recall_any_cochrane_version"] == 0.6
    assert pr["synthesis_recall"] == 0.2 and pr["synthesis_recall_any_cochrane_version"] == 0.4
    reasons = {m["review_doi"]: m["reason"] for m in missed}
    assert reasons == {"10.9/r2": "found but classed as other", "10.9/r3": "review cites other trials in ledger",
                       "10.9/r4": "review not in ledger"}

    agree = summary["review_level_agreement"]
    # r1 and r3 are VITALITY reviews, x is not, .pub3 matches only ignoring the version,
    # the late one is out of window and r2 is not a synthesis.
    assert agree["synthesis_citations_of_vitality_trials"] == 5
    assert agree["in_vitality_reviews"] == 3
    assert agree["in_vitality_reviews_any_cochrane_version"] == 4
    assert agree["by_class"]["meta_analysis"] == {"citations": 3, "in_vitality": 2, "share": 0.6667,
                                                  "in_vitality_any_cochrane_version": 3, "share_any_cochrane_version": 1.0}

    inc = summary["inclusion_check"]
    assert inc["verified_pairs"] == {"by_verdict": {"included_evidence:table": 1}, "assessed": 1,
                                     "included_evidence": 1, "share_included_evidence": 1.0,
                                     "included_evidence_from_table": 1, "share_from_table": 1.0}
    assert inc["negatives"]["by_verdict"] == {"cited_outside_results": 1}
    assert inc["negatives"]["share_included_evidence"] == 0.0


def test_review_id_strips_only_cochrane_versions():
    assert review_id("10.1002/14651858.cd000567.pub7") == "10.1002/14651858.cd000567"
    assert review_id("10.1002/14651858.cd000567") == "10.1002/14651858.cd000567"
    assert review_id("10.1000/x.pub2") == "10.1000/x.pub2"
