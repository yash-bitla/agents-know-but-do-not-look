# Inter-rater agreement (2026-11-05)

Rater A: LLM labeller (`classify.py`, claude sonnet). Rater B: the author, by hand, using `GUIDE.md`, blind to rater A.
Sample: 100 of the 509 reports, stratified by rater A's label (35 M, 15 I, 8 U, 4 W, 38 N), shuffled.

| Decision | n | Raw agreement | Cohen's kappa |
|---|---|---|---|
| Incident Y/N | 100 | 99% | 0.98 |
| Cause M/I/W/U (both said Y) | 61 | 75.4% | 0.57 |
| M vs other (both said Y) | 61 | 78.7% | 0.56 |

Confusion (A, B) on cause: M-M 30, I-I 10, W-W 3, U-U 3, I->M 5, M->W 3, U->M 3, U->I 2, M->I 1, M->U 1.
The one incident disagreement: claude-code #81333 (A: Y/W, B: N, the report says nothing was lost). B is right.

## Re-estimate on all 509, using rater B as reference

P(B label | A stratum) times A's stratum sizes (M 105, I 45, U 27, W 6, N 326):
incidents about 182, M about 115 (63%), I about 40, W about 14, U about 13.

Earlier estimates: rater A alone 105/183 = 57%. Author's 25-item spot check 82/183 = 45%. All are above the 25% threshold.

## Main source of disagreement

W vs M (3 cases: #48, #74, #83): B used W when the agent's own action hit the wrong target.
Proposed rule: W only when a setting or environment outside the command chose the target (env file, cwd change, config).
If the agent itself built the wrong path or attached to the wrong object, label M.
I vs M on git commands (5 cases): the "would it still have run it?" test moved several cases to M.

Next: adjudicate the 15 disagreements together, then report pre- and post-adjudication numbers.

## After adjudication (author accepted the resolutions proposed in review)

Resolutions by sheet number: #13 #17 #40 #57 #72 -> M (follow "would it still have run it?"), #48 #74 #83 -> M (agent built the wrong target itself),
#64 #69 -> I (misread request, deleted on purpose), #77 -> M, #5 #56 #75 #79 -> U (mechanism not stated or not proven), #93 -> N. Saved in `final_labels.json`.

Final sample labels: N 39, M 39, I 12, U 7, W 3. Rater A matches the final cause on 52/61.
Re-estimate on 509: incidents about 182, M about 117 = 64.7%, 95% bootstrap interval 56.4% to 72.5% (5,000 resamples within strata).

## Sheet 2, Part A (121 remaining AI-flagged incidents), labelled by the author (2026-11-05)

Rater B labels are taken as final for Part A (no adjudication). Saved in `final_labels_sheet2.json`.
Agreement with rater A on cause (both Y): 95/114 = 83%, kappa 0.72. Incident: 114 Y, 7 N.

## Human-verified census of all 183 AI-flagged reports (sheet 1 final + Part A)

N 8, incidents 175: M 101 (57.7%), I 44 (25.1%), U 22, W 8.
The 326 reports rater A called non-incidents were checked by a 38-report sample, 0 errors.
Note: the W rule from the adjudication (agent-built wrong target = M) was not added to GUIDE.md before Part A.
Part A has 3 cases A=M, B=W. Under that rule M would be at most 104 (59.4%).

Mechanisms (Part A M cases only, 62): G 12, O 12, P 9, S 9, E 6, X 6, F 5, T 3. Part B (39 sheet-1 M cases) still open.

## Mechanisms for all 101 M incidents (Part A + Part B, author labels, 2026-11-05)

G git also wiped user work 21 (20.8%), O overwrite by an edit 18 (17.8%), P platform difference 12 (11.9%),
T hidden tool behaviour 12 (11.9%), S script or test the agent wrote 11 (10.9%), X other or unknown 11 (10.9%),
E expansion or quoting 8 (7.9%), F file-system side effect 8 (7.9%). Saved in `final_labels_sheet2.json` and `mechanisms_partB.json`.
Command-level mechanisms (all but O) cover 83 of 101 (82%). O comes from file-edit tools, not shell commands.

## Round 3: four workbooks of 1,277 rows (author labels, 2026-11-07)

1,197 AI-flagged reports + 80 hidden checks (50 stage-2 "not incident", 30 stage-1 dropped).

| Batch | Incidents | M | I | W | U | M of clear | Cause kappa vs AI |
|---|---|---|---|---|---|---|---|
| 1 | 253 | 138 | 80 | 0 | 35 | 63.3% | 0.35 |
| 2 | 269 | 141 | 79 | 6 | 43 | 61.8% | 0.63 |
| 3 | 251 | 153 | 55 | 3 | 40 | 72.5% | 0.59 |
| 4 | 262 | 140 | 72 | 4 | 46 | 64.8% | 0.60 |

- AI flag precision: 1,034 of 1,197 flagged rows are incidents (86.4%).
- Hidden checks: 1 of 50 stage-2 "N" rows was an incident (about 71 of 3,542 missed, 95% CI roughly 13 to 370). 0 of 30 stage-1 drops.
- Batch 1 recheck by 4 Claude reviewers on the 151 disagreements: M of clear 63.3% -> 62.4% with every change. The author kept their labels.
- GUIDE.md "Lessons from batch 1" was added before batch 2 (planned rewrite = I; bare "deleted without asking" = U). Kappa rose from 0.35 to about 0.6 after it.

## Final census, all human-labelled incidents (census_all.py -> census_all.json)

1,204 incidents (175 round 1 + 1,029 round 3, 6 marked duplicates dropped, 0 overlap).
M 669 (55.6% of all, **65.7% of the 1,018 with a clear cause**), I 328, W 21, U 186.
Mechanisms over 669 M: O 257, G 112, T 80, X 67, S 50, P 42, E 31, F 30. Not-O (command-level) 412 of 669 (62%).

## Time trend divided by tracker volume (labelling/trend_normalised.py, round2/volume.json, 2026-11-07)

Denominator: all issues per repo and half-year, same repos and same extra word for vscode/zed/warp as collect2.py.
Collection ended 2026-11-06, so 2026-H2 covers about 4 of 6 months in both numerator and denominator.

| Half | Issues | Incidents | per 10k | M | M per 10k | M of clear |
|---|---|---|---|---|---|---|
| 2024-H2 | 7,943 | 17 | 21.4 | 15 | 18.9 | 88% |
| 2025-H1 | 26,445 | 78 | 29.5 | 56 | 21.2 | 82% |
| 2025-H2 | 58,103 | 281 | 48.4 | 138 | 23.8 | 65% |
| 2026-H1 | 126,297 | 544 | 43.1 | 286 | 22.6 | 61% |
| 2026-H2 | 93,096 | 282 | 30.3 | 172 | 18.5 | 68% |

Claude Code alone: M per 10k = 25.9, 37.2, 37.0, 36.4 (2025-H1 to 2026-H2). All other trackers: 18.9, 20.6, 20.0, 11.7, 7.7.
