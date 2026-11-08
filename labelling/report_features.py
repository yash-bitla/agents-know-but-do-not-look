"""What the incident reports contain, as aggregate shares (the issue bodies themselves are not released).

Reads the local issue bodies of every census incident. Output: report_features.json, used by paper/gen.py.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "replay"))
from common import load_issue  # noqa: E402


def main():
    census = json.load(open(os.path.join(HERE, "census_all.json")))
    issues = [load_issue(r["url"]) for r in census]
    assert all(issues), "every census incident needs a local body"
    bodies = [i.get("body") or "" for i in issues]
    n = len(bodies)
    out = dict(
        incidents=n,
        code_block=sum("```" in b for b in bodies),         # a pasted command, log, diff or transcript
        template=sum(bool(re.search(r"^#{2,3} ", b, re.M)) for b in bodies),  # headings from the tracker's form
        version=sum(bool(re.search(r"version", b, re.I)) for b in bodies),
        closed=sum(i.get("state") == "CLOSED" for i in issues),
        median_chars=sorted(len(b) for b in bodies)[n // 2],
    )
    json.dump(out, open(os.path.join(HERE, "report_features.json"), "w"), indent=1)
    print(out)


if __name__ == "__main__":
    main()
