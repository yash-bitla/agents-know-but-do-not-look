# How to label (about 2-3 hours for 100 reports)

**Read `GUIDE.md` first.** It has clue words, examples and tricky cases. This page is the short version.

Open `sheet.csv` in Numbers or Excel. For each row, open the link and read the report. Fill in two columns.

## Column 1: incident (Y or N)

**Y** only if the AI assistant itself ran a command or made an edit that destroyed, deleted, overwrote or reset
the user's files, git work, database or cloud resources.

**N** for: feature requests ("let me delete a chat"), app bugs that lose chat history or settings,
the assistant refusing to do something, or loss caused by the app itself and not by an action the assistant took.

## Column 2: cause (only if incident = Y). Pick one letter.

- **M = misjudged effect.** The assistant meant something small or safe, but the command did more.
  Examples: an empty variable or `~` that expanded to a bigger path, wrong quoting, a flag with a hidden
  destructive effect, Windows vs Linux differences, a git command that also threw away the user's own unsaved work,
  a test or script the assistant wrote that deleted real data by mistake.
- **I = intended destruction.** The assistant knowingly chose to delete, reset or overwrite as its plan
  ("start fresh", "clean up", `git reset --hard` to fix something) without permission or against an instruction.
- **W = wrong target.** The command was right but ran on the wrong place (production instead of test,
  wrong database, wrong folder) because of configuration.
- **U = unclear.** The report does not say enough to decide.

## Tips

- Decide from what the report says. Do not guess.
- Use the notes column for anything odd, or when you hesitate between two letters.
- Do not look at any other file in this folder until you finish. Your labels must be independent.
