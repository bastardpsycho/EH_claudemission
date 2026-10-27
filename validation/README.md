# Validation set: VITALITY Study I

Reference data for `fallout validate`, derived from the VITALITY Study I datasets.

**Source.** Xu C, et al. *Investigating the impact of trial retractions on the healthcare evidence ecosystem (VITALITY Study I): retrospective cohort study.* BMJ 2025;389:e082068. https://doi.org/10.1136/bmj-2024-082068. Data: OSF project "Impact of retracted RCTs for Evidence Synthesis", https://osf.io/7eazq/, © Chang Xu 2024, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The files here are derived from that data: columns were selected, DOIs normalised and rows aggregated. They are shared under the same licence.

| OSF file | GUID | SHA-256 |
|---|---|---|
| Baseline information of 1330_R_RCT.xlsx | [8zqf7](https://osf.io/8zqf7) | `fd0822fc12ebc1608a903f3e743035040595deab7bb00582baec6824ed10e6f2` |
| All in one final - 30_Dec updated 3.xlsx | [ukg3j](https://osf.io/ukg3j) | `8476ee530354b7f071aacded86d4dbfd2b365811b6d765ab4e1f7486942e75a1` |

Both were downloaded on 2026-10-26. Rebuild with `python scripts/build_vitality_gold.py <8zqf7.xlsx> <ukg3j.xlsx> validation` (needs `openpyxl`).

## Files

- `vitality_trials.csv`: the 1,330 retracted RCTs. Fields: `rct_id`, `doi` (first DOI in the cell), `other_dois`, `retraction_date`, `publication_date` and `paper_mill`, all as recorded by VITALITY. 24 trials have no DOI.
- `vitality_inclusions.csv`: 850 rows, one per (index trial, review file). Each row is a review VITALITY verified by full text as pooling that trial in at least one pairwise meta-analysis. The rows come from the "All" sheet, replicated or not. `ma_rows` counts that sheet's rows; the sheet has 4,482 rows against the paper's 4,095 meta-analyses, so it is not a count of distinct analyses. 43 rows have no review DOI.

## How to read it

- **One index trial per review.** VITALITY files each review (`srfile` = `<rct_id>_<n>`) under a single trial, even when the review pooled several retracted trials (`max_retracted_in_ma` > 1). The inclusion pairs are therefore true but incomplete: a review pooling trials A and B may be listed only under A. 323 distinct index trials appear.
- **The cohort is broader than Fallout's filter.** VITALITY searched Retraction Watch for "Clinical Study" and "Research Article" records in Health Sciences, then kept RCTs by full-text review. Fallout keeps only "Clinical Study".
- **The search window ended in late 2024.** Retractions were searched up to 5 November 2024. Forward citations were last updated on 21 November 2024 (Scopus) and 21 November–2 December 2024 (Google Scholar).
- The sheet-to-meaning mapping above is our reading of the column names and the paper; the OSF project does not include a codebook.
- **Some listed reviews are protocols.** Three titles say "A protocol for systematic review" (`10.1097/md.0000000000026662`, `10.1097/md.0000000000027782`, `10.1097/md.0000000000024607`). The PubMed title of `10.1186/s13643-021-01702-9` ends "…a systematic review and meta-analysis protocol", although VITALITY's copy drops the word, and its PMC full text has no tables or results. A protocol cannot have pooled a trial, so a few of the 850 pairs are probably not inclusions. The pairs are kept as published.
