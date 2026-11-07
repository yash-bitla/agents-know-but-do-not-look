"""Flat CSV files for the paper's data release.

data/human_reviewed.csv: every report a human read (1,498 rows), with the AI label and the human label.
data/incidents.csv:      the final census (one row per counted incident), copied from census_all.json.
Run census_all.py first.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DATA = os.path.join(ROOT, "data")
CODE = {"misjudged_effect": "M", "intended_destruction": "I", "wrong_target": "W", "unclear": "U", "": ""}


def load(name):
    return json.load(open(os.path.join(HERE, name)))


def main():
    os.makedirs(DATA, exist_ok=True)
    census = {r["url"]: r for r in load("census_all.json")}
    sys.path.insert(0, HERE)
    from census_all import created
    rows = []

    # Round 1, sheet 1: 100 reports. Human first pass, then adjudicated final label.
    human1 = load("human_labels.json")
    ai1 = {d["url"]: d for d in load("ai_labels_sheet1.json")}
    final1 = load("final_labels.json")
    mech = load("mechanisms_partB.json")
    for url, f in final1.items():
        h, a = human1[url], ai1[url]
        rows.append(dict(url=url, round=1, sheet="sheet1", row=f["n"], source="flagged_or_sample",
                         ai_incident="Y" if a["incident"] else "N", ai_cause=CODE[a.get("cause") or ""],
                         human_incident=h["inc"], human_cause=h.get("cause") or "",
                         final_incident="N" if f["final"] == "N" else "Y", final_cause="" if f["final"] == "N" else f["final"],
                         mechanism=mech.get(url, {}).get("mech") or "", duplicate_of="", notes=h.get("notes") or ""))

    # Round 1, sheet 2 Part A: 121 AI-flagged reports.
    ai2 = {d["url"]: d for d in load("ai_labels_sheet2.json")}
    for url, f in load("final_labels_sheet2.json").items():
        rows.append(dict(url=url, round=1, sheet="sheet2", row=f["n"], source="flagged",
                         ai_incident="Y", ai_cause=CODE[ai2[url].get("cause") or ""],
                         human_incident="N" if f["final"] == "N" else "Y", human_cause="" if f["final"] == "N" else f["final"],
                         final_incident="N" if f["final"] == "N" else "Y", final_cause="" if f["final"] == "N" else f["final"],
                         mechanism=f.get("mech") or "", duplicate_of="", notes=f.get("notes") or ""))

    # Round 3: four batches, 1,277 rows (1,197 flagged + 80 hidden checks).
    ai3 = {d["n"]: d for d in load("ai_labels_sheet3.json")}
    for b in range(1, 5):
        for d in load("final_labels_sheet3_batch%d.json" % b):
            a = ai3[d["n"]]
            rows.append(dict(url=d["url"], round=3, sheet="sheet3_batch%d" % b, row=d["n"], source=a["source"],
                             ai_incident="Y" if a.get("ai_incident") else "N", ai_cause=CODE[a.get("ai_cause") or ""] if a.get("ai_incident") else "",
                             human_incident=d["incident"], human_cause=d["cause"],
                             final_incident=d["incident"], final_cause=d["cause"],
                             mechanism=d["mechanism"], duplicate_of=d["duplicate_of"], notes=d["notes"]))

    for r in rows:
        r["repo"] = "/".join(r["url"].split("/")[3:5])
        r["created"] = created(r["url"])
        r["in_census"] = "Y" if r["url"] in census and census[r["url"]]["round"] == r["round"] else "N"
    cols = ["url", "repo", "created", "round", "sheet", "row", "source", "ai_incident", "ai_cause",
            "human_incident", "human_cause", "final_incident", "final_cause", "mechanism", "duplicate_of", "in_census", "notes"]
    with open(os.path.join(DATA, "human_reviewed.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(DATA, "incidents.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["url", "repo", "created", "round", "cause", "mechanism"])
        w.writeheader()
        for r in sorted(census.values(), key=lambda r: r["url"]):
            w.writerow({k: r[k] for k in w.fieldnames})
    print(len(rows), "reviewed rows,", len({r["url"] for r in rows}), "unique reports,", len(census), "incidents,",
          sum(r["in_census"] == "Y" for r in rows), "rows in census")


if __name__ == "__main__":
    main()
