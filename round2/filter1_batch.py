"""Stage 1 filter, batched: 10 issues per Haiku call, high-recall yes/no screen.

Usage: python3 filter1_batch.py <issues_dir> <out.jsonl>
Each issue gets keep=true/false. Unsure or unparsed answers count as keep.
"""
import glob
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from filter1 import HERE

PER_CALL = 10
PROMPT = """You screen bug reports about AI coding assistants. For EACH numbered report, answer YES if it might describe
the AI assistant itself deleting, overwriting, wiping, resetting or otherwise destroying the user's files, code, git work,
database, or cloud resources. Answer YES when unsure. Answer NO only if it is clearly about something else: a feature request,
a UI bug, lost chat history or settings, billing, login, or loss caused by the app and not by an action of the assistant.

Reply with one line per report, in order, exactly like:
1: YES
2: NO

Reports:
"""


def screen(batch):
    parts = []
    for k, (path, issue) in enumerate(batch, 1):
        parts.append("=== Report %d ===\nTITLE: %s\n%s\n" % (k, issue["title"], (issue.get("body") or "")[:1500]))
    cmd = ["claude", "-p", "--safe-mode", "--tools", "", "--no-session-persistence", "--model", "haiku",
           "--system-prompt", "You screen bug reports. Reply with one 'N: YES' or 'N: NO' line per report."]
    answers = {}
    for _ in range(3):
        r = subprocess.run(cmd, input=PROMPT + "\n".join(parts), capture_output=True, text=True,
                           cwd=os.path.join(HERE, "..", "empty"), timeout=300)
        answers = {int(n): v == "YES" for n, v in re.findall(r"^\s*(\d+)\s*[:.)-]\s*(YES|NO)\b", r.stdout.upper(), re.M)}
        if len(answers) == len(batch):
            break
    return [dict(url=issue["url"], keep=answers.get(k, True), parsed=k in answers)
            for k, (path, issue) in enumerate(batch, 1)]


def main():
    src, out_path = sys.argv[1], sys.argv[2]
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)["url"] for l in open(out_path)}
    items = []
    for p in sorted(glob.glob(os.path.join(src, "*.json"))):
        issue = json.load(open(p))
        if issue["url"] not in done:
            items.append((p, issue))
    batches = [items[i:i + PER_CALL] for i in range(0, len(items), PER_CALL)]
    n = 0
    with ThreadPoolExecutor(8) as pool, open(out_path, "a") as out:
        for res in pool.map(screen, batches):
            for d in res:
                out.write(json.dumps(d) + "\n")
            out.flush()
            n += len(res)
            if n % 2000 < PER_CALL:
                print("screened %d of %d" % (n, len(items)), flush=True)
    print("screened", len(items), flush=True)


if __name__ == "__main__":
    main()
