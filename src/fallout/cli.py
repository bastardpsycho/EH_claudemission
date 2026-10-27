"""Command-line interface: ``fallout retractions | pubtypes | trace | enrich | inclusion | report | impact | validate``."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import ledger as ledger_mod
from .inclusion import PMCClient, verify_inclusion
from .metaanalysis import effect_from_2x2, impact_without
from .openalex import OpenAlexClient
from .pubmed import PubMedClient
from .report import render_all
from .retractions import (
    DEFAULT_ARTICLE_TYPES, POPULATIONS, RW_CSV_URL, TRIAL_PUBLICATION_TYPES, health_science_research_articles,
    load_selection_data, random_allocation_phrase, read_records, select_population, summarize,
)
from .validate import load_vitality, validate


def _types(args) -> list[str] | None:
    return None if args.all_types else (args.type or list(DEFAULT_ARTICLE_TYPES))


def _population(args, records) -> list:
    pubtypes = signals = None
    if args.population == "trials":
        if not args.pubtypes:
            raise SystemExit("--population trials needs --pubtypes (written by `fallout pubtypes`)")
        pubtypes, signals = load_selection_data(args.pubtypes)
    return select_population(records, args.population, pubtypes, _types(args), signals)


def _add_source(p: argparse.ArgumentParser) -> None:
    p.add_argument("--csv", default=RW_CSV_URL, help="Retraction Watch CSV path or URL (default: Crossref's GitLab mirror)")
    p.add_argument("--type", action="append", help="ArticleType to keep (repeatable; default 'Clinical Study')")
    p.add_argument("--all-types", action="store_true", help="keep retractions of every article type")
    p.add_argument("--population", choices=POPULATIONS, default="clinical-study",
                   help="'trials' adds Health Sciences research articles that PubMed indexes as trials")
    p.add_argument("--pubtypes", help="JSON from `fallout pubtypes` (needed for --population trials)")


def cmd_retractions(args) -> int:
    records = list(read_records(args.csv))
    selected = _population(args, records)
    summary = summarize(records, selected)
    summary["article_types"] = _types(args) or "all"
    summary["population"] = args.population
    print(json.dumps(summary, indent=2))
    return 0


def cmd_pubtypes(args) -> int:
    records = list(read_records(args.csv))
    candidates = health_science_research_articles(records)
    client = PubMedClient(email=args.email)
    types = client.publication_types(r.pmid for r in candidates if r.pmid)
    typed = {r.pmid for r in candidates if r.pmid and set(types.get(r.pmid, [])) & set(TRIAL_PUBLICATION_TYPES)}
    # For candidates PubMed does not type as a trial, look for random allocation in the abstract.
    # Only the matched phrase is kept, not the abstract.
    abstracts = client.abstracts(r.pmid for r in candidates if r.pmid and r.pmid not in typed)
    signals = {pmid: phrase for pmid, text in abstracts.items() if (phrase := random_allocation_phrase(text))}
    out = {"source": "NCBI E-utilities esummary (publication types) and efetch (abstracts)",
           "fetched_at": ledger_mod._now(), "candidates": len(candidates), "pubtypes": types, "abstract_signals": signals}
    Path(args.out).write_text(json.dumps(out, sort_keys=True))
    print(json.dumps({"candidates": len(candidates), "with_pmid": sum(1 for r in candidates if r.pmid),
                      "pmids_found": len(types), "trial_typed": len(typed), "abstracts_read": len(abstracts),
                      "abstract_random_allocation": len(signals), "requests": client.requests_made}, indent=2))
    return 0


def cmd_trace(args) -> int:
    records = list(read_records(args.csv))
    trials = _population(args, records)
    # Most recently retracted first: those are likeliest to be cited by new syntheses.
    trials.sort(key=lambda r: (r.retraction_date is not None, r.retraction_date), reverse=True)
    led = ledger_mod.load(args.ledger)
    client = OpenAlexClient(mailto=args.mailto, cache_dir=args.cache_dir)

    def progress(n, trial, entry):
        print(f"[{n}] {trial.key} {entry.get('status')} edges+{entry.get('edges_added', 0)}", file=sys.stderr)

    n = ledger_mod.trace(
        led, trials, client, limit=args.limit, retrace=args.retrace, max_citing=args.max_citing,
        on_progress=progress, checkpoint=lambda l: ledger_mod.save(l, args.ledger),
    )
    ledger_mod.save(led, args.ledger)
    print(json.dumps({"traced_this_run": n, "requests": client.requests_made, **ledger_mod.stats(led)}, indent=2))
    return 0


def cmd_enrich(args) -> int:
    led = ledger_mod.load(args.ledger)
    client = PubMedClient(email=args.email)
    result = ledger_mod.enrich_pubmed(led, client)
    ledger_mod.save(led, args.ledger)
    print(json.dumps({**result, "requests": client.requests_made, **ledger_mod.stats(led)}, indent=2))
    return 0


def cmd_inclusion(args) -> int:
    led = ledger_mod.load(args.ledger)
    client = PMCClient(email=args.email)
    result = verify_inclusion(led, client, limit=args.limit, recheck=args.recheck)
    ledger_mod.save(led, args.ledger)
    print(json.dumps(result, indent=2))
    return 0


def cmd_report(args) -> int:
    led = ledger_mod.load(args.ledger)
    print(json.dumps(render_all(led, args.out_dir), indent=2))
    return 0


def cmd_validate(args) -> int:
    records = list(read_records(args.csv))
    population = _population(args, records)
    trials, pairs = load_vitality(args.vitality_dir)
    summary, missed = validate(ledger_mod.load(args.ledger), records, population, trials, pairs)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "vitality_summary.json").write_text(json.dumps(summary, indent=2))
    fields = ["rct_id", "fallout_trial", "review_doi", "reason", "class", "review_title"]
    with open(out / "vitality_missed_pairs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(missed)
    print(json.dumps(summary, indent=2))
    return 0


def cmd_impact(args) -> int:
    studies, yi, vi = [], [], []
    with open(args.studies, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("yi") not in (None, "") and row.get("vi") not in (None, ""):
                y, v = float(row["yi"]), float(row["vi"])
            else:
                eff = effect_from_2x2(*(float(row[c]) for c in ("ai", "bi", "ci", "di")), measure=args.measure)
                if eff is None:
                    print(f"skipping {row['study']}: no events in either arm", file=sys.stderr)
                    continue
                y, v = eff
            studies.append(row["study"])
            yi.append(y)
            vi.append(v)
    remove = [s.strip() for s in args.remove.split(",") if s.strip()]
    diff = impact_without(studies, yi, vi, remove, model=args.model)
    print(json.dumps(diff.to_dict(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fallout", description="Trace where retracted clinical trials end up in the evidence base.")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("retractions", help="summarise the retracted trials in the Retraction Watch data")
    _add_source(r)
    r.set_defaults(func=cmd_retractions)

    pt = sub.add_parser("pubtypes", help="fetch PubMed publication types and abstract signals for Health Sciences research articles")
    pt.add_argument("--csv", default=RW_CSV_URL, help="Retraction Watch CSV path or URL (default: Crossref's GitLab mirror)")
    pt.add_argument("--out", default="rw_pubtypes.json")
    pt.add_argument("--email", help="contact email sent to NCBI (or NCBI_EMAIL)")
    pt.set_defaults(func=cmd_pubtypes)

    t = sub.add_parser("trace", help="find works citing retracted trials via OpenAlex (resumable)")
    _add_source(t)
    t.add_argument("--ledger", default="ledger.json")
    t.add_argument("--limit", type=int, default=50, help="trials to trace this run (default 50)")
    t.add_argument("--max-citing", type=int, default=2000, help="cap on citing works fetched per trial")
    t.add_argument("--mailto", help="contact email for OpenAlex's polite pool (or OPENALEX_MAILTO)")
    t.add_argument("--cache-dir", default=".cache/openalex")
    t.add_argument("--retrace", action="store_true", help="re-trace trials already in the ledger")
    t.set_defaults(func=cmd_trace)

    en = sub.add_parser("enrich", help="add PubMed publication types and re-classify citing works")
    en.add_argument("--ledger", default="ledger.json")
    en.add_argument("--email", help="contact email sent to NCBI (or NCBI_EMAIL)")
    en.set_defaults(func=cmd_enrich)

    inc = sub.add_parser("inclusion", help="look for inclusion evidence in open full text of citing syntheses (PMC)")
    inc.add_argument("--ledger", default="ledger.json")
    inc.add_argument("--limit", type=int, help="distinct syntheses to check this run (default: all unchecked)")
    inc.add_argument("--recheck", action="store_true", help="re-check syntheses already checked")
    inc.add_argument("--email", help="contact email sent to NCBI (or NCBI_EMAIL)")
    inc.set_defaults(func=cmd_inclusion)

    rep = sub.add_parser("report", help="render ledger as HTML, Atom and CSV")
    rep.add_argument("--ledger", default="ledger.json")
    rep.add_argument("--out-dir", default="site")
    rep.set_defaults(func=cmd_report)

    im = sub.add_parser("impact", help="re-pool a meta-analysis without the named studies")
    im.add_argument("studies", help="CSV with columns study,yi,vi or study,ai,bi,ci,di")
    im.add_argument("--remove", required=True, help="comma-separated study labels to drop")
    im.add_argument("--model", choices=["random", "fixed"], default="random")
    im.add_argument("--measure", choices=["RR", "OR"], default="RR", help="for 2x2 input")
    im.set_defaults(func=cmd_impact)

    v = sub.add_parser("validate", help="measure the ledger against VITALITY Study I's verified inclusions")
    _add_source(v)
    v.add_argument("--ledger", default="ledger.json")
    v.add_argument("--vitality-dir", default="validation", help="folder with vitality_trials.csv and vitality_inclusions.csv")
    v.add_argument("--out-dir", default="validation-results")
    v.set_defaults(func=cmd_validate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
