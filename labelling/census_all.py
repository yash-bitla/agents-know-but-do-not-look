"""Final census over every human-labelled report: round 1 (sheet 1 + sheet 2 Part A) and round 3 (sheet3 batches 1-4).

Output: census_all.json and a printed summary. Duplicates marked by the reviewer are dropped when the
report they point to is also a counted incident. Reports in corrections.json marked N are dropped. Incidents that the final pipeline
does not flag are out of scope: 4 pilot (round 1) incidents and 1 found among the hidden recall checks.
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")


def load_dates():
    """Creation date of every issue, from the released search results (no issue bodies needed)."""
    dates = {}
    for x in json.load(open(os.path.join(ROOT, "candidates.json"))):
        dates[x["url"]] = x["createdAt"][:10]
    for line in open(os.path.join(ROOT, "round2", "hits.jsonl")):
        x = json.loads(line)
        dates[x["url"]] = x["created"]
    return dates


DATES = load_dates()
def final_pipeline_flags():
    """Reports the final pipeline flags: found by the 21-tracker search, kept by stage 1, flagged by stage 2."""
    flagged = set()
    for line in open(os.path.join(ROOT, "round2", "labels2.jsonl")):
        x = json.loads(line)
        if x["incident"]:
            flagged.add(x["url"])
    return flagged


# Scope: the census counts only incidents that the final pipeline reaches. Pilot (round 1) incidents that it does not
# flag are left out; their labels stay in the round 1 files.
FLAGGED = final_pipeline_flags()

# Label corrections found after the census was final (for example, by the replay fidelity audit).
CORRECTIONS = json.load(open(os.path.join(HERE, "corrections.json")))


def created(url):
    return DATES.get(url, "")


def main():
    recs = {}
    s1 = json.load(open(os.path.join(HERE, "final_labels.json")))
    s2 = json.load(open(os.path.join(HERE, "final_labels_sheet2.json")))
    mb = json.load(open(os.path.join(HERE, "mechanisms_partB.json")))
    for url, d in list(s1.items()) + list(s2.items()):
        if d["final"] in "MIWU" and d["final"]:
            recs[url] = dict(url=url, round=1, cause=d["final"], mechanism=(d.get("mech") or mb.get(url, {}).get("mech") or ""))
    overlap = 0
    dups = []
    for b in range(1, 5):
        for d in json.load(open(os.path.join(HERE, "final_labels_sheet3_batch%d.json" % b))):
            if d["incident"] != "Y":
                continue
            if d["url"] in recs:
                overlap += 1
                continue
            recs[d["url"]] = dict(url=d["url"], round=3, cause=d["cause"], mechanism=d["mechanism"] if d["cause"] == "M" else "")
            if d["duplicate_of"]:
                dups.append((d["url"], d["duplicate_of"].strip()))
    dropped = [u for u, t in dups if t in recs and t != u]
    for u in dropped:
        del recs[u]
    corrected = [c["url"] for c in CORRECTIONS if c["to"]["incident"] == "N" and c["url"] in recs]
    for u in corrected:
        del recs[u]
    for c in CORRECTIONS:  # cause corrections keep the incident and change its cause
        if c["to"]["incident"] == "Y" and c["url"] in recs:
            assert recs[c["url"]]["cause"] == c["from"]["cause"], c["url"]
            recs[c["url"]]["cause"] = c["to"]["cause"]
            recs[c["url"]]["mechanism"] = c["to"]["mechanism"]
    pilot_only = sorted(u for u, r in recs.items() if r["round"] == 1 and u not in FLAGGED)
    # Incidents found among the hidden recall checks (reports the screen rejected) measure recall only.
    recall_checks = sorted(u for u, r in recs.items() if r["round"] == 3 and u not in FLAGGED)
    for u in pilot_only + recall_checks:
        del recs[u]
    for r in recs.values():
        r["repo"] = "/".join(r["url"].split("/")[3:5])
        r["created"] = created(r["url"])
    out = sorted(recs.values(), key=lambda r: r["url"])
    json.dump(out, open(os.path.join(HERE, "census_all.json"), "w"), indent=1)

    C = collections.Counter
    print("round-1 incidents", sum(r["round"] == 1 for r in out), "| round-3 new", sum(r["round"] == 3 for r in out),
          "| round-3 already in round 1", overlap, "| duplicates dropped", len(dropped), "of", len(dups), "| corrected to N", len(corrected), "| pilot-only, out of scope", len(pilot_only), "| from recall checks, out of scope", len(recall_checks))
    c = C(r["cause"] for r in out)
    t = len(out)
    print("TOTAL", t, dict(c), "M %.1f%% of all, %.1f%% of clear (%d)" % (100 * c["M"] / t, 100 * c["M"] / (t - c["U"]), t - c["U"]))
    m = C(r["mechanism"] for r in out if r["cause"] == "M")
    print("mechanisms", m.most_common(), "| missing", m.get("", 0))
    print("command-level (not O) %d of %d" % (sum(v for k, v in m.items() if k not in ("O", "")), c["M"]))
    half = lambda d: d[:4] + ("-H1" if d[5:7] <= "06" else "-H2") if d else "?"
    for h, n in sorted(C(half(r["created"]) for r in out).items()):
        sub = [r for r in out if half(r["created"]) == h]
        cc = C(r["cause"] for r in sub)
        clear = len(sub) - cc["U"]
        print("  %s %4d incidents, M %3d (%.0f%% of clear)" % (h, n, cc["M"], 100 * cc["M"] / clear if clear else 0))
    for repo, n in C(r["repo"] for r in out).most_common():
        sub = [r for r in out if r["repo"] == repo]
        cc = C(r["cause"] for r in sub)
        clear = len(sub) - cc["U"]
        print("  %-38s %4d  M %3d (%.0f%% of clear)" % (repo, n, cc["M"], 100 * cc["M"] / clear if clear else 0))


if __name__ == "__main__":
    main()
