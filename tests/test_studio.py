import unittest
from pathlib import Path

from openswift.studio import sketch

ROOT = Path(__file__).resolve().parents[1]


class StudioTest(unittest.TestCase):
    def test_hello_sketch_has_a_phone_and_a_problem_list(self) -> None:
        source = (ROOT / "examples" / "hello.swift").read_text(encoding="utf-8")
        data = sketch(source)
        self.assertTrue(data["ok"])
        self.assertIn("<svg", data["svg"])
        self.assertEqual(data["tree"]["kind"], "VStack")
        self.assertIsInstance(data["problems"], list)


if __name__ == "__main__":
    unittest.main()
