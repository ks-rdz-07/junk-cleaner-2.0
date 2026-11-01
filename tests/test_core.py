import os
import shutil
import tempfile
import threading
import unittest

from junkcleaner import cleaner, scanner
from junkcleaner.domain import MB, ScanOptions, classify, fmt_size
from junkcleaner.platform_os import PROTECTED, is_protected


class Rules(unittest.TestCase):
    def test_classify(self):
        cases = {("Thumbs.db", 10): "System junk", ("a.TMP", 10): "Temp files", ("~$report.docx", 10): "Temp files",
                 ("app.log.3", 10): "Logs & dumps", ("x.bak", 10): "Backups & leftovers",
                 ("notes.txt~", 10): "Backups & leftovers", ("x.txt", 0): "Empty files",
                 ("__init__.py", 0): None, (".gitkeep", 0): None, ("notes.txt", 10): None,
                 ("movie.mkv", 600 * MB): "Large files"}
        for (name, size), want in cases.items():
            self.assertEqual(classify(name, size, 500 * MB), want, name)

    def test_fmt_size(self):
        self.assertEqual(fmt_size(512), "512 B")
        self.assertEqual(fmt_size(1536), "1.5 KB")

    def test_protected(self):
        self.assertTrue(is_protected(PROTECTED[0]))
        self.assertTrue(is_protected(os.path.join(PROTECTED[0], "sub")))
        self.assertFalse(is_protected(tempfile.gettempdir()))


class ScanAndClean(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.old, self.new, self.keep = (os.path.join(self.dir, n) for n in ("old.tmp", "new.log", "keep.txt"))
        for p in (self.old, self.new, self.keep):
            with open(p, "w") as fh:
                fh.write("x")
        os.utime(self.old, (0, 0))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _scan(self, skip_recent=True):
        found = []
        scanner.scan(ScanOptions(False, (self.dir,), 500 * MB, skip_recent), threading.Event(), found.extend)
        return found

    def test_scan_is_read_only_and_finds_junk(self):
        self.assertEqual([i.path for i in self._scan()], [self.old])  # fresh .log skipped, .txt not junk
        self.assertTrue(all(os.path.exists(p) for p in (self.old, self.new, self.keep)))
        self.assertEqual(sorted(i.path for i in self._scan(skip_recent=False)), sorted([self.old, self.new]))

    def test_clean_removes_only_given_items(self):
        result = cleaner.clean(self._scan(), use_trash=False)
        self.assertEqual((len(result.done), result.errors, result.freed), (1, [], 1))
        self.assertFalse(os.path.exists(self.old))
        self.assertTrue(os.path.exists(self.new) and os.path.exists(self.keep))

    def test_clean_reports_missing_file(self):
        items = self._scan()
        os.remove(self.old)
        result = cleaner.clean(items, use_trash=False)
        self.assertEqual(len(result.errors), 1)


class Worktrees(unittest.TestCase):
    def test_find_and_remove_worktree(self):
        root = tempfile.mkdtemp()
        try:
            wt = os.path.join(root, "repo", ".claude", "worktrees", "agent-1")
            os.makedirs(os.path.join(wt, "src"))
            os.makedirs(os.path.join(root, "other", "worktrees", "not-claude"))
            with open(os.path.join(wt, "src", "a.py"), "w") as fh:
                fh.write("abc")
            self.assertEqual(list(scanner.find_worktrees([root], threading.Event())), [wt])
            self.assertEqual(scanner._tree_stats(wt, threading.Event())[0], 3)
            item = scanner.JunkItem(wt, 3, 0, "Agent worktrees")
            self.assertEqual(cleaner.clean([item], use_trash=False).errors, [])
            self.assertFalse(os.path.exists(wt))
        finally:
            shutil.rmtree(root, ignore_errors=True)


class SecurityParsers(unittest.TestCase):
    def test_winget_table(self):
        from junkcleaner.security import parse_winget_table
        out = ("\r   - \rName        Id          Version Available Source\n"
               "---------------------------------------------------\n"
               "Git         Git.Git     2.55.0  2.56.0    winget\n"
               "Some App…   Vendor.App  1.0     1.1       winget\n"
               "2 upgrades available.\n")
        rows = parse_winget_table(out)
        self.assertEqual([r["id"] for r in rows], ["Git.Git", "Vendor.App"])
        self.assertEqual((rows[0]["version"], rows[0]["available"], rows[0]["source"]), ("2.55.0", "2.56.0", "winget"))
        self.assertEqual(parse_winget_table("No installed package found."), [])

    def test_winget_progress(self):
        from junkcleaner.security import is_busy_failure, parse_winget_progress, summary_line
        self.assertEqual(parse_winget_progress("  ██████▒▒▒▒  120 MB / 240 MB"), (50, "Downloading 120 MB / 240 MB"))
        self.assertEqual(parse_winget_progress("   45%"), (45, None))
        self.assertEqual(parse_winget_progress("Successfully verified installer hash")[1], "Installing…")
        self.assertEqual(parse_winget_progress("Found Git [Git.Git] Version 2.56.0"), (None, None))
        self.assertEqual(summary_line(["Found Git", "██▒ 1 MB / 2 MB", "-", "Successfully installed", "100%"], 0),
                         "Successfully installed")
        self.assertEqual(summary_line([], 3), "exit code 3")
        self.assertTrue(is_busy_failure("another installation is in progress"))

    def test_msert_log(self):
        from junkcleaner.security import parse_msert_log
        log = ("Microsoft Safety Scanner v1.0, (build 1.1)\nQuick Scan Results:\n-------------------\n"
               "Threat Detected: Trojan:Win32/Test and Removed!\nAction: Remove, Result: 0x00000000\n"
               "    file://C:\\bad\\x.exe SigSeq: 0x1\n\nResults Summary:\n----------------\n"
               "Found Trojan:Win32/Test, Removed!\nMicrosoft Safety Scanner Finished On Mon\n")
        threats, files, summary = parse_msert_log("old run\n" + log)
        self.assertEqual(threats, ["Trojan:Win32/Test and Removed!"])
        self.assertEqual(files, ["C:\\bad\\x.exe"])
        self.assertEqual(summary, ["Found Trojan:Win32/Test, Removed!"])


class QuarantineAndHistory(unittest.TestCase):
    def setUp(self):
        from junkcleaner import history, quarantine
        self.h, self.q = history, quarantine
        self.dir = tempfile.mkdtemp()
        self._old = (quarantine.ROOT, history.PATH)
        quarantine.ROOT = os.path.join(self.dir, "q")
        history.PATH = os.path.join(self.dir, "h.jsonl")

    def tearDown(self):
        self.q.ROOT, self.h.PATH = self._old
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_quarantine_restore_delete(self):
        a, b = os.path.join(self.dir, "a.tmp"), os.path.join(self.dir, "b.tmp")
        for p in (a, b):
            with open(p, "w") as fh:
                fh.write("xy")
        items = [scanner.JunkItem(p, 2, 0, "Temp files", True) for p in (a, b)]
        self.assertEqual(cleaner.clean(items, False, to_quarantine=True).errors, [])
        self.assertFalse(os.path.exists(a) or os.path.exists(b))
        ids = {os.path.basename(e["original"]): e["id"] for e in self.q.entries()}
        self.assertEqual(self.q.restore([ids["a.tmp"]]), {})
        self.assertTrue(os.path.exists(a))
        with open(b, "w") as fh:  # name taken again: restore must refuse, not overwrite
            fh.write("new")
        self.assertIn(ids["b.tmp"], self.q.restore([ids["b.tmp"]]))
        self.assertEqual(self.q.delete([ids["b.tmp"]]), {})
        with open(b) as fh:
            self.assertEqual(fh.read(), "new")
        self.assertEqual(sorted(e["status"] for e in self.q.entries()), ["Deleted", "Restored"])  # history kept

    def test_purge_expired(self):
        p = os.path.join(self.dir, "old.tmp")
        open(p, "w").close()
        self.q.add([scanner.JunkItem(p, 0, 0, "Temp files")])
        self.assertEqual(self.q.purge_expired(days=1), 0)
        self.assertEqual(self.q.purge_expired(days=-1), 1)
        self.assertEqual(self.q.entries()[0]["status"], "Deleted")

    def test_history(self):
        self.assertEqual(self.h.load(), [])
        self.h.log("Scan", "first", items=1)
        self.h.log("Clean", "second", bytes=5)
        with open(self.h.PATH, "a") as fh:
            fh.write('{"torn')
        self.assertEqual([e["summary"] for e in self.h.load()], ["second", "first"])
        self.h.clear()
        self.assertEqual(self.h.load(), [])

    def test_av_state(self):
        from junkcleaner.security import decode_av_state
        self.assertEqual(decode_av_state(0x061100), (True, True))
        self.assertEqual(decode_av_state(0x060100), (False, True))
        self.assertEqual(decode_av_state(0x061110), (True, False))


class ContributorsImage(unittest.TestCase):
    def test_svg_layout_and_escaping(self):
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".github", "scripts",
                            "contributors_svg.py")
        spec = importlib.util.spec_from_file_location("contributors_svg", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out = mod.svg([{"login": f"user{i}", "avatar": b"png"} for i in range(9)] + [{"login": "<x>", "avatar": b""}])
        self.assertIn('width="736"', out)        # 8 per row
        self.assertEqual(out.count("<image"), 10)
        self.assertIn("&lt;x&gt;", out)          # usernames are escaped
        self.assertNotIn("<x>", out)


if __name__ == "__main__":
    unittest.main()
