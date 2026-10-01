import tempfile
import json
import unittest
from pathlib import Path

from openswift.session import focus, render_session, status_text

ROOT = Path(__file__).resolve().parents[1]


class SessionTest(unittest.TestCase):
    def test_focus_then_two_iterations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            target = ROOT / "examples" / "hello.swift"
            focus(target, ["Theme.swift"], "less cramped", "approximate-web", cwd)
            record = json.loads((cwd / ".ui-session" / "target.json").read_text(encoding="utf-8"))
            self.assertEqual(record["writable_paths"][0], str(target.resolve()))
            self.assertEqual(record["writable_paths"][1], str((target.parent / "Theme.swift").resolve()))
            first = render_session(cwd)
            second = render_session(cwd)
            self.assertTrue(first.name == "001.png")
            self.assertTrue(second.name == "002.png")
            text = status_text(cwd)
            self.assertIn("hello.swift", text)
            self.assertIn("Theme.swift", text)
            self.assertIn("iteration: 2", text)
            self.assertTrue((cwd / ".ui-session" / "preview.sha256").read_text(encoding="utf-8").strip())

    def test_miniswift_is_named_not_wired(self) -> None:
        with self.assertRaises(ValueError):
            focus(ROOT / "examples" / "hello.swift", [], "x", "miniswift")


if __name__ == "__main__":
    unittest.main()
