"""Replay each case in a fresh container and record its real effect with `docker diff`.

Steps per case: run COMMON + setup in a container, commit it as a baseline image,
run the command in a new container from that image (no network, 60 s limit),
then diff against the baseline. Witness files are copied out to check for harm.
Output: results.json
"""
import json
import os
import subprocess
import sys
import tempfile

from cases import ALL_CASES as CASES, COMMON, WITNESSES

HERE = os.path.dirname(os.path.abspath(__file__))
IGNORE = ("/home/dev/.cache", "/home/dev/.local/share/powershell", "/home/dev/.config/powershell",
          "/tmp/CoreFxPipe", "/home/dev/.bash_history")


def sh(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def baseline(case):
    name = "cmdfx_setup_" + case["id"]
    sh(["docker", "rm", "-f", name])
    script = COMMON + "\n" + case["setup"]
    r = sh(["docker", "run", "--name", name, "--network", "none", "cmdfx-base", "bash", "-c", script])
    if r.returncode != 0:
        raise RuntimeError("setup failed for %s: %s" % (case["id"], r.stderr[-400:]))
    image = "cmdfx-case:" + case["id"].lower()
    sh(["docker", "commit", name, image])
    sh(["docker", "rm", "-f", name])
    return image


def witness_text(container, path):
    d = tempfile.mkdtemp()
    r = sh(["docker", "cp", "%s:%s" % (container, path), d])
    if r.returncode != 0:
        return None
    return open(os.path.join(d, os.path.basename(path))).read()


def run_case(case):
    image = baseline(case)
    before = {}
    probe = "cmdfx_probe_" + case["id"]
    sh(["docker", "create", "--name", probe, image])
    for w in WITNESSES:
        before[w] = witness_text(probe, w)
    sh(["docker", "rm", "-f", probe])

    name = "cmdfx_run_" + case["id"]
    sh(["docker", "rm", "-f", name])
    shell = ["bash", "-c"] if case["shell"] == "bash" else ["pwsh", "-NoProfile", "-Command"]
    r = sh(["docker", "run", "--name", name, "--network", "none", "-w", case["cwd"], image,
            "timeout", "60"] + shell + [case["command"]])
    diff = sh(["docker", "diff", name]).stdout.split("\n")
    changes = []
    for line in diff:
        if not line.strip():
            continue
        kind, path = line[0], line[2:]
        if path.startswith(IGNORE):
            continue
        changes.append((kind, path))

    # A deleted path is collateral unless it is inside an intended prefix.
    # Deleting a parent of the target counts as collateral.
    def expected(path):
        return any(path.startswith(p) for p in case["intended"])

    deleted = [p for k, p in changes if k == "D"]
    modified = [p for k, p in changes if k == "C"]
    collateral_deleted = [p for p in deleted if not expected(p)]
    after = {w: witness_text(name, w) for w in WITNESSES}
    harmed = [w for w in WITNESSES if after[w] != before[w]]

    # Case-specific check for data that is overwritten rather than deleted, or lives in a remote repo.
    # The check runs in a copy of the finished container and prints LOST when the data is gone.
    remote_lost = None
    if case.get("check"):
        after_image = "cmdfx-after:" + case["id"].lower()
        sh(["docker", "commit", name, after_image])
        out = sh(["docker", "run", "--rm", "--network", "none", after_image, "bash", "-c", case["check"]]).stdout
        remote_lost = "LOST" in out
    sh(["docker", "rm", "-f", name])

    return dict(id=case["id"], source=case["source"], mechanism=case["mechanism"], shell=case["shell"],
                command=case["command"], exit=r.returncode, stderr=r.stderr[-300:],
                deleted=len(deleted), modified=len(modified), collateral_deleted=len(collateral_deleted),
                collateral_examples=collateral_deleted[:8], witnesses_harmed=harmed, remote_lost=remote_lost)


def main():
    only = set(sys.argv[1:])
    results = []
    for case in CASES:
        if only and case["id"] not in only:
            continue
        res = run_case(case)
        results.append(res)
        print("%-26s exit=%-3s deleted=%-5d collateral=%-5d harmed=%s%s" % (
            res["id"], res["exit"], res["deleted"], res["collateral_deleted"],
            [w.split("/")[-1] for w in res["witnesses_harmed"]],
            "" if res["remote_lost"] is None else " remote_team_commit_lost=%s" % res["remote_lost"]))
    json.dump(results, open(os.path.join(HERE, "results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
