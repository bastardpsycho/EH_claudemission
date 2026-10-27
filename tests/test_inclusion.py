import xml.etree.ElementTree as ET

from fallout import inclusion as I

# Hand-built after the JATS layout of a BMC meta-analysis in PMC (PMC6366034): numbered secs,
# a characteristics table naming studies as "Surname (year)" without xrefs, element-citations.
ARTICLE = """<article><front><article-meta><article-id pub-id-type="pmc">111</article-id></article-meta></front>
<body>
 <sec id="s1"><title>Introduction</title><p>Earlier trials <xref ref-type="bibr" rid="r1">1</xref>.</p></sec>
 <sec id="s2"><title>Results</title>
  <sec id="s2a"><title>Pregnancy rate</title><p>Three studies <xref ref-type="bibr" rid="r2">2</xref>&#8211;<xref ref-type="bibr" rid="r4">4</xref> reported it.</p></sec>
  <table-wrap id="t1"><label>Table 1</label><caption><title>Characteristics of the studies included in the review</title></caption>
   <table><tbody><tr><td>Abu Hashim (2010)</td><td>Egypt</td></tr><tr><td>Diaz (2013)</td><td>Spain</td></tr></tbody></table></table-wrap>
  <table-wrap id="t2"><label>Table 2</label><caption><title>Characteristics of excluded studies</title></caption>
   <table><tbody><tr><td><xref ref-type="bibr" rid="r5">Evans</xref></td><td>wrong comparator</td></tr></tbody></table></table-wrap>
 </sec>
 <sec id="s3"><title>Discussion</title><p>As Brown found <xref ref-type="bibr" rid="r2">2</xref>.</p></sec>
</body>
<back><ref-list>
 <ref id="r1"><element-citation><person-group><name><surname>Abu Hashim</surname></name></person-group><year>2010</year><pub-id pub-id-type="doi">10.1000/T1</pub-id></element-citation></ref>
 <ref id="r2"><element-citation><person-group><name><surname>Brown</surname></name></person-group><year>2011</year><pub-id pub-id-type="pmid">222</pub-id></element-citation></ref>
 <ref id="r3"><element-citation><person-group><name><surname>Chen</surname></name></person-group><year>2012</year><pub-id pub-id-type="doi">10.1000/t3</pub-id></element-citation></ref>
 <ref id="r4"><element-citation><person-group><name><surname>Diaz</surname></name></person-group><year>2013</year></element-citation></ref>
 <ref id="r5"><element-citation><person-group><name><surname>Evans</surname></name></person-group><year>2014</year><pub-id pub-id-type="doi">10.1000/t5</pub-id></element-citation></ref>
 <ref id="r6"><element-citation><person-group><name><surname>Fox</surname></name></person-group><year>2015</year><article-title>A randomised trial of drug Z for chronic pain in older adults</article-title></element-citation></ref>
</ref-list>
<ref-list><title>Included studies</title>
 <ref id="r7"><element-citation><person-group><name><surname>Gray</surname></name></person-group><year>2016</year><pub-id pub-id-type="doi">10.1000/t7</pub-id></element-citation></ref>
</ref-list></back></article>"""


def art(xml=ARTICLE):
    return ET.fromstring(xml)


def verdict(trial):
    return I.assess(art(), trial)


def test_characteristics_table_counts_as_inclusion():
    r = verdict({"doi": "10.1000/t1"})
    assert r["verdict"] == I.INCLUDED and r["ref_match"] == "doi" and r["strength"] == "table"
    assert "table: Table 1 Characteristics of the studies included in the review" in r["signals"]
    assert "section: Introduction" in r["signals"]


def test_results_citation_inside_a_range():
    r = verdict({"doi": "10.1000/t3"})
    assert r["verdict"] == I.INCLUDED
    assert r["signals"] == ["Results: Results > Pregnancy rate"] and r["strength"] == "results_citation"


def test_discussion_only_and_pmid_match():
    # Brown is also the start of the Results range, so check a trial cited only in the Discussion.
    xml = ARTICLE.replace('<xref ref-type="bibr" rid="r2">2</xref>&#8211;', '<xref ref-type="bibr" rid="r3">3</xref>&#8211;')
    r = I.assess(art(xml), {"pmid": "222"})
    assert r["verdict"] == I.OUTSIDE_RESULTS and r["ref_match"] == "pmid"
    assert r["signals"] == ["section: Discussion"]


def test_excluded_table_reference_only_and_not_found():
    assert verdict({"doi": "10.1000/t5"})["verdict"] == I.EXCLUDED
    r = verdict({"title": "A randomized trial of drug Z for chronic pain in older adults"})
    assert (r["verdict"], r["ref_match"]) == (I.REFERENCE_ONLY, "title")
    assert verdict({"doi": "10.1000/absent"})["verdict"] == I.NOT_FOUND


def test_included_studies_reference_list():
    r = verdict({"doi": "10.1000/t7"})
    assert r["verdict"] == I.INCLUDED and r["signals"] == ["reference list: Included studies"]


def test_no_body_means_no_full_text():
    assert I.assess(art("<article><front/><back/></article>"), {"doi": "10.1000/t1"})["verdict"] == I.NO_FULL_TEXT


class FakePMC:
    requests_made = 2

    def pmcids(self, dois):
        return {"10.9000/rev": "PMC111"} if "10.9000/rev" in dois else {}

    def articles(self, pmcids):
        return {"PMC111": art()} if "PMC111" in pmcids else {}


def test_verify_inclusion_marks_edges():
    def edge(trial, doi, cls="meta_analysis"):
        return {"trial": trial, "class": cls, "citing": {"doi": doi}}
    ledger = {
        "trials": {"rw:1": {"doi": "10.1000/t1"}, "rw:2": {"doi": "10.1000/t5"}},
        "edges": [edge("rw:1", "10.9000/rev"), edge("rw:2", "10.9000/rev"), edge("rw:1", "10.9000/closed"),
                  edge("rw:1", "10.9000/narrative", cls="other")],
    }
    out = I.verify_inclusion(ledger, FakePMC())
    assert out["syntheses_checked"] == 2 and out["with_pmcid"] == 1
    assert out["edges_by_verdict"] == {I.NO_PMC: 1, I.INCLUDED: 1, I.EXCLUDED: 1}
    e = ledger["edges"]
    assert e[0]["inclusion"]["source"] == "PubMed Central full text PMC111 (NCBI efetch)"
    assert e[2]["inclusion"]["verdict"] == I.NO_PMC
    assert "inclusion" not in e[3]
    # Checked edges are skipped next time unless recheck is set.
    assert I.verify_inclusion(ledger, FakePMC())["syntheses_checked"] == 0
    assert I.verify_inclusion(ledger, FakePMC(), recheck=True)["syntheses_checked"] == 2


def test_short_surnames_match_whole_words_only():
    xml = """<article><body><table-wrap><caption><title>Characteristics of included studies</title></caption>
    <table><tbody><tr><td>Liu (2015)</td></tr><tr><td>Clinical trial, 2015</td></tr></tbody></table></table-wrap></body>
    <back><ref-list><ref id="a"><element-citation><person-group><name><surname>Li</surname></name></person-group>
    <year>2015</year><pub-id pub-id-type="doi">10.1000/li</pub-id></element-citation></ref></ref-list></back></article>"""
    assert I.assess(art(xml), {"doi": "10.1000/li"})["verdict"] == I.REFERENCE_ONLY
    assert I.assess(art(xml.replace("Liu (2015)", "Li et al. (2015)")), {"doi": "10.1000/li"})["verdict"] == I.INCLUDED


def test_cli_checks_in_chunks_and_saves(tmp_path, monkeypatch):
    import json
    from fallout import cli, ledger as L
    led = L.new_ledger()
    led["trials"] = {"rw:1": {"doi": "10.1000/t1"}}
    led["edges"] = [{"trial": "rw:1", "class": "meta_analysis", "citing": {"doi": f"10.9000/r{i}"}} for i in range(5)]
    L.save(led, tmp_path / "l.json")
    monkeypatch.setattr(cli, "PMCClient", lambda email=None: FakePMC())
    assert cli.main(["inclusion", "--ledger", str(tmp_path / "l.json"), "--chunk", "2"]) == 0
    saved = json.loads((tmp_path / "l.json").read_text())
    assert all(e["inclusion"]["verdict"] == I.NO_PMC for e in saved["edges"])


def test_included_studies_sections_and_summary_tables():
    base = """<article><body>{body}</body><back><ref-list><ref id="a"><element-citation><person-group><name>
    <surname>Park</surname></name></person-group><year>2011</year><pub-id pub-id-type="doi">10.1000/p</pub-id>
    </element-citation></ref></ref-list></back></article>"""
    sec = '<sec><title>Description of included studies</title><p>See <xref ref-type="bibr" rid="a">1</xref>.</p></sec>'
    r = I.assess(art(base.format(body=sec)), {"doi": "10.1000/p"})
    assert (r["verdict"], r["strength"]) == (I.INCLUDED, "table")
    # "Inclusion criteria" is about eligibility, not about which studies were included.
    crit = '<sec><title>Methods</title><sec><title>Inclusion criteria</title><p><xref ref-type="bibr" rid="a">1</xref></p></sec></sec>'
    assert I.assess(art(base.format(body=crit)), {"doi": "10.1000/p"})["verdict"] == I.OUTSIDE_RESULTS
    table = ('<table-wrap><label>Table 4</label><caption><title>Summary of the studies of the association</title></caption>'
             '<table><tbody><tr><td>Park 2011</td></tr></tbody></table></table-wrap>')
    assert I.assess(art(base.format(body=table)), {"doi": "10.1000/p"})["verdict"] == I.INCLUDED
