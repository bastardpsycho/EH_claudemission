from pathlib import Path

from fallout.retractions import normalize_doi, normalize_pmid, parse_rw_date, read_records, select_retracted_trials, summarize

FIX = Path(__file__).parent / "fixtures" / "rw_sample.csv"


def test_normalizers():
    assert normalize_doi("https://doi.org/10.1000/ABC.1") == "10.1000/abc.1"
    assert normalize_doi("doi: 10.1000/x") == "10.1000/x"
    assert normalize_doi("not a doi") is None
    assert normalize_doi("") is None
    assert normalize_pmid("00000000") is None
    assert normalize_pmid("0") is None
    assert normalize_pmid("0012345") == "12345"
    assert parse_rw_date("4/1/2026 0:00").isoformat() == "2026-04-01"
    assert parse_rw_date("") is None


def test_read_handles_bom_and_fields():
    recs = list(read_records(str(FIX)))
    assert len(recs) == 6
    first = recs[0]
    assert first.record_id == "1"
    assert first.doi == "10.1000/trial.1"
    assert first.pmid == "12345678"
    assert first.reasons == ["Fabrication of Data", "Investigation by Journal/Publisher"]
    assert first.retraction_date.isoformat() == "2020-03-15"


def test_select_excludes_non_retractions_other_types_and_reinstated():
    recs = list(read_records(str(FIX)))
    keys = [r.key for r in select_retracted_trials(recs)]
    # 2: wrong type; 3: expression of concern; 4: later reinstated (record 5)
    assert keys == ["rw:1", "rw:6"]
    assert [r.key for r in select_retracted_trials(recs, None)] == ["rw:1", "rw:2", "rw:6"]


def test_summary_counts():
    recs = list(read_records(str(FIX)))
    sel = select_retracted_trials(recs)
    s = summarize(recs, sel)
    assert s["records_total"] == 6
    assert s["selected"] == 2
    assert s["selected_with_doi"] == 1
    assert s["by_nature"]["Retraction"] == 4


def _rec(rid, types, subjects=("(HSC) Medicine",), nature="Retraction", doi=None, pmid=None):
    from fallout.retractions import Retraction
    return Retraction(record_id=rid, title="", journal="", publisher="", article_types=list(types), nature=nature,
                      reasons=[], doi=doi or f"10.1/{rid}", pmid=pmid, original_date=None, retraction_date=None,
                      retraction_doi=None, subjects=list(subjects))


def test_subjects_are_read():
    assert list(read_records(str(FIX)))[0].subjects == ["(HSC) Medicine"]


def test_trials_population_adds_pubmed_typed_health_science_articles():
    import pytest
    from fallout.retractions import health_science_research_articles, select_population
    recs = [
        _rec("cs", ["Clinical Study"]),
        _rec("rct", ["Research Article"], pmid="1"),
        _rec("both", ["Research Article"], pmid="2"),
        _rec("cohort", ["Research Article"], pmid="3"),                          # PubMed: not a trial
        _rec("nopmid", ["Research Article"]),
        _rec("chem", ["Research Article"], subjects=["(BLS) Chemistry"], pmid="4"),  # not Health Sciences
        _rec("eoc", ["Research Article"], nature="Expression of concern", pmid="5"),
        _rec("back", ["Research Article"], pmid="6", doi="10.1/back"),
        _rec("reinst", ["Research Article"], nature="Reinstatement", doi="10.1/back"),
    ]
    pubtypes = {"1": ["Journal Article", "Randomized Controlled Trial"],
                "2": ["Clinical Trial", "Randomized Controlled Trial"],
                "3": ["Journal Article", "Observational Study"],
                "4": ["Randomized Controlled Trial"], "5": ["Randomized Controlled Trial"],
                "6": ["Randomized Controlled Trial"]}
    assert [r.record_id for r in health_science_research_articles(recs)] == ["rct", "both", "cohort", "nopmid"]

    default = select_population(recs)
    assert [(r.record_id, r.selected_by) for r in default] == [("cs", "article_type")]
    trials = select_population(recs, "trials", pubtypes)
    assert [(r.record_id, r.selected_by) for r in trials] == [
        ("cs", "article_type"), ("rct", "pubmed:Randomized Controlled Trial"), ("both", "pubmed:Randomized Controlled Trial")]
    assert recs[1].selected_by is None  # inputs are not mutated
    assert trials[1].to_dict()["selected_by"] == "pubmed:Randomized Controlled Trial"
    with pytest.raises(ValueError):
        select_population(recs, "trials")
    with pytest.raises(ValueError):
        select_population(recs, "everything", pubtypes)


def test_random_allocation_phrase():
    from fallout.retractions import random_allocation_phrase as f
    assert f("A total of 120 patients were randomly assigned to two groups.") == "randomly assigned"
    assert f("This randomized controlled trial enrolled 80 women.") == "randomized"
    assert f("Patients were randomly selected from the registry.") is None       # sampling, not allocation
    assert f("A non-randomized comparison in 40 patients.") is None
    assert f("Rats were randomly divided into four groups.") is None
    assert f("Rats were randomly divided; findings may help patients.") is None   # animal study
    assert f("A meta-analysis of randomized trials in patients.") is None
    assert f("Samples were randomized to two assays.") is None                   # no people
    assert f(None) is None


def test_trials_population_uses_abstract_signals_after_pubmed_types():
    from fallout.retractions import select_population
    recs = [_rec("typed", ["Research Article"], pmid="1"), _rec("abs", ["Research Article"], pmid="2"),
            _rec("none", ["Research Article"], pmid="3")]
    got = select_population(recs, "trials", {"1": ["Randomized Controlled Trial"]}, abstract_signals={"1": "randomized", "2": "randomly assigned"})
    assert [(r.record_id, r.selected_by) for r in got] == [
        ("typed", "pubmed:Randomized Controlled Trial"), ("abs", "abstract:randomly assigned")]
