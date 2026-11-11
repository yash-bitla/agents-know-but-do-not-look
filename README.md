# Agents Know, But Do Not Look: An Empirical Study of Misjudged Action Effects in AI Coding Agents

Data and code for the paper of the same name. The paper studies AI coding agents that destroy user data, and asks three questions:

1. **How do coding agents destroy user data?** How often is the cause a *misjudged effect*, where the agent meant a small, safe action and the action did more than it expected?
2. **Do the reported actions really cause the reported loss?** We replay each incident in a sealed sandbox.
3. **Can a language model predict the effect of a command before it runs,** with and without the state of the machine?

## Main results

**Incident census** (public issue trackers of 21 coding agents)

| | Count |
|---|---|
| Issues found by the search | 26,087 |
| Reports flagged by the screen and read by the author | 1,375 |
| Human-verified incidents | 1,198 |
| Cause M: the agent misjudged the effect | 666 (65.7% of the 1,014 with a clear cause) |
| Cause I: the agent meant to destroy the data | 328 |
| Cause W: a setting outside the command picked the wrong target | 20 |
| Cause U: the report does not say enough | 184 |

Mechanisms of the 666 M incidents: O overwrite by an edit 255, G git also discarded user work 112, T hidden tool behaviour 80,
X other 66, S script or test the agent wrote 50, P platform difference 42, E expansion or quoting 31, F file-system side effect 30.

**Replay** (one case per M incident, audited by the author against its report)

| | Count |
|---|---|
| Replayable cases | 249 (177 command, 72 edit) |
| Rated faithful or acceptable by the audit | 236 (94.8%) |
| Command cases that reproduce the reported loss | 165 of 169 (97.6%) |
| ...and still exit with status 0 | 142 of 165 (86%) |
| Safe twins that destroy data | 0 |

**Prediction** (share of answers that call an item destructive, %)

| Model | Real incidents, command only | Real incidents, with state | Safe near-misses, command only | Safe near-misses, with state |
|---|---|---|---|---|
| Claude Haiku 5.5 | 83.9 | 92.4 | 66.3 | 7.2 |
| Claude Sonnet 5.5 | 81.3 | 94.8 | 51.8 | 7.2 |
| Claude Opus 5.5 | 84.3 | 95.4 | 55.4 | 3.6 |
| GPT-6.1-sol (Codex CLI) | 82.5 | 94.0 | 57.2 | 5.4 |

With the machine state, models catch most destructive commands and rarely raise false alarms. From the command alone, they miss about one in six and cannot tell a dangerous command from a nearly identical safe one. Full scores are in `replay/predictions_scores.json`.

## How the study works

```
Search      round2/collect2.py         21 trackers, 18 neutral + 6 command phrases  -> round2/hits.jsonl (26,087 issues)
Screen      round2/filter1_batch.py    stage 1, Claude Haiku, high recall            -> round2/screen1.jsonl (4,917 kept)
            round2/classify2.py        stage 2, Claude Sonnet, labelling rubric      -> round2/labels2.jsonl (1,375 flagged)
Label       the author, blind to the model labels, with labelling/GUIDE.md           -> labelling/final_labels*.json
Census      labelling/census_all.py, labelling/export_csv.py                          -> data/incidents.csv (1,198)
Trend       round2/volume.py, labelling/trend_normalised.py                           incidents per 10,000 issues
Replay      replay/build.py            Claude Opus drafts one case per M incident    -> replay/builds.jsonl
            replay/run.py              Docker sandbox, --network none, no mounts     -> replay/results.jsonl
            replay/audit.py            the author audits every case                  -> replay/audit/final_verdicts.json
Variants    replay/variants.py         2 synthetic variants per case, labelled by execution -> replay/variants/
Prediction  replay/predict.py          4 models, blind and full context              -> replay/predictions.jsonl
            replay/score_predict.py                                                   -> replay/predictions_scores.json
```

**Pilot.** The first search (`collect1.py`, files `candidates.json`, `filtered.json`, `labels.jsonl`, labelling sheets 1 and 2) was a pilot on 4 trackers. It shaped the search terms, the screen and the labelling guide. The census counts only incidents that the final pipeline flags. The final pipeline flags 171 of the 175 pilot incidents. The other 4, and 1 incident found among the hidden recall checks, are out of scope. In file names, "round 1" is the pilot, "round 2" is the final search, and "sheet 3" or "round 3" is the labelling of the final search.

**Replay honesty rules.** The case builder sees only the issue text and fixed rules, never a replay result. It builds each case once, and rebuilds a case only after a harness error. Every build attempt is kept in `replay/builds.jsonl`. Cases that the audit rated unfaithful are excluded from all replay and prediction results. See `replay/NOTES.md` for the audit criterion, every reassessment with its reason, and the control-layer failures.

## Data

| File | What it holds |
|---|---|
| `data/incidents.csv` | The census: one row per human-verified incident (url, repo, created, round, cause, mechanism) |
| `data/human_reviewed.csv` | Every report the author labelled (1,498 rows): model label, human label, final label, mechanism, duplicate link, notes |
| `labelling/GUIDE.md`, `labelling/RUBRIC.md` | The labelling guide and the rubric given to the screening model |
| `labelling/census_all.json`, `labelling/AGREEMENT.md` | The census as JSON. Agreement between the author and the model labels, and the time trend. |
| `labelling/corrections.json` | Label corrections found after the census was final |
| `labelling/report_features.json` | Aggregate features of the incident reports (form, version, pasted command, length) |
| `labelling/workbooks/`, `labelling/final_labels*.json` | The completed labelling workbooks and the labels taken from them |
| `round2/hits.jsonl`, `round2/screen1.jsonl`, `round2/labels2.jsonl`, `round2/volume.json` | Search hits, the two screening stages, and issues per tracker per half-year |
| `replay/builds.jsonl`, `replay/results.jsonl` | Every replay case with every build attempt, and every replay result |
| `replay/audit/` | The audit workbooks as the author filled them in, the reassessments, and `final_verdicts.json` |
| `replay/variants/` | The synthetic variants and their execution results |
| `replay/predictions.jsonl`, `replay/predictions_scores.json` | Every model answer, and the scores |
| `replay/EDIT_CONTRACTS.md`, `replay/edit_tools.py` | The nine edit-tool contracts used to replay edit incidents, with their sources and tests |

Issue bodies are **not** included. They belong to their authors. `collect1.py` and `round2/fetch_bodies.py` download them again from GitHub.
Some files hold issue titles and short quotes from public issues, for reference.

## Labels

- **incident**: Y when the agent itself deleted, overwrote or reset real user data.
- **cause**: M misjudged effect, I intended destruction, W wrong target, U unclear. The test question: "If the agent had known exactly what the command would do, would it still have run it?" A violated instruction alone does not make a case I.
- **mechanism** (M only): O, G, T, X, S, P, E, F. See `labelling/GUIDE.md`, Part 2.

## Reproduce

The census, the CSV files, the trend, the audit and the prediction scores run on the released files alone:

```
python3 labelling/census_all.py
python3 labelling/export_csv.py
python3 labelling/trend_normalised.py
cd replay
uv run -q --with openpyxl python audit.py --freeze
python3 score_predict.py
python3 test_edit_tools.py
```

Collection, screening, case building and prediction need the GitHub CLI (`gh`, logged in) and the Claude Code CLI (`claude`). The Codex predictions need the Codex CLI. GitHub search results and model outputs change over time, so a new run gives a different set. The released files are the ones used in the paper.

## Sandbox safety

`replay/run.py` and `replay/variants.py` run destructive commands, such as `rm -rf` and `git reset --hard`. They run them only inside Docker containers with `--network none`, no host folders mounted, and a time limit. **Do not run the commands in `replay/builds.jsonl` or `replay/variants/` on your own machine.**

```
cd replay
docker build -t cmdfx-replay .
python3 run.py              # replays every built case not yet replayed, appends to results.jsonl
python3 variants.py run     # replays the synthetic variants
```

`predict.py` asks the Codex model through the Codex CLI in its own container (`bench/codex-image/`), in read-only mode. It copies only `~/.codex/auth.json` into that container and removes the container afterwards.

`bench/` holds an earlier 29-case prototype of the sandbox. The replay study in `replay/` replaces it.

## Limits

- Bug reports show what people choose to report. They give the make-up of incidents, not a rate of damage per agent session.
- One person labelled the reports and audited the replay cases. The model labels show how stable the guide is, but they are not a second human rater.
- A model drafted the replay cases and the variants. The same model family is also tested in the prediction study.
- The sandbox runs Linux. Windows-only and cloud incidents are not replayed, so the replay results speak most strongly for git, expansion and script losses.
- 58% of incidents come from one tracker (anthropics/claude-code).

## License

Code: MIT (`LICENSE`). Labels and derived data: CC BY 4.0 (`DATA_LICENSE.md`). Issue titles and quotes remain the property of their authors.
