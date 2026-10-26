import json
from datetime import date
import xml.etree.ElementTree as ET
from pathlib import Path

from fallout import ledger as L
from fallout.openalex import OpenAlexClient
from fallout.report import render_all
from fallout.retractions import read_records, select_retracted_trials

FIX = Path(__file__).parent / "fixtures" / "rw_sample.csv"


def build(fake, tmp_path):
    trials = select_retracted_trials(read_records(str(FIX)))
    led = L.new_ledger()
    client = OpenAlexClient(session=fake, min_interval=0)
    n = L.trace(led, trials, client)
    return led, n, client, trials


def test_trace_edges_and_timing(fake, tmp_path):
    led, n, _, _ = build(fake, tmp_path)
    assert n == 2
    assert led["trials"]["rw:1"]["status"] == "traced"
    assert led["trials"]["rw:6"]["status"] == "no_doi"
    edges = {e["citing"]["openalex_id"].rsplit("/", 1)[-1]: e for e in led["edges"]}
    assert set(edges) == {"W10", "W11", "W12", "W13", "W14"}
    assert all(e["relation"] == "cites" for e in led["edges"])
    ma = edges["W10"]
    assert ma["class"] == "meta_analysis"
    assert ma["cited_after_retraction"] is True
    assert ma["days_after_retraction"] == (date(2022, 1, 10) - date(2020, 3, 15)).days
    assert edges["W13"]["cited_after_retraction"] is False
    assert edges["W12"]["class"] == "guideline"
    assert edges["W14"]["class"] == "other"
    s = L.stats(led)
    assert s["synthesis_edges"] == 3
    assert s["synthesis_edges_after_retraction"] == 2
    assert s["trials_cited_by_a_synthesis"] == 1


def test_resumable_and_idempotent(fake, tmp_path):
    led, _, client, trials = build(fake, tmp_path)
    path = tmp_path / "ledger.json"
    L.save(led, path)
    again = L.load(path)
    assert L.trace(again, trials, client) == 0
    L.trace(again, trials, client, retrace=True)
    assert len(again["edges"]) == 5


def test_errors_are_recorded_not_raised(tmp_path):
    class Boom:
        def get_json(self, url):
            raise TimeoutError("slow")
    trials = select_retracted_trials(read_records(str(FIX)))
    led = L.new_ledger()
    L.trace(led, trials, OpenAlexClient(session=Boom(), min_interval=0))
    assert led["trials"]["rw:1"]["status"] == "error"


def test_render(fake, tmp_path):
    led, *_ = build(fake, tmp_path)
    out = render_all(led, tmp_path / "site")
    assert out["csv_rows"] == 5
    assert out["feed_entries"] == 2
    feed = ET.parse(tmp_path / "site" / "feed.xml").getroot()
    assert len(feed.findall("{http://www.w3.org/2005/Atom}entry")) == 2
    page = (tmp_path / "site" / "index.html").read_text()
    assert "included in any analysis has not been verified" in page
    assert "<script" not in page
    json.dumps(led)
