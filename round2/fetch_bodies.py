"""Download issue title + body for every unique hit, 50 issues per GraphQL request.

Output: issues/<owner>__<repo>_<number>.json, same shape as round 1 (gh issue view JSON).
Skips issues already downloaded, so a rerun resumes.
"""
import json
import os
import subprocess
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "issues")
BATCH = 50


def gql(query):
    for attempt in range(6):
        r = subprocess.run(["gh", "api", "graphql", "-f", "query=" + query], capture_output=True, text=True)
        if r.returncode == 0 or '"data"' in r.stdout:
            return json.loads(r.stdout).get("data") or {}
        time.sleep(15 * (attempt + 1))
    raise RuntimeError(r.stderr[-300:])


def main():
    os.makedirs(OUT, exist_ok=True)
    urls = {json.loads(l)["url"] for l in open(os.path.join(HERE, "hits.jsonl"))}
    todo = defaultdict(list)
    for u in urls:
        parts = u.split("/")
        owner, repo, num = parts[3], parts[4], int(parts[6])
        if not os.path.exists(os.path.join(OUT, "%s__%s_%d.json" % (owner, repo, num))):
            todo[(owner, repo)].append(num)
    total = sum(len(v) for v in todo.values())
    done = 0
    for (owner, repo), nums in todo.items():
        for i in range(0, len(nums), BATCH):
            chunk = nums[i:i + BATCH]
            fields = " ".join('i%d: issue(number: %d) { number title body createdAt url state }' % (n, n) for n in chunk)
            data = gql('query { r: repository(owner: "%s", name: "%s") { %s } }' % (owner, repo, fields))
            for n in chunk:
                it = (data.get("r") or {}).get("i%d" % n)
                if it:
                    with open(os.path.join(OUT, "%s__%s_%d.json" % (owner, repo, n)), "w") as f:
                        json.dump(it, f)
            done += len(chunk)
            if done % 1000 < BATCH:
                print("fetched %d of %d" % (done, total), flush=True)
    print("done", len(os.listdir(OUT)), "files", flush=True)


if __name__ == "__main__":
    main()
