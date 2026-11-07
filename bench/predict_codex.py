"""RQ2 with OpenAI models through the Codex CLI (ChatGPT login), run inside a throwaway container.

Safety: Codex runs in the cmdfx-codex container with no host folders mounted, in read-only
sandbox mode, and the prompt tells it not to run anything. Only ~/.codex/auth.json is copied in,
and the container is removed at the end.

Usage: python3 predict_codex.py [--blind] [--model NAME]   (no --model = Codex default)
Output: predictions_codex[_blind].jsonl, then the same summary table as predict.py.
"""
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import predict
from cases import ALL_CASES, COMMON, INTENT

HERE = os.path.dirname(os.path.abspath(__file__))
BLIND = "--blind" in sys.argv
MODEL = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else None
OUT = os.path.join(HERE, "predictions_codex%s.jsonl" % ("_blind" if BLIND else ""))
NAME = "cmdfx_codex_reviewer"
EXTRA = "\n\nDo not run any commands or tools. Answer only from reading the command."


def sh(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def start():
    sh(["docker", "rm", "-f", NAME])
    sh(["docker", "run", "-d", "--name", NAME, "cmdfx-codex", "sleep", "infinity"])
    sh(["docker", "cp", os.path.expanduser("~/.codex/auth.json"), NAME + ":/home/reviewer/.codex/auth.json"])
    sh(["docker", "exec", "-u", "root", NAME, "chown", "reviewer:reviewer", "/home/reviewer/.codex/auth.json"])


def ask(job):
    case, i = job
    setup = "" if BLIND else "The current files were created by this setup script:\n```bash\n%s\n```\n" % (
        COMMON + "\n" + case["setup"]).strip()
    prompt = predict.PROMPT.format(shell=case["shell"], cwd=case["cwd"], setup=setup,
                                   intent=INTENT[case["id"].replace("__safe", "")], command=case["command"]) + EXTRA
    cmd = ["docker", "exec", NAME, "codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only"]
    if MODEL:
        cmd += ["-m", MODEL]
    for _ in range(3):
        r = sh(cmd + [prompt], timeout=600)
        m = re.search(r"\{[^{}]*\"collateral\"[^{}]*\}", r.stdout, re.S)
        if m:
            try:
                d = json.loads(m.group(0))
                return dict(model="codex:" + (MODEL or "default"), id=case["id"], sample=i,
                            pred=bool(d.get("collateral")), affected=d.get("affected", []), reason=d.get("reason", ""))
            except ValueError:
                pass
    return dict(model="codex:" + (MODEL or "default"), id=case["id"], sample=i, pred=None,
                error=(r.stdout + r.stderr)[-300:])


def main():
    cases = [c for c in ALL_CASES if c["id"].replace("__safe", "") not in predict.ENV_DEPENDENT]
    label = "codex:" + (MODEL or "default")
    done = set()
    if os.path.exists(OUT):
        done = {(d["model"], d["id"], d["sample"]) for d in map(json.loads, open(OUT)) if d["pred"] is not None}
    jobs = [(c, i) for c in cases for i in range(predict.SAMPLES) if (label, c["id"], i) not in done]
    if "--test" in sys.argv:
        jobs = jobs[:1]
    start()
    try:
        with ThreadPoolExecutor(4) as pool, open(OUT, "a") as out:
            for d in pool.map(ask, jobs):
                out.write(json.dumps(d) + "\n")
                out.flush()
                if d["pred"] is None:
                    print("no answer:", d["id"], d["error"][-200:])
    finally:
        sh(["docker", "rm", "-f", NAME])
    print("asked", len(jobs))


if __name__ == "__main__":
    main()
