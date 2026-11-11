"""Shared paths and helpers for the Tier A replay study."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
IMAGE = "cmdfx-replay"


def issue_path(url):
    """Local copy of an issue body (downloaded by collect1.py or round2/fetch_bodies.py)."""
    p = url.split("/")
    name = "%s__%s_%s.json" % (p[3], p[4], p[6])
    for d in (os.path.join(ROOT, "round2", "issues"), os.path.join(ROOT, "issues")):
        f = os.path.join(d, name)
        if os.path.exists(f):
            return f
    return None


def load_issue(url):
    f = issue_path(url)
    return json.load(open(f)) if f else None


def case_id(url):
    p = url.split("/")
    return "%s_%s" % (p[4].lower().replace("-", "_").replace(".", "_"), p[6])


def read_jsonl(path):
    return [json.loads(l) for l in open(path)] if os.path.exists(path) else []


def out_of_scope():
    """Case ids left out of the replay and prediction results: rated unfaithful by the audit, or no longer a
    misjudged-effect (M) incident after a census label correction (labelling/corrections.json)."""
    out = set(json.load(open(os.path.join(HERE, "audit", "final_verdicts.json")))["summary"]["excluded"])
    census = json.load(open(os.path.join(ROOT, "labelling", "census_all.json")))
    m_ids = {case_id(r["url"]) for r in census if r["cause"] == "M"}
    for c in read_jsonl(os.path.join(HERE, "candidates.jsonl")):
        if c["id"] not in m_ids:
            out.add(c["id"])
    return out
