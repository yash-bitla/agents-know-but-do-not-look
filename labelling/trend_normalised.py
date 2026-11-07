"""Time trend divided by tracker volume: human-verified incidents per 10,000 issues, per half-year.

Inputs: labelling/census_all.json (incidents), round2/volume.json (all issues per repo and half-year).
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
census = json.load(open(os.path.join(HERE, "census_all.json")))
vol = json.load(open(os.path.join(HERE, "..", "round2", "volume.json")))
half = lambda d: d[:4] + ("-H1" if d[5:7] <= "06" else "-H2")
HALVES = ["2024-H2", "2025-H1", "2025-H2", "2026-H1", "2026-H2"]


def table(repos, label):
    print(label)
    print("  half      issues  incidents  per10k   M  M-per10k  M-of-clear")
    for h in HALVES:
        sub = [r for r in census if r["repo"] in repos and half(r["created"]) == h]
        n = sum(vol[r].get(h, 0) for r in repos)
        c = collections.Counter(r["cause"] for r in sub)
        clear = len(sub) - c["U"]
        if n:
            print("  %s %8d %9d %8.1f %4d %8.1f %9s" % (h, n, len(sub), 1e4 * len(sub) / n, c["M"], 1e4 * c["M"] / n,
                                                     "%.0f%%" % (100 * c["M"] / clear) if clear else "-"))


table(list(vol), "ALL 21 TRACKERS")
table(["anthropics/claude-code"], "CLAUDE CODE ONLY")
table([r for r in vol if r != "anthropics/claude-code"], "ALL EXCEPT CLAUDE CODE")
