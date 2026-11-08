"""Replay every Tier A case and its safe twin in a fresh, sealed container.

Per case: COMMON + setup run in a container, which is committed as the baseline image. The case's check must print
nothing on the baseline (otherwise the case is a harness error). The command then runs in a new container from the
baseline (--network none, no mounts, 120 s limit), the file system is compared with `docker diff`, and the check runs
in a copy of the finished container. The twin runs the same way from the same baseline.

Outcome per case:
  reproduced       the check prints LOST after the command
  not_reproduced   the check prints nothing after the command
  harness_error    setup failed, or the check already printed LOST on the baseline (build.py --repair may fix these)
  not_replayable   the builder declined the incident (reason recorded)

Usage: python3 run.py [ids...]   Output: results.jsonl (one line per case, latest build attempt; reruns resume).
"""
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from common import HERE, IMAGE, read_jsonl

sys.path.insert(0, os.path.join(HERE, "..", "bench"))
from cases import COMMON, WITNESSES  # noqa: E402

OUT = os.path.join(HERE, "results.jsonl")
IGNORE = ("/home/dev/.cache", "/home/dev/.local/share/powershell", "/home/dev/.config/powershell", "/tmp",
          "/home/dev/.bash_history", "/home/dev/pg.log", "/home/dev/pgdata/pg_wal", "/home/dev/pgdata/pg_stat",
          "/home/dev/pgdata/postmaster", "/home/dev/pgdata/pg_logical", "/home/dev/pgdata/pg_subtrans",
          "/home/dev/pgdata/global/pg_control", "/home/dev/.npm", "/home/dev/.psql_history", "/home/dev/.python_history")
SHELLS = {"bash": 'exec bash -c "$CMD"', "sh": 'exec sh -c "$CMD"', "pwsh": 'exec pwsh -NoProfile -Command "$CMD"',
          "edit": 'exec python3 /opt/edit_tools.py "$CMD"'}


def sh(args, timeout=300, **kw):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kw)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", "harness timeout")


def prelude(case):
    return "start-postgres >/dev/null 2>&1; " if "postgres" in (case.get("services") or []) else ""


def run_script(image, case, script, name=None, workdir="/home/dev"):
    """Run a bash script as dev in a new container. Returns (CompletedProcess, container name or None)."""
    args = ["docker", "run", "--network", "none", "-w", workdir, "-e", "CMD=" + script]
    if name:
        args += ["--name", name]
    else:
        args += ["--rm"]
    return sh(args + [image, "bash", "-c", prelude(case) + 'exec bash -c "$CMD"']), name


def check_lost(image, case):
    r, _ = run_script(image, case, case["check"])
    return "LOST" in r.stdout


def witness(container, path):
    d = tempfile.mkdtemp()
    if sh(["docker", "cp", "%s:%s" % (container, path), d]).returncode != 0:
        return None
    return open(os.path.join(d, os.path.basename(path)), errors="replace").read()


def execute(case, base, cid, which):
    """Run the command (or twin) from the baseline image and measure its effect."""
    name = "rp_%s_%s" % (which, cid)
    sh(["docker", "rm", "-f", name])
    command = case["command"] if which == "cmd" else case["twin"]
    if not isinstance(command, str):
        command = json.dumps(command)  # edit cases: the call may come back as an object
    shell = SHELLS.get(case.get("shell", "bash"), SHELLS["bash"])
    cwd = case.get("cwd") or "/home/dev"
    r = sh(["docker", "run", "--name", name, "--network", "none", "-w", cwd, "-e", "CMD=" + command, base,
            "timeout", "120", "bash", "-c", prelude(case) + shell], timeout=400)
    changes = []
    for line in sh(["docker", "diff", name]).stdout.split("\n"):
        if line.strip() and not line[2:].startswith(IGNORE):
            changes.append((line[0], line[2:]))
    intended = case.get("intended") or []
    deleted = [p for k, p in changes if k == "D"]
    collateral = [p for p in deleted if not any(p.startswith(i) for i in intended)]
    harmed = [w for w in WITNESSES if witness(name, w) != case["_witness"][w]]
    after = "rp_after_%s_%s" % (which, cid)
    sh(["docker", "commit", name, after.lower()])
    lost = check_lost(after.lower(), case)
    sh(["docker", "rm", "-f", name])
    sh(["docker", "rmi", "-f", after.lower()])
    return dict(exit=r.returncode, stderr=r.stderr[-300:], deleted=len(deleted), changed=len(changes),
                collateral=len(collateral), collateral_examples=collateral[:6], witnesses_harmed=harmed, lost=lost)


def replay(b):
    case = b["case"]
    out = dict(id=b["id"], url=b["url"], mechanism=b["mechanism"], attempt=b["attempt"])
    if not case.get("replayable"):
        return dict(out, status="not_replayable", exclusion=case.get("exclusion"), reason=case.get("exclusion_reason"))
    out.update(fidelity=case.get("fidelity"), shell=case.get("shell"), command=case.get("command"))
    cid = b["id"].lower()
    setup_name = "rp_setup_" + cid
    sh(["docker", "rm", "-f", setup_name])
    r, _ = run_script(IMAGE, case, "set -e\n" + COMMON + "\nset -e\ncd /home/dev\n" + case.get("setup", ""), name=setup_name)
    if r.returncode != 0:
        sh(["docker", "rm", "-f", setup_name])
        return dict(out, status="harness_error", harness_error="setup failed: " + (r.stderr or r.stdout)[-400:])
    base = "rp_base_" + cid
    sh(["docker", "commit", setup_name, base])
    sh(["docker", "rm", "-f", setup_name])
    try:
        if check_lost(base, case):
            return dict(out, status="harness_error", harness_error="the check prints LOST on the state right after setup")
        probe = "rp_probe_" + cid
        sh(["docker", "rm", "-f", probe])
        sh(["docker", "create", "--name", probe, base])
        case["_witness"] = {w: witness(probe, w) for w in WITNESSES}
        sh(["docker", "rm", "-f", probe])
        cmd = execute(case, base, cid, "cmd")
        twin = execute(case, base, cid, "twin")
    finally:
        sh(["docker", "rmi", "-f", base])
    return dict(out, status="reproduced" if cmd["lost"] else "not_reproduced", cmd=cmd, twin=twin)


def main():
    only = set(sys.argv[1:])
    latest = {}
    for b in read_jsonl(os.path.join(HERE, "builds.jsonl")):
        if b["case"] is not None:
            latest[b["id"]] = b
    done = {(r["id"], r["attempt"]) for r in read_jsonl(OUT)}
    todo = [b for i, b in sorted(latest.items()) if (i, b["attempt"]) not in done and (not only or i in only)]
    print("replaying", len(todo), "cases", flush=True)
    n = 0
    with ThreadPoolExecutor(4) as pool, open(OUT, "a") as out:
        for res in pool.map(replay, todo):
            out.write(json.dumps(res) + "\n")
            out.flush()
            n += 1
            if n % 25 == 0:
                print("replayed %d of %d" % (n, len(todo)), flush=True)
    print("done", n, flush=True)


if __name__ == "__main__":
    main()
