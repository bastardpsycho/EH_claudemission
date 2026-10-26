"""Render a ledger as CSV, an Atom feed, and a static HTML page (no external assets)."""

from __future__ import annotations

import csv
import html
from pathlib import Path
from xml.sax.saxutils import escape

from .classify import SYNTHESIS_CLASSES
from .ledger import stats, synthesis_edges

CAVEAT = (
    "Each row means a work's reference list cites a retracted trial, according to OpenAlex. "
    "Whether the trial was included in any analysis has not been verified, and a citation can be "
    "legitimate (for example, a review that notes the retraction). Nothing here is an accusation."
)
CLASS_NAMES = {"guideline": "Guideline", "meta_analysis": "Meta-analysis", "systematic_review": "Systematic review"}

CSV_FIELDS = [
    "trial", "trial_doi", "trial_title", "retraction_date", "relation", "class", "class_confidence",
    "citing_openalex_id", "citing_doi", "citing_title", "citing_publication_date",
    "cited_after_retraction", "days_after_retraction", "first_seen",
]


def write_csv(ledger: dict, path: str | Path) -> int:
    rows = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for e in ledger["edges"]:
            t = ledger["trials"].get(e["trial"], {})
            w.writerow({
                "trial": e["trial"], "trial_doi": t.get("doi"), "trial_title": t.get("title"),
                "retraction_date": t.get("retraction_date"), "relation": e["relation"], "class": e["class"],
                "class_confidence": e["class_confidence"], "citing_openalex_id": e["citing"]["openalex_id"],
                "citing_doi": e["citing"]["doi"], "citing_title": e["citing"]["title"],
                "citing_publication_date": e["citing"]["publication_date"],
                "cited_after_retraction": e["cited_after_retraction"],
                "days_after_retraction": e["days_after_retraction"], "first_seen": e["first_seen"],
            })
            rows += 1
    return rows


def _doi_url(doi: str | None) -> str | None:
    return f"https://doi.org/{doi}" if doi else None


def write_atom(ledger: dict, path: str | Path, limit: int = 200, feed_id: str = "urn:fallout:post-retraction-syntheses") -> int:
    """Feed of syntheses published after the trial they cite was retracted, newest finds first."""
    edges = sorted(synthesis_edges(ledger, after_retraction_only=True), key=lambda e: e["first_seen"], reverse=True)[:limit]
    updated = edges[0]["first_seen"] if edges else ledger["generated_at"]
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        "<title>Fallout: syntheses citing already-retracted trials</title>",
        f"<id>{escape(feed_id)}</id>",
        f"<updated>{escape(updated)}</updated>",
        f"<subtitle>{escape(CAVEAT)}</subtitle>",
    ]
    for e in edges:
        t = ledger["trials"].get(e["trial"], {})
        c = e["citing"]
        title = f"{CLASS_NAMES.get(e['class'], e['class'])} cites a trial retracted {t.get('retraction_date')}"
        summary = (
            f"{c['title']} ({c['publication_date']}) cites \"{t.get('title')}\" "
            f"(doi:{t.get('doi')}), retracted {t.get('retraction_date')}, "
            f"{e['days_after_retraction']} days before the citing work's publication date. "
            "Inclusion in analysis not verified."
        )
        link = _doi_url(c["doi"]) or c["openalex_id"] or ""
        parts += [
            "<entry>",
            f"<title>{escape(title)}</title>",
            f"<id>{escape('urn:fallout:' + e['trial'] + ':' + str(c['openalex_id']))}</id>",
            f"<updated>{escape(e['first_seen'])}</updated>",
            f'<link href="{escape(link)}"/>',
            f"<summary>{escape(summary)}</summary>",
            "</entry>",
        ]
    parts.append("</feed>")
    Path(path).write_text("\n".join(parts) + "\n", encoding="utf-8")
    return len(edges)


_CSS = """
:root{--bg:#fff;--fg:#1b1b1b;--muted:#5c5c5c;--line:#ddd;--warn:#8a4b00;--chip:#f3f3f3}
@media (prefers-color-scheme:dark){:root{--bg:#141414;--fg:#e8e8e8;--muted:#a3a3a3;--line:#333;--warn:#f0b35a;--chip:#222}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:72rem;padding:1rem}
h1{font-size:1.5rem;margin:.5rem 0}h2{font-size:1.1rem;margin-top:2rem}
.caveat{border-left:3px solid var(--warn);padding:.5rem .75rem;color:var(--muted)}
.stats{display:flex;flex-wrap:wrap;gap:.75rem;padding:0;list-style:none}
.stats li{background:var(--chip);padding:.5rem .75rem;border-radius:6px}
.stats b{display:block;font-size:1.3rem}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%}
th,td{text-align:left;vertical-align:top;padding:.4rem;border-bottom:1px solid var(--line)}
td.n{text-align:right;font-variant-numeric:tabular-nums}a{color:inherit}
small{color:var(--muted)}
"""


def _link(text: str, url: str | None) -> str:
    t = html.escape(text or "(untitled)")
    return f'<a href="{html.escape(url)}">{t}</a>' if url else t


def write_html(ledger: dict, path: str | Path) -> None:
    s = stats(ledger)
    syn = sorted(
        synthesis_edges(ledger),
        key=lambda e: (not e["cited_after_retraction"], -(e["days_after_retraction"] or 0)),
    )
    rows = []
    for e in syn:
        t = ledger["trials"].get(e["trial"], {})
        c = e["citing"]
        when = "after" if e["cited_after_retraction"] else ("before" if e["cited_after_retraction"] is False else "unknown")
        rows.append(
            "<tr>"
            f"<td>{_link(c['title'], _doi_url(c['doi']) or c['openalex_id'])}<br><small>{html.escape(str(c['publication_date']))}</small></td>"
            f"<td>{html.escape(CLASS_NAMES.get(e['class'], e['class']))}<br><small>{html.escape(e['class_confidence'])}: {html.escape('; '.join(e['class_reasons']))}</small></td>"
            f"<td>{_link(t.get('title', ''), _doi_url(t.get('doi')))}<br><small>retracted {html.escape(str(t.get('retraction_date')))}</small></td>"
            f"<td>{when}</td>"
            f"<td class=n>{'' if e['days_after_retraction'] is None else e['days_after_retraction']}</td>"
            "</tr>"
        )
    by_class = ", ".join(f"{CLASS_NAMES[k]}: {s['synthesis_edges_by_class'].get(k, 0)}" for k in SYNTHESIS_CLASSES)
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fallout ledger</title><style>{_CSS}</style></head><body>
<h1>Fallout: where retracted trials end up</h1>
<p class="caveat">{html.escape(CAVEAT)}</p>
<ul class="stats">
<li><b>{s['trials_traced']}</b>retracted trials traced</li>
<li><b>{s['citing_edges']}</b>citing works found</li>
<li><b>{s['synthesis_edges']}</b>citations from syntheses<br><small>{html.escape(by_class)}</small></li>
<li><b>{s['synthesis_edges_after_retraction']}</b>of those published after the retraction</li>
<li><b>{s['trials_cited_by_a_synthesis']}</b>trials cited by at least one synthesis</li>
</ul>
<p><small>Not traced: {s['trials_no_doi']} without a DOI, {s['trials_not_in_openalex']} not found in OpenAlex, {s['trials_error']} errors.
Generated {html.escape(ledger['generated_at'])}. Classification uses title patterns and is approximate. Publication dates in OpenAlex are sometimes only a year or month, so "days after" can be off.</small></p>
<h2>Syntheses citing a retracted trial</h2>
<div class="wrap"><table>
<thead><tr><th>Citing work</th><th>Class</th><th>Retracted trial</th><th>Published vs retraction</th><th>Days after</th></tr></thead>
<tbody>
{''.join(rows) or '<tr><td colspan=5>None found yet.</td></tr>'}
</tbody></table></div>
<p><small>Sources: Retraction Watch database (via Crossref) and OpenAlex. Fallout is open source: github.com/bastardpsycho/EH_claudemission</small></p>
</body></html>
"""
    Path(path).write_text(doc, encoding="utf-8")


def render_all(ledger: dict, out_dir: str | Path) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = write_csv(ledger, out / "edges.csv")
    entries = write_atom(ledger, out / "feed.xml")
    write_html(ledger, out / "index.html")
    return {"csv_rows": rows, "feed_entries": entries, "html": str(out / "index.html")}
