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
