# Fallout

**Trace where retracted clinical trials end up in the evidence base.**

When a clinical trial is retracted, the systematic reviews, meta-analyses and clinical guidelines built on it are usually not updated. Fallout is an open, continuously rebuildable ledger that links each retracted trial to the evidence syntheses that cite it, flags the ones published *after* the retraction, and can re-pool a meta-analysis without the retracted study when the data is available.

Status: MVP (v0.1). The pipeline, tests and scheduled workflow exist; no public ledger has been published yet.

## The problem, with sources

The VITALITY study (Xu et al., *BMJ* 2025;389:e082068, [PDF](https://ueaeprints.uea.ac.uk/99702/1/bmj-2024-082068.pdf)) found:

- 1,330 retracted randomised controlled trials included in 847 systematic reviews.
- Of 3,902 meta-analyses it could replicate, removing the retracted trials changed the **direction** of the pooled effect in 8.4%, its **statistical significance** in 16.0%, and either one in 20.6%.
- Distorted meta-analyses fed into 157 guideline documents.
- 38.3% of the affected reviews were published *after* the trial had already been retracted.

Existing responses cover parts of this:

- Emailing authors does not work on its own. The RetractoBot randomised trial (15,921 retracted articles, about 247,000 emails) found no change in later citation rates: mean difference −0.007, 95% CI −0.055 to 0.041 ([Peer Review Congress abstract](https://peerreviewcongress.org/abstract/notifying-authors-that-they-have-cited-a-retracted-article-and-future-citations-of-retracted-articles-the-retractobot-randomized-controlled-trial/)).
- Cochrane now flags retracted studies in **its own** reviews and reports that just under 1% of its 9,500+ reviews use retracted data in analyses ([Retraction Watch, June 2026](https://retractionwatch.com/2026/06/10/cochrane-reviews-retracted-studies-central-database/)). Non-Cochrane reviews and guidelines are not covered.
- Tools such as Covidence alert reviewers at screening time ([Covidence](https://support.covidence.org/help/how-covidence-displays-research-integrity-alerts)), and the Feet of Clay Detector flags papers citing retracted work in general. We found no open tool that follows retracted trials into syntheses and guidelines over time.

Fallout's design follows from those findings: it is a **pull** resource (a public ledger, a feed and per-trial pages) for guideline developers, evidence-synthesis teams and journals, not an email campaign at authors, and it is meant to complement Cochrane's work by covering everything else.

## What Fallout claims, and what it does not

Fallout records that a work **cites** a retracted trial, according to OpenAlex. It does **not** claim the trial was included in an analysis, that the citing work is wrong, or that anyone acted improperly. A review can cite a retracted trial correctly, for example to exclude it or to note the retraction. Every edge carries its source and the reason for its classification.

## What the current data looks like

`fallout retractions` on the Retraction Watch CSV pulled on **2026-10-26** (latest retraction date in the file: 2026-10-09):

| | Count |
|---|---|
| Records in the database | 73,356 |
| of which retractions | 67,916 (also 3,733 expressions of concern, 1,544 corrections, 163 reinstatements) |
| Retractions labelled "Clinical Study" (minus later reinstatements) | 2,729 |
| ...with a DOI (traceable via OpenAlex) | 2,616 |
| ...with a PubMed ID | 2,590 |

812 of the 2,729 were retracted in 2023, and 644 of those were Hindawi papers, consistent with Hindawi's mass paper-mill retractions that year. Note that VITALITY found 1,330 retracted RCTs *included in reviews* by its own screening, a different quantity from these counts.

The "Clinical Study" label is Retraction Watch's, and it is an imperfect proxy for an RCT: it includes non-randomised studies and misses RCTs labelled "Research Article". Use `--type` or `--all-types` to change the filter.

## How it works

1. **Retractions** (`fallout.retractions`): downloads the [Retraction Watch database](https://gitlab.com/crossref/retraction-watch-data) that Crossref publishes, keeps full retractions of the chosen article types, drops papers later reinstated, and normalises DOIs, PubMed IDs and dates.
2. **Tracing** (`fallout.openalex`, `fallout.ledger`): resolves each trial's DOI in [OpenAlex](https://openalex.org) and pages through works whose reference lists include it (`filter=cites:`), with rate limiting, retries and an on-disk cache. Runs are resumable.
3. **Classification** (`fallout.classify`): labels citing works as systematic review, meta-analysis, guideline or other, using conservative title patterns (and indexer publication types when supplied). Narrative reviews are deliberately not counted.
4. **Outputs** (`fallout.report`): `ledger.json` ([schema](docs/ledger-schema.md)), `edges.csv`, an Atom feed of syntheses published after the retraction, and a static HTML page with no scripts or external assets.
5. **Impact re-analysis** (`fallout.metaanalysis`): fixed-effect and DerSimonian–Laird random-effects pooling, effect sizes from 2×2 tables (log RR/OR, 0.5 continuity correction only when a cell is zero) or means (MD, Hedges' g), and a leave-studies-out diff that reports direction and significance changes using VITALITY's definitions. The implementation reproduces metafor's DL results for the BCG vaccine dataset (estimate −0.7141, SE 0.1787, τ² 0.3088) in the tests.

## Usage

```bash
pip install -e .
fallout retractions                       # summary of the current Retraction Watch data
fallout trace --limit 50 --mailto you@example.org   # trace 50 trials, most recently retracted first
fallout report --out-dir site             # site/index.html, site/feed.xml, site/edges.csv
fallout impact examples/bcg.csv --remove "TPT Madras 1980"
```

`trace` writes `ledger.json` and checkpoints every 25 trials; rerun it to continue. `OPENALEX_MAILTO` and `OPENALEX_API_KEY` are read from the environment if set. OpenAlex's key and rate-limit policy has changed over time, so check [its docs](https://docs.openalex.org) for current rules; we have not verified them from here.

The `trace` GitHub Actions workflow runs weekly (and on demand), traces up to 200 trials per run, carries the ledger forward in the Actions cache, and uploads the ledger and HTML as a build artifact.

## Limitations

- **Cites is not included.** The biggest gap. Many citing reviews mention a trial without pooling it.
- **OpenAlex coverage.** Reference lists are incomplete for some publishers, and many guidelines have no DOI or indexed reference list, so guideline linkage is weak.
- **Classification is approximate.** Title patterns miss syntheses with unusual titles and can mislabel some works.
- **Dates.** Publication dates are sometimes only year-precise; "after retraction" near zero days is unreliable.
- **No general recomputation.** Per-trial effect data for most published meta-analyses is not openly available. `fallout impact` works on data you supply.
- **Licence of the source data.** Crossref's documentation does not state a licence for the Retraction Watch CSV, so this repository never commits or redistributes it.
- The test fixtures for OpenAlex are hand-built from its documented response schema, not recorded from the live API. The live API could not be reached from the environment where this was written.

## Roadmap

1. **Inclusion verification.** Compare each citing synthesis's included-studies list (from open full text, e.g. PubMed Central) against the trial, and record a separate `inclusion` field with provenance.
2. **Validation.** Score Fallout's recall and precision against the VITALITY datasets ([OSF](https://osf.io/ukg3j)).
3. **Better classification.** Add PubMed publication types for works with a PMID.
4. **Guideline linkage.** Import reference lists from guideline publishers that publish them (e.g. NICE, WHO, MAGICapp).
5. **Open-data recomputation.** Leave-one-out re-analysis where data is open (Cochrane data packages under open licences, VITALITY reconstructions), with a data-provenance badge.
6. **Public site.** Publish the ledger, feed and per-trial pages on GitHub Pages.

## Ethics

Fallout is about where evidence travels, not about people. It shows provenance on every claim, avoids accusatory language, and does not email or name authors. Corrections are welcome as issues.

## Licence

MIT. See [LICENSE](LICENSE). Data from Retraction Watch/Crossref and OpenAlex are subject to their own terms.
