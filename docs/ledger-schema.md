# Ledger schema `fallout.ledger/1`

`ledger.json` is one JSON object:

| Field | Type | Meaning |
|---|---|---|
| `schema` | string | Always `fallout.ledger/1`. Readers must reject other values. |
| `generated_at` | ISO 8601 UTC | When the file was last written. |
| `sources` | object | Human-readable description of data sources. |
| `trials` | object | Keyed by `rw:<Retraction Watch Record ID>`. |
| `edges` | array | One entry per (retracted trial, citing work) pair. |

## `trials[key]`

All fields of the Retraction Watch record that Fallout uses (`record_id`, `title`, `journal`, `publisher`, `article_types`, `nature`, `reasons`, `doi`, `pmid`, `original_date`, `retraction_date`, `retraction_doi`, `countries`, `subjects`), plus:

- `selected_by`: why the record is in the population. `article_type` means RW's ArticleType matched (by default "Clinical Study"). `pubmed:<type>` means a Health Sciences "Research Article" that PubMed indexes with that trial publication type (`--population trials`). `abstract:<phrase>` means such a record without a trial publication type whose PubMed abstract describes random allocation, with the matched phrase. Entries traced before this field existed lack it and were all selected by `article_type`.

- `status`: `traced`, `no_doi`, `not_in_openalex` or `error`.
- `openalex_id`, `cited_by_count`: from OpenAlex, when traced.
- `edges_added`: new edges found by the latest trace.
- `citing_may_be_truncated`: true when the per-trial cap (`--max-citing`) was reached.
- `traced_at`; `error` when `status` is `error`.

## `edges[]`

- `trial`: key into `trials`.
- `relation`: always `"cites"`. It means the citing work's reference list, as indexed by OpenAlex, contains the trial. It does **not** mean the trial was included in an analysis.
- `citing`: `openalex_id`, `doi`, `title`, `publication_date`, `type`, `pmid` (from OpenAlex).
- `class`: `systematic_review`, `meta_analysis`, `guideline` or `other`.
- `class_confidence`: `high` (indexer publication type), `medium` (title pattern) or `low`.
- `class_reasons`: list of strings explaining the label.
- `cited_after_retraction`: true if the citing work's publication date is later than the retraction date; null if either date is unknown. OpenAlex dates are sometimes only year- or month-precise, so values near zero days are unreliable.
- `days_after_retraction`: signed integer, citing publication date minus retraction date.
- `first_seen`: when Fallout first recorded the edge (used to order the Atom feed).

Future schema versions will add a separate, provenance-carrying `inclusion` field once a verification step exists. `relation` will stay `"cites"`.
