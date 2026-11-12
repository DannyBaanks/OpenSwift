import unittest
from pathlib import Path

from openswift.studio import highlight, sketch

ROOT = Path(__file__).resolve().parents[1]


class StudioTest(unittest.TestCase):
    def test_hello_sketch_has_a_phone_and_a_problem_list(self) -> None:
        source = (ROOT / "examples" / "hello.swift").read_text(encoding="utf-8")
        data = sketch(source)
        self.assertTrue(data["ok"])
        self.assertIn("<svg", data["svg"])
        self.assertEqual(data["tree"]["kind"], "VStack")
        self.assertIsInstance(data["problems"], list)

    @unittest.skipUnless((ROOT / "bin" / "openswift-lex").is_file(), "lexer not built (tools/build-lex.sh)")
    def test_highlight_uses_the_optional_lexer(self) -> None:
        source = (ROOT / "examples" / "hello.swift").read_text(encoding="utf-8")
        kinds = {tok["type"] for tok in highlight(source)}
        self.assertIn("keyword", kinds)
        self.assertIn("string_lit", kinds)

    def test_highlight_is_empty_without_the_lexer(self) -> None:
        if (ROOT / "bin" / "openswift-lex").is_file():
            self.skipTest("lexer present")
        self.assertEqual(highlight("let x = 1"), [])


if __name__ == "__main__":
    unittest.main()
