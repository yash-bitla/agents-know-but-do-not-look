"""Denominator for the time trend: how many issues each tracker got per half-year.

Uses the same repos and the same extra word for mixed repos as collect2.py. Count-only queries.
Output: volume.json {repo: {half: count}}. Reruns skip counts already fetched.
"""
import json
import os

from collect2 import AGENT_REPOS, HERE, MIXED_REPOS, search

OUT = os.path.join(HERE, "volume.json")
HALVES = [("2023-H2", "2023-07-01", "2023-12-31"), ("2024-H1", "2024-01-01", "2024-06-30"),
          ("2024-H2", "2024-07-01", "2024-12-31"), ("2025-H1", "2025-01-01", "2025-06-30"),
          ("2025-H2", "2025-07-01", "2025-12-31"), ("2026-H1", "2026-01-01", "2026-06-30"),
          ("2026-H2", "2026-07-01", "2026-12-31")]


def main():
    vol = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for repo in AGENT_REPOS + list(MIXED_REPOS):
        extra = MIXED_REPOS.get(repo)
        for h, a, b in HALVES:
            if str(vol.get(repo, {}).get(h, "")) != "":
                continue
            q = "repo:%s is:issue created:%s..%s" % (repo, a, b) + (" " + extra if extra else "")
            n = search(q, 1)["total_count"]
            vol.setdefault(repo, {})[h] = n
            json.dump(vol, open(OUT, "w"), indent=1)
        print(repo, vol[repo], flush=True)


if __name__ == "__main__":
    main()
