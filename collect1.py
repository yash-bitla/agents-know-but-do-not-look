"""Round 1 collection: 10 data-loss phrases on 4 agent trackers, then a title filter.

Output: candidates.json (every hit), filtered.json (titles that describe loss), issues/ (bodies, gh issue view JSON).
This is the script form of the shell commands run on 2026-11-04. GitHub search results change over time,
so a rerun returns a different set. The released candidates.json and filtered.json are the sets used in the paper.
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPOS = ["anthropics/claude-code", "google-gemini/gemini-cli", "openai/codex", "cline/cline"]
PHRASES = ["deleted my", "rm -rf", "data loss", "wiped", "lost all", "git reset --hard", "git checkout",
           "deleted all", "dropped database", "lost uncommitted"]
TITLE = re.compile(r"delet|wipe|wiping|rm -rf|\brm\b|lost|data loss|reset --hard|destroy|erase|overwr|removed (my|all|the)"
                   r"|drop(ped)? (table|database|db)|git clean|git checkout|discard|nuked|catastroph", re.I)


def main():
    seen = {}
    for repo in REPOS:
        for q in PHRASES:
            r = subprocess.run(["gh", "search", "issues", q, "--repo", repo, "--limit", "100",
                                "--json", "number,title,url,createdAt,repository"], capture_output=True, text=True)
            for x in json.loads(r.stdout or "[]"):
                seen[x["url"]] = x
    json.dump(list(seen.values()), open(os.path.join(HERE, "candidates.json"), "w"), indent=0)
    kept = [x for x in seen.values() if TITLE.search(x["title"])]
    json.dump(kept, open(os.path.join(HERE, "filtered.json"), "w"), indent=0)
    print(len(seen), "candidates,", len(kept), "kept by the title filter")

    os.makedirs(os.path.join(HERE, "issues"), exist_ok=True)
    for x in kept:
        repo = x["repository"]["nameWithOwner"]
        path = os.path.join(HERE, "issues", "%s_%d.json" % (repo.replace("/", "__"), x["number"]))
        if not os.path.exists(path):
            r = subprocess.run(["gh", "issue", "view", str(x["number"]), "--repo", repo,
                                "--json", "body,createdAt,labels,number,state,title,url"], capture_output=True, text=True)
            if r.returncode == 0:
                open(path, "w").write(r.stdout)


if __name__ == "__main__":
    main()
