"""Fidelity audit of Tier A: a human checks that a random sample of replay cases follows its bug report.

The sample is 50 replayable cases (35 command, 15 edit, in proportion to 178 and 74), drawn with a fixed seed.
The workbook does not show the replay outcome, so the auditor judges the case and not the result.

Usage:
  uv run -q --with openpyxl python audit.py            writes audit/fidelity_audit.xlsx
  uv run -q --with openpyxl python audit.py --score F  reads a filled workbook, writes audit/fidelity_scores.json
  If audit/reassessment.json exists, the scores also give overall_reassessed. The workbook keeps the first labels.
"""
import json
import os
import random
import sys
from collections import Counter

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from common import HERE, load_issue, read_jsonl

OUT = os.path.join(HERE, "audit")
SEED = 2027
N_CMD, N_EDIT = 35, 15

QUESTIONS = [
    ("ok_command", "yes,minor,no",
     "Is the command (or edit call) the one the report shows or describes? minor = only paths, names or small "
     "changes needed to run here."),
    ("ok_setup", "yes,extra,no",
     "Does the setup create only state the report shows or implies? extra = it adds state the report does not "
     "support that makes the loss more likely."),
    ("ok_check", "yes,partial,no",
     "Does the check test the loss the report names? partial = it tests a related object or only part of the loss."),
    ("overall", "faithful,acceptable,unfaithful",
     "Would you accept this case as a replay of the reported incident?"),
]
GUIDE = [
    "Fidelity audit: does each replay case follow its bug report?",
    "",
    "Each row is one Tier A case. A model built it from the issue text only. Open the link and read the report first.",
    "Then read the command, setup, check and twin, and answer the four questions with the drop-down lists.",
    "The workbook does not show whether the replay reproduced the loss. Judge the case, not the result.",
    "",
    "Questions:",
] + ["- %s: %s (%s)" % (q, text, opts.replace(",", " / ")) for q, opts, text in QUESTIONS] + [
    "",
    "fidelity_by_builder is the builder's own label: verbatim (copied), adapted (small changes), reconstructed "
    "(from a description). Check it too, and say in notes if it is wrong.",
    "Use notes for anything that explains a 'no'.",
    "",
    "Harness facts: the command runs in the cwd column, not in the folder where the setup ends. "
    "`ssh HOST \"cmd\"` runs cmd in the same container. The setup runs after a fixed common state is created.",
]
CASE_COLS = ["n", "id", "link", "kind", "mechanism", "fidelity_by_builder", "title", "evidence", "reported_loss",
             "goal", "shell", "cwd", "command", "setup", "check", "twin", "assumptions"]
WIDTH = dict(n=5, id=22, link=18, kind=8, mechanism=10, fidelity_by_builder=14, title=30, evidence=40,
             reported_loss=35, goal=30, shell=8, cwd=20, command=50, setup=60, check=45, twin=40, assumptions=35)


def sample():
    latest = {}
    for b in read_jsonl(os.path.join(HERE, "builds.jsonl")):
        if b["case"] is not None:
            latest[b["id"]] = b
    ok = sorted(i for i, b in latest.items() if b["case"].get("replayable"))
    cmd = [i for i in ok if latest[i]["mechanism"] != "O"]
    edit = [i for i in ok if latest[i]["mechanism"] == "O"]
    rng = random.Random(SEED)
    picked = rng.sample(cmd, N_CMD) + rng.sample(edit, N_EDIT)
    rng.shuffle(picked)
    return [latest[i] for i in picked]


def text(v):
    return v if isinstance(v, str) else json.dumps(v)


def write():
    os.makedirs(OUT, exist_ok=True)
    wb = openpyxl.Workbook()
    g = wb.active
    g.title = "Guide"
    for line in GUIDE:
        g.append([line])
    g["A1"].font = Font(bold=True, size=13)
    g.column_dimensions["A"].width = 140
    ws = wb.create_sheet("Audit")
    cols = CASE_COLS + [q for q, _, _ in QUESTIONS] + ["notes"]
    ws.append(cols)
    for n, b in enumerate(sample(), 1):
        c = b["case"]
        issue = load_issue(b["url"]) or {}
        row = dict(n=n, id=b["id"], link=b["url"], kind="edit" if b["mechanism"] == "O" else "command",
                   mechanism=b["mechanism"], fidelity_by_builder=c.get("fidelity"), title=issue.get("title", ""),
                   evidence=c.get("evidence"), reported_loss=c.get("reported_loss"), goal=c.get("goal"),
                   shell=c.get("shell"), cwd=c.get("cwd"),
                   command=text(c.get("command")), setup=c.get("setup"), check=c.get("check"),
                   twin=text(c.get("twin")), assumptions=c.get("assumptions"))
        ws.append([row[k] for k in CASE_COLS])
        ws.cell(n + 1, 3).hyperlink = b["url"]
        ws.cell(n + 1, 3).font = Font(color="0563C1", underline="single")
    last = ws.max_row
    head = PatternFill("solid", fgColor="DDEBF7")
    answer = PatternFill("solid", fgColor="FFF2CC")
    for j, name in enumerate(cols, 1):
        letter = openpyxl.utils.get_column_letter(j)
        ws.column_dimensions[letter].width = WIDTH.get(name, 14 if name != "notes" else 40)
        ws.cell(1, j).font = Font(bold=True)
        ws.cell(1, j).fill = answer if j > len(CASE_COLS) else head
        for i in range(2, last + 1):
            ws.cell(i, j).alignment = Alignment(wrap_text=True, vertical="top")
    for j, (q, opts, _) in enumerate(QUESTIONS, len(CASE_COLS) + 1):
        letter = openpyxl.utils.get_column_letter(j)
        dv = DataValidation(type="list", formula1='"%s"' % opts, allow_blank=True)
        ws.add_data_validation(dv)
        dv.add("%s2:%s%d" % (letter, letter, last))
        for i in range(2, last + 1):
            ws.cell(i, j).fill = answer
    ws.freeze_panes = "D2"
    path = os.path.join(OUT, "fidelity_audit.xlsx")
    wb.save(path)
    print("wrote", path, last - 1, "cases")


def score(path):
    ws = openpyxl.load_workbook(path)["Audit"]
    head = [c.value for c in ws[1]]
    rows = [dict(zip(head, [c.value for c in r])) for r in ws.iter_rows(min_row=2)]
    results = {}
    for r in read_jsonl(os.path.join(HERE, "results.jsonl")):
        results[r["id"]] = r
    out = dict(n=len(rows), answered=sum(bool(r.get("overall")) for r in rows))
    for q, _, _ in QUESTIONS:
        out[q] = dict(Counter(r.get(q) or "blank" for r in rows))
        for kind in ("command", "edit"):
            out["%s_%s" % (q, kind)] = dict(Counter(r.get(q) or "blank" for r in rows if r["kind"] == kind))
    # Does fidelity relate to the outcome? Joined only here, after the audit.
    out["overall_by_status"] = dict(Counter("%s/%s" % (r.get("overall") or "blank", results[r["id"]]["status"])
                                            for r in rows))
    out["overall_by_builder_fidelity"] = dict(Counter("%s/%s" % (r.get("overall") or "blank",
                                                                 r["fidelity_by_builder"]) for r in rows))
    re = os.path.join(OUT, "reassessment.json")
    if os.path.exists(re):
        changes = json.load(open(re))
        for q in ("ok_command", "ok_setup", "ok_check", "overall"):
            change = changes.get(q, {})
            if not change:
                continue
            for r in rows:
                if r["id"] in change:
                    assert r[q] == change[r["id"]][0], (q, r["id"])
            revised = [change[r["id"]][1] if r["id"] in change else r.get(q) for r in rows]
            out[q + "_reassessed"] = dict(Counter(v or "blank" for v in revised))
            for kind in ("command", "edit"):
                out["%s_reassessed_%s" % (q, kind)] = dict(Counter(v or "blank" for v, r in zip(revised, rows)
                                                                   if r["kind"] == kind))
            out["reassessed_" + q] = sorted(change)
    dest = os.path.join(OUT, "fidelity_scores.json")
    json.dump(out, open(dest, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    if "--score" in sys.argv:
        score(sys.argv[sys.argv.index("--score") + 1])
    else:
        write()
