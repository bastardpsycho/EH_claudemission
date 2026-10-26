"""The exposure ledger: which works cite each retracted trial, and when.

Every edge has ``relation: "cites"``. Fallout never records that a trial was
*included in an analysis*; that is a separate, unverified question.
See docs/ledger-schema.md for the format.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from .classify import SYNTHESIS_CLASSES, classify
from .openalex import OpenAlexClient
from .retractions import Retraction, normalize_doi

SCHEMA = "fallout.ledger/1"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_ledger() -> dict:
    return {
        "schema": SCHEMA,
        "generated_at": _now(),
        "sources": {
            "retractions": "Retraction Watch database via Crossref (gitlab.com/crossref/retraction-watch-data)",
            "citations": "OpenAlex (api.openalex.org), filter=cites:",
        },
        "trials": {},
        "edges": [],
    }


def load(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return new_ledger()
    data = json.loads(p.read_text())
    if data.get("schema") != SCHEMA:
        raise ValueError(f"unsupported ledger schema: {data.get('schema')!r}")
    return data


def save(ledger: dict, path: str | Path) -> None:
    ledger["generated_at"] = _now()
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(ledger, indent=1, sort_keys=True))
    tmp.replace(p)


def _parse_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def make_edge(trial: Retraction, work: dict, first_seen: str) -> dict:
    title = work.get("display_name") or work.get("title") or ""
    cls = classify(title, work.get("type"))
    pub = _parse_date(work.get("publication_date"))
    after = days = None
    if pub and trial.retraction_date:
        days = (pub - trial.retraction_date).days
        after = days > 0
    return {
        "trial": trial.key,
        "relation": "cites",
        "citing": {
            "openalex_id": work.get("id"),
            "doi": normalize_doi(work.get("doi")),
            "title": title,
            "publication_date": pub.isoformat() if pub else None,
            "type": work.get("type"),
            "pmid": ((work.get("ids") or {}).get("pmid") or "").rsplit("/", 1)[-1] or None,
        },
        "class": cls.label,
        "class_confidence": cls.confidence,
        "class_reasons": cls.reasons,
        "cited_after_retraction": after,
        "days_after_retraction": days,
        "first_seen": first_seen,
    }


def trace_trial(ledger: dict, trial: Retraction, client: OpenAlexClient, max_citing: int | None = 2000) -> dict:
    """Look up one retracted trial and record every citing work. Idempotent per (trial, citing work)."""
    entry = trial.to_dict()
    entry["traced_at"] = _now()
    if not trial.doi:
        entry.update(status="no_doi", openalex_id=None, cited_by_count=None)
        ledger["trials"][trial.key] = entry
        return entry
    work = client.work_by_doi(trial.doi)
    if not work:
        entry.update(status="not_in_openalex", openalex_id=None, cited_by_count=None)
        ledger["trials"][trial.key] = entry
        return entry
    entry.update(status="traced", openalex_id=work.get("id"), cited_by_count=work.get("cited_by_count"))
    existing = {(e["trial"], e["citing"]["openalex_id"]) for e in ledger["edges"]}
    added = seen = 0
    for citing in client.citing_works(work["id"], max_results=max_citing):
        seen += 1
        if (trial.key, citing.get("id")) not in existing:
            ledger["edges"].append(make_edge(trial, citing, entry["traced_at"]))
            existing.add((trial.key, citing.get("id")))
            added += 1
    entry["edges_added"] = added
    # Hitting the cap means OpenAlex may hold more citing works than were fetched.
    entry["citing_may_be_truncated"] = max_citing is not None and seen >= max_citing
    ledger["trials"][trial.key] = entry
    return entry


def trace(
    ledger: dict,
    trials: list[Retraction],
    client: OpenAlexClient,
    limit: int | None = None,
    retrace: bool = False,
    max_citing: int | None = 2000,
    on_progress: Callable[[int, Retraction, dict], None] | None = None,
    checkpoint: Callable[[dict], None] | None = None,
    checkpoint_every: int = 25,
) -> int:
    """Trace trials not yet in the ledger (resumable). Returns the number traced in this call."""
    done = 0
    for trial in trials:
        if limit is not None and done >= limit:
            break
        if not retrace and trial.key in ledger["trials"]:
            continue
        try:
            entry = trace_trial(ledger, trial, client, max_citing=max_citing)
        except Exception as err:  # keep going; record the failure for a later retry
            entry = trial.to_dict()
            entry.update(status="error", error=f"{type(err).__name__}: {err}", traced_at=_now())
            ledger["trials"][trial.key] = entry
        done += 1
        if on_progress:
            on_progress(done, trial, entry)
        if checkpoint and done % checkpoint_every == 0:
            checkpoint(ledger)
    return done


def synthesis_edges(ledger: dict, after_retraction_only: bool = False) -> list[dict]:
    out = [e for e in ledger["edges"] if e["class"] in SYNTHESIS_CLASSES]
    if after_retraction_only:
        out = [e for e in out if e["cited_after_retraction"]]
    return out


def stats(ledger: dict) -> dict:
    trials = ledger["trials"].values()
    syn = synthesis_edges(ledger)
    by_class: dict[str, int] = {}
    for e in syn:
        by_class[e["class"]] = by_class.get(e["class"], 0) + 1
    exposed = {e["trial"] for e in syn}
    return {
        "trials_traced": sum(1 for t in trials if t.get("status") == "traced"),
        "trials_no_doi": sum(1 for t in trials if t.get("status") == "no_doi"),
        "trials_not_in_openalex": sum(1 for t in trials if t.get("status") == "not_in_openalex"),
        "trials_error": sum(1 for t in trials if t.get("status") == "error"),
        "citing_edges": len(ledger["edges"]),
        "synthesis_edges": len(syn),
        "synthesis_edges_by_class": by_class,
        "synthesis_edges_after_retraction": sum(1 for e in syn if e["cited_after_retraction"]),
        "trials_cited_by_a_synthesis": len(exposed),
    }
