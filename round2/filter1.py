"""Stage 1 filter: a cheap, high-recall yes/no screen before the full rubric.

Reads an issue file (gh issue view JSON) and asks Haiku whether the report MIGHT describe an
AI agent destroying user data. It should say "yes" whenever unsure.
Usage: python3 filter1.py <issues_dir> <out.jsonl>
"""
import glob
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT = """You screen bug reports about AI coding assistants. Answer YES if the report might describe the AI assistant
itself deleting, overwriting, wiping, resetting or otherwise destroying the user's files, code, git work, database,
or cloud resources. Answer YES when unsure. Answer NO only if it is clearly about something else: a feature request,
a UI bug, lost chat history or settings, billing, login, or loss caused by the app and not by an action of the assistant.
Reply with exactly one word: YES or NO.

Report:
"""


def screen(path):
    issue = json.load(open(path))
    text = "TITLE: %s\n\n%s" % (issue["title"], (issue.get("body") or "")[:2500])
    cmd = ["claude", "-p", "--safe-mode", "--tools", "", "--no-session-persistence", "--model", "haiku",
           "--system-prompt", "You screen bug reports. Reply YES or NO."]
    for _ in range(3):
        r = subprocess.run(cmd, input=PROMPT + text, capture_output=True, text=True,
                           cwd=os.path.join(HERE, "..", "empty"), timeout=180)
        m = re.search(r"\b(YES|NO)\b", r.stdout.upper())
        if m:
            return dict(url=issue["url"], keep=m.group(1) == "YES")
    return dict(url=issue["url"], keep=True, error=True)  # unsure: keep


def main():
    src, out_path = sys.argv[1], sys.argv[2]
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)["url"] for l in open(out_path)}
    files = [p for p in sorted(glob.glob(os.path.join(src, "*.json"))) if json.load(open(p))["url"] not in done]
    with ThreadPoolExecutor(8) as pool, open(out_path, "a") as out:
        for d in pool.map(screen, files):
            out.write(json.dumps(d) + "\n")
            out.flush()
    print("screened", len(files))


if __name__ == "__main__":
    main()
