# Labelling guide

This guide explains how to fill in the two columns in `sheet.csv`. No technical background is needed.
The examples below are **not** in your sheet, so they do not give away any answers.

Each row is a public bug report that a user wrote about an AI coding assistant
(Claude Code, Codex, Gemini CLI or Cline). Open the link, read the report, then answer two questions.

---

## Question 1: Did the AI assistant itself destroy something? (column `incident`, Y or N)

Answer **Y** only if all three are true:

1. **Something was lost or ruined.** Files, folders, a project, unsaved work, a database, a server, cloud resources or git history were deleted, overwritten, emptied or reset.
2. **The user's real data was hit.** Not a test copy that was meant to be thrown away.
3. **The assistant did it.** The assistant ran the command or made the edit that caused the loss.

### Clues that the assistant did it (lean Y)

- The report shows the command the assistant ran, often in a grey code box: `rm -rf ...`, `git reset --hard`, `Remove-Item`, `prisma migrate reset`, `DROP TABLE`.
- Words like "Claude ran", "the agent executed", "it deleted", "Codex wiped", "the AI overwrote".
- The report quotes the assistant admitting it: "I made a critical mistake by running ...".
- The report includes a transcript or a list of tool calls.

### Clues that it is NOT an assistant incident (lean N)

| The report is about | Example title | Answer |
|---|---|---|
| A feature request | "Allow deleting individual chat messages" | N |
| The app losing its own data (chats, settings, sessions) after an update or crash | "Desktop app update silently deleted all custom sidebar session groups" | N |
| A bug in the app's buttons or keys | "VS Code: Up Arrow overwrites unsent prompts with history" | N |
| A bug in a safety feature, with no data actually lost | "Built-in dangerous-rm safety check is spelling-dependent" | N |
| The assistant refusing to delete something | "Agent refuses to delete my bot's messages" | N |
| A command of the app itself, not the AI's choice | "`claude mcp remove` deletes the OAuth tokens" | N |

**Rule of thumb:** if a person could have lost the same data while using the app *with the AI turned off*, answer **N**.

---

## Question 2: Why did it happen? (column `cause`, only when incident = Y)

Pick exactly one letter. Ask this test question first:

> **"If the assistant had known exactly what the command would do, would it still have run it?"**
> - **No**, it would not: the effect surprised it. Usually **M**.
> - **Yes**, it wanted that effect, just without asking. Usually **I**.
> - The command was fine, but it hit the wrong place. **W**.
> - You cannot tell from the report. **U**.

### M: Misjudged effect

The assistant meant to do something **small or safe**, but the command did **more** than it expected.

Typical clues:
- "It was only supposed to delete X, but it deleted Y too."
- A **blank that turned out empty**: "the variable was empty", "expanded to `/`", "`$HOME`", "`~`".
- **Quoting or escaping** problems, or **Windows vs Linux** differences: "PowerShell", "backslash", "path with spaces".
- A **hidden shortcut**: "symlink", "junction", "it followed the link".
- A **git command that also threw away the user's own unsaved work**, when the assistant only meant to undo *its own* change.
- A **test or script the assistant wrote** that deleted real data by accident.
- A tool option that does more than its name suggests: "the API *replaces* the whole list", "Prisma *resets* the shadow database".

Examples (not in your sheet):
- A subagent cleaned up "its own" temp folder with a name pattern, and the pattern also matched other agents' folders. **M** (claude-code #104804)
- A test passed the text `"20; rm -rf ~"` to a program, and the computer ran `rm -rf ~` as a second command. **M** (claude-code #105342)
- The assistant ran `git checkout` and `git reset --hard` to switch branches, and git silently overwrote the user's private `.env` file. **M** (claude-code #104331)

### I: Intended destruction

The assistant **knowingly chose** to delete, reset, wipe or overwrite as part of its plan, **without permission** or **against an instruction**. It knew what the command does. It just should not have done it.

Typical clues:
- "To start fresh", "to clean up", "to fix the error, I reset the database".
- Commands whose purpose *is* destruction: `git reset --hard`, `git clean -fd`, `migrate:fresh`, `db reset`, `--force-reset`, `--accept-data-loss`, "destroy server", `DELETE`.
- "Even though I said not to", "during a code freeze", together with a command or reason that shows it chose the loss. "Without asking" **alone** is not enough for I (see "Lessons from batch 1" below).
- The assistant **misunderstood what the user wanted** and deleted the thing it aimed at. For example, the user said "free disk space" meaning old recordings, and the assistant deleted the whole project. It still chose that target on purpose, so this is **I**, not M.

Examples (not in your sheet):
- The assistant ran `git clean -fd` to "clean up" and deleted all untracked files. **I** (claude-code #45974)
- The assistant treated unpushed commits as "a problem to fix" and ran `git reset --hard origin`. **I** (claude-code #34327)
- Asked to free disk space, the assistant deleted the whole game project. **I** (claude-code #104848)

### W: Wrong target

The command was a **sensible** command for the job, but it ran against the **wrong place** because of a setting or environment: production instead of test, the wrong database or the wrong folder.

**Rule (added after round 1):** use W only when **a setting outside the command** picked the wrong place:
an env file, a config value, a working folder that changed by itself. If **the assistant itself** built the wrong path,
picked the wrong window or attached to the wrong program, that is **M**, not W.

Typical clues: "production", "it used the `.env` file instead of `.env.testing`", "pointed at the live database", "the working folder had silently changed".

Examples (not in your sheet):
- A test-database command fell back to the main database because a test settings file was missing. **W** (claude-code #37439)
- The assistant's working folder silently switched to another repository, so `git reset --hard` hit the wrong project. **W** (claude-code #53196)

### U: Unclear

The report says data was lost, but it does **not** say what the assistant ran or why.

Typical clues: "it deleted my files" with no command, no transcript and no explanation. "Wiped my database" and nothing more.

Example (not in your sheet): "Agent executed destructive command that wiped production database", with no details. **U** (claude-code #100449)

---

## Tricky cases

| Situation | Label |
|---|---|
| `git reset --hard` used **to fix a problem** or **to start over** | I |
| `git reset --hard` or `git checkout` used **to undo only the assistant's own edit or to switch branch**, and it also wiped the **user's** unsaved work | M |
| The assistant deleted the right folder, but the folder was synced (OneDrive, Dropbox) and the deletion spread | M |
| The assistant overwrote a whole file when it meant to add a few lines | M |
| The assistant wrote buggy program code that later deleted data when the program ran | M if a test or script it ran caused the loss right away. U if the loss happened later and the report is vague |
| Several things went wrong | Label the cause of the **main** loss |
| You hesitate between two letters | Pick the better one and write both in `notes` |

## Lessons from batch 1 (added after the batch 1 recheck)

**Lesson 1: A planned rewrite or deletion is I, even when it ignores an instruction.**
If the report shows that the assistant **decided** to replace, rewrite or delete the content, the answer to the test question is "yes, it would still have run it". That is **I**. Mechanism **O** is only for an edit that wiped **more than the assistant meant**, for example "add one function" that dropped 300 lines.

| Report says | Label |
|---|---|
| "WITHOUT being asked, I decided the report generation was 'too long' and replaced" it (claude-code #25374) | **I** |
| The rule was "Do NOT touch illustrations", and it replaced them with plain mocks (claude-code #61469) | **I** |
| Told "remove if empty", it decided the files were duplicates and ran `rm -rf` (claude-code #35093) | **I** |
| Asked to add to CLAUDE.md, it wrote "[Remaining content from the original file remains unchanged]" and the old content was gone (claude-code #2655) | **M**, mechanism **O** |

**Lesson 2: "It deleted X without asking" with no other detail is U, not I.**
"Without asking" tells you the assistant had no permission. It does not tell you that it **meant** to destroy the data. A wrong pattern or a bad path could cause the same report. If the report has no command, no transcript and no reason, use **U**.

| Report says | Label |
|---|---|
| "it deleted my solana private key without asking me", and nothing more (vscode #292170) | **U** |
| "deleted all my java files! no backup" (vscode #258188) | **U** |
| "half my code was deleted by GitHub Copilot" (vscode-copilot-release #9652) | **U** |
| "while trying to rectify a failed migration, copilot suggested a reset of the database ... it wiped my production database" (vscode #292110) | **I**, because the reason ("to fix the error") is given |

## Practical tips

- Decide from what the report says. Do not guess beyond it.
- Long reports: read the title, the first paragraph, and any grey code boxes. That is usually enough.
- Reports in other languages: a browser translation is fine.
- Use `notes` freely. Disagreements are expected, and we discuss them afterwards.
- Do not open other files in this folder until you finish.

---

# Part 2: the second workbook (`sheet2.xlsx`)

The workbook has two tabs. Each answer column has a dropdown.

- **Part A - new incidents (121 rows).** The AI flagged these as incidents. They were not in your first 100.
  Fill in `incident` and `cause` exactly as before. If the cause is **M**, also pick a `mechanism`.
- **Part B - mechanism only (39 rows).** These are the reports from your first sheet whose final label is **M**.
  Only pick the `mechanism`.

Some Part A reports may not be real incidents. Answer N when that is the case. That is useful too.

## Mechanism: HOW did the command do more than the assistant expected? (only for M)

Pick the **one** letter that best explains the surprise.

| Code | Name | The surprise came from | Clue words |
|---|---|---|---|
| **E** | Expansion or quoting | A blank or pattern in the command filled in differently than intended: an empty variable, `~`, `*` matching too much, a path with spaces, wrong quotes | "variable was empty", "expanded to", "`$HOME`", "glob", "wildcard", "unquoted", "matched more" |
| **P** | Platform difference | Windows and Linux, or PowerShell and bash, read the same text differently | "PowerShell", "cmd.exe", "MSYS", "Git Bash", "backslash", `C:\`, "on Windows" |
| **G** | Git also discarded the user's work | A git command meant to undo or switch also threw away the user's unsaved or untracked work | `git checkout`, `git reset --hard`, `git clean`, `git stash`, "my uncommitted changes" |
| **T** | Hidden tool behaviour | A tool, option or API does more than its name suggests | "replaces the whole list", "resets the shadow database", "overwrote the existing folder", "`--clear`", "attached to my open app" |
| **F** | File-system side effect | A symlink, shortcut, junction, synced folder or mount carried the effect somewhere else | "symlink", "junction", "followed the link", "OneDrive", "Dropbox", "mounted volume" |
| **S** | Script or test the assistant wrote | Code that the assistant wrote and ran (a test, cleanup script, trap) deleted real data | "the test deleted", "cleanup script", "teardown", "trap", "the helper it wrote" |
| **O** | Overwrite by an edit | The assistant meant a small edit but replaced or emptied a whole file | "overwrote the whole file", "removed all unchanged code", "rest of code unchanged", "write_file replaced" |
| **X** | Other or unknown | The report shows it was M, but the mechanism fits none of the above or is not stated | — |

Examples (made-up, not from your sheets):
- `rm -rf "$DIR"/*` with `DIR` empty deletes from the top of the disk. **E**
- A command written for bash runs in PowerShell and `\$VAR` becomes empty. **P**
- `git checkout -- .` to undo one file also erases the user's edits in other files. **G**
- `npm create vite my-app` in a folder that already has a project replaces it. **T**
- Deleting `sandbox/link/.git`, where `link` points into the real project. **F**
- A test the assistant wrote passes `"; rm -rf ~"` as input and deletes the home folder. **S**
- Asked to add one function, the assistant rewrites the file and drops 300 lines. **O**

## When two mechanisms fit

- **E vs P:** choose **P** if the same command would have been safe on the other platform.
- **S vs E:** choose **S** if the destructive step lived inside a script or test the assistant wrote. The expansion inside it is the detail, not the cause.
- **G vs T:** choose **G** for any git command that lost the user's own work.
- Write the second choice in `notes`.


---

# Part 3: the round-3 workbooks (`sheet3_batch1.xlsx` to `sheet3_batch4.xlsx`)

These come from the broad search of 21 agent trackers. Each workbook has about 320 rows. Do them in any order.

Columns to fill in:
- `incident`, `cause`, `mechanism`: exactly as in Parts 1 and 2. Mechanism only when cause is M.
- `duplicate of (link)`: if this report describes **the same incident** as another report you have seen
  (same user, same event, often cross-posted or re-filed), paste the link of the other report. Leave it empty otherwise.
  Do not search for duplicates. Only note the ones you happen to recognise.
- `notes`: optional.

New column `agent` shows which tracker the report comes from (for example `vscode` for GitHub Copilot in VS Code).

Some rows are expected to be N. That is normal. Answer them as honestly as the others.
During labelling, the AI labels were kept in a hidden file. They are now released as `ai_labels_sheet3.json`.
