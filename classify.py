"""Classify each downloaded issue with a fixed rubric, using the claude CLI in safe mode.

Output: labels.jsonl, one JSON object per issue. Reruns skip issues already labelled.
"""
import glob
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "labels.jsonl")

RUBRIC = """You label bug reports about AI coding agents. Read the report and answer with one JSON object only.

Step 1. "incident": true only if the report says the AI agent itself ran a command or made an edit
that destroyed, deleted, overwrote or reset the user's data, files, git work, database, or cloud resources.
false for feature requests, UI or app bugs that lose chat history or settings, refusals, and loss
caused by the harness software rather than an action the agent took.

Step 2 (only if incident is true). "cause", exactly one of:
- "misjudged_effect": the agent meant a narrow or safe action, but the command's real effect was wider or
  destructive. Examples: shell expansion (~, *, $VAR empty), path quoting, a flag or subcommand with a hidden
  destructive side effect, platform differences (PowerShell vs bash), a git command that also discarded
  the user's own uncommitted work while the agent meant to discard only its own changes, a test or script
  the agent wrote that deleted real data by mistake.
- "intended_destruction": the agent knowingly chose to delete, reset, overwrite or drop as its plan
  (for example "start fresh", "clean up", git reset --hard to fix a problem) without permission,
  or against an explicit instruction.
- "wrong_target": the command was right, but it ran against the wrong environment, database,
  credentials or directory because of configuration (for example production instead of dev).
- "unclear": the report does not say enough to decide.

Also give "command": the destructive command or action if the report shows it (short), else "".
And "evidence": one short quote from the report that supports your label.

Reply format:
{"incident": true|false, "cause": "...", "command": "...", "evidence": "..."}

Report:
"""


def label(path):
    issue = json.load(open(path))
    text = "TITLE: %s\n\n%s" % (issue["title"], (issue.get("body") or "")[:7000])
    cmd = ["claude", "-p", "--safe-mode", "--tools", "", "--no-session-persistence", "--model", "sonnet",
           "--system-prompt", "You label bug reports. Reply with one JSON object only."]
    for _ in range(3):
        r = subprocess.run(cmd, input=RUBRIC + text, capture_output=True, text=True,
                           cwd=os.path.join(HERE, "empty"), timeout=300)
        m = re.search(r"\{.*\}", r.stdout, re.S)
        if m:
            try:
                d = json.loads(m.group(0))
                d.update(url=issue["url"], title=issue["title"], created=issue["createdAt"][:10])
                return d
            except ValueError:
                pass
    return {"url": issue["url"], "title": issue["title"], "error": r.stdout[-200:]}


def main():
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["url"] for l in open(OUT)}
    todo = [p for p in sorted(glob.glob(os.path.join(HERE, "issues", "*.json")))
            if json.load(open(p))["url"] not in done]
    os.makedirs(os.path.join(HERE, "empty"), exist_ok=True)
    with ThreadPoolExecutor(8) as pool, open(OUT, "a") as out:
        for d in pool.map(label, todo):
            out.write(json.dumps(d) + "\n")
            out.flush()
    print("labelled", len(todo))


if __name__ == "__main__":
    main()
