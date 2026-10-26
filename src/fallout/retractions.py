"""Load and filter the Retraction Watch database (distributed by Crossref).

The CSV is published at RW_CSV_URL and updated on working days. Its licence is
not stated on Crossref's documentation page, so Fallout downloads it at run
time and never redistributes it.

Retraction Watch's ``ArticleType`` labels are an imperfect proxy for
"randomised controlled trial": "Clinical Study" covers non-randomised studies
too, and some RCTs are labelled "Research Article". Treat counts as
approximate.
"""

from __future__ import annotations

import csv
import io
import re
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, Iterator

RW_CSV_URL = "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv"
DEFAULT_ARTICLE_TYPES = ("Clinical Study",)

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)
_DOI_SHAPE = re.compile(r"^10\.\d{4,9}/\S+$")


def normalize_doi(raw: str | None) -> str | None:
    """Lowercase a DOI and strip URL/``doi:`` prefixes. Returns None if it is not DOI-shaped."""
    if not raw:
        return None
    doi = _DOI_PREFIX.sub("", raw.strip()).strip().lower()
    return doi if _DOI_SHAPE.match(doi) else None


def normalize_pmid(raw: str | None) -> str | None:
    """Retraction Watch uses ``0`` / ``00000000`` for a missing PubMed ID."""
    if not raw:
        return None
    digits = raw.strip()
    if not digits.isdigit() or int(digits) == 0:
        return None
    return str(int(digits))


def parse_rw_date(raw: str | None) -> date | None:
    """Parse Retraction Watch dates such as ``4/1/2026 0:00``."""
    if not raw or not raw.strip():
        return None
    text = raw.strip().split(" ")[0]
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _split(raw: str | None) -> list[str]:
    return [part.strip() for part in (raw or "").split(";") if part.strip()]


@dataclass
class Retraction:
    record_id: str
    title: str
    journal: str
    publisher: str
    article_types: list[str]
    nature: str
    reasons: list[str]
    doi: str | None
    pmid: str | None
    original_date: date | None
    retraction_date: date | None
    retraction_doi: str | None
    countries: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"rw:{self.record_id}"

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "record_id": self.record_id,
            "title": self.title,
            "journal": self.journal,
            "publisher": self.publisher,
            "article_types": self.article_types,
            "nature": self.nature,
            "reasons": self.reasons,
            "doi": self.doi,
            "pmid": self.pmid,
            "original_date": self.original_date.isoformat() if self.original_date else None,
            "retraction_date": self.retraction_date.isoformat() if self.retraction_date else None,
            "retraction_doi": self.retraction_doi,
            "countries": self.countries,
        }


def _row_to_retraction(row: dict) -> Retraction:
    # The published CSV starts with a UTF-8 BOM; utf-8-sig strips it, but be defensive.
    record_id = row.get("Record ID") or row.get("﻿Record ID") or ""
    return Retraction(
        record_id=record_id.strip(),
        title=(row.get("Title") or "").strip(),
        journal=(row.get("Journal") or "").strip(),
        publisher=(row.get("Publisher") or "").strip(),
        article_types=_split(row.get("ArticleType")),
        nature=(row.get("RetractionNature") or "").strip(),
        reasons=[r.lstrip("+") for r in _split(row.get("Reason"))],
        doi=normalize_doi(row.get("OriginalPaperDOI")),
        pmid=normalize_pmid(row.get("OriginalPaperPubMedID")),
        original_date=parse_rw_date(row.get("OriginalPaperDate")),
        retraction_date=parse_rw_date(row.get("RetractionDate")),
        retraction_doi=normalize_doi(row.get("RetractionDOI")),
        countries=_split(row.get("Country")),
    )


def read_records(source: str | io.TextIOBase) -> Iterator[Retraction]:
    """Yield every record from a path, an http(s) URL, or an open text stream."""
    if isinstance(source, str) and source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=120) as resp:
            text = resp.read().decode("utf-8-sig")
        stream: io.TextIOBase = io.StringIO(text)
    elif isinstance(source, str):
        stream = open(source, encoding="utf-8-sig", newline="")
    else:
        stream = source
    try:
        for row in csv.DictReader(stream):
            yield _row_to_retraction(row)
    finally:
        if isinstance(source, str):
            stream.close()


def select_retracted_trials(
    records: Iterable[Retraction],
    article_types: Iterable[str] | None = DEFAULT_ARTICLE_TYPES,
) -> list[Retraction]:
    """Keep full retractions of the given article types, minus papers later reinstated.

    ``article_types=None`` keeps every type. Records without a DOI are kept (they
    are counted) but cannot be traced through OpenAlex.
    """
    records = list(records)
    wanted = {t.lower() for t in article_types} if article_types else None
    reinstated = {r.doi for r in records if r.nature == "Reinstatement" and r.doi}
    out = []
    for rec in records:
        if rec.nature != "Retraction":
            continue
        if wanted is not None and not wanted.intersection(t.lower() for t in rec.article_types):
            continue
        if rec.doi and rec.doi in reinstated:
            continue
        out.append(rec)
    return out


def summarize(all_records: list[Retraction], selected: list[Retraction]) -> dict:
    by_year = Counter(r.retraction_date.year for r in selected if r.retraction_date)
    reasons = Counter(reason for r in selected for reason in r.reasons)
    return {
        "records_total": len(all_records),
        "by_nature": dict(Counter(r.nature for r in all_records).most_common()),
        "selected": len(selected),
        "selected_with_doi": sum(1 for r in selected if r.doi),
        "selected_with_pmid": sum(1 for r in selected if r.pmid),
        "selected_unique_doi": len({r.doi for r in selected if r.doi}),
        "retraction_year_counts": dict(sorted(by_year.items())),
        "top_reasons": dict(reasons.most_common(10)),
    }
