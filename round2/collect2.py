"""Round 2 collection: broad, neutral search of coding-agent issue trackers.

Searches title AND body (GitHub default) for loss-describing phrases (NEUTRAL) and, separately,
command phrases (COMMAND) so the bias of command words can be measured later.
GitHub returns at most 1,000 results per query, so big queries are split by creation date.
Output: hits.jsonl (one line per issue per matching phrase).
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "hits.jsonl")

AGENT_REPOS = ["anthropics/claude-code", "openai/codex", "google-gemini/gemini-cli", "cline/cline", "Aider-AI/aider",
               "OpenHands/OpenHands", "RooCodeInc/Roo-Code", "Kilo-Org/kilocode", "continuedev/continue",
               "microsoft/vscode-copilot-release", "github/copilot-cli", "aws/amazon-q-developer-cli", "kirodotdev/Kiro",
               "anomalyco/opencode", "aaif-goose/goose", "charmbracelet/crush", "QwenLM/qwen-code", "Exafunction/codeium"]
# General tools with an agent feature: require an agent word so plain editor bugs stay out.
MIXED_REPOS = {"microsoft/vscode": "copilot", "zed-industries/zed": "agent", "warpdotdev/warp": "agent"}

NEUTRAL = ["deleted my", "deleted all", "deleted the", "deleted everything", "lost my", "lost all", "data loss", "wiped",
           "destroyed", "overwrote", "overwritten", "unrecoverable", "irreversible", "erased", "disappeared",
           "permanently deleted", "lost work", "lost changes"]
COMMAND = ["rm -rf", "git reset --hard", "git checkout", "git clean", "drop table", "force push"]

YEARS = [("2023-01-01", "2024-12-31"), ("2025-01-01", "2025-06-30"), ("2025-07-01", "2025-12-31"),
         ("2026-01-01", "2026-03-31"), ("2026-04-01", "2026-06-30"), ("2026-07-01", "2026-09-30"), ("2026-10-01", "2026-12-31")]


def search(q, page):
    for attempt in range(6):
        r = subprocess.run(["gh", "api", "-X", "GET", "search/issues", "-f", "q=" + q, "-f", "per_page=100",
                            "-f", "page=%d" % page], capture_output=True, text=True)
        if r.returncode == 0:
            time.sleep(2.1)  # stay under 30 search requests per minute
            return json.loads(r.stdout)
        # Rate limits and network errors: wait and retry.
        time.sleep(30 * (attempt + 1) if ("rate limit" in r.stderr.lower() or "403" in r.stderr or "429" in r.stderr) else 10)
    raise RuntimeError("rate limited: " + q)


def halves(a, b):
    import datetime
    d0, d1 = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    mid = d0 + (d1 - d0) / 2
    return [(a, mid.isoformat()), ((mid + datetime.timedelta(days=1)).isoformat(), b)]


def collect(q, tag, out, span=None):
    query = q if span is None else "%s created:%s..%s" % (q, span[0], span[1])
    first = search(query, 1)
    total = first["total_count"]
    if total >= 1000:
        # Too many for one query: split the date range until each part is under the cap.
        parts = YEARS if span is None else (halves(*span) if span[0] != span[1] else [])
        if parts:
            for part in parts:
                collect(q, tag, out, part)
            return total
    items = first["items"]
    for page in range(2, min(10, (total + 99) // 100) + 1):
        items += search(query, page)["items"]
    for it in items:
        out.write(json.dumps(dict(url=it["html_url"], title=it["title"], created=it["created_at"][:10],
                                  repo=it["repository_url"].split("repos/")[1], phrase=tag[1], kind=tag[0])) + "\n")
    return total


def main():
    done = set()
    if os.path.exists(OUT + ".done"):
        done = set(open(OUT + ".done").read().split("\n"))
    jobs = [(r, None) for r in AGENT_REPOS] + list(MIXED_REPOS.items())
    with open(OUT, "a") as out, open(OUT + ".done", "a") as mark:
        for repo, extra in jobs:
            for kind, phrases in (("neutral", NEUTRAL), ("command", COMMAND)):
                for p in phrases:
                    key = "%s|%s" % (repo, p)
                    if key in done:
                        continue
                    q = '"%s" repo:%s is:issue' % (p, repo) + (" " + extra if extra else "")
                    total = collect(q, (kind, p), out)
                    out.flush()
                    mark.write(key + "\n")
                    mark.flush()
                    print("%-34s %-20s %d" % (repo, p, total), flush=True)


if __name__ == "__main__":
    main()
