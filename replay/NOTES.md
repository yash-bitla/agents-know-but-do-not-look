# Tier A replay notes

## Files

- `builds.jsonl`: every build attempt (669 first builds, 2 repairs). The last attempt per id is the one replayed.
- `results.jsonl`: one replay per attempt. The last line per id is the final result.

## Repairs

Two cases were harness errors after the first build. `build.py --repair` rebuilt each one once, and both reproduced.

| Case | Harness error |
|---|---|
| claude_code_11416 | The check printed LOST on the state right after setup. |
| claude_code_97534 | The setup failed (`src/feature.py: No such file or directory`). |

## Replayed again

codex_42355 first gave `not_reproduced` with docker exit 125 (image not found). A duplicate replay loop ran at the same
time and removed the shared base image. The same build was replayed again (no rebuild) and reproduced. The new line in
`results.jsonl` has a `note` field.

## Twins that report LOST

Three safe twins report `lost: true`. In each one the twin keeps the data, and the check looks only at the original path.
These are faults in the check, not losses caused by the twin. The cases were not rebuilt, because the rules permit a rebuild
only for harness errors. The paper reports them as check faults.

| Case | Twin | Where the data goes |
|---|---|---|
| claude_code_11821 | `git stash push -m 'wip config before lint fix'` | git stash |
| claude_code_89254 | `git stash push ... -- src/app.py` | git stash |
| gemini_cli_19729 | `mv libs/sublib/.git.bak /home/dev/sublib-git-backup-$(date +%s)` | a backup folder in the home folder |

## Edit cases (mechanism O)

74 edit cases reproduce. 71 of them have `loss_source: call_content`: the call itself carries the loss, so the replay
reproduces it by construction. 62 of the 74 are `reconstructed`. Only 3 cases (`tool_contract`) test a tool behaviour.
The paper reports the 71 as a count and the 3 as tool-contract reproductions.
