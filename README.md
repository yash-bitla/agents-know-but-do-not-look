# Agents Know, But Do Not Look: An Empirical Study of Misjudged Action Effects in AI Coding Agents

Data and code for the paper of the same name (working title). The paper studies AI coding agents that destroy user data. The study asks three questions:

1. **RQ1. Incident study.** How do coding agents destroy user data, according to public bug reports?
2. **RQ2. Sandbox replay.** Do the commands in those reports really do what the reports say?
3. **RQ3. Effect prediction.** Can a language model tell what a command will do before it runs?

## Main numbers

| | Count |
|---|---|
| Issues found by search | 26,087 (round 2, 21 trackers) + 1,809 (round 1, 4 trackers) |
| Reports read by a human | 1,498 |
| Human-verified incidents | 1,204 |
| Cause M: the agent misjudged the effect | 669 (65.7% of the 1,018 with a clear cause) |
| Cause I: the agent meant to destroy | 328 |
| Cause W: a setting picked the wrong target | 21 |
| Cause U: the report does not say | 186 |

Mechanisms of the 669 M incidents: O overwrite by an edit 257, G git also discarded user work 112, T hidden tool behaviour 80,
X other 67, S script or test the agent wrote 50, P platform difference 42, E expansion or quoting 31, F file-system side effect 30.

Sandbox: 26 of 29 rebuilt commands destroy data, and 22 of those 26 exit with status 0. None of the 29 corrected "safe twin" commands do.

Prediction (26 dangerous + 26 safe commands, 3 samples each):

| Model | Full context: caught / false alarms | Command only: caught / false alarms |
|---|---|---|
| Claude Haiku | 73/78, 3/78 | 59/78, 13/78 |
| Claude Sonnet | 78/78, 0/78 | 60/78, 3/78 |
| Claude Opus | 78/78, 0/78 | 66/78, 3/78 |
| gpt-6.1-sol (Codex CLI) | 77/78, 3/78 | 59/78, 4/78 |

## Data

| File | What it holds |
|---|---|
| `data/incidents.csv` | The final census: one row per human-verified incident (url, repo, created, round, cause, mechanism) |
| `data/human_reviewed.csv` | Every report a human read (1,498 rows): AI label, human label, final label, mechanism, duplicate link, notes |
| `labelling/census_all.json` | Same as `incidents.csv`, as JSON |
| `labelling/AGREEMENT.md` | Agreement between the human and the AI labels, hidden-check results, batch table, normalised time trend |
| `labelling/GUIDE.md`, `labelling/RUBRIC.md` | The labelling guide the human followed and the rubric given to the AI |
| `labelling/ai_labels_sheet*.json` | The AI labels, hidden from the human during labelling |
| `labelling/final_labels*.json`, `human_labels.json`, `mechanisms_partB.json` | Human labels per workbook (round 1: sheet 1 and sheet 2; round 3: batches 1 to 4) |
| `labelling/recheck_sheet3_batch1_verdicts.json` | Second-opinion check of the 151 batch-1 disagreements (robustness only, not used in the census) |
| `labelling/workbooks/` | The completed labelling workbooks |
| `candidates.json`, `filtered.json`, `labels.jsonl` | Round 1: search hits, title filter, AI labels |
| `round2/hits.jsonl` | Round 2: every search hit (url, title, date, repo, phrase) |
| `round2/screen1.jsonl`, `round2/labels2.jsonl` | Round 2: stage-1 screen (Haiku) and stage-2 rubric labels (Sonnet) |
| `round2/volume.json` | Issues per tracker per half-year, the denominator for the time trend |
| `bench/results.json`, `bench/predictions*.jsonl` | Sandbox replay results and model predictions |

Issue bodies are **not** included. They belong to their authors. `collect1.py` and `round2/fetch_bodies.py` download them again from GitHub.
Some files hold issue titles and short quotes from public issues, for reference.

## Labels

- **incident**: Y when the agent itself deleted, overwrote or reset real user data.
- **cause**: M misjudged effect, I intended destruction, W wrong target, U unclear. The test question: "If the assistant had known exactly what the command would do, would it still have run it?"
- **mechanism** (M only): E, P, G, T, F, S, O, X. See `labelling/GUIDE.md`, Part 2.

## Pipeline

```
Round 1   collect1.py -> candidates.json -> filtered.json + issues/ -> classify.py -> labels.jsonl -> human sheets 1 and 2
Round 2   round2/collect2.py -> hits.jsonl -> fetch_bodies.py -> round2/issues/
          -> filter1_batch.py (Haiku, high recall) -> screen1.jsonl
          -> classify2.py (Sonnet, full rubric) -> labels2.jsonl -> human batches 1 to 4 (+80 hidden checks)
Census    labelling/census_all.py -> census_all.json ; labelling/export_csv.py -> data/*.csv
Trend     round2/volume.py -> volume.json ; labelling/trend_normalised.py
Sandbox   bench/run.py (Docker) -> results.json ; bench/predict.py, bench/predict_codex.py -> predictions*.jsonl
```

The census, CSV and trend scripts run on the released files alone:

```
python3 labelling/census_all.py
python3 labelling/export_csv.py
python3 labelling/trend_normalised.py
```

Collection and labelling need the GitHub CLI (`gh`, logged in) and the Claude Code CLI (`claude`). GitHub search results change over time, so a new collection returns a different set. The released files are the sets used in the paper.

## Sandbox safety

`bench/run.py` runs destructive commands. It runs them only inside Docker containers with `--network none` and no host folders mounted. Do not run the commands in `bench/cases.py` on your own machine.

```
cd bench
docker build -t cmdfx-base .
python3 run.py              # all cases, writes results.json
python3 predict.py          # Claude models, text only, nothing executed
python3 predict.py --blind
```

`predict_codex.py` runs Codex CLI in its own container (`bench/codex-image/`) in read-only mode. It copies only `~/.codex/auth.json` into that container and removes the container afterwards.

## Limits

- Bug reports show what people choose to report. They do not give a rate of damage per agent session.
- One person labelled the reports. AI labels were a second rater. Agreement is in `labelling/AGREEMENT.md`.
- The sandbox covers shell commands. File-edit overwrites (mechanism O) are not replayed.
- 58% of incidents come from one tracker (anthropics/claude-code).

## License

Code: MIT (`LICENSE`). Labels and derived data: CC BY 4.0 (`DATA_LICENSE.md`). Issue titles and quotes remain the property of their authors.
