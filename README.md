# Fallout

**Trace where retracted clinical trials end up in the evidence base.**

When a clinical trial is retracted, the systematic reviews, meta-analyses and clinical guidelines built on it are usually not updated. Fallout is an open, continuously rebuildable ledger that links each retracted trial to the evidence syntheses that cite it, flags the ones published *after* the retraction, and can re-pool a meta-analysis without the retracted study when the data is available.

Status: MVP (v0.1). The pipeline, tests and scheduled workflow exist; no public ledger has been published yet.

## The problem, with sources

The VITALITY study (Xu et al., *BMJ* 2025;389:e082068, [PDF](https://ueaeprints.uea.ac.uk/99702/1/bmj-2024-082068.pdf)) found:

- A cohort of 1,330 retracted randomised controlled trials, and 847 systematic reviews that quantitatively synthesised some of them.
- Of 3,902 meta-analyses it could replicate, removing the retracted trials changed the **direction** of the pooled effect in 8.4%, its **statistical significance** in 16.0%, and either one in 20.6%.
- Evidence from 68 systematic reviews whose conclusions were distorted by retracted trials was used in 157 guideline documents.
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

812 of the 2,729 were retracted in 2023, and 644 of those were Hindawi papers, consistent with Hindawi's mass paper-mill retractions that year. VITALITY's cohort of 1,330 retracted RCTs comes from its own full-text screening of Retraction Watch records, a different quantity from these counts; not all 1,330 were pooled in reviews.

The "Clinical Study" label is Retraction Watch's, and it is an imperfect proxy for an RCT: it includes non-randomised studies and misses RCTs labelled "Research Article". Use `--type` or `--all-types` to change the filter, or `--population trials` (with `fallout pubtypes`) to add Health Sciences "Research Article" retractions that PubMed indexes as a trial (publication type "Randomized Controlled Trial", "Clinical Trial", "Controlled Clinical Trial", or a phase or pragmatic trial). Each ledger trial records `selected_by`.

## Validation against VITALITY

`fallout validate` compares the ledger with VITALITY Study I's verified inclusions (see `validation/README.md`). On the full trace of 2026-10-26 (findings run 40405439120):

| Check | Result |
|---|---|
| VITALITY's 1,330 retracted RCTs selected by Fallout's filter | 842 (63.3%) |
| VITALITY index trials (those with a verified review) selected | 243 of 323 |
| Verified (trial, review) pairs Fallout could check | 628 of 850 (179 trial outside the population, 43 review without DOI) |
| ...where the ledger holds the citation | 598 (**95.2%**) |
| ...where it also labels the review a synthesis | 574 (**91.4%**); 24 were labelled "other" |
| Synthesis citations of VITALITY trials up to 21 Nov 2024 that VITALITY lists as a review pooling a retracted trial | 884 of 3,289 (26.9%); 1,061 (32.3%) ignoring Cochrane review versions |
| ...for citations labelled "meta-analysis" | 835 of 2,258 (37.0%); 972 (43.1%) ignoring versions |

Read the last two rows with care. If VITALITY's search was complete, they are an upper bound on how often a synthesis citation means the review pooled that trial in a pairwise meta-analysis. They are not the precision of Fallout's own claims, which are "cites". VITALITY also excludes systematic reviews without a pairwise meta-analysis and guidelines, so low shares for those classes are expected. In a random sample of 25 non-matching "meta-analysis" citations, 24 were syntheses by title and one was a commentary.

## How it works

1. **Retractions** (`fallout.retractions`): downloads the [Retraction Watch database](https://gitlab.com/crossref/retraction-watch-data) that Crossref publishes, keeps full retractions of the chosen article types, drops papers later reinstated, and normalises DOIs, PubMed IDs and dates.
2. **Tracing** (`fallout.openalex`, `fallout.ledger`): resolves each trial's DOI in [OpenAlex](https://openalex.org) and pages through works whose reference lists include it (`filter=cites:`), with rate limiting, retries and an on-disk cache. Runs are resumable.
3. **Classification** (`fallout.classify`): labels citing works as systematic review, meta-analysis, guideline or other, using conservative title patterns. `fallout enrich` then adds PubMed publication types (via NCBI E-utilities) for citing works with a PMID and re-labels them with those indexer-assigned types, which take precedence over titles. Narrative reviews are deliberately not counted.
4. **Outputs** (`fallout.report`): `ledger.json` ([schema](docs/ledger-schema.md)), `edges.csv`, an Atom feed of syntheses published after the retraction, and a static HTML page with no scripts or external assets.
5. **Impact re-analysis** (`fallout.metaanalysis`): fixed-effect and DerSimonian–Laird random-effects pooling, effect sizes from 2×2 tables (log RR/OR, 0.5 continuity correction only when a cell is zero) or means (MD, Hedges' g), and a leave-studies-out diff that reports direction and significance changes using VITALITY's definitions. The implementation reproduces metafor's DL results for the BCG vaccine dataset (estimate −0.7141, SE 0.1787, τ² 0.3088) in the tests.

## Usage

```bash
pip install -e .
fallout retractions                       # summary of the current Retraction Watch data
fallout trace --limit 50 --mailto you@example.org   # trace 50 trials, most recently retracted first
fallout pubtypes --out rw_pubtypes.json   # PubMed publication types for Health Sciences research articles
fallout trace --population trials --pubtypes rw_pubtypes.json   # also trace those PubMed indexes as trials
fallout enrich                            # add PubMed publication types, re-classify
fallout report --out-dir site             # site/index.html, site/feed.xml, site/edges.csv
fallout impact examples/bcg.csv --remove "TPT Madras 1980"
fallout validate --out-dir validation-results    # score the ledger against VITALITY (see validation/README.md)
```

`trace` writes `ledger.json` and checkpoints every 25 trials; rerun it to continue. `OPENALEX_MAILTO` and `OPENALEX_API_KEY` are read from the environment if set. As of October 2026, [OpenAlex's authentication docs](https://developers.openalex.org/api-reference/authentication) allow $0.10 of usage per day without a key and $1 per day with a free key (sent as the `api_key` query parameter), resetting at midnight UTC. A keyless run covered about 1,000 trials before hitting HTTP 429, so set a key (as the `OPENALEX_API_KEY` repository secret for the workflows) for full traces. Trials that fail are retried on the next run.

The `trace` GitHub Actions workflow runs weekly (and on demand), traces up to 200 trials per run, carries the ledger forward in the Actions cache, and uploads the ledger and HTML as a build artifact.

## Limitations

- **Cites is not included.** The biggest gap. Many citing reviews mention a trial without pooling it.
- **The population filter misses trials.** Fallout keeps Retraction Watch records labelled "Clinical Study". Of VITALITY's 1,330 retracted RCTs, 842 (63%) pass that filter; 417 are labelled only "Research Article" and 45 have DOIs not found in Retraction Watch. Conversely, "Clinical Study" also includes non-randomised studies.
- **OpenAlex coverage.** Reference lists are incomplete for some publishers, and many guidelines have no DOI or indexed reference list, so guideline linkage is weak.
- **Classification is approximate.** Title patterns miss syntheses with unusual titles and can mislabel some works. Of 598 VITALITY-verified reviews found in the ledger, 24 were labelled "other". 10 of those are Cochrane reviews, whose titles often omit "systematic review" (for example "Colloid solutions for fluid resuscitation"), and 3 have "protocol" titles.
- **Dates.** Publication dates are sometimes only year-precise; "after retraction" near zero days is unreliable.
- **No general recomputation.** Per-trial effect data for most published meta-analyses is not openly available. `fallout impact` works on data you supply.
- **Licence of the source data.** Crossref's documentation does not state a licence for the Retraction Watch CSV, so this repository never commits or redistributes it.
- The test fixtures for OpenAlex and PubMed are hand-built from their documented response schemas, not recorded. The `live-smoke` workflow traces three real trials against live OpenAlex on every PR that touches `src/`.

## Roadmap

1. **Inclusion verification.** Compare each citing synthesis's included-studies list (from open full text, e.g. PubMed Central) against the trial, and record a separate `inclusion` field with provenance.
2. **Validation.** `fallout validate` scores the ledger against VITALITY's verified inclusions ([OSF](https://osf.io/7eazq/); see `validation/README.md`). A systematic precision check of Fallout's synthesis labels is still needed.
3. **Guideline linkage.** Import reference lists from guideline publishers that publish them (e.g. NICE, WHO, MAGICapp).
4. **Open-data recomputation.** Leave-one-out re-analysis where data is open (Cochrane data packages under open licences, VITALITY reconstructions), with a data-provenance badge.
5. **Public site.** Publish the ledger, feed and per-trial pages on GitHub Pages.

## Ethics

Fallout is about where evidence travels, not about people. It shows provenance on every claim, avoids accusatory language, and does not email or name authors. Corrections are welcome as issues.

## Licence

MIT. See [LICENSE](LICENSE). Data from Retraction Watch/Crossref and OpenAlex are subject to their own terms.
