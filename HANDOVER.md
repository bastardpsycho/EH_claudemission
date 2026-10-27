# Handover: Save Humanity / Fallout

Pick-up file for the next Claude session. Written 2026-10-26 at about 17:45 UTC; sections 6, 7, 9 and 10 updated at about 18:30 UTC after the trace finished, again at about 21:40 UTC after the VITALITY validation, and on 2026-10-27 at about 18:45 UTC after the wider population and the inclusion check (PRs #6 and #7). Read this first, then `README.md`.

Owner: **Foot** (GitHub `bastardpsycho`). They described their role as "the interface, not the instructor": work autonomously, choose for yourself, and ask only when a human is genuinely needed. They value rigorous accuracy, so cite sources, flag uncertainty, and never round a caveat away.

---

## 1. Goal

The brief: find something crucial that humans are getting wrong and that software could fix, then build it. The repository `bastardpsycho/EH_claudemission` started empty on 2026-10-26.

## 2. How the idea was chosen

Six "champion" agents each researched one domain and pitched two ideas, twelve in total. Three "critic" agents then checked the champions' claims against sources, looked for competitors, and scored the six strongest pitches out of 10. The scores covered five things: is the problem real, is it neglected, is software the missing piece, can an MVP be built now from public data, and is impact plausible.

| Pitch | Score | Verdict |
|---|---|---|
| **Fallout: retraction exposure ledger** (health/science) | **7** | **Chosen.** The harm is well measured, there is a gap outside Cochrane, the data is open, and two champions reached the idea independently. |
| Distro-layer census of at-risk open source | 6.5 | A real blind spot, since OpenSSF criticality_score has stalled. It overlaps heavily with ecosyste.ms, and money is the binding constraint, not lists. |
| Phone-tutoring scheduler (ConnectEd) | 6 | Strong RCT evidence (+0.33 SD), but Youth Impact is building this tooling in-house. |
| Methane-alert accountability tracker (UNEP MARS) | 5 | About 88% of alerts go unanswered, but the cause is political will. Public data lags 30 days and has a non-commercial licence. |
| Automating INSPECT-SR results checks | 4 | INSPECT-AI and Barnett's tools already exist, and false positives run high. |
| Clean Slate record matching | 4 | State data sits behind firewalls, and Delaware and Michigan are automating it themselves. |

The champions dropped some ideas themselves before the critique round:
- outcome-switching detection (crowded);
- free tax filing (needs IRS authorisation);
- a Medicaid exemption engine (late and crowded);
- distributed-generation interconnection screening;
- oral-reading-fluency scoring.

The critics caught several champion errors, all corrected in the report:
- ConnectEd's "35k" counted teachers, not students.
- The VITALITY 20.6% and 16.0% figures measure different things and are both correct.
- The INSPECT-SR "45 min per trial" figure could not be verified.
- Delaware is already automated.
- Open-source Census III supersedes Census II.

Full decision report, with sources and the first findings: https://claude.ai/artifact/CfUzPKZ7yArE4dm3tdomNN (private to Foot).

## 3. The problem Fallout addresses

From VITALITY (Xu et al., BMJ 2025;389:e082068, https://ueaeprints.uea.ac.uk/99702/1/bmj-2024-082068.pdf):
- The searches identified a cohort of 1,330 retracted RCTs, and 847 systematic reviews that quantitatively synthesised some of them. (Earlier versions of this file said "1,330 retracted RCTs were pooled in 847 systematic reviews"; the paper does not say all 1,330 were pooled. VITALITY's data lists 323 index trials, see `validation/README.md`.)
- Of 3,902 meta-analyses re-run without them, 20.6% changed direction or significance: direction alone 8.4%, significance alone 16.0%, both 3.9%.
- Evidence from 68 systematic reviews whose conclusions were distorted by retracted trials was used in 157 guideline documents.
- 38.3% of the contaminated reviews (324 of 847) were published after the retraction.

Existing fixes each cover one slice:
- **RetractoBot** emailed authors. Its RCT found no effect (difference −0.007, 95% CI −0.055 to 0.041).
- **Cochrane**, since June 2026, flags retracted studies in its own reviews only.
- **Covidence** flags retractions only at the screening stage.
- **Feet of Clay Detector** and the R `retraction` package stop at the citation. They do not follow it to guidelines or recompute effects.

## 4. Design decisions (keep these)

- **Edges say "cites", never "included".** A citation does not prove a review pooled the trial. Inclusion needs verification against the review's included-studies list, and that is not built yet. Every output says so.
- **Pull, not push.** Fallout publishes a ledger, an Atom feed and an HTML page for guideline developers and review teams. It does not email authors, because the RetractoBot RCT showed that does nothing.
- **Neutral language, provenance on every claim.** Name no people and make no accusations beyond what the retraction notice says.
- **Do not redistribute the Retraction Watch CSV.** Crossref's docs state no licence. It is downloaded at run time and git-ignored (`*.csv`). The findings CSV lists DOIs and titles of citing works, not the RW file.
- **Use only the standard library at runtime.** The package needs only Python's standard library; tests use pytest.
- **Classification:** PubMed publication types (Meta-Analysis, Systematic Review, Practice Guideline) are trusted first and labelled "high" confidence. Conservative title regexes come next and are labelled "medium". Narrative reviews are not counted as syntheses.

## 5. Code map (`main`)

| Path | What it does |
|---|---|
| `src/fallout/retractions.py` | Load the RW CSV (GitLab mirror or path), filter `RetractionNature == "Retraction"` and `ArticleType` containing "Clinical Study", drop reinstated items, normalise DOI, PMID and dates. |
| `src/fallout/openalex.py` | OpenAlex client: DOI lookup, `filter=cites:` cursor paging, rate limit, retries, on-disk cache (keys stripped). |
| `src/fallout/pubmed.py` | NCBI E-utilities esummary client for publication types (batches of 200, POST). |
| `src/fallout/classify.py` | Labels: systematic_review, meta_analysis, guideline or other, with reasons and confidence. |
| `src/fallout/ledger.py` | Ledger schema, `trace` (resumable, checkpoints every 25 trials), `enrich_pubmed`, `stats`. |
| `src/fallout/report.py` | `ledger.json` to HTML, Atom and `edges.csv`. |
| `src/fallout/metaanalysis.py` | Fixed-effect and DerSimonian–Laird pooling, 2×2 and mean-difference effect sizes, leave-out impact diff using VITALITY's definitions. Matches metafor on the BCG data (−0.7141, SE 0.1787, τ² 0.3088). |
| `src/fallout/cli.py` | `fallout retractions | trace | enrich | report | impact` |
| `docs/ledger-schema.md` | The versioned ledger schema. |
| `.github/workflows/ci.yml` | pytest on Python 3.11 and 3.13. |
| `.github/workflows/smoke.yml` | Live trace of 3 real trials plus PubMed enrichment on PRs that touch `src/`. |
| `.github/workflows/trace.yml` | Weekly or manual bounded trace (200 trials), ledger carried in the Actions cache, uploaded as an artifact. Reads secret `OPENALEX_API_KEY` and variable `OPENALEX_MAILTO`. |

## 6. Where things stand

**Merged:** PR #1, the Fallout MVP. https://github.com/bastardpsycho/EH_claudemission/pull/1, merge commit `0766d06`. Foot approved the merge.

**Merged:** PR #2, "Retry trials that errored on a previous trace run". https://github.com/bastardpsycho/EH_claudemission/pull/2, merge commit `e7db6f2`.
- `trace` now retries trials whose last status was `error`. Before this, they were skipped forever.
- The README and `openalex.py` docstring now document OpenAlex's key rules, checked against its docs.

**Merged:** PR #3, which adds this file. Foot asked for all three PRs to be merged.

**Open:** PR #4 (this update to the file), https://github.com/bastardpsycho/EH_claudemission/pull/4.

**Open:** PR #5, `fallout validate`, https://github.com/bastardpsycho/EH_claudemission/pull/5 (branch `claude/vitality-validation`).
- `scripts/build_vitality_gold.py` builds `validation/vitality_trials.csv` and `validation/vitality_inclusions.csv` from VITALITY's OSF data (CC BY 4.0; provenance and hashes are in `validation/README.md`).
- `src/fallout/validate.py` reports population recall, citation and synthesis recall over verified pairs, and review-level agreement.
- It also corrects three README statements about VITALITY (see section 3).

**Open:** PR #6, wider population and Cochrane labels, https://github.com/bastardpsycho/EH_claudemission/pull/6 (branch `claude/rct-population`, **stacked on #5**).
- `fallout pubtypes` fetches PubMed publication types for Health Sciences "Research Article" retractions, plus abstracts for the untyped ones (only the matched phrase is kept). `--population trials` adds records PubMed types as trials, or whose abstract describes random allocation of people.
- Records carry `selected_by` and `subjects`. `fallout validate` reports a selection-precision proxy per rule.
- Cochrane `.pubN` DOIs are labelled `systematic_review`, and `enrich` re-classifies every edge.

**Open:** PR #7, `fallout inclusion`, https://github.com/bastardpsycho/EH_claudemission/pull/7 (branch `claude/inclusion`, **stacked on #6**).
- Reads PMC full text (NCBI ID converter by GET, then efetch) and records an `inclusion` verdict with `strength` (`table` or `results_citation`), signals and source on synthesis edges.
- `validate` scores the check on verified pairs and on negatives; the report and CSV show it.

**Merge order: #4, #5, #6, #7.** Foot approved merging #4 and #5 on 2026-10-27, but the session's auto-mode permission check blocked the merge call, so a person (or a session with that permission) has to merge them.

**Side branch `claude/findings-run`** (not for merging). It is `main` (as of PR #2) plus:
- `.github/workflows/findings.yml` runs on push to this branch when the workflow or `scripts/summarize_findings.py` changes. It restores the partial ledger from the Actions cache (`findings-ledger-*`) and traces with `--limit 5000` under a 75-minute step timeout with `continue-on-error`. It then saves the cache, runs `fallout enrich`, runs the summary script, and commits `findings/` back to the branch.
- `scripts/summarize_findings.py` writes `findings/summary.json` and `findings/syntheses_citing_after_retraction.csv`.
- `scripts/summarize_findings.py` takes the RW CSV as an optional third argument and then also reports `trials_in_population`, `trials_untraced` and `trials_pending_retry` (commit `9445829`). It also counts `trials_citing_may_be_truncated` (commit `c03fcf1`).
- Commit `3bd3609` passes `OPENALEX_API_KEY: ${{ secrets.OPENALEX_API_KEY }}` to the trace step.
- Branches `claude/vitality-validation`, `claude/rct-population` and `claude/inclusion` are merged in.
- `findings.yml` runs, in order: `fallout pubtypes`, a trace with `--population trials`, `enrich`, `inclusion` (40-minute timeout, `continue-on-error`), cache save, summary, then `validate` twice. Output goes to `findings/validation/` (the clinical-study population) and `findings/validation-trials/`.
- The workflow re-runs on changes to `src/fallout/**`, `validation/**`, the workflow itself or the summary script.
- `findings/`: results of run 40374400563 (18:15 UTC, commit `4a21c17`), the first run with the key. **The trace is complete**: 747 trials in 5.5 minutes (the 607 untraced plus the 140 retries), zero errors. Run 40376496151 (18:23 UTC, commit `71e0571`) only re-summarised with the truncation count and changed no other number. Run 40560357475 (commit `e50ea54`, 2026-10-27) holds the latest output, including inclusion verdicts.

## 7. Results so far, with caveats

Retraction Watch data was pulled 2026-10-26; the latest retraction in the file is 2026-10-09.
- 73,356 records, of which 67,916 are retractions.
- 2,729 are retractions labelled "Clinical Study", once reinstated items are dropped.
- Median time from publication to retraction for those: 639 days.

The trace covers all 2,729 studies (run 40374400563):
- 2,613 resolved in OpenAlex, 113 had no DOI, 3 were not found, 0 errored.
- The 113 without a DOI cannot be traced through OpenAlex. They are spread across years: 35 were retracted before 2011 and 78 since.

Findings:
- 72,151 citing works.
- 6,519 citation links from syntheses: 4,226 meta-analyses, 1,679 systematic reviews, 614 guidelines. 5,052 are "high" confidence and 1,467 "medium".
- **1,264** retracted studies are cited by at least one synthesis.
- **2,226 distinct syntheses cite a study after its retraction**; 1,854 of them more than 180 days after. These come from 2,566 links: 1,614 meta-analysis, 737 systematic review, 215 guideline.
- 944 retracted studies are cited by a synthesis after their retraction.
- Post-retraction synthesis citations by publication year: 2010: 37 · 2013: 93 · 2016: 116 · 2019: 139 · 2021: 214 · 2022: 233 · 2023: 195 · 2024: 312 · 2025: 232 · 2026 (to October): 144. Full series in `findings/summary.json`.

Caveats (always state these):
1. A citation is not inclusion.
2. Publication dates can be year-only or lag acceptance. 144 of the 2,566 after-retraction links have a 1 January date. That is why the 180-day count is shown.
3. RW's "Clinical Study" label includes non-randomised studies.
4. 812 of the 2,729 studies were retracted in 2023, 644 of them from Hindawi, during the paper-mill wave.
5. 113 studies (4.1%) have no DOI and are not traced.
6. A random spot-check of 12 rows (on the earlier, partial run) looked plausible, but there has been no systematic precision check.
7. 2 traced studies hit the `--max-citing 2000` cap, so their citing works may be undercounted.
8. The counts come from one OpenAlex snapshot and are bounded by OpenAlex's citation coverage, which has not been measured here.

### Validation against VITALITY (run 40405439120)

| Check | Result |
|---|---|
| VITALITY's 1,330 retracted RCTs in Fallout's population | 842 (63.3%). 417 are labelled only "Research Article" in RW, 45 have DOIs not in RW, 24 have no DOI, 2 were excluded by nature or reinstatement |
| VITALITY index trials in the population | 243 of 323 |
| Verified (trial, review) pairs checkable | 628 of 850 (179 trial outside the population, 43 review without DOI) |
| Citation recall | 598 / 628 (95.2%). Of the 30 misses, 25 reviews are absent from the ledger and 5 cite other trials in it |
| Synthesis recall | 574 / 628 (91.4%). 24 found reviews were labelled "other": 10 Cochrane reviews, 3 "protocol" titles |
| Synthesis citations of VITALITY trials up to 2024-11-21 that VITALITY lists as pooling reviews | 884 / 3,289 (26.9%); 32.3% ignoring Cochrane versions. Meta-analysis label: 835 / 2,258 (37.0%; 43.1%). SR: 6.5%. Guideline: 0.3% |

How to read it:
- VITALITY files each review under one index trial, so the pairs are true but incomplete.
- If VITALITY's search was complete, the agreement row is an **upper bound** on "a synthesis citation means the review pooled that trial in a pairwise meta-analysis". It is not the precision of Fallout's "cites" claims. Low shares for SRs and guidelines are expected, because VITALITY counted only reviews with a pairwise meta-analysis.
- Spot check: of 25 random non-matching "meta-analysis" citations (after retraction, before the cut-off), 24 were syntheses by title and 1 was a commentary.
- Takeaway: Fallout finds the citations (about 95%), but most synthesis citations of a retracted trial are not verified pooling. That supports keeping "cites" and makes step 4 (inclusion verification) the priority. The population filter is the biggest recall loss.

### Wider population (PR #6; runs 40550938193 and 40554396901)

- Of 14,709 Health Sciences research-article retractions, PubMed types 300 as trials and the abstract rule adds 181. The population is now 3,211; 3,080 were traced, 128 have no DOI and 3 were not found.
- VITALITY trials in the population: 842 → **1,074 of 1,330 (80.8%)**; index trials 243 → 289 of 323. 185 VITALITY trials still have neither signal.
- Selection-precision proxy: of each rule's trials retracted by 2024-11-05, the share in VITALITY's cohort:
  - "Clinical Study" label: 34% (841 / 2,452);
  - PubMed "Randomized Controlled Trial": 72% (153 / 214);
  - abstract rules: 48% (75 / 156);
  - PubMed "Clinical Trial" or "Controlled Clinical Trial": 3–9%, mostly non-randomised trials. These are still clinical studies, as with RW's own label.
- The Cochrane rule cut verified reviews labelled "other" from 24 to 14. Synthesis recall is 93.2% on 737 checkable pairs.

### Inclusion check (PR #7; run 40560357475)

| | All synthesis citations | Published after retraction | >180 days after |
|---|---|---|---|
| Full text read (PMC) | 2,522 | 1,140 | 927 |
| Inclusion evidence | 1,471 (58.3%) | 642 (56.3%) | 500 |
| …from a table, included-studies section or list | 882 | 380 | 288 |
| Cited only outside the Results | 879 | 411 | 343 |
| Distinct syntheses with table evidence | 758 | **355** | **271** |

- About two thirds of synthesis citations could not be checked: 4,298 are not in PMC, and 962 are in PMC without open full text.
- On VITALITY's verified pairs, 259 of 267 (97.0%) show evidence, 73.4% from a table. On 22 negatives, 9 do, 4 from a table. The negatives test "pooled", not "included in the review"; their table hits look like real inclusions that VITALITY's meta-analyses did not count.
- **Manual spot check:** in 20 random after-retraction citations with table evidence, the trial was listed as an included study in all 20. By the rule of three, that puts the 95% lower bound on precision at about 85%.
- Not read: figures (forest plots) and supplementary files.
- Headline for the report, with the caveats: at least 355 systematic reviews or meta-analyses published after a trial's retraction list that trial among their included studies, counting only the third of citing syntheses whose full text is open in PMC.

## 8. The OpenAlex API key (needs Foot)

OpenAlex's authentication docs (https://developers.openalex.org/api-reference/authentication, read 2026-10-26):
- **No key:** $0.10 of usage per day.
- **Free key:** $1 per day.
- The budget resets at midnight UTC. The key goes in the `api_key` query parameter, which is what `openalex.py` already does.
- HTTP 429 means the daily budget or 100 requests per second was exceeded. The docs don't describe the 401s we saw.

Steps for Foot:
1. Sign up or log in at https://openalex.org and create an API key in the account's API settings.
2. In GitHub, open `bastardpsycho/EH_claudemission`, then **Settings → Secrets and variables → Actions → New repository secret**.
3. Name it `OPENALEX_API_KEY` and paste the key as the value. Optionally, add a repository variable `OPENALEX_MAILTO` with a contact email.
4. Tell the Claude session the key has been added. Never paste the key into chat or commit it.

**Done** (Foot added the secret on 2026-10-26). The session proxy blocks listing secrets, so this was not checked directly; run 40374400563's zero errors and speed are the evidence that the key works.

## 9. Gotchas

- **2-hour job limit.** One GitHub Actions job cannot trace all 2,729 trials; the first attempt timed out at 120 minutes. Keyless runs are slow because of 429 back-off. That is why `findings.yml` caps the trace at 75 minutes and resumes from the cache.
- **Logs.** `gh api .../actions/jobs/<id>/logs` redirects to a blob host that the session proxy blocks. Read logs with the GitHub MCP tool `get_job_logs` (`return_content: true`). Artifacts can't be downloaded either, so the findings run commits its outputs to the branch instead.
- **Network from the cloud container.** OpenAlex, Crossref and OSF return 403 through the proxy (NCBI works; see below). The WebFetch tool can still download OSF files: follow `https://osf.io/download/<guid>/` through its two redirects quickly, because the final signed URL expires in 60 seconds, and check the SHA-256 against the OSF API. gitlab.com (the RW CSV), GitHub and PyPI work. Live tracing can only run in GitHub Actions. Unit tests use hand-built fixtures; `smoke.yml` is the live check.
- **Shallow clone.** Fetch branches explicitly, e.g. `git fetch origin claude/findings-run && git checkout -B claude/findings-run FETCH_HEAD`.
- **Triggering the findings run.** A push to `claude/findings-run` starts it only if it touches `.github/workflows/findings.yml`, `scripts/summarize_findings.py`, `src/fallout/validate.py` or `validation/**`, and the commit message has no `[skip ci]`. `workflow_dispatch` won't work, because the workflow is not on the default branch.
- **The run commits back to its own branch.** Pull before pushing to `claude/findings-run`.
- **Cache keys.** `actions/cache/save` writes `findings-ledger-<run_id>`, and the next run restores the newest one by prefix. If the cache is evicted (after 7 days unused), the trace restarts from zero, which is fine with a key.
- **NCBI from the container.** `eutils.ncbi.nlm.nih.gov` and the PMC ID converter work from the container (checked 2026-10-27; an earlier version of this file said PubMed returned 403). Europe PMC returned 503 on 2026-10-27. The ID converter accepts **GET only** (POST gets HTTP 400). Use this for live tests; the ledger itself lives only in the Actions cache.
- **`continue-on-error` hides failures.** A failed step still reports "success". Check that the step's output file is non-empty (the first inclusion run died in 2 seconds unnoticed).
- **Merging.** The auto-mode permission check denied `PUT /pulls/<n>/merge`, so merges need a person or an explicit permission rule.
- **Remote-tracking refs.** The shallow clone tracks only `main`, so `git status` (and the stop hook) reports a pushed side branch as unpushed. Fix with `git config --add remote.origin.fetch '+refs/heads/<branch>:refs/remotes/origin/<branch>'` and a fetch.

## 10. Next steps, in order

1. ~~Get the key in place~~ (done, section 8).
2. ~~Finish the trace~~ (done, run 40374400563; section 7 updated; decision report updated).
3. ~~Validate against VITALITY~~ (done, PR #5; results in section 7). Follow-ups, in order of measured impact:
   - ~~Widen the population~~ (PR #6: 63% → 81% of VITALITY's trials).
   - ~~Classify Cochrane reviews~~ (PR #6).
   - **Check precision by hand.** Sample synthesis labels systematically, not by title alone. Still open.
4. ~~Verify inclusion~~ (PR #7; results in section 7). Follow-ups:
   - Widen coverage beyond PMC, e.g. Europe PMC full text, and publisher XML where licences allow.
   - Read forest-plot study labels where figures carry text.
   - Build a larger hand-checked set of "cited outside the Results" cases, to estimate how many hide inclusion in figures.
5. **Link guidelines.** Import reference lists from NICE, WHO and MAGICapp, since many guidelines lack DOIs.
6. **Recompute where the data is open.** Use leave-one-out on Cochrane open data packages and VITALITY reconstructions, with a provenance badge.
7. **Publish the ledger** on GitHub Pages (needs Foot to enable Pages) and offer the feed to Cochrane, GIN and the VITALITY team.

Biggest open risk: no one has shown that guideline developers act on alerts. Validation (step 3) should come before outreach (step 7).
