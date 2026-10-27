"""Build Fallout's validation set from the VITALITY Study I data on OSF (CC BY 4.0).

Usage: build_vitality_gold.py TRIALS_XLSX META_XLSX OUT_DIR

TRIALS_XLSX is "Baseline information of 1330_R_RCT.xlsx" (https://osf.io/8zqf7) and
META_XLSX is "All in one final - 30_Dec updated 3.xlsx" (https://osf.io/ukg3j), both
from https://osf.io/7eazq/. Needs openpyxl, which the fallout package itself does not.

Writes two CSVs:
- vitality_trials.csv: the 1,330 retracted RCTs, one row per trial.
- vitality_inclusions.csv: one row per (index trial, systematic review) that VITALITY
  verified pooled that trial in at least one pairwise meta-analysis. VITALITY files each
  review under a single index trial, so a review that pooled several retracted trials
  lists only one of them here.
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

_DOI = re.compile(r"10\.\d{4,9}/[^\s;,]+", re.I)


def dois_in(raw) -> list[str]:
    """Every DOI-shaped string in a cell, lowercased, without trailing punctuation."""
    return [d.rstrip(".").lower() for d in _DOI.findall(str(raw or ""))]


def sheet_rows(path, name=None):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = (wb[name] if name else wb.worksheets[0]).iter_rows(values_only=True)
    header = next(rows)
    return [dict(zip(header, r)) for r in rows if any(v is not None for v in r)]


def iso(value):
    return value.date().isoformat() if hasattr(value, "date") else (str(value)[:10] if value else "")


def main(trials_xlsx, meta_xlsx, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    trials = sheet_rows(trials_xlsx)
    with open(out / "vitality_trials.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rct_id", "doi", "other_dois", "retraction_date", "publication_date", "paper_mill"])
        for t in sorted(trials, key=lambda t: int(t["RCT_ID"])):
            found = dois_in(t["DOI"])
            w.writerow([t["RCT_ID"], found[0] if found else "", " ".join(found[1:]),
                        iso(t["RetractionDate"]), iso(t["Date of Publish"]), t["Paper mill"] or ""])

    # The "All" sheet holds every meta-analysis row, replicated or not; inclusion was verified either way.
    # It has 4,482 rows against the paper's 4,095 meta-analyses, so ma_rows counts rows, not distinct analyses.
    pairs = defaultdict(lambda: {"ma_rows": 0, "replicated": 0, "max_retracted_in_ma": 0, "title": ""})
    for row in sheet_rows(meta_xlsx, "All"):
        rct_id = str(row["srfile"]).split("_", 1)[0]
        found = dois_in(row["doi"])
        p = pairs[(int(rct_id), str(row["srfile"]), found[0] if found else "")]
        p["ma_rows"] += 1
        p["replicated"] += row["Notes"] == "Replicated"
        p["max_retracted_in_ma"] = max(p["max_retracted_in_ma"], int(row["noofretraction"] or 0))
        p["title"] = p["title"] or (row["Reviewtitle"] or "").strip()
    with open(out / "vitality_inclusions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rct_id", "srfile", "review_doi", "ma_rows", "replicated", "max_retracted_in_ma", "review_title"])
        for (rct_id, srfile, doi), p in sorted(pairs.items()):
            w.writerow([rct_id, srfile, doi, p["ma_rows"], p["replicated"], p["max_retracted_in_ma"], p["title"]])
    print(f"{len(trials)} trials, {len(pairs)} inclusion pairs, "
          f"{sum(p['ma_rows'] for p in pairs.values())} meta-analysis rows")


if __name__ == "__main__":
    main(*sys.argv[1:4])
