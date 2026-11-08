"""Tier A input: every human-verified misjudged-effect (M) incident.

Output: candidates.jsonl, one line per M incident, with its mechanism and whether its issue body is available.
Edit overwrites (mechanism O) are listed too. build.py handles shell cases first, and the edit harness handles O.
"""
import json
import os

from common import HERE, ROOT, case_id, issue_path


def main():
    census = json.load(open(os.path.join(ROOT, "labelling", "census_all.json")))
    rows = []
    for r in census:
        if r["cause"] != "M":
            continue
        rows.append(dict(id=case_id(r["url"]), url=r["url"], repo=r["repo"], created=r["created"],
                         mechanism=r["mechanism"], body=issue_path(r["url"]) is not None))
    assert len({r["id"] for r in rows}) == len(rows)
    with open(os.path.join(HERE, "candidates.jsonl"), "w") as f:
        for r in sorted(rows, key=lambda r: r["id"]):
            f.write(json.dumps(r) + "\n")
    print(len(rows), "M incidents,", sum(r["body"] for r in rows), "with a local issue body,",
          sum(r["mechanism"] == "O" for r in rows), "are edit overwrites (O)")


if __name__ == "__main__":
    main()
