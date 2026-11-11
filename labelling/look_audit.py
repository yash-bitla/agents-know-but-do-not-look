"""Did the agent look? A coded sample that tests the "do not look" claim directly.

Sample: 100 misjudged-effect (M) incidents, drawn with a fixed seed from those whose report pastes a command, log, diff
or transcript (a code block), because only those can show the agent's steps before the destructive action.
The author answers one question per report: before the destructive action, did the agent read the state that decided
its effect?

Usage:
  uv run -q --with openpyxl python labelling/look_audit.py            writes labelling/workbooks/look_audit.xlsx
  uv run -q --with openpyxl python labelling/look_audit.py --score F  reads the filled workbook, writes look_audit_scores.json
"""
import collections
import json
import os
import random
import sys

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "replay"))
from common import load_issue  # noqa: E402

SEED = 2027
N = 100
ANSWERS = "no_look,looked_missed,unknown"
GUIDE = [
    "Did the agent look? One question per report.",
    "",
    "Open the link and read the report, including any pasted transcript, log or command.",
    "Question: before the destructive action, did the agent read the state that decided its effect?",
    "",
    "no_look: the report shows the agent's steps before the action, and none of them read the deciding state.",
    "   Examples: no `git status` before `git checkout -- .`; no `ls` of the folder before `rm -rf`; no check of a",
    "   variable before a command expands it; no read of the file before an edit that replaced it.",
    "looked_missed: the report shows that the agent read the deciding state, or saw output that showed it, and still",
    "   ran the action. (This would count against the claim that agents fail because they do not look.)",
    "unknown: the report does not show the agent's steps before the action, or it is not clear which state decided",
    "   the effect.",
    "",
    "deciding_state: a few words on the state that decided the effect, e.g. 'uncommitted changes in src/',",
    "   'VAR was empty', 'path was a symlink', 'file had 300 lines'. Fill it in when you can tell.",
    "notes: anything that explains the answer.",
    "",
    "Code from the report only. Do not count the agent's apology after the loss as evidence of what it read before.",
]
COLS = ["n", "id", "link", "agent", "mechanism", "title", "looked", "deciding_state", "notes"]
WIDTH = dict(n=5, id=22, link=18, agent=18, mechanism=10, title=50, looked=16, deciding_state=35, notes=50)


def sample():
    census = json.load(open(os.path.join(HERE, "census_all.json")))
    pool = []
    for r in sorted(census, key=lambda r: r["url"]):
        if r["cause"] != "M":
            continue
        body = (load_issue(r["url"]) or {}).get("body") or ""
        if "```" in body:
            pool.append(r)
    return random.Random(SEED).sample(pool, N), len(pool)


def write():
    rows, pool = sample()
    wb = openpyxl.Workbook()
    g = wb.active
    g.title = "Guide"
    for line in GUIDE:
        g.append([line])
    g["A1"].font = Font(bold=True, size=13)
    g.column_dimensions["A"].width = 120
    ws = wb.create_sheet("Look")
    ws.append(COLS)
    for n, r in enumerate(rows, 1):
        issue = load_issue(r["url"]) or {}
        p = r["url"].split("/")
        ws.append([n, "%s_%s" % (p[4].lower().replace("-", "_"), p[6]), r["url"], r["repo"], r["mechanism"],
                   issue.get("title", ""), None, None, None])
        ws.cell(n + 1, 3).hyperlink = r["url"]
        ws.cell(n + 1, 3).font = Font(color="0563C1", underline="single")
    head, answer = PatternFill("solid", fgColor="DDEBF7"), PatternFill("solid", fgColor="FFF2CC")
    for j, name in enumerate(COLS, 1):
        letter = openpyxl.utils.get_column_letter(j)
        ws.column_dimensions[letter].width = WIDTH[name]
        ws.cell(1, j).font = Font(bold=True)
        ws.cell(1, j).fill = answer if name in ("looked", "deciding_state", "notes") else head
        for i in range(2, ws.max_row + 1):
            ws.cell(i, j).alignment = Alignment(wrap_text=True, vertical="top")
            if name in ("looked", "deciding_state", "notes"):
                ws.cell(i, j).fill = answer
    dv = DataValidation(type="list", formula1='"%s"' % ANSWERS, allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("G2:G%d" % ws.max_row)
    ws.freeze_panes = "D2"
    path = os.path.join(HERE, "workbooks", "look_audit.xlsx")
    wb.save(path)
    print("wrote", path, "with", len(rows), "of", pool, "M incidents that paste a code block")


def score(path):
    ws = openpyxl.load_workbook(path)["Look"]
    head = [c.value for c in ws[1]]
    rows = [dict(zip(head, [c.value for c in r])) for r in ws.iter_rows(min_row=2)]
    c = collections.Counter(r["looked"] or "blank" for r in rows)
    known = c["no_look"] + c["looked_missed"]
    out = dict(n=len(rows), answers=dict(c), known=known,
               no_look_share_of_known=round(100.0 * c["no_look"] / known, 1) if known else None,
               by_mechanism={m: dict(collections.Counter(r["looked"] or "blank" for r in rows if r["mechanism"] == m))
                             for m in sorted({r["mechanism"] for r in rows})})
    json.dump(out, open(os.path.join(HERE, "look_audit_scores.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    if "--score" in sys.argv:
        score(sys.argv[sys.argv.index("--score") + 1])
    else:
        write()
