"""Tests: each documented behaviour in EDIT_CONTRACTS.md that the harness relies on. Run: python3 test_edit_tools.py"""
import os
import tempfile
import unittest

from edit_tools import (ToolError, Unsupported, aider_diff, claude_edit, cline_v3, codex_apply_patch,
                        gemini_replace, opencode_v1, opencode_v2)

FILE = "def a():\n    return 1\n\ndef b():\n    x = 2\n    y = 3\n    z = 4\n    return x\n\ndef c():\n    return 3\n"


class OpenCode(unittest.TestCase):
    def test_prefix_empty_old_overwrites_whole_file(self):
        self.assertEqual(opencode_v1(FILE, "", "NEW\n", False, True, prefix=True), "NEW\n")

    def test_postfix_empty_old_errors_on_existing_file(self):
        with self.assertRaises(ToolError):
            opencode_v1(FILE, "", "NEW\n", False, True, prefix=False)

    def test_prefix_block_anchor_replaces_large_region(self):
        # First and last lines match "def a():" and "return 3" far apart; the middle line does not match at all.
        old = "def a():\n    something else\n    return 3"
        out = opencode_v1(FILE, old, "def a():\n    return 9", False, True, prefix=True)
        self.assertNotIn("def b", out)
        self.assertNotIn("def c", out)

    def test_postfix_block_anchor_respects_size(self):
        old = "def a():\n    something else\n    return 3"
        with self.assertRaises((ToolError, Unsupported)):
            opencode_v1(FILE, old, "x", False, True, prefix=False)

    def test_exact_unique_replace(self):
        self.assertIn("y = 30", opencode_v1(FILE, "y = 3", "y = 30", False, True, prefix=True))

    def test_v2_empty_old_errors(self):
        with self.assertRaises(ToolError):
            opencode_v2(FILE, "", "x", False, True)


class Others(unittest.TestCase):
    def test_claude_edit_requires_unique(self):
        with self.assertRaises(ToolError):
            claude_edit(FILE, "return", "ret", False, True)

    def test_gemini_empty_old_on_existing_file_errors(self):
        with self.assertRaises(ToolError):
            gemini_replace(FILE, "", "x", False, True)

    def test_aider_empty_search_appends(self):
        self.assertEqual(aider_diff(FILE, "", "NEW\n", True), FILE + "NEW\n")

    def test_aider_first_occurrence_without_uniqueness(self):
        out = aider_diff(FILE, "return", "RET", True)
        self.assertEqual(out.count("RET"), 1)
        self.assertTrue(out.startswith("def a():\n    RET 1"))

    def test_cline_v300_empty_search_replaces_whole_file(self):
        self.assertEqual(cline_v3(FILE, [("", "NEW\n")], v300=True), "NEW\n")

    def test_cline_v3_empty_search_errors(self):
        with self.assertRaises(ToolError):
            cline_v3(FILE, [("", "NEW\n")], v300=False)

    def test_cline_block_anchor_ignores_middle_lines(self):
        search = "def b():\n    totally\n    different\n    middle\n    return x\n"
        out = cline_v3(FILE, [(search, "def b():\n    return 0\n")], v300=False)
        self.assertNotIn("y = 3", out)

    def test_codex_add_file_overwrites(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "f.py")
        open(p, "w").write(FILE)
        store = {}
        codex_apply_patch("*** Begin Patch\n*** Add File: %s\n+print(1)\n*** End Patch" % p,
                          lambda q: open(q).read(), lambda q, t: store.__setitem__(q, t), os.remove)
        self.assertEqual(store[p], "print(1)\n")

    def test_codex_update_first_match(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "f.py")
        open(p, "w").write(FILE)
        store = {}
        codex_apply_patch("*** Begin Patch\n*** Update File: %s\n@@\n-    return 3\n+    return 30\n*** End Patch" % p,
                          lambda q: open(q).read(), lambda q, t: store.__setitem__(q, t), os.remove)
        self.assertIn("return 30", store[p])
        self.assertIn("def b", store[p])


if __name__ == "__main__":
    unittest.main()
