"""Edit-tool contracts for replaying file-edit incidents (mechanism O).

Each function reimplements the documented or source-code behaviour of one tool version, as recorded with permalinks
in EDIT_CONTRACTS.md. Only the parts that decide WHICH text gets replaced are implemented. Permission prompts,
formatters and line-ending handling are left out. Tools or paths that are not covered raise Unsupported.

Usage inside the sandbox:  python3 /opt/edit_tools.py '<json call>'
  {"contract": "opencode_v1_prefix", "tool": "edit", "path": "...", "old": "...", "new": "...", "replace_all": false}
  {"contract": "codex_apply_patch", "patch": "*** Begin Patch\n..."}
Exit 0 when the tool applied the edit, 1 when the tool returned an error (the file is unchanged), 2 when unsupported.
"""
import json
import os
import sys


class ToolError(Exception):
    """The real tool would have returned an error and left the file unchanged."""


class Unsupported(Exception):
    """The harness does not implement this part of the contract."""


# ---------------------------------------------------------------- shared helpers

def lev(a, b):
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def region(lines, i, j):
    """Text of lines i..j (inclusive), without the last line's newline, and its start offset."""
    start = sum(len(l) + 1 for l in lines[:i])
    return "\n".join(lines[i:j + 1]), start


def write_whole(content, new, exists):
    return new


# ---------------------------------------------------------------- OpenCode v1 (edit.ts, through v1.19.5)

def oc_line_trimmed(content, find):
    lines, search = content.split("\n"), find.split("\n")
    if search and search[-1] == "":
        search = search[:-1]
    n = len(search)
    for i in range(len(lines) - n + 1):
        if all(lines[i + k].strip() == search[k].strip() for k in range(n)):
            yield region(lines, i, i + n - 1)[0]


def oc_block_anchor(content, find, prefix):
    lines, search = content.split("\n"), find.split("\n")
    if len(search) < 3:
        return
    if search[-1] == "":
        search = search[:-1]
    n = len(search)
    first, last = search[0].strip(), search[-1].strip()
    cands = []
    for i, l in enumerate(lines):
        if l.strip() != first:
            continue
        for j in range(i + 2, len(lines)):
            if lines[j].strip() == last:
                if prefix or abs((j - i + 1) - n) <= max(1, n * 25 // 100):
                    cands.append((i, j))
                break
    if not cands:
        return

    def sim(i, j):
        size = j - i + 1
        to_check = min(n, size) - 2
        if to_check <= 0:
            return 1.0
        sims = []
        for k in range(1, min(n, size) - 1):
            a, b = lines[i + k].strip(), search[k].strip()
            if not a and not b:
                continue
            sims.append(1 - lev(a, b) / max(len(a), len(b)))
        return sum(sims) / to_check if sims else 1.0

    single, multi = (0.0, 0.3) if prefix else (0.65, 0.65)
    if len(cands) == 1:
        i, j = cands[0]
        if sim(i, j) >= single:
            yield region(lines, i, j)[0]
        return
    best = max(cands, key=lambda c: sim(*c))
    if sim(*best) >= multi:
        yield region(lines, best[0], best[1])[0]


def oc_disproportionate(search, old):
    ol, sl = len(old.split("\n")), len(search.split("\n"))
    if sl >= max(ol + 3, ol * 2):
        return True
    if ol == 1:
        return False
    return len(search.strip()) > max(len(old.strip()) + 500, len(old.strip()) * 4)


def opencode_v1(content, old, new, replace_all, exists, prefix):
    if old == new:
        raise ToolError("oldString and newString are identical")
    if old == "":
        if prefix or not exists:
            return new  # pre-fix: the whole existing file becomes newString
        raise ToolError("oldString cannot be empty when editing an existing file")
    found = False
    # SimpleReplacer, LineTrimmedReplacer, BlockAnchorReplacer are implemented. The later replacers
    # (whitespace-normalised, indentation-flexible, escape-normalised, trimmed-boundary, context-aware) are not.
    for cands in ([old], oc_line_trimmed(content, old), oc_block_anchor(content, old, prefix)):
        for search in cands:
            idx = content.find(search)
            if idx < 0:
                continue
            found = True
            if not prefix and oc_disproportionate(search, old):
                raise ToolError("matched span is much larger than oldString")
            if replace_all:
                return content.replace(search, new)
            if content.rfind(search) != idx:
                continue
            return content[:idx] + new + content[idx + len(search):]
    if not found:
        raise Unsupported("no match in the implemented replacers (later fuzzy replacers not implemented)")
    raise ToolError("found multiple matches for oldString")


# ---------------------------------------------------------------- OpenCode v2 (current)

UNI = str.maketrans({c: "'" for c in "‘’‚‛"} | {c: '"' for c in "“”„‟"}
                    | {c: "-" for c in "‐‑‒–—―−"}
                    | {c: " " for c in "            　"})


def find_all(text, s):
    out, i = [], text.find(s)
    while i >= 0:
        out.append((i, i + len(s)))
        i = text.find(s, i + len(s))
    return out


def opencode_v2(content, old, new, replace_all, exists):
    if old == new:
        raise ToolError("identical")
    if old == "":
        raise ToolError("oldString must not be empty")
    if not exists:
        raise ToolError("file not found")
    m = find_all(content, old) or find_all(content.translate(UNI), old.translate(UNI))
    if not m:
        raise Unsupported("tier-3 trailing-whitespace matching not implemented")
    if len(m) > 1 and not replace_all:
        raise ToolError("found %d matches" % len(m))
    for a, b in reversed(m if replace_all else m[:1]):
        content = content[:a] + new + content[b:]
    return content


# ---------------------------------------------------------------- Claude Code (docs only)

def claude_edit(content, old, new, replace_all, exists):
    if old == "":
        raise Unsupported("Claude Code behaviour for an empty old_string is not documented")
    if not exists:
        raise ToolError("file does not exist")
    n = content.count(old)
    if n == 0:
        raise ToolError("old_string not found")
    if n > 1 and not replace_all:
        raise ToolError("old_string is not unique")
    return content.replace(old, new) if replace_all else content.replace(old, new, 1)


# ---------------------------------------------------------------- Gemini CLI replace

def gemini_replace(content, old, new, allow_multiple, exists):
    if old == "":
        if exists:
            raise ToolError("attempt to create a file that already exists")
        return new
    if not exists:
        raise ToolError("file not found")
    n = content.count(old)
    if n == 0:
        # Fallback: trimmed-line match. Token-regex and Levenshtein fallbacks are not implemented.
        hits = list(oc_line_trimmed(content, old))
        if not hits:
            raise Unsupported("no exact or trimmed-line match (later Gemini fallbacks not implemented)")
        if len(hits) > 1 and not allow_multiple:
            raise ToolError("multiple matches")
        for h in hits:
            content = content.replace(h, new)
        return content
    if n > 1 and not allow_multiple:
        raise ToolError("expected 1 occurrence but found %d" % n)
    return content.replace(old, new)


# ---------------------------------------------------------------- Aider diff (SEARCH/REPLACE)

def aider_diff(content, search, replace, exists):
    if search.strip() == "":
        return (content if exists else "") + replace  # empty SEARCH appends
    if any(l.strip() == "..." for l in search.split("\n")):
        raise Unsupported("aider '...' elision not implemented")
    idx = content.find(search)
    if idx < 0:
        raise Unsupported("leading-whitespace and blank-line fallbacks not implemented")
    return content[:idx] + replace + content[idx + len(search):]  # first occurrence, no uniqueness check


# ---------------------------------------------------------------- Cline v3 replace_in_file

def cline_v3(content, blocks, v300):
    out, last = [], 0
    reps = []
    for search, replace in blocks:
        if search == "":
            if content == "":
                reps.append((0, 0, replace))
                continue
            if v300:
                reps.append((0, len(content), replace))  # v3.0.0: whole-file replacement
                continue
            raise ToolError("empty SEARCH block with non-empty file")
        s = search if search.endswith("\n") else search + "\n"
        idx = content.find(s, last)
        span = None
        if idx >= 0:
            span = (idx, idx + len(s))
        else:
            lines = content.split("\n")
            sl = s.split("\n")
            if sl[-1] == "":
                sl = sl[:-1]
            n = len(sl)
            start_line = content[:last].count("\n")
            for i in range(start_line, len(lines) - n + 1):  # line-trimmed
                if all(lines[i + k].strip() == sl[k].strip() for k in range(n)):
                    a = sum(len(l) + 1 for l in lines[:i])
                    span = (a, a + sum(len(l) + 1 for l in lines[i:i + n]))
                    break
            if span is None and n >= 3:  # block anchor: first and last line only
                for i in range(start_line, len(lines) - n + 1):
                    if lines[i].strip() == sl[0].strip() and lines[i + n - 1].strip() == sl[-1].strip():
                        a = sum(len(l) + 1 for l in lines[:i])
                        span = (a, a + sum(len(l) + 1 for l in lines[i:i + n]))
                        break
            if span is None:
                idx = content.find(s)
                if idx < 0:
                    raise ToolError("SEARCH block does not match anything in the file")
                span = (idx, idx + len(s))
        r = replace if replace.endswith("\n") or replace == "" else replace + "\n"
        reps.append((span[0], span[1], r))
        last = span[1]
    for a, b, r in sorted(reps, reverse=True):
        content = content[:a] + r + content[b:]
    return content


# ---------------------------------------------------------------- Codex apply_patch

def codex_apply_patch(patch, read, write, delete):
    lines = patch.split("\n")
    if not lines or lines[0].strip() != "*** Begin Patch":
        raise ToolError("patch must start with *** Begin Patch")
    i = 1
    while i < len(lines) and lines[i].strip() != "*** End Patch":
        h = lines[i]
        if h.startswith("*** Add File: "):
            path, body = h[14:].strip(), []
            i += 1
            while i < len(lines) and not lines[i].startswith("***"):
                if not lines[i].startswith("+"):
                    raise ToolError("invalid add-file line")
                body.append(lines[i][1:])
                i += 1
            write(path, "\n".join(body) + "\n")  # overwrites an existing file without a check
        elif h.startswith("*** Delete File: "):
            delete(h[17:].strip())
            i += 1
        elif h.startswith("*** Update File: "):
            path = h[17:].strip()
            i += 1
            if i < len(lines) and lines[i].startswith("*** Move to: "):
                raise Unsupported("move not implemented")
            file_lines = read(path).split("\n")
            if file_lines and file_lines[-1] == "":
                file_lines = file_lines[:-1]
            cursor = 0
            while i < len(lines) and not lines[i].startswith("*** ") or (i < len(lines) and lines[i] == "*** End of File"):
                if lines[i] == "*** End of File":
                    i += 1
                    continue
                if lines[i].startswith("@@"):
                    i += 1
                old, new = [], []
                while i < len(lines) and not lines[i].startswith("@@") and not lines[i].startswith("*** "):
                    l = lines[i]
                    tag, text = (l[0], l[1:]) if l else (" ", "")
                    if tag not in " -+":
                        raise ToolError("invalid hunk line")
                    if tag in " -":
                        old.append(text)
                    if tag in " +":
                        new.append(text)
                    i += 1
                if not old:
                    file_lines = file_lines + new  # pure addition appends at end of file
                    continue
                pos = None
                for norm in (lambda s: s, str.rstrip, str.strip):
                    for k in range(cursor, len(file_lines) - len(old) + 1):
                        if all(norm(file_lines[k + t]) == norm(old[t]) for t in range(len(old))):
                            pos = k
                            break
                    if pos is not None:
                        break
                if pos is None:
                    raise ToolError("failed to find expected lines")
                file_lines = file_lines[:pos] + new + file_lines[pos + len(old):]
                cursor = pos + len(new)
            write(path, "\n".join(file_lines) + "\n")
        else:
            raise ToolError("unknown patch header: " + h)
    return True


# ---------------------------------------------------------------- dispatcher

def apply(call):
    c = call["contract"]
    if c == "codex_apply_patch":
        return codex_apply_patch(call["patch"], lambda p: open(p).read(),
                                 lambda p, t: (os.makedirs(os.path.dirname(p) or ".", exist_ok=True), open(p, "w").write(t)),
                                 os.remove)
    path = call["path"]
    exists = os.path.exists(path)
    content = open(path).read() if exists else ""
    tool = call.get("tool", "edit")
    if tool == "write" or c in ("aider_whole", "write"):
        new = call["content"]
        if c == "cline_v3_write" and new.startswith("```"):
            new = new.split("\n", 1)[1] if "\n" in new else ""
            new = new.rsplit("```", 1)[0] if new.rstrip().endswith("```") else new
        result = new
    elif c in ("opencode_v1_prefix", "opencode_v1_postfix"):
        result = opencode_v1(content, call["old"], call["new"], call.get("replace_all", False), exists, c.endswith("prefix"))
    elif c == "opencode_v2":
        result = opencode_v2(content, call["old"], call["new"], call.get("replace_all", False), exists)
    elif c == "claude_edit":
        result = claude_edit(content, call["old"], call["new"], call.get("replace_all", False), exists)
    elif c == "gemini_replace":
        result = gemini_replace(content, call["old"], call["new"], call.get("allow_multiple", False), exists)
    elif c == "aider_diff":
        result = aider_diff(content, call["old"], call["new"], exists)
    elif c in ("cline_v3", "cline_v3_0"):
        result = cline_v3(content, [tuple(b) for b in call["blocks"]], c == "cline_v3_0")
    else:
        raise Unsupported("unknown contract " + c)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(result)
    return True


def main():
    call = json.loads(sys.argv[1])
    try:
        apply(call)
    except ToolError as e:
        print("tool error:", e, file=sys.stderr)
        sys.exit(1)
    except Unsupported as e:
        print("unsupported:", e, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
