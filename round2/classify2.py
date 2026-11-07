"""Stage 2: full rubric on issues kept by stage 1. Same rubric as round 1 (classify.py), plus:
- the W rule settled in adjudication (agent-built wrong target is M, not W)
- the AI model the report names, if any (for the "still happening with new models?" question)

Output: labels2.jsonl. Reruns skip issues already labelled.
"""
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
import sys
sys.path.insert(0, ROOT)
from classify import RUBRIC as BASE  # noqa: E402

RUBRIC = BASE.replace(
    '- "wrong_target": the command was right, but it ran against the wrong environment, database,\n'
    '  credentials or directory because of configuration (for example production instead of dev).',
    '- "wrong_target": the command was right, but it ran against the wrong environment, database,\n'
    '  credentials or directory because a setting outside the command chose it (an env file, a changed\n'
    '  working directory, a config value). If the agent itself built the wrong path or picked the wrong\n'
    '  object, use "misjudged_effect" instead.').replace(
    'And "evidence": one short quote from the report that supports your label.',
    'And "evidence": one short quote from the report that supports your label.\n'
    'And "model": the AI model the report names (for example "Claude Opus 5", "gpt-6.1"), else "".').replace(
    '{"incident": true|false, "cause": "...", "command": "...", "evidence": "..."}',
    '{"incident": true|false, "cause": "...", "command": "...", "evidence": "...", "model": "..."}')
assert "a setting outside the command" in RUBRIC and '"model"' in RUBRIC

OUT = os.path.join(HERE, "labels2.jsonl")


def label(path):
    issue = json.load(open(path))
    text = "TITLE: %s\n\n%s" % (issue["title"], (issue.get("body") or "")[:7000])
    cmd = ["claude", "-p", "--safe-mode", "--tools", "", "--no-session-persistence", "--model", "sonnet",
           "--system-prompt", "You label bug reports. Reply with one JSON object only."]
    for _ in range(3):
        r = subprocess.run(cmd, input=RUBRIC + text, capture_output=True, text=True,
                           cwd=os.path.join(ROOT, "empty"), timeout=300)
        m = re.search(r"\{.*\}", r.stdout, re.S)
        if m:
            try:
                d = json.loads(m.group(0))
                d.update(url=issue["url"], title=issue["title"], created=issue["createdAt"][:10],
                         repo="/".join(issue["url"].split("/")[3:5]))
                return d
            except ValueError:
                pass
    return {"url": issue["url"], "title": issue["title"], "error": r.stdout[-200:]}


def main():
    keep = {json.loads(l)["url"] for l in open(os.path.join(HERE, "screen1.jsonl")) if json.loads(l)["keep"]}
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["url"] for l in open(OUT)}
    paths = []
    for f in sorted(os.listdir(os.path.join(HERE, "issues"))):
        p = os.path.join(HERE, "issues", f)
        u = json.load(open(p))["url"]
        if u in keep and u not in done:
            paths.append(p)
    n = 0
    with ThreadPoolExecutor(8) as pool, open(OUT, "a") as out:
        for d in pool.map(label, paths):
            out.write(json.dumps(d) + "\n")
            out.flush()
            n += 1
            if n % 250 == 0:
                print("labelled %d of %d" % (n, len(paths)), flush=True)
    print("labelled", len(paths), flush=True)


if __name__ == "__main__":
    main()
