# Handover: Save Humanity / Fallout

Pick-up file for the next Claude session. Written 2026-10-26 at about 17:45 UTC. Read this first, then `README.md`.

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
- 1,330 retracted RCTs were pooled in 847 systematic reviews.
- Of 3,902 meta-analyses re-run without them, 20.6% changed direction or significance: direction alone 8.4%, significance alone 16.0%, both 3.9%.
- 157 guidelines were fed by distorted meta-analyses.
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

**Merged:** PR #3, which adds this file. Foot asked for all three PRs to be merged, and no PRs are open.

**Side branch `claude/findings-run`** (not for merging). It is `main` (as of PR #2) plus:
- `.github/workflows/findings.yml` runs on push to this branch when the workflow or `scripts/summarize_findings.py` changes. It restores the partial ledger from the Actions cache (`findings-ledger-*`) and traces with `--limit 5000` under a 75-minute step timeout with `continue-on-error`. It then saves the cache, runs `fallout enrich`, runs the summary script, and commits `findings/` back to the branch.
- `scripts/summarize_findings.py` writes `findings/summary.json` and `findings/syntheses_citing_after_retraction.csv`.
- `findings/`: results of the latest run (run 40349479205, 16:46 UTC).
- The last commit, `3bd3609`, "Pass the OpenAlex API key to the findings run [skip ci]", is **pushed**. It adds one line to the trace step's `env`: `OPENALEX_API_KEY: ${{ secrets.OPENALEX_API_KEY }}`. `[skip ci]` kept it from starting a keyless run.

## 7. Results so far, with caveats

Retraction Watch data was pulled 2026-10-26; the latest retraction in the file is 2026-10-09.
- 73,356 records, of which 67,916 are retractions.
- 2,729 are retractions labelled "Clinical Study", once reinstated items are dropped.
- Median time from publication to retraction for those: 639 days.

The trace runs from the most recent retraction backwards and has reached 2013. Of the 2,729 studies:
- 2,122 processed: 1,920 resolved in OpenAlex, 60 had no DOI, 2 were not found, 140 errored (120 HTTP 429, 20 HTTP 401).
- **607 oldest not yet traced.**

Findings so far:
- 35,196 citing works.
- 4,636 citation links from syntheses: 3,061 meta-analyses, 1,200 systematic reviews, 375 guidelines. 3,545 are "high" confidence and 1,091 "medium".
- **906** retracted studies are cited by at least one synthesis.
- **1,319 distinct syntheses cite a study after its retraction**; 1,013 of them more than 180 days after. These come from 1,455 links: 924 meta-analysis, 438 systematic review, 93 guideline.
- 618 retracted studies are cited by a synthesis after their retraction.
- Post-retraction synthesis citations by publication year: 2016: 37 · 2019: 84 · 2021: 164 · 2022: 183 · 2023: 162 · 2024: 282 · 2025: 212 · 2026 (to October): 122.

Caveats (always state these):
1. A citation is not inclusion.
2. Publication dates can be year-only or lag acceptance. Only 62 of the 1,455 after-retraction links have a 1 January date. That is why the 180-day count is shown.
3. RW's "Clinical Study" label includes non-randomised studies.
4. 812 of the traced studies were retracted in 2023, 644 of them from Hindawi, during the paper-mill wave.
5. Coverage is incomplete (see the numbers above).
6. A random spot-check of 12 rows looked plausible, but there has been no systematic precision check.

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

## 9. Gotchas

- **2-hour job limit.** One GitHub Actions job cannot trace all 2,729 trials; the first attempt timed out at 120 minutes. Keyless runs are slow because of 429 back-off. That is why `findings.yml` caps the trace at 75 minutes and resumes from the cache.
- **Logs.** `gh api .../actions/jobs/<id>/logs` redirects to a blob host that the session proxy blocks. Read logs with the GitHub MCP tool `get_job_logs` (`return_content: true`). Artifacts can't be downloaded either, so the findings run commits its outputs to the branch instead.
- **Network from the cloud container.** OpenAlex, Crossref, PubMed and OSF return 403 through the proxy. gitlab.com (the RW CSV), GitHub and PyPI work. Live tracing can only run in GitHub Actions. Unit tests use hand-built fixtures; `smoke.yml` is the live check.
- **Shallow clone.** Fetch branches explicitly, e.g. `git fetch origin claude/findings-run && git checkout -B claude/findings-run FETCH_HEAD`.
- **Triggering the findings run.** A push to `claude/findings-run` starts it only if it touches `.github/workflows/findings.yml` or `scripts/summarize_findings.py` and the commit message has no `[skip ci]`. `workflow_dispatch` won't work, because the workflow is not on the default branch.
- **The run commits back to its own branch.** Pull before pushing to `claude/findings-run`.
- **Cache keys.** `actions/cache/save` writes `findings-ledger-<run_id>`, and the next run restores the newest one by prefix. If the cache is evicted (after 7 days unused), the trace restarts from zero, which is fine with a key.

## 10. Next steps, in order

1. **Get the key in place** (section 8). Until then, live tracing is limited to $0.10 a day.
2. **Finish the trace.** Make a real change on `claude/findings-run` that touches `findings.yml` or `scripts/summarize_findings.py`, with no `[skip ci]`, and push it. One useful change: add a `"trials_untraced"` count to the summary. Expect 1–2 runs for the remaining 607 trials plus the 140 retries. Then update section 7 of this file and the report's findings section.
3. **Validate against VITALITY.** Their datasets are on OSF (https://osf.io/ukg3j), which is reachable only from Actions. Measure Fallout's recall and precision on known contaminated reviews before any public claim.
4. **Verify inclusion.** For open-access syntheses in PubMed Central, parse the included-studies list and record a separate `inclusion` field with its provenance. This answers the main critique.
5. **Link guidelines.** Import reference lists from NICE, WHO and MAGICapp, since many guidelines lack DOIs.
6. **Recompute where the data is open.** Use leave-one-out on Cochrane open data packages and VITALITY reconstructions, with a provenance badge.
7. **Publish the ledger** on GitHub Pages (needs Foot to enable Pages) and offer the feed to Cochrane, GIN and the VITALITY team.

Biggest open risk: no one has shown that guideline developers act on alerts. Validation (step 3) should come before outreach (step 7).
