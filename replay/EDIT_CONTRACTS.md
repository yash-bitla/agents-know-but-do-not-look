# File-edit tool contracts (for replay harness)

Compiled 2026-11-07/08 from primary sources. Every source file below was downloaded at the commit or tag shown in its URL (raw.githubusercontent.com at that ref) and read; the `blob` permalinks point at the same ref and line ranges. Behaviour described as "per ECMAScript" or "derived" is my reading of the code, not something I executed.

Version pins used:

| Tool | Ref read | Notes |
|---|---|---|
| OpenCode (current) | `dev` @ `da8c0211f7c00afbf1dd96e629801fe84d205541` (2026-11-08); same `edit.ts` as tag `v2.2.6` (`dc2ffcf8`, released 2026-11-06) | v2 rewrite, `packages/core/src/tool/plugin/` |
| OpenCode (legacy v1) | tag `v1.19.5` @ `810c0eba1a7348036f8bdf61e6632d0c36c6876c`; pre-fix `604a5f781f75bc090a4db35de47b2bcca5ebf687`; fix `236cfcbbc31530fde6a9e65318703f40adad8455` (PR #30932, merged 2026-06-05) | `packages/opencode/src/tool/` |
| Gemini CLI | `main` @ `62bab5b232c15b925d31e655ce844ab939c882b7` (2026-11-06); latest release v0.67.0 (2026-11-04); `v0.25.0` read for `expected_replacements` | |
| Aider | `main` @ `5dc9490bb35f9729ef2c95d00a19ccd30c26339c`; `editblock_coder.py` and `wholefile_coder.py` are byte-identical to release `v0.86.0` (2025-08-09) | |
| Codex CLI | `main` @ `748ab55ca7de0b647d9a7a9d9a8e70e00f28666d` (2026-11-08); latest stable release rust-v0.167.0 | `codex-rs/apply-patch/` |
| Cline (legacy v3) | tag `v3.89.2` @ `e1bdeeff68e95734901c7a4b3a31753bae54a634`; tag `v3.0.0` for the older empty-SEARCH behaviour | `replace_in_file` / `write_to_file` |
| Cline (current v4) | `main` @ `94eecbbe1a2f899c66b118d13656651b0a884e1f` (2026-11-06); latest release v4.1.26 | SDK tools `editor`, `apply_patch` |
| Claude Code | docs at code.claude.com (fetched 2026-11-08) | closed source |

---

## 1. OpenCode (anomalyco/opencode, formerly sst/opencode)

OpenCode has two edit contracts that a harness must keep apart: the **v1 line** (`packages/opencode/src/tool/edit.ts`, used through v1.19.5) with the 9-replacer fallback chain, and the **v2 rewrite** (`packages/core/src/tool/plugin/edit.ts`, shipped in v2.x, current) with a much narrower 3-tier matcher. Inside v1, the empty-`oldString` behaviour changed on 2026-06-05.

### 1a. OpenCode v2 (current: v2.2.6 / dev HEAD)

Contract, `edit`:
- Name `edit`. Params: `path` (string; relative resolves in the active Location), `oldString` (string), `newString` (string), `replaceAll` (optional boolean, default false). Note that v2 uses `path`, not `filePath`. (edit.ts L22-34)
- `oldString === newString` -> error "No changes to apply: oldString and newString are identical." (L280-284)
- **`oldString === ""` -> always an error**: "oldString must not be empty. Use write to create or overwrite a file." The file is not touched, and v2 has no create-via-edit path. (L285-290)
- If the file is missing -> "File not found"; if it is a directory -> error. (L293-302)
- "Endings-only" special case: if `oldString` and `newString` are equal after removing every `\r`, the tool matches `oldString` byte-exactly on the raw source (plain `indexOf` loop) and writes `newString` verbatim. (L306-309)
- Otherwise `matchView` (L168-188) does the following:
  - Build `view = source.replaceAll("\r\n","\n")`. Also normalise `oldString` and `newString` the same way.
  - Tier 1, **exact**: find all non-overlapping occurrences of `search` in `view` (indexOf, then advance by `search.length`). (L56-64)
  - Tier 2, only if tier 1 found none, **unicode-normalised**: run the same search on `normalizeForMatch(view)` and `normalizeForMatch(search)`. `normalizeForMatch` maps `‘ ’ ‚ ‛` to `'`, `“ ” „ ‟` to `"`, `‐ ‑ ‒ – — ― −` to `-`, and U+00A0, U+2002-200A, U+202F, U+205F, U+3000 to a space. Each mapping is one char to one char, so offsets are preserved. (L49-54)
  - Tier 3, only if tiers 1 and 2 found none, **per-line trailing-whitespace-insensitive**:
    - Split `search` on `\n`. If it ends with `\n`, drop the final empty element and require the last matched line to have a newline.
    - Every window of consecutive file lines whose `normalizeForMatch(line.trimEnd())` equals the same for each search line is a candidate. The region runs from the start of the first line to either the end of the last line's content (`\r` excluded), or past its `\n` when `search` ended with `\n`.
    - Overlapping candidates are dropped greedily, first one wins. (L66-102)
  - Match offsets are mapped back to the raw source by adding back the removed `\r` count. (L170, L179-182, L243-253)
  - The replacement text gets per-line endings copied from the matched region, aligned by LCS. Lines with no counterpart take the region's dominant ending, or the file's. (L104-162, L183-186)
- Match count: 0 -> error "Could not find oldString ...". The error may include a "closest lines" hint, shown only if reading the file is already permitted. (L322-334, L199-241)
- More than 1 match and `replaceAll !== true` -> error "Found N matches for oldString, but expected exactly one ...". (L335-339)
- `replaceAll` -> every match in the list is replaced (right to left). Otherwise exactly 1 match must exist, and it is replaced. Replacement is by slicing, so `$` in `newString` is literal. (L310-316)
- If the result equals the source -> error, no write. (L340-346)
- A permission ask (`edit`) with a diff preview comes before the write. After the write, a formatter may rewrite the file, and the returned diff reflects the formatted text. (L317-321, L347-353; file-write.ts L83-90)
- Fuzzy region growth: **none beyond line-trailing whitespace and the unicode map**. A tier-3 match always spans exactly as many lines as `oldString`.

Contract, `write`:
- Name `write`. Params: `path`, `content`. (write.ts L14-22)
- Creates the file or **overwrites the existing file unconditionally**, after an `edit` permission ask with a diff preview. Missing parent dirs are created. An existing UTF-8 BOM is kept. A formatter may run afterwards. (write.ts L51, L56; file-write.ts L92-101, L83-90)
- No read-before-write or staleness check in v2 code (none found in `write.ts` / `file-write.ts`).

Placeholders: none detected in v2. `// ... existing code ...` in `newString` or `content` is written literally.

### 1b. OpenCode v1 line (through v1.19.5)

Contract, `edit`:
- Params `filePath`, `oldString`, `newString`, `replaceAll?`. Relative `filePath` is joined to the instance directory. (v1.19.5 edit.ts L47-56, L80-82)
- `oldString === newString` -> error. (L75-77)
- **`oldString === ""`, behaviour depends on version:**
  - **Before fix `236cfcbb` (PR #30932, 2026-06-05)**: `if (params.oldString === "")`, then read the existing file if any and **write `newString` as the entire file**. This is a full overwrite of an existing file, with only the permission ask in front of it. (pre-fix 604a5f78 edit.ts L90-117)
  - Before 2026-04-17 (commit `76a14109`, "delete filetime module", #22999), the empty-`oldString` branch wrote `params.newString` and **skipped `filetime.assert`**, the read-before-edit/stale check that the non-empty branch ran. So the empty-string path also bypassed the "must read first" guard. (diff of 76a14109, removed lines in `packages/opencode/src/tool/edit.ts`)
  - **After the fix (v1.16.2 and later v1 tags contain it; checked v1.15.x-v1.19.x via compare API)**: if the file exists -> error "oldString cannot be empty when editing an existing file. Provide the exact text to replace, or use write for an intentional full-file replacement." If the file does not exist -> create it with `newString`. (v1.19.5 L90-121) `replace()` also rejects `""` itself. (L686-690)
- Line endings: if the file contains any `\r\n`, `oldString` and `newString` are converted to CRLF first. (L22-33, L129-131)
- `replace(content, oldString, newString, replaceAll)` (L682-729) is the matching core:
  - For each replacer in this order: `SimpleReplacer, LineTrimmedReplacer, BlockAnchorReplacer, WhitespaceNormalizedReplacer, IndentationFlexibleReplacer, EscapeNormalizedReplacer, TrimmedBoundaryReplacer, ContextAwareReplacer, MultiOccurrenceReplacer`:
    - Take each candidate string `search` the replacer yields (each candidate is a substring copied out of `content`, or a transformed find string).
    - `index = content.indexOf(search)`. If -1, try the next candidate.
    - Set `notFound = false`.
    - (Post-fix only) if `isDisproportionateMatch(search, oldString)` -> throw "Refusing replacement because the matched span is much larger than oldString ...".
    - If `replaceAll` -> `return content.replaceAll(search, newString)`. With a string pattern, JS `replaceAll` expands `$&`, `$$`, `` $` ``, `$'` in `newString` (per ECMAScript; not tested).
    - Else, if `content.lastIndexOf(search) !== index`, the candidate is ambiguous: try the next candidate or replacer.
    - Else splice `newString` in at `index` (literal).
  - After all replacers: if `notFound` -> "Could not find oldString in the file ..."; else -> "Found multiple matches for oldString ...".
  - Note: the splice location is the **first textual occurrence of the yielded string**, not the location where the replacer found it. The uniqueness check makes these the same.
- `isDisproportionateMatch` (post-fix, L731-737): `oldLines = oldString.split("\n").length`, `searchLines = search.split("\n").length`.
  - True if `searchLines >= max(oldLines+3, oldLines*2)`.
  - Otherwise, if `oldLines === 1`, false.
  - Otherwise true if `search.trim().length > max(oldTrimLen+500, oldTrimLen*4)`.
  - Example: oldString of 3 lines -> refuse when the matched span is >= max(6, 6) = 6 lines.
- Replacers (all split on `\n`). "Yield region" means yield `content.substring(start, end)`, where `start` = sum of `(len(line)+1)` for lines before the match and `end` = start + the line lengths of the block + `(n-1)` newlines, so the last line's `\n` is not included.
  1. **SimpleReplacer** (L244-246): yields `find` unchanged.
  2. **LineTrimmedReplacer** (L248-286): drop a trailing `""` search line. For every window of `n` file lines where `orig[i+j].trim() === search[j].trim()` for all j, yield the region.
  3. **BlockAnchorReplacer** (L288-425):
     - Requires at least 3 search lines (counted before the trailing `""` is dropped). `first = search[0].trim()`, `last = search[n-1].trim()`.
     - Candidates: for each file line i with `trim()==first`, scan j from i+2 forward to the **first** j with `trim()==last`.
       - Post-fix: keep the candidate only if `|(j-i+1) - n| <= max(1, floor(n*0.25))`.
       - **Pre-fix: no size limit.** The block could be arbitrarily longer than `oldString`.
     - Similarity uses only the middle lines: for k=1..min(n,blockSize)-2, `sim_k = 1 - levenshtein(origTrim, searchTrim)/max(len)`. Lines where both are empty are skipped.
       - **Single candidate**: running sum of `sim_k/linesToCheck`, with an early exit once it reaches the threshold.
       - **Multiple candidates**: the plain average of the sims; the best candidate wins.
       - If there are no middle lines, sim = 1.0.
     - **Thresholds: post-fix 0.65 / 0.65. Pre-fix: single candidate 0.0, multiple candidates 0.3.**
       - So pre-fix, a single candidate with matching first and last lines was **always accepted, whatever the middle lines said**.
       - Also pre-fix, nothing capped the block size. Together these are the mechanism by which a small 3-line `oldString` could replace a large region.
     - Yields the region for lines i..j.
  4. **WhitespaceNormalizedReplacer** (L427-469): `norm(s) = s.replace(/\s+/g," ").trim()`.
     - For each line: if `norm(line)==norm(find)`, yield the line. Else, if `norm(line)` includes `norm(find)`, build the regex `words(find).map(escape).join("\\s+")` and yield its first match in the line.
     - Then, if find has more than 1 line, yield every n-line window whose `norm(window.join("\n"))==norm(find)`.
  5. **IndentationFlexibleReplacer** (L471-497): `removeIndentation` strips the minimum leading-whitespace count of the non-blank lines from every non-blank line. Yields every n-line window whose de-indented text equals the de-indented find.
  6. **EscapeNormalizedReplacer** (L499-546): unescape `\n \t \r \' \" \` \\ \<newline> \$` in find. If content includes the unescaped find, yield it. Also yield every window whose unescaped text equals the unescaped find.
  7. **TrimmedBoundaryReplacer** (L562-586): only if `find.trim() !== find`. Yield `find.trim()` if the content contains it. Also yield every n-line window whose `.trim()` equals `find.trim()`.
  8. **ContextAwareReplacer** (L588-644): requires at least 3 lines; a trailing `""` is dropped.
     - First/last anchors are compared trimmed. For each first-anchor line i, the first later j>=i+2 with the last anchor is taken.
     - Accept only if the block has exactly as many lines as find and at least 50% of the non-empty middle lines match exactly after trim (or there are no non-empty middle lines). Yield the block, then stop.
  9. **MultiOccurrenceReplacer** (L548-560): yields `find` once per exact occurrence (lets `replaceAll` work and makes ambiguity visible).
- Effective result for multiple matches: an exact `oldString` that occurs more than once makes SimpleReplacer fail the uniqueness test. Later replacers may then find a *unique* fuzzy candidate and apply it, but the post-fix version applies it only if it is not disproportionate. With no unique candidate anywhere -> "Found multiple matches" error.

Contract, `write` (v1.19.5 write.ts L20-25, L46-64):
- Params `content`, `filePath`. Reads the old text only to build the diff, then asks the `edit` permission and **overwrites the whole file** (BOM kept if the old file or the new content had one). A formatter may run.
- Read-first rule: before 2026-04-17 (`76a14109`), an existing file had to pass `FileTime.assert`. That check threw "You must read file X before overwriting it. Use the Read tool first" if the session had not read the file. It threw "File X has been modified since it was last read" if mtime or size changed. `OPENCODE_DISABLE_FILETIME_CHECK` disabled the check. After that commit there is no read-first check in edit or write.

Placeholders (v1): no detection. Text is written literally. EscapeNormalizedReplacer only affects how `oldString` is matched.

Sources:
- https://github.com/anomalyco/opencode/blob/da8c0211f7c00afbf1dd96e629801fe84d205541/packages/core/src/tool/plugin/edit.ts#L22-L368
- https://github.com/anomalyco/opencode/blob/da8c0211f7c00afbf1dd96e629801fe84d205541/packages/core/src/tool/plugin/write.ts#L14-L71
- https://github.com/anomalyco/opencode/blob/da8c0211f7c00afbf1dd96e629801fe84d205541/packages/core/src/file-write.ts#L83-L101
- https://github.com/anomalyco/opencode/blob/dc2ffcf8bf26f9e669b6aa22b95f50e12be15e06/packages/core/src/tool/plugin/edit.ts (v2.2.6, identical to HEAD)
- https://github.com/anomalyco/opencode/blob/810c0eba1a7348036f8bdf61e6632d0c36c6876c/packages/opencode/src/tool/edit.ts#L47-L737 (v1.19.5)
- https://github.com/anomalyco/opencode/blob/810c0eba1a7348036f8bdf61e6632d0c36c6876c/packages/opencode/src/tool/write.ts#L20-L104
- https://github.com/anomalyco/opencode/blob/604a5f781f75bc090a4db35de47b2bcca5ebf687/packages/opencode/src/tool/edit.ts#L90-L117 (pre-fix empty-oldString overwrite)
- https://github.com/anomalyco/opencode/commit/236cfcbbc31530fde6a9e65318703f40adad8455 (fix: prevent destructive edit matches, #30932)
- https://github.com/anomalyco/opencode/pull/30932
- https://github.com/anomalyco/opencode/commit/76a141090ea33da574d06e17cd1c5dbddbde2952 (delete filetime module, #22999; shows the removed `FileTime.assert` and that the empty-oldString branch skipped it)

Unknown/unverified:
- Which release first shipped the pre-fix overwrite, and the exact first release with the fix. I checked only v1.15.x-v1.19.x tags: v1.16.2 is the first in that range that contains `236cfcbb`. I did not look up the incident report itself.
- When v1 replacer thresholds were first set to 0.0/0.3. Only the values right before the fix were read.
- Whether v2 adds any read-first or staleness rule outside `edit.ts`, `write.ts` and `file-write.ts` (for example in the permission layer). None was seen in those files.
- v2 `patch` tool (`packages/core/src/tool/plugin/patch.ts`) not reviewed.

---

## 2. Gemini CLI (google-gemini/gemini-cli)

Contract, `replace` (edit tool, `EDIT_TOOL_NAME = 'replace'`):
- Params (current): `file_path`, `instruction`, `old_string`, `new_string`, `allow_multiple?`. The legacy schema requires `file_path`, `instruction`, `old_string` and `new_string`. (base-declarations.ts L65-69; default-legacy.ts L349-405; edit.ts L394-430)
- **`expected_replacements` history**: up to v0.30.0 the param was `expected_replacements` (number, default 1). The edit failed unless `occurrences === expected_replacements` exactly. (v0.25.0 edit.ts `getErrorReplaceResult`, the `occurrences !== expectedReplacements` branch.) From v0.31.0 on it is `allow_multiple` (boolean). I checked tags by grepping `edit.ts`: v0.30.0 has `expected_replacements` and no `allow_multiple`; v0.31.0 has the reverse.
- Validation, before execution (L1191-1258):
  - Empty `file_path` -> error.
  - **Omission-placeholder guard**: if `detectOmissionPlaceholders(new_string)` returns any placeholder that is not also in `detectOmissionPlaceholders(old_string)` -> error "`new_string` contains an omission placeholder ... Provide exact literal replacement text." (L1247-1258)
- `calculateEdit` (L685-816) reads the file and records whether it had CRLF. It normalises the content to LF.
  - **`old_string === ""` and file missing** -> new file with content `new_string` (occurrences = 1). (L707-718)
  - File missing and `old_string` non-empty -> error FILE_NOT_FOUND "Use an empty old_string to create a new file." (L721-734)
  - **`old_string === ""` and file exists** -> error ATTEMPT_TO_CREATE_EXISTING_FILE "Attempted to create a file that already exists." No write. (L751-764)
  - Otherwise, run `calculateReplacement` (L306-359). Strategies are tried in order, and the first that returns non-null wins:
    1. **exact** (L142-179):
       - `occurrences = content.split(search).length - 1`.
       - If `!allow_multiple && occurrences > 1`, return the count unchanged, which leads to an error.
       - If `occurrences > 0`, replace **all** occurrences via `safeLiteralReplace` (`replaceAll`, with `$` escaped as `$$` so it stays literal; textUtils.ts L13-28), then `restoreTrailingNewline`.
    2. **flexible** (L181-239):
       - Split the source into lines that keep their `\n`. Compare each search line after `trim()`.
       - Slide a window of n lines. When every `window[k].trim() === search[k].trim()`, count it and replace the window with `applyIndentation(newLines, indentOfFirstWindowLine)` joined by `\n`. Add a `\n` if `new_string !== ''` and the window's last line had one.
       - The splice is in place and the loop continues, so **all** flexible matches are replaced. The occurrence count is then checked.
    3. **regex** (L241-304):
       - Put spaces around each of `( ) : [ ] { } > < =` in `search`, split on whitespace, regex-escape each token, and join with `\s*`. The pattern is `^([ \t]*)` + tokens, flags `gm` for counting.
       - Replace with flag `m` (first only) or `gm` when `allow_multiple`. The replacement is `applyIndentation(newLines, captured indent)`.
       - Note: the pattern has no end anchor, so it matches from a line start through the last token, and anything after the last token on that line is kept.
    4. **fuzzy** (L1430-1568; `ENABLE_FUZZY_MATCH_RECOVERY = true`, `FUZZY_MATCH_THRESHOLD = 0.1`, `WHITESPACE_PENALTY_FACTOR = 0.1`, L71-73):
       - Skip if `old_string.length < 10`, or if `sourceLines * old_string.length^2 > 4e8`.
       - Search lines are `trimEnd()`ed and joined with `\n` (`searchBlock`). Slide a window of N = number of search lines. `windowText` is the window lines `trimEnd()`ed and joined.
       - Skip a window if `|len(windowText) - len(searchBlock)| / len(searchBlock) > 0.1/0.1 = 1.0`.
       - `d_raw = levenshtein(windowText, searchBlock)`; `d_norm = levenshtein(stripAllWhitespace(windowText), stripAllWhitespace(searchBlock))`.
       - `score = (d_norm + 0.1*(d_raw - d_norm)) / len(searchBlock)`. Keep windows with score <= 0.1.
       - Sort by (score, index). Greedily select windows that do not overlap (`|i-j| >= N`).
       - **Every selected window** is replaced (bottom-up) by `applyIndentation(newLines, indentOfWindowFirstLine)`, plus a `\n` if the window's last line had one. occurrences = number selected.
       - Worked example: a 200-char searchBlock tolerates a weighted distance <= 0.1*200 = 20, for example 20 non-whitespace edits, or 200 whitespace-only edits (200*0.1 = 20).
  - `applyIndentation(lines, target)` (L1393-1414):
    - `refIndent` = the leading `[ \t]*` of `lines[0]`.
    - Blank lines become `""`.
    - Lines that start with `refIndent` become `target + rest`.
    - Other lines become `target + trimStart()`.
  - `restoreTrailingNewline` (L120-131) makes the result's trailing-`\n` state match the original file.
  - Errors (`getErrorReplaceResult`, L361-389):
    - occurrences 0 -> EDIT_NO_OCCURRENCE_FOUND.
    - `!allow_multiple && occurrences !== 1` -> EDIT_EXPECTED_OCCURRENCE_MISMATCH "expected 1 occurrence but found N".
    - final old === final new -> EDIT_NO_CHANGE.
- **LLM self-correction** (`attemptSelfCorrection`, L554-677; `FixLLMEditWithInstruction`, llm-edit-fixer.ts L143+). It runs on any of the errors above (including multiple matches), and only when `config.getDisableLLMCorrection()` is false and the extension is not `.json/.ipynb/.jsonc/.json5` (L792-815).
  - **Default: `disableLLMCorrection` = true**, so correction is OFF by default. (config.ts L1149; settingsSchema.ts `tools.disableLLMCorrection` default true)
  - When enabled:
    - Fail fast if `old_string` is empty or whitespace.
    - Re-read the file. If its hash differs, use the on-disk content.
    - Ask an LLM (40 s timeout) for `{search, replace, noChangesRequired, explanation}`.
    - `noChangesRequired` -> error EDIT_NO_CHANGE_LLM_JUDGEMENT.
    - Otherwise rerun the full `calculateReplacement` with the LLM's `search`/`replace`. Accept only if that produces no error. Note that the LLM's `replace` may differ from the model's `new_string`.
- Write (`applyEdit`, L962+): if the original had CRLF, convert every `\r?\n` to `\r\n`; a new file gets CRLF only if `os.EOL` is CRLF. Then write the whole new content.
- Read-before-edit: not enforced in code. The tool description only tells the model to use read_file first (default-legacy.ts L351).

Contract, `write_file`:
- Params `file_path`, `content` (both required). (default-legacy.ts L111-136)
- Validation: **if `detectOmissionPlaceholders(content)` is non-empty -> error** "`content` contains an omission placeholder ... Provide complete file content." (write-file.ts L705-708)
- `getCorrectedFileContent` (L116-225) reads the existing file, if any, for the diff only. For non-JSON files it runs `ensureCorrectFileContent` (editCorrector.ts L32-67):
  - With LLM correction disabled (the default) and `aggressiveUnescape` false (Gemini 2/3 and custom models), the content is unchanged.
  - With `aggressiveUnescape` true (other models), `unescapeStringForGeminiBug` (L140+) rewrites `\\+n`, `\\+t`, `\\+r`, `\\+'`, `\\+"`, `` \\+` ``, `\\+\\` and `\\+<newline>` to the unescaped char.
  - If correction is enabled, an LLM is asked to fix the escaping.
- Then **overwrite the whole file unconditionally** (mkdir -p the parent). CRLF follows the original file's line endings, or `os.EOL` for a new file. (applyWrite L418-478)
- No read-first or stale check in code.

Placeholder detector (omissionPlaceholderDetector.ts L7-105), exact algorithm. For each line:
1. Trim it. Strip a leading `//` and trim again.
2. If the text is wrapped in `( )`, unwrap it and trim.
3. Find the first `...`. `prefix` = the text before it, lower-cased, with whitespace runs collapsed to one space. `suffix` = the text after it.
4. It is a placeholder only if `prefix` is one of {`rest of`, `rest of method`, `rest of methods`, `rest of code`, `unchanged code`, `unchanged method`, `unchanged methods`} and `suffix` is empty or all dots.

As a consequence:
- `// ... existing code ...` (empty prefix) and `// ... rest of the code unchanged ...` (empty prefix) are **NOT detected** and will be written literally.
- `// rest of the code unchanged ...` (prefix `rest of the code unchanged`) is not detected either.
- `// rest of code ...` and `(unchanged methods ...)` are detected.
- `# rest of code ...` is not detected, because only `//` is stripped.

Sources:
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/edit.ts#L71-L430
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/edit.ts#L554-L816
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/edit.ts#L962-L1010
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/edit.ts#L1191-L1260
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/edit.ts#L1385-L1568
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/write-file.ts#L116-L225
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/write-file.ts#L418-L480
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/write-file.ts#L700-L711
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/omissionPlaceholderDetector.ts#L7-L105
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/utils/textUtils.ts#L13-L28
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/utils/editCorrector.ts#L32-L180
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/utils/llm-edit-fixer.ts#L17-L207
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/definitions/base-declarations.ts#L61-L69
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/definitions/model-family-sets/default-legacy.ts#L111-L136
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/tools/definitions/model-family-sets/default-legacy.ts#L349-L410
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/core/src/config/config.ts#L1149
- https://github.com/google-gemini/gemini-cli/blob/62bab5b232c15b925d31e655ce844ab939c882b7/packages/cli/src/config/settingsSchema.ts#L1779-L1789
- https://github.com/google-gemini/gemini-cli/blob/v0.25.0/packages/core/src/tools/edit.ts (expected_replacements era)

Unknown/unverified:
- The default of `disableLLMCorrection` in older releases. Only HEAD was read. In the `expected_replacements` era, correction may have been on by default.
- The fuzzy strategy's arrival date. v0.25.0 has only exact/flexible/regex, and I did not bisect.
- The `gemini-3.ts` model-family schema was only skimmed; it also has `instruction` and `allow_multiple`.
- `ensureCorrectEdit` (the older LLM correction of `old_string`/`new_string` in editCorrector.ts) no longer exists at HEAD. Its old behaviour was not reviewed.

---

## 3. Aider (Aider-AI/aider)

Contract, `diff` format (EditBlockCoder, `edit_format = "diff"`):
- Block grammar (editblock_coder.py L386-396, L439-535):
  - Markers: HEAD `^<{5,9} SEARCH>?\s*$`, DIVIDER `^={5,9}\s*$`, UPDATED `^>{5,9} REPLACE\s*$`. Each is matched against `line.strip()`.
  - SEARCH text runs from HEAD to DIVIDER. REPLACE text runs from DIVIDER to UPDATED or to another DIVIDER.
  - Missing DIVIDER or UPDATED -> ValueError.
- Filename resolution (`find_filename`, L538-600):
  - Look at up to 3 lines before HEAD, moving back only while they are fence lines.
  - Prefer an exact in-chat name, then a basename match, then **`difflib.get_close_matches(cutoff=0.8)` against the chat files**, then any candidate with a `.`, then the first candidate.
  - If no filename is found, reuse the previous block's filename.
  - So an edit can land on a *different* file whose name is similar.
- `do_replace` (L364-383):
  - `strip_quoted_wrapping` removes a leading filename line and surrounding fences, and forces a trailing `\n`.
  - **Empty SEARCH (`not before_text.strip()`)**: if the file does not exist, touch it. Then `new_content = content + after_text`. The REPLACE text is **appended** to the existing file, not overwritten.
  - Otherwise `replace_most_similar_chunk(content, before, after)`.
- `replace_most_similar_chunk` (L157-187):
  - `prep()` adds a trailing `\n` and splits lines with keepends.
  - (a) `perfect_replace` (L146-154): the **first** window of lines equal to the SEARCH lines is replaced. **There is no uniqueness check: with several matches, the first occurrence wins.**
  - (b) `replace_part_with_missing_leading_whitespace` (L243-293):
    - Outdent SEARCH and REPLACE by the minimum leading whitespace over both.
    - Find the first window where every line matches after `lstrip()` and every non-blank line has the same extra prefix.
    - Replace it, with that prefix added to the non-blank REPLACE lines.
  - (c) If SEARCH has more than 2 lines and its first line is blank, retry (a) and (b) without that first line.
  - (d) `try_dotdotdots` (L190-240) handles `...` elision:
    - Split SEARCH and REPLACE on lines matching `^\s*\.\.\.\n`. The two piece counts must be equal, and the `...` lines must match pairwise; otherwise ValueError, which is caught and gives no match.
    - For each (search piece, replace piece): if both are empty, skip. If the search piece is empty and the replace piece is not, **append** the replace piece to the end of the file. Otherwise the search piece must occur **exactly once** (`whole.count`), or ValueError. Replace it once with `str.replace`.
  - `replace_closest_edit_distance` (SequenceMatcher ratio >= 0.8, chunk lengths +/-10%) sits **after an unconditional `return` (L183) and is dead code**. No edit-distance fuzzy matching is active.
- `apply_edits` (L41-124):
  - If the target fails, `if not new_content and original.strip()`, the **same block is tried against every other file in the chat**, and the first file that matches is edited.
  - A result of `""` counts as a failure (falsy), so a block cannot empty a file.
  - Failure -> ValueError listing the failed blocks, plus "Did you mean" lines. The other blocks have already been written.
- Permissions (`base_coder.allowed_to_edit`, base_coder.py L2191-2236):
  - Files in the chat are editable without a prompt.
  - A file not in the chat needs user confirmation. A new file needs "Create new file?" confirmation.
  - Gitignored files are skipped.
  - There is no separate "read first" rule. Being in the chat means the content was sent.

Contract, `whole` format (WholeFileCoder, `edit_format = "whole"`, wholefile_coder.py L22-128):
- Format: the filename on the line before an opening fence, then the full new content, then a closing fence.
- Filename sources, in priority order:
  - "block": the line before the fence. `*`, `:`, `` ` ``, `#` are stripped. A bogus dir prefix is dropped if the basename is in chat.
  - "saw": a backticked chat filename mentioned earlier in the text.
  - "chat": the only file in the chat.
- `apply_edits` writes the joined lines with `io.write_text(full_path, ...)`, a **whole-file overwrite with no content checks** (L124-128).
- Placeholders: **written literally**. The prompt forbids eliding with `...` or "... rest of code ..." (wholefile_prompts.py L57-58), but the code has no detection.

Placeholders in `diff` format: only a line that is exactly `...`, with optional leading whitespace (`^\s*\.\.\.\n`), is special. Comment-style placeholders like `// ... existing code ...` are ordinary text. In REPLACE they are written literally, and in SEARCH they must match literally.

Sources:
- https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/editblock_coder.py#L41-L124
- https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/editblock_coder.py#L127-L383
- https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/editblock_coder.py#L386-L600
- https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/wholefile_coder.py#L22-L144
- https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/wholefile_prompts.py#L42-L58
- https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/base_coder.py#L2191-L2236
- https://github.com/Aider-AI/aider/tree/v0.86.0/aider/coders (release; both coder files identical to HEAD)

Unknown/unverified:
- Whether `io.write_text` performs any atomic write or backup. Not read.
- Other Aider formats (`udiff`, `editor-diff`, `patch`, `architect`) not reviewed.
- When `replace_closest_edit_distance` was disabled. I did not bisect.

---

## 4. Codex CLI (openai/codex) — `apply_patch`

Contract, format (parser.rs L4-25 doc grammar; core/assets/tools/apply_patch.lark):
- `*** Begin Patch` ... `*** End Patch`. An optional `*** Environment ID: <id>` comes first (Rust parser only).
- Hunks: `*** Add File: <path>` followed by `+line` lines; `*** Delete File: <path>`; `*** Update File: <path>`, then an optional `*** Move to: <path>`, then chunks.
- A chunk starts with `@@` or `@@ <context line>`. The first chunk may omit `@@`. Body lines are ` ctx`, `-old`, `+new`. A truly empty line counts as an empty context line. An optional `*** End of File` follows a chunk.
- Parsing is **lenient** (`PARSE_IN_STRICT_MODE = false`):
  - Markers are compared after trim.
  - A heredoc wrapper `<<EOF` / `<<'EOF'` / `<<"EOF"` ... `EOF` (at least 4 lines) is stripped. (parser.rs L37-53, L154-274)
  - Update-hunk lines are `trim_end()`ed when checked for markers.
  - Any other line (no ` `/`+`/`-` prefix) -> InvalidHunkError "Unexpected line found in update hunk" or "Expected update hunk to start with a @@ context marker". (streaming_parser.rs L227-367)
  - An update hunk with no chunks -> "Update file hunk for path ... is empty".
- Each chunk keeps `old_lines` (context + `-`), `new_lines` (context + `+`), `context_line_indices`, `change_context` and `is_end_of_file`. (parser.rs L114-143)

Contract, application (lib.rs `apply_hunks_to_files` L438-690):
- Hunks are applied **sequentially and are not transactional**. An earlier hunk stays written if a later one fails. An empty hunk list -> "No files were modified."
- **Add File**: write `contents` (each `+` line plus `\n`) and create parent dirs. **If the file exists, it is overwritten without error.** The old content is recorded only for the delta. (L473-500)
- **Delete File**: refuse a directory, then remove the file. (L501-560)
- **Update File**: read the file, compute the replacements, then write the full new contents. With `Move to`, write the new contents to the destination (overwriting it if it exists) and remove the source. (L561-684)
- `compute_replacements` (file_update.rs L60-166), starting with `line_index = 0` and taking chunks in order:
  - If `change_context` is set: `seek_sequence([ctx], from line_index)`. If not found -> error "Failed to find context". Else `line_index = idx+1`.
  - **`old_lines` empty (a pure-addition chunk)**: insert `new_lines` at **end of file**, `(original_lines.len(), 0, new_lines)`, **regardless of `@@` context**. (L86-89)
  - Else `seek_sequence(old_lines, from line_index, eof=is_end_of_file)`. If that fails and `old_lines` ends with `""`, retry without the trailing `""` (and drop a trailing `""` from `new_lines` too).
  - Not found -> error "Failed to find expected lines in <path>". Found at `start` -> context lines are kept byte-for-byte, and the non-context runs are replaced. `line_index = start + pattern.len()`.
  - **Multiple matches: no ambiguity check. The first match at or after `line_index` wins.**
- `seek_sequence(lines, pattern, start, eof)` (seek_sequence.rs L12-110):
  - Empty pattern -> `Some(start)`.
  - `pattern.len() > lines.len()` -> None.
  - If `eof`, start the search at `max(start, len-plen)`.
  - Passes, each over i in `[search_start, len-plen]`, first hit returns:
    1. exact equality;
    2. `trim_end` equality per line;
    3. `trim` equality per line;
    4. `trim` plus unicode normalisation: `‐ ‑ ‒ – — ― −` to `-`; `‘ ’ ‚ ‛` to `'`; `“ ” „ ‟` to `"`; NBSP, U+2002-200A, U+202F, U+205F, U+3000 to a space.
  - All passes compare the same number of lines (`pattern.len()`), so the matched region is never larger than the patch's old lines. Note: with `eof=true`, the fallback to searching from `start` that the doc comment describes is not implemented. Only `search_start` is used.
- Line endings (text_file.rs L30-121):
  - The file is split keeping each line's ending (LF/CRLF/CR). The preferred ending is the first one seen, or LF.
  - Unchanged lines keep their ending, and inserted lines use the preferred ending.
  - **Every line ends up with an ending, so a trailing newline is always added after an update.**
- Placeholders: there is no expansion.
  - A placeholder line written as `+// ... existing code ...` is **written literally**.
  - As ` // ... existing code ...` (context) it must match a real file line, so the hunk fails.
  - With no prefix it is a parse error.
  - In `*** Add File`, lines must start with `+`.

Sources:
- https://github.com/openai/codex/blob/748ab55ca7de0b647d9a7a9d9a8e70e00f28666d/codex-rs/apply-patch/src/parser.rs#L1-L274
- https://github.com/openai/codex/blob/748ab55ca7de0b647d9a7a9d9a8e70e00f28666d/codex-rs/apply-patch/src/streaming_parser.rs#L227-L367
- https://github.com/openai/codex/blob/748ab55ca7de0b647d9a7a9d9a8e70e00f28666d/codex-rs/apply-patch/src/file_update.rs#L25-L166
- https://github.com/openai/codex/blob/748ab55ca7de0b647d9a7a9d9a8e70e00f28666d/codex-rs/apply-patch/src/seek_sequence.rs#L1-L110
- https://github.com/openai/codex/blob/748ab55ca7de0b647d9a7a9d9a8e70e00f28666d/codex-rs/apply-patch/src/text_file.rs#L30-L121
- https://github.com/openai/codex/blob/748ab55ca7de0b647d9a7a9d9a8e70e00f28666d/codex-rs/apply-patch/src/lib.rs#L438-L690
- https://github.com/openai/codex/blob/748ab55ca7de0b647d9a7a9d9a8e70e00f28666d/codex-rs/core/assets/tools/apply_patch.lark
- https://github.com/openai/codex/blob/748ab55ca7de0b647d9a7a9d9a8e70e00f28666d/codex-rs/core/src/tools/handlers/apply_patch_spec.rs

Unknown/unverified:
- Whether the core tool layer (`core/src/apply_patch.rs`, `tools/runtimes/apply_patch.rs`) adds approval or safety checks, such as refusing an Add File over an existing file. Not read.
- The model-facing prose instructions for apply_patch (prompt files) were not located at this commit.
- Codex has no separate whole-file write tool in this crate. Whole-file writes happen via Add File, or via shell commands.

---

## 5. Cline (cline/cline)

Cline has two contracts. The **v3 line** (through v3.89.2) has `replace_in_file` and `write_to_file`. The **v4 SDK** (v4.0.0 onwards, current v4.1.26) replaces them with `editor` and `apply_patch`. Its docs say: "Some older docs/examples reference XML-style names like `read_file`, `replace_in_file` ... Current SDK/ClineCore runtime uses the built-in tool names listed above".

### 5a. v3 `replace_in_file` / `write_to_file` (v3.89.2)

Contract, `replace_in_file`:
- Params `path`, `diff` (one or more SEARCH/REPLACE blocks). The handler is shared with `write_to_file` (WriteToFileToolHandler.ts L27, L37-42). `applyModelContentFixes` runs on the diff first. (L490-493)
- Markers (diff.ts L1-39):
  - SEARCH start `^[-]{3,} SEARCH>?$` or legacy `^[<]{3,} SEARCH>?$`.
  - Divider `^[=]{3,}$`.
  - REPLACE end `^[+]{3,} REPLACE>?$` or legacy `^[>]{3,} REPLACE>?$`.
  - A last line that looks like a partial marker is dropped.
- `constructNewFileContentV1` (the default version, `constructNewFileContent(..., version="v1")`, L245-491):
  - SEARCH and REPLACE content are built as `line + "\n"` for each line.
  - **Empty SEARCH**: if the original file is empty, insert at 0. **If the file is non-empty -> throw** "Empty SEARCH block detected with non-empty file. This usually indicates a malformed SEARCH marker." (L324-337)
    - The function's doc comment (L213-217) still says an empty SEARCH on a non-empty file is "a complete file replacement". That is stale for v3.89.2.
    - **In v3.0.0 the code did exactly that**: `searchMatchIndex = 0; searchEndIndex = originalContent.length`, so the whole file was replaced by the REPLACE content (v3.0.0 diff.ts L171-181).
  - Non-empty SEARCH, in order:
    1. exact `originalContent.indexOf(search, lastProcessedIndex)`;
    2. `lineTrimmedFallbackMatch`;
    3. `blockAnchorFallbackMatch`;
    4. exact `indexOf(search, 0)` over the whole file. This allows out-of-order blocks.
    - If all fail -> throw "...does not match anything in the file."
  - **Multiple matches: no uniqueness check. The first match at or after the end of the previous block wins.**
  - `lineTrimmedFallbackMatch` (L51-103):
    - Drop a trailing `""` search line.
    - Starting from the line containing `lastProcessedIndex`, take the first window where every `orig.trim()===search.trim()`.
    - The region ends **after** the last line's `\n` (+1 per line).
  - `blockAnchorFallbackMatch` (L132-185):
    - Requires at least 3 search lines (counted before the trailing `""` is dropped).
    - Take the first i at or after the start line where `orig[i].trim()===search[0].trim()` and `orig[i+n-1].trim()===search[n-1].trim()`.
    - **Middle lines are not compared at all.** The region has the same line count as SEARCH, but the replaced middle content can be completely different from what the model wrote.
  - The final result applies all replacements sorted by start (L468-485). With `isFinal`, a block missing its REPLACE end marker is still applied (L441-465).
- Failure -> diff_error, the diff view reverts, and the file is unchanged. (WriteToFileToolHandler.ts L509-557)

Contract, `write_to_file`:
- Params `path`, `content`. `content == null` -> error. An empty string is valid. (L126-143, L559-561)
- Preprocessing:
  - If the content starts with a fence line (```` ``` ````), drop the first line and trim.
  - If it ends with ```` ``` ````, drop the last line and trim.
  - Then run `applyModelContentFixes`. (L563-573)
- **The whole file is replaced** through the diff view and saved after user approval or auto-approve. No read-first check was found in the handler.
- Placeholders: no detection. Text is written literally.

### 5b. v4 SDK `editor` (current)

- Params `path`, `old_text?` (nullable), `new_text`, `insert_line?` (1-based). (schemas.ts L198-232; definitions.ts L719-760)
- With `insert_line`: split the file on `\r\n|\n`, insert the lines of `new_text` before that line (1..len+1), and join with the file's EOL. (editor.ts L194-216, L237-244)
- **File does not exist** -> create it with `new_text`; `old_text` is ignored. (L246-248, L141-151)
- File exists and `old_text` is null or omitted -> error "already exists, but `old_text` was ...". (L249-258)
- **`old_text === ""` on an existing file**: `countOccurrences` returns 0 for an empty needle, so the result is the error "No replacement performed: text not found". (L67-70, L175-177)
- `old_text` and `new_text` are first normalised to the file's line endings. Then: 0 matches -> error; **more than 1 match -> error** "multiple occurrences"; exactly 1 -> literal replace (function replacer, so `$` stays literal). (L162-192)
- No fuzzy matching. No whole-file overwrite of an existing file through `editor`.
- `apply_patch` (SDK) exists, offered by default to GPT/Codex/openai-native models. It reports a "fuzz factor" and has a "File already exists" guard for Add File. (apply-patch.ts L231, L409-422) Its matching algorithm was not reviewed.

Sources:
- https://github.com/cline/cline/blob/e1bdeeff68e95734901c7a4b3a31753bae54a634/apps/vscode/src/core/assistant-message/diff.ts#L1-L491
- https://github.com/cline/cline/blob/e1bdeeff68e95734901c7a4b3a31753bae54a634/apps/vscode/src/core/task/tools/handlers/WriteToFileToolHandler.ts#L27-L143
- https://github.com/cline/cline/blob/e1bdeeff68e95734901c7a4b3a31753bae54a634/apps/vscode/src/core/task/tools/handlers/WriteToFileToolHandler.ts#L436-L580
- https://github.com/cline/cline/blob/v3.0.0/src/core/assistant-message/diff.ts#L171-L181 (old empty-SEARCH = full-file replace)
- https://github.com/cline/cline/blob/94eecbbe1a2f899c66b118d13656651b0a884e1f/sdk/packages/core/src/extensions/tools/executors/editor.ts#L67-L268
- https://github.com/cline/cline/blob/94eecbbe1a2f899c66b118d13656651b0a884e1f/sdk/packages/core/src/extensions/tools/schemas.ts#L198-L232
- https://github.com/cline/cline/blob/94eecbbe1a2f899c66b118d13656651b0a884e1f/sdk/packages/core/src/extensions/tools/definitions.ts#L619-L760
- https://github.com/cline/cline/blob/94eecbbe1a2f899c66b118d13656651b0a884e1f/sdk/packages/core/src/extensions/tools/executors/apply-patch.ts
- https://github.com/cline/cline/blob/94eecbbe1a2f899c66b118d13656651b0a884e1f/docs/tools-reference/all-cline-tools.mdx#L19-L77
- https://github.com/cline/cline/blob/94eecbbe1a2f899c66b118d13656651b0a884e1f/apps/vscode/src/sdk/message-translator.ts#L684-L760

Unknown/unverified:
- The exact release where empty SEARCH on a non-empty file changed from full replacement to an error. It lies between v3.0.0 and v3.89.2, and I did not bisect.
- Behaviour of `constructNewFileContentV2` (diff.ts L499-855), and whether any v3 config selected v2. Only the default V1 was traced.
- What `applyModelContentFixes` changes, beyond the comments about HTML entities and escape characters.
- The v4 SDK `apply_patch` matching and fuzz algorithm (apply-patch-parser.ts) was not read.

---

## 6. Claude Code (Anthropic, closed source — docs only)

Contract (from docs):
- Tool input fields (hooks reference):
  - **Write**: `file_path` (absolute), `content`. "Creates or overwrites a file."
  - **Edit**: `file_path`, `old_string`, `new_string`, `replace_all` (boolean, default false). "Replaces a string in an existing file."
- **Edit**:
  - "performs exact string replacement ... It doesn't use regex or fuzzy matching."
  - **Match**: `old_string` must appear exactly as written. One character of whitespace difference is a miss.
  - **Uniqueness**: `old_string` must appear exactly once, unless `replace_all: true` replaces them all.
- **Read-before-edit**:
  - Required for Claude Opus 4.6, Haiku 4.5 and older models.
  - Newer models may edit an unread file when reading it would need no permission prompt and the Read tool is available.
  - A `PARTIAL view` read doesn't count.
  - A file that changed on disk since the last read can still be edited if `old_string` matches the current content exactly and unambiguously.
  - Single-file `cat`/`head`/`tail`/`sed -n`/`grep`/`rg` etc. with no pipes also count as a read.
- **Write**:
  - Creates a file or overwrites an existing one with the full content provided. It "doesn't append or merge."
  - Read-before-overwrite: required for Opus 4.6, Haiku 4.5 and older models, so a Write to an unread existing file fails. Newer models follow the same conditions as read-before-edit. Notebooks and partially-read files always require the read.
  - Not required for new files.
  - Before v2.1.228, every model required the read.
- Non-UTF-8:
  - Edit refuses files that are not valid UTF-8, unless the file starts with a UTF-16LE BOM.
  - Write can still replace such a file, unless the new content contains U+FFFD. It saves as UTF-8.
- Anthropic API text editor tool (`text_editor_20250728`, `str_replace_based_edit_tool`): commands `view`, `str_replace` (`path`, `old_str`, `new_str`), `create` (`path`, `file_text`), `insert`.
  - This tool is **implemented by the client application**. The docs only *recommend* "exactly one match" and give example errors for 0 and multiple matches. It is not Claude Code's implementation and sets no contract for Claude Code.

Sources:
- https://code.claude.com/docs/en/tools-reference (sections "Edit tool behavior", "Non-UTF-8 files", "Write tool behavior", "Read tool behavior"; fetched as `/docs/en/tools-reference.md`)
- https://code.claude.com/docs/en/hooks (tool input tables "Write" and "Edit")
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool (redirected from docs.claude.com; sections "str_replace", "create", "Handle errors")

Unknown/unverified:
- **What Edit does with `old_string === ""`.** The docs do not say whether it errors, creates a file, or overwrites.
- Behaviour when `old_string === new_string`.
- **MultiEdit**: not listed in the current tools reference or hooks tool tables, so its existence and semantics are unverified. Treat it as removed or undocumented.
- Line-ending, trailing-newline and BOM handling, and whether matching normalises CRLF (Edit) or quote styles.
- Whether Write is atomic.

---

## Summary table

| Tool | Empty old string | Multiple matches | Fuzzy matching | Placeholders written literally? |
|---|---|---|---|---|
| OpenCode v2 `edit` (current) | Error, always | Error unless `replaceAll` | Unicode quote/dash/space map, then per-line trailing-whitespace; never grows the span | Yes |
| OpenCode v1 `edit`, before 2026-06-05 fix | **Overwrites whole existing file with `newString`** (and pre-2026-04-17 skipped the read check) | Falls through 9 replacers; error only if none yields a unique hit | Yes: trimmed lines, block-anchor (pre-fix threshold 0.0 single / 0.3 multi, no size cap), whitespace-normalised, indent-flexible, escape-normalised, trimmed-boundary, context-aware | Yes |
| OpenCode v1 `edit`, after fix (v1.16.2+ … v1.19.5) | Error if file exists; creates file if missing | Same chain; error if no unique hit; disproportionate-span guard | Same chain, block-anchor 0.65 and +/-25% size | Yes |
| Gemini CLI `replace` | Error if file exists (ATTEMPT_TO_CREATE_EXISTING_FILE); creates if missing | Error unless `allow_multiple` (formerly count must equal `expected_replacements`); exact/flexible/fuzzy then replace all | Yes: trimmed-line, token regex, Levenshtein fuzzy (<=10% weighted); optional LLM fixer (off by default) | Narrow guard rejects `rest of … ...`/`unchanged code ...` forms; `// ... existing code ...` passes and is written |
| Gemini CLI `write_file` | n/a (overwrites) | n/a | n/a (optional unescape / LLM escape fix) | Same narrow guard on `content` |
| Aider `diff` | **Appends** REPLACE to file (creates if missing) | **First occurrence replaced**, no check (the `...` path requires uniqueness) | Leading-whitespace offset, drop a leading blank line, `...` elision; edit-distance code is dead; filename fuzzy (difflib 0.8) and fallback to other chat files | Yes, except a bare `...` line, which is elision |
| Aider `whole` | n/a (always full overwrite) | n/a | n/a | Yes |
| Codex `apply_patch` | Pure-addition chunk (no `-`/context) **appends at EOF**; Add File overwrites existing file | **First match after cursor**, no check | Exact, then rstrip, then trim, then trim + unicode punctuation; same line count | Yes if `+`; context placeholder fails; bare line is parse error |
| Cline v3 `replace_in_file` (v3.89.2) | Error on non-empty file (**v3.0.0: whole-file replacement**) | **First match after previous block**, no check | Line-trimmed; block-anchor on first/last line only with **no middle-line check**; whole-file exact fallback | Yes |
| Cline v3 `write_to_file` | n/a (full overwrite; strips wrapping ``` fences) | n/a | n/a | Yes |
| Cline v4 `editor` (current) | Error ("text not found") on existing file; missing file is created from `new_text` | Error | None | Yes |
| Claude Code Edit/Write | **Unknown (not documented)** | Error unless `replace_all` (docs) | None (docs: "doesn't use regex or fuzzy matching") | Unknown (not documented) |
