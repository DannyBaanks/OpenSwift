import unittest
from pathlib import Path

from openswift.parse import parse_swiftui
from openswift.render import render_svg

ROOT = Path(__file__).resolve().parents[1]


class PreviewTest(unittest.TestCase):
    def test_hello_mentions_the_title(self) -> None:
        source = (ROOT / "examples" / "hello.swift").read_text(encoding="utf-8")
        svg = render_svg(parse_swiftui(source))
        self.assertIn("opencode", svg)
        self.assertIn("connect", svg)
        self.assertIn("<svg", svg)
        self.assertIn("not compiled Swift", svg)

    def test_unknown_view_is_labeled(self) -> None:
        svg = render_svg(parse_swiftui("var body: some View { Gauge(value: 1) }"))
        self.assertIn("Gauge", svg)


if __name__ == "__main__":
    unittest.main()
