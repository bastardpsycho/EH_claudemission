"""Look for evidence, in open full text, that a synthesis included a retracted trial.

A ledger edge says a synthesis *cites* a trial. For syntheses with open full text
in PubMed Central, this module reads the JATS XML and records where the trial
appears:

- a row of a table about included studies or study characteristics;
- a citation inside the Results;
- a reference sub-list titled "included studies" (Cochrane style);
- or only an excluded-studies table or list, or only the Introduction or Discussion.

The verdict is evidence, not proof. A trial in a characteristics table was almost
certainly included in the review, but not necessarily pooled in a meta-analysis;
a trial cited only in the Discussion may still appear in a figure, which is not
read. Each verdict carries the signals it rests on and its source.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Callable, Iterable

from .classify import SYNTHESIS_CLASSES
from .retractions import normalize_doi, normalize_pmid

IDCONV_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

INCLUDED = "included_evidence"
EXCLUDED = "excluded"
OUTSIDE_RESULTS = "cited_outside_results"
REFERENCE_ONLY = "reference_only"
NOT_FOUND = "reference_not_found"
NO_FULL_TEXT = "no_open_full_text"
NO_PMC = "no_pmc_record"
# Verdicts that come from reading a full text, as opposed to not finding one.
ASSESSED = (INCLUDED, EXCLUDED, OUTSIDE_RESULTS, REFERENCE_ONLY, NOT_FOUND)

_INCLUDED_CAPTION = re.compile(r"includ|characteristic|\bsummary\s+of\s+(?:the\s+)?(?:\w+\s+){0,2}(?:studies|trials)\b", re.I)
_INCLUDED_SECTION = re.compile(r"\bincluded\s+(?:studies|trials|articles|reports|rcts)\b", re.I)
_EXCLUDED = re.compile(r"exclu", re.I)
_RESULTS = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?\s*)?results?\b", re.I)
_DASHES = {"-", "–", "—", "‒", "−"}
_WORD = re.compile(r"[a-z0-9]+")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _text(el: ET.Element | None) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def _child(el: ET.Element, name: str) -> ET.Element | None:
    return next((c for c in el if _local(c.tag) == name), None)


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _find_ref(article: ET.Element, trial: dict) -> tuple[ET.Element | None, str | None]:
    """The reference-list entry for the trial, and how it was matched (doi, pmid or title)."""
    doi, pmid = normalize_doi(trial.get("doi")), normalize_pmid(trial.get("pmid"))
    title = _words(trial.get("title") or "")
    best = None
    for ref in article.iter():
        if _local(ref.tag) != "ref":
            continue
        for pid in ref.iter():
            if _local(pid.tag) != "pub-id":
                continue
            kind, value = pid.get("pub-id-type"), (pid.text or "").strip()
            if doi and kind == "doi" and normalize_doi(value) == doi:
                return ref, "doi"
            if pmid and kind == "pmid" and normalize_pmid(value) == pmid:
                return ref, "pmid"
        if best is None and len(title) >= 5:
            art = next((t for t in ref.iter() if _local(t.tag) == "article-title"), None)
            cand = _words(_text(art)) if art is not None else set()
            if cand and len(title & cand) / len(title | cand) >= 0.8:
                best = ref
    return (best, "title") if best is not None else (None, None)


def _ref_ids_in_order(article: ET.Element) -> list[str]:
    return [r.get("id") for r in article.iter() if _local(r.tag) == "ref" and r.get("id")]


def _citing_xrefs(article: ET.Element, ref_id: str, order: list[str]) -> list[ET.Element]:
    """Every bibr xref that cites ref_id, including ranges written as <xref/>–<xref/>."""
    pos = {rid: i for i, rid in enumerate(order)}
    target = pos.get(ref_id)
    hits = []
    for parent in article.iter():
        kids = list(parent)
        for i, x in enumerate(kids):
            if _local(x.tag) != "xref" or x.get("ref-type") != "bibr":
                continue
            rids = (x.get("rid") or "").split()
            if ref_id in rids:
                hits.append(x)
                continue
            # A range: this xref, a dash, then the next xref.
            nxt = kids[i + 1] if i + 1 < len(kids) else None
            if (target is not None and nxt is not None and _local(nxt.tag) == "xref" and (x.tail or "").strip() in _DASHES
                    and rids and (nxt.get("rid") or "").split()):
                lo, hi = pos.get(rids[-1]), pos.get((nxt.get("rid") or "").split()[0])
                if lo is not None and hi is not None and lo < target < hi:
                    hits.append(x)
    return hits


def _ref_surname_year(ref: ET.Element) -> tuple[str | None, str | None]:
    surname = next((_text(s) for s in ref.iter() if _local(s.tag) == "surname"), None)
    year = next((_text(y)[:4] for y in ref.iter() if _local(y.tag) == "year"), None)
    return surname, year


def assess(article: ET.Element, trial: dict) -> dict:
    """Assess one synthesis full text (a JATS <article>) for one trial. See the module docstring."""
    if not any(_local(e.tag) == "body" for e in article.iter()):
        return {"verdict": NO_FULL_TEXT, "signals": []}
    ref, method = _find_ref(article, trial)
    if ref is None:
        return {"verdict": NOT_FOUND, "signals": []}
    ref_id = ref.get("id") or ""
    parents = {c: p for p in article.iter() for c in p}

    def ancestors(el):
        while el in parents:
            el = parents[el]
            yield el

    signals: list[str] = []
    included = excluded = cited = False
    strong = False  # a table row, included-studies section or included-studies reference list

    # Cochrane-style reference sub-lists: "Included studies", "Excluded studies".
    for anc in ancestors(ref):
        if _local(anc.tag) == "ref-list":
            title = _text(_child(anc, "title"))
            if _EXCLUDED.search(title):
                excluded = True
                signals.append(f"reference list: {title}")
            elif re.search(r"includ", title, re.I):
                included = strong = True
                signals.append(f"reference list: {title}")

    # Table rows that cite the trial or name its first author and year.
    surname, year = _ref_surname_year(ref)
    # Whole words only: a short surname such as "Li" must not match "Liu" or "clinical".
    named_re = (re.compile(rf"(?<!\w){re.escape(surname)}(?!\w).*?(?<!\d){year}(?!\d)", re.I | re.S)
                if surname and year and year.isdigit() else None)
    xrefs = _citing_xrefs(article, ref_id, _ref_ids_in_order(article))
    xref_set = set(xrefs)
    for tw in article.iter():
        if _local(tw.tag) != "table-wrap":
            continue
        caption = " ".join(x for x in (_text(_child(tw, "label")), _text(_child(tw, "caption"))) if x)
        for tr in tw.iter():
            if _local(tr.tag) != "tr":
                continue
            row = _text(tr)
            linked = any(x in xref_set for x in tr.iter())
            named = bool(named_re and named_re.search(row))
            if not (linked or named):
                continue
            cited = True
            if _EXCLUDED.search(caption):
                excluded = True
                signals.append(f"excluded-studies table: {caption[:120]}")
            elif _INCLUDED_CAPTION.search(caption):
                included = strong = True
                signals.append(f"table: {caption[:120]}")
            else:
                signals.append(f"other table: {caption[:120]}")
            break

    # Body citations, located by their section path.
    for x in xrefs:
        anc = list(ancestors(x))
        if any(_local(a.tag) in ("table-wrap", "ref-list") for a in anc):
            continue
        if any(_local(a.tag) == "fig" for a in anc):
            cited = True
            signals.append("figure caption")
            continue
        titles = [_text(_child(a, "title")) for a in reversed(anc) if _local(a.tag) == "sec"]
        path = " > ".join(t for t in titles if t) or "body"
        cited = True
        if titles and any(_EXCLUDED.search(t) for t in titles):
            excluded = True
            signals.append(f"section: {path[:120]}")
        elif any(_INCLUDED_SECTION.search(t) for t in titles):
            included = strong = True
            signals.append(f"included-studies section: {path[:120]}")
        elif titles and _RESULTS.match(titles[0]):
            included = True
            signals.append(f"Results: {path[:120]}")
        else:
            signals.append(f"section: {path[:120]}")

    signals = list(dict.fromkeys(signals))
    result = {"signals": signals[:8], "ref_match": method}
    if included:
        result["strength"] = "table" if strong else "results_citation"
        verdict = INCLUDED
    elif excluded:
        verdict = EXCLUDED
    elif cited:
        verdict = OUTSIDE_RESULTS
    else:
        verdict = REFERENCE_ONLY
    return {"verdict": verdict, **result}


class HttpSession:
    def __init__(self, user_agent: str, timeout: float = 120.0, retries: int = 4):
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = retries

    def get(self, url: str, data: dict | None = None, post: bool = False) -> bytes:
        """GET with ``data`` as the query string, or POST it as a form when ``post`` is set."""
        query = urllib.parse.urlencode(data or {})
        if post:
            req = urllib.request.Request(url, data=query.encode(), headers={"User-Agent": self.user_agent})
        else:
            req = urllib.request.Request(f"{url}?{query}" if query else url, headers={"User-Agent": self.user_agent})
        delay = 2.0
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.read()
            except (urllib.error.HTTPError, urllib.error.URLError) as err:
                code = getattr(err, "code", None)
                if attempt < self.retries and (code is None or code in (429, 500, 502, 503, 504)):
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        return b""


class PMCClient:
    """NCBI's PMC ID converter (DOI to PMCID) and efetch for PMC full-text XML."""

    def __init__(self, email: str | None = None, api_key: str | None = None, session=None,
                 min_interval: float | None = None, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        self.email = email or os.environ.get("NCBI_EMAIL") or os.environ.get("OPENALEX_MAILTO")
        self.api_key = api_key or os.environ.get("NCBI_API_KEY")
        self.session = session or HttpSession("fallout/0.1 (+https://github.com/bastardpsycho/EH_claudemission)")
        self.min_interval = min_interval if min_interval is not None else (0.11 if self.api_key else 0.35)
        self._sleep, self._clock, self._last = sleep, clock, float("-inf")
        self.requests_made = 0

    def _call(self, url: str, data: dict, post: bool = False) -> bytes:
        wait = self.min_interval - (self._clock() - self._last)
        if wait > 0:
            self._sleep(wait)
        self._last = self._clock()
        self.requests_made += 1
        data = {**data, "tool": "fallout"}
        if self.email:
            data["email"] = self.email
        return self.session.get(url, data, post=post)

    def pmcids(self, dois: Iterable[str], batch_size: int = 100) -> dict[str, str]:
        """Map DOI to PMCID ("PMC123") for the DOIs PMC holds. The converter accepts GET only."""
        ids = sorted({d for d in dois if d})
        out = {}
        for i in range(0, len(ids), batch_size):
            resp = json.loads(self._call(IDCONV_URL, {"ids": ",".join(ids[i:i + batch_size]), "format": "json"}))
            for rec in resp.get("records") or []:
                doi, pmcid = normalize_doi(rec.get("doi") or rec.get("requested-id")), rec.get("pmcid")
                if doi and pmcid:
                    out[doi] = pmcid
        return out

    def articles(self, pmcids: Iterable[str], batch_size: int = 20) -> dict[str, ET.Element]:
        """Fetch JATS <article> elements keyed by PMCID. Articles PMC cannot serve are left out."""
        ids = sorted({p for p in pmcids if p})
        out = {}
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            data = {"db": "pmc", "retmode": "xml", "id": ",".join(p.removeprefix("PMC") for p in batch)}
            if self.api_key:
                data["api_key"] = self.api_key
            root = ET.fromstring(self._call(EFETCH_URL, data, post=True))
            for art in (a for a in root.iter() if _local(a.tag) == "article"):
                for aid in art.iter():
                    if _local(aid.tag) == "article-id" and aid.get("pub-id-type") in ("pmc", "pmcid"):
                        out["PMC" + (aid.text or "").strip().removeprefix("PMC")] = art
                        break
        return out


def verify_inclusion(ledger: dict, client: PMCClient, limit: int | None = None, recheck: bool = False) -> dict:
    """Add an ``inclusion`` field to synthesis edges whose citing work has open full text in PMC.

    Works through up to ``limit`` distinct citing syntheses not yet checked (all with ``recheck``).
    Syntheses without a PMC record or open full text are marked so they are not retried every run.
    """
    pending: dict[str, list[dict]] = {}
    for e in ledger["edges"]:
        doi = e["citing"].get("doi")
        if e["class"] in SYNTHESIS_CLASSES and doi and (recheck or "inclusion" not in e):
            pending.setdefault(doi, []).append(e)
    dois = sorted(pending)[:limit] if limit is not None else sorted(pending)
    pmc = client.pmcids(dois)
    checked_at = _now()
    counts: dict[str, int] = {}

    def mark(edges, result):
        for e in edges:
            e["inclusion"] = {**result, "checked_at": checked_at}
            counts[result["verdict"]] = counts.get(result["verdict"], 0) + 1

    for doi in dois:
        if doi not in pmc:
            mark(pending[doi], {"verdict": NO_PMC, "signals": [], "source": "NCBI PMC ID converter"})
    found = sorted({pmc[d] for d in dois if d in pmc})
    for i in range(0, len(found), 20):
        arts = client.articles(found[i:i + 20])
        for doi in (d for d in dois if pmc.get(d) in found[i:i + 20]):
            art = arts.get(pmc[doi])
            source = f"PubMed Central full text {pmc[doi]} (NCBI efetch)"
            for e in pending[doi]:
                trial = ledger["trials"].get(e["trial"], {})
                result = assess(art, trial) if art is not None else {"verdict": NO_FULL_TEXT, "signals": []}
                mark([e], {**result, "source": source})
    return {"syntheses_checked": len(dois), "with_pmcid": len(found), "edges_by_verdict": counts,
            "requests": client.requests_made}
