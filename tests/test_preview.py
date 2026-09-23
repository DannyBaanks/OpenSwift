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

    def test_swiftui_body_is_the_screen(self) -> None:
        source = '''
        import SwiftUI
        struct ContentView: View {
            @State private var count = 0
            var body: some View {
                VStack(spacing: 24) {
                    Text("MiniSwift")
                    Button("Increment") { count += 1 }
                }
            }
        }
        '''
        node = parse_swiftui(source)
        self.assertEqual(node.kind, "VStack")
        svg = render_svg(node)
        self.assertIn("MiniSwift", svg)
        self.assertIn("Increment", svg)

    def test_file_without_a_view_still_draws(self) -> None:
        node = parse_swiftui("let answer = 42\n")
        svg = render_svg(node)
        self.assertIn("<svg", svg)
        self.assertNotIn("no SwiftUI view call found", svg)


if __name__ == "__main__":
    unittest.main()
