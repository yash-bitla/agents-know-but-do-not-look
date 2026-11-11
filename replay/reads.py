"""The "reads" condition for the prediction study: what one cheap look at the state shows.

For each item, the case setup runs in the sealed sandbox, and a fixed set of read-only commands runs in the working
directory. The model later sees only their output, never the setup script, so cue strings in the setup cannot help it.
Real cases and their twins share one setup, so they share one read. Each variant has its own setup and its own read.

Usage: python3 reads.py   Output: reads.jsonl, one line per setup: {"key": case id or variant id, "reads": text}
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import run
from common import HERE, IMAGE, read_jsonl

sys.path.insert(0, os.path.join(HERE, "..", "bench"))
from cases import COMMON  # noqa: E402

OUT = os.path.join(HERE, "reads.jsonl")
MARK = "__READS_START__"
LIMIT = 4000  # characters of read output given to the model

# A fixed, cheap look at the state: where am I, what is here, what does git hold, and where do links point.
READS = r"""
echo '$ pwd'; pwd
echo '$ ls -la'; ls -la
echo '$ git status --short --branch'; git status --short --branch 2>&1 | head -40
echo '$ git stash list'; git stash list 2>&1 | head -10
echo '$ find . -maxdepth 2 -type l'; find . -maxdepth 2 -type l -printf '%p -> %l\n' 2>/dev/null | head -20
echo '$ ls -la ~'; ls -la ~ 2>&1 | head -40
"""


def collect(job):
    key, case = job
    cwd = case.get("cwd") or "/home/dev"
    script = ("( set -e\n" + COMMON + "\ncd /home/dev\n" + (case.get("setup") or "") + "\n) >/dev/null 2>&1\n"
              + "echo " + MARK + "\ncd '" + cwd + "' 2>&1\n" + READS)
    r, _ = run.run_script(IMAGE, case, script)
    out = r.stdout.split(MARK, 1)[-1].strip() if MARK in r.stdout else "(the setup failed)"
    return dict(key=key, reads=out[:LIMIT], truncated=len(out) > LIMIT)


def jobs():
    excluded = set(json.load(open(os.path.join(HERE, "audit", "final_verdicts.json")))["summary"]["excluded"])
    builds = {b["id"]: b for b in read_jsonl(os.path.join(HERE, "builds.jsonl")) if b["case"] is not None}
    results = {r["id"]: r for r in read_jsonl(os.path.join(HERE, "results.jsonl"))}
    out = [(i, builds[i]["case"]) for i, r in sorted(results.items())
           if r["status"] == "reproduced" and r["mechanism"] != "O" and i not in excluded]
    variants = {m["id"]: m for m in read_jsonl(os.path.join(HERE, "variants", "builds.jsonl")) if m["variants"]}
    for v in read_jsonl(os.path.join(HERE, "variants", "results.jsonl")):
        if "executed" in v and v["source"] not in excluded:
            out.append((v["vid"], variants[v["source"]]["variants"][v["kind"]]))
    return out


def main():
    done = {d["key"] for d in read_jsonl(OUT)}
    todo = [j for j in jobs() if j[0] not in done]
    print("collecting reads for", len(todo), "setups", flush=True)
    with ThreadPoolExecutor(4) as pool, open(OUT, "a") as out:
        for n, d in enumerate(pool.map(collect, todo), 1):
            out.write(json.dumps(d) + "\n")
            out.flush()
            if n % 100 == 0:
                print("collected %d of %d" % (n, len(todo)), flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
