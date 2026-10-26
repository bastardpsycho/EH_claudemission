from fallout import ledger as ledger_mod
from fallout.pubmed import PubMedClient
from fallout.retractions import Retraction


class FakePost:
    """Serves responses shaped like NCBI's documented esummary JSON (retmode=json)."""

    def __init__(self, docs):
        self.docs = docs
        self.calls = []

    def post_form(self, url, data):
        self.calls.append(data)
        ids = data["id"].split(",")
        found = [i for i in ids if i in self.docs]
        result = {"uids": found}
        for i in found:
            result[i] = {"uid": i, "pubtype": self.docs[i]}
        return {"header": {"type": "esummary"}, "result": result}


def test_publication_types_batches_and_skips_missing():
    s = FakePost({"1": ["Journal Article", "Meta-Analysis"], "3": ["Practice Guideline"]})
    c = PubMedClient(session=s, min_interval=0)
    got = c.publication_types(["3", "1", "2", "", "x"], batch_size=2)
    assert got == {"1": ["Journal Article", "Meta-Analysis"], "3": ["Practice Guideline"]}
    assert [d["id"] for d in s.calls] == ["1,2", "3"]


def test_enrich_reclassifies_with_indexer_types(fake):
    from fallout.openalex import OpenAlexClient

    fake.citing["W1"][1]["ids"]["pmid"] = "https://pubmed.ncbi.nlm.nih.gov/111"  # "A randomised trial of drug D"
    fake.citing["W1"][4]["ids"]["pmid"] = "https://pubmed.ncbi.nlm.nih.gov/222"  # narrative review title
    led = ledger_mod.new_ledger()
    trial = next(t for t in _trials())
    ledger_mod.trace_trial(led, trial, OpenAlexClient(session=fake, min_interval=0))
    before = {e["citing"]["openalex_id"].rsplit("/", 1)[-1]: e["class"] for e in led["edges"]}
    assert before["W11"] == "other" and before["W14"] == "other"

    pm = PubMedClient(session=FakePost({"111": ["Journal Article"], "222": ["Systematic Review", "Review"]}), min_interval=0)
    res = ledger_mod.enrich_pubmed(led, pm)
    after = {e["citing"]["openalex_id"].rsplit("/", 1)[-1]: e for e in led["edges"]}
    assert res == {"pmids_requested": 2, "pmids_found": 2, "edges_reclassified": 1}
    assert after["W14"]["class"] == "systematic_review" and after["W14"]["class_confidence"] == "high"
    assert after["W11"]["class"] == "other" and after["W11"]["citing"]["pubmed_types"] == ["Journal Article"]


def _trials():
    from datetime import date
    yield Retraction(record_id="1", title="Trial of drug A versus placebo", journal="J", publisher="P",
                     article_types=["Clinical Study"], nature="Retraction", reasons=[], doi="10.1000/trial.1",
                     pmid=None, original_date=date(2015, 6, 1), retraction_date=date(2018, 1, 1), retraction_doi=None)
