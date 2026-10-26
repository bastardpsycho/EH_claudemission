"""Command-line interface: ``fallout retractions | trace | report | impact``."""

from __future__ import annotations

import argparse
import csv
import json
import sys

from . import ledger as ledger_mod
from .metaanalysis import effect_from_2x2, impact_without
from .openalex import OpenAlexClient
from .pubmed import PubMedClient
from .report import render_all
from .retractions import DEFAULT_ARTICLE_TYPES, RW_CSV_URL, read_records, select_retracted_trials, summarize


def _types(args) -> list[str] | None:
    return None if args.all_types else (args.type or list(DEFAULT_ARTICLE_TYPES))


def _add_source(p: argparse.ArgumentParser) -> None:
    p.add_argument("--csv", default=RW_CSV_URL, help="Retraction Watch CSV path or URL (default: Crossref's GitLab mirror)")
    p.add_argument("--type", action="append", help="ArticleType to keep (repeatable; default 'Clinical Study')")
    p.add_argument("--all-types", action="store_true", help="keep retractions of every article type")


def cmd_retractions(args) -> int:
    records = list(read_records(args.csv))
    selected = select_retracted_trials(records, _types(args))
    summary = summarize(records, selected)
    summary["article_types"] = _types(args) or "all"
    print(json.dumps(summary, indent=2))
    return 0


def cmd_trace(args) -> int:
    records = list(read_records(args.csv))
    trials = select_retracted_trials(records, _types(args))
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


def cmd_report(args) -> int:
    led = ledger_mod.load(args.ledger)
    print(json.dumps(render_all(led, args.out_dir), indent=2))
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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
