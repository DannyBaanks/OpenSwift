import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from openswift.devices import DEVICES
from openswift.studio import make_server, sketch

ROOT = Path(__file__).resolve().parents[1]


class ExamplesTest(unittest.TestCase):
    def test_every_example_draws_without_problems(self) -> None:
        for path in sorted((ROOT / "examples").glob("*.swift")):
            data = sketch(path.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"], path.name)
            self.assertEqual(data["problems"], [], path.name)

    def test_every_device_draws(self) -> None:
        source = (ROOT / "examples" / "hello.swift").read_text(encoding="utf-8")
        for device_id in DEVICES:
            self.assertIn("<svg", sketch(source, device_id)["svg"], device_id)

    def test_studio_lists_devices_and_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            httpd = make_server(Path(tmp), port=0)
            port = httpd.server_address[1]
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            try:
                def get(route: str) -> dict:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}{route}") as res:
                        return json.loads(res.read())

                ids = {d["id"] for d in get("/api/devices")["devices"]}
                self.assertEqual(ids, set(DEVICES))
                self.assertIsNone(get("/api/session")["session"])
            finally:
                httpd.shutdown()
                httpd.server_close()


if __name__ == "__main__":
    unittest.main()


class RegressionTest(unittest.TestCase):
    """The dashboard bug: `.white`, `.gray` and `.leading` never reached the renderer."""

    def test_modifier_arguments_keep_their_dots(self) -> None:
        from openswift.parse import parse_swiftui

        root = parse_swiftui(
            'var body: some View { VStack(alignment: .leading) { Text("a").foregroundColor(.gray) }'
            '.background(Color.blue.opacity(0.2)) }'
        )
        self.assertEqual(root.alignment, "leading")
        self.assertEqual(root.children[0].color, "#8e8e93")
        self.assertEqual(root.background, "#0a84ff")
        self.assertAlmostEqual(root.bg_opacity, 0.2)

    def test_light_and_dark_use_different_text_and_case_colors(self) -> None:
        from openswift.parse import parse_swiftui
        from openswift.render import render_svg

        root = parse_swiftui('var body: some View { Text("hi") }')
        dark = render_svg(root, "iphone-15", "dark", "black")
        light = render_svg(root, "iphone-15", "light", "natural")
        self.assertIn('fill="#ffffff" opacity="1.00" text-anchor="start"', dark)
        self.assertIn('fill="#000000" opacity="1.00" text-anchor="start"', light)
        self.assertIn("#8c867b", light)
        self.assertNotIn("<rect x=\"4\"", render_svg(root, "iphone-15", "dark", "none"))

    def test_hstack_children_with_max_width_share_the_row(self) -> None:
        from openswift.parse import parse_swiftui
        from openswift.render import layout

        root = parse_swiftui(
            'var body: some View { HStack { Text("a").frame(maxWidth: .infinity)'
            ' Text("b").frame(maxWidth: .infinity) } }'
        )
        boxes = layout(root, "iphone-14")
        a, b = boxes[1], boxes[2]
        self.assertAlmostEqual(a.w, b.w)
        self.assertLessEqual(b.x + b.w, 390 + 18)


class PendingFeaturesTest(unittest.TestCase):
    def test_landscape_swaps_the_screen_and_moves_the_island(self) -> None:
        from openswift.parse import parse_swiftui
        from openswift.render import render_svg

        root = parse_swiftui('var body: some View { Text("hi") }')
        portrait = render_svg(root, "iphone-15")
        landscape = render_svg(root, "iphone-15", orientation="landscape")
        self.assertIn('width="126" height="36"', portrait)
        self.assertIn('width="36" height="126"', landscape)
        self.assertNotIn(">9:41<", landscape)

    def test_ipad_has_no_island_and_a_wide_screen(self) -> None:
        from openswift.devices import DEVICES, get_device
        from openswift.parse import parse_swiftui
        from openswift.render import render_svg

        self.assertEqual(DEVICES["ipad-pro-11"].idiom, "pad")
        self.assertEqual(get_device("ipad-pro-11", "landscape").width, 1210)
        svg = render_svg(parse_swiftui('var body: some View { Text("hi") }'), "ipad-pro-11")
        self.assertNotIn('id="island"', svg)
        self.assertNotIn('id="notch"', svg)

    def test_foreach_and_custom_views_expand(self) -> None:
        from openswift.parse import parse_swiftui

        root = parse_swiftui(
            'struct Row: View { var body: some View { Text("row") } }\n'
            'struct Home: View { var body: some View { VStack { ForEach(0..<3) { _ in Row() } } } }'
        )
        self.assertEqual(root.kind, "VStack")
        self.assertEqual(len(root.children), 3)
        self.assertEqual(root.children[0].children[0].text, "row")

    def test_symbols_are_drawn_and_unknown_ones_get_a_marker(self) -> None:
        from openswift.parse import parse_swiftui
        from openswift.render import render_svg, symbol_path

        self.assertIsNotNone(symbol_path("star.fill"))
        self.assertTrue(symbol_path("star.fill")[1])
        self.assertIsNone(symbol_path("some.unknown.symbol"))
        root = parse_swiftui('var body: some View { Label("A", systemImage: "bell") }')
        self.assertEqual(root.symbol, "bell")
        self.assertIn("scale(", render_svg(root))

    def test_session_png_follows_look_and_orientation(self) -> None:
        import os

        from openswift.session import focus, render_session

        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                Path("V.swift").write_text('var body: some View { Text("hi") }', encoding="utf-8")
                focus(Path("V.swift"), [], "check", "approximate-web")
                dark = render_session(device_id="iphone-15")
                light = render_session(device_id="iphone-15", appearance="light", frame="natural", orientation="landscape")
                self.assertNotEqual(dark.read_bytes(), light.read_bytes())
            finally:
                os.chdir(cwd)


class FramesTest(unittest.TestCase):
    def test_expand_devices_presets_and_errors(self) -> None:
        from openswift.devices import DEVICES, expand_devices

        self.assertEqual(set(expand_devices("all")), set(DEVICES))
        self.assertTrue(all(i.startswith("ipad") for i in expand_devices("ipads")))
        self.assertEqual(expand_devices("iphone-15, iphone-15"), ["iphone-15"])
        with self.assertRaises(ValueError):
            expand_devices("iphone-99")

    def test_sheet_lays_each_device_out_for_its_own_screen(self) -> None:
        from openswift.parse import parse_swiftui
        from openswift.render import sheet_svg

        svg = sheet_svg(parse_swiftui('var body: some View { Text("hi") }'), ["iphone-12", "ipad-pro-11"])
        self.assertEqual(svg.count("<svg "), 3)  # the sheet and two frames
        self.assertIn("iPad Pro 11", svg)
        ids = [part.split('"')[0] for part in svg.split('id="')[1:]]
        self.assertEqual(len(ids), len(set(ids)), "ids must stay unique across frames")

    def test_session_keeps_every_frame_and_a_sheet(self) -> None:
        import os

        from openswift.session import focus, render_session, status_text

        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                Path("V.swift").write_text('var body: some View { Text("hi") }', encoding="utf-8")
                focus(Path("V.swift"), [], "check", "approximate-web")
                first = render_session(device_id="iphone-12,ipad-air-11")
                names = sorted(p.name for p in first.parent.glob("*.png"))
                self.assertEqual(first.name, "001.png")
                self.assertIn("001-ipad-air-11-dark.png", names)
                self.assertIn("png:", status_text())
                both = render_session(device_id="iphone-12", appearance="both")
                self.assertEqual(both.name, "002.png")
                self.assertTrue((both.parent / "002-iphone-12-light.png").is_file())
            finally:
                os.chdir(cwd)

    def test_png_falls_back_when_no_rasterizer_exists(self) -> None:
        import os
        from unittest import mock

        from openswift import raster
        from openswift.session import focus, render_session

        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                Path("V.swift").write_text('var body: some View { Text("hi") }', encoding="utf-8")
                focus(Path("V.swift"), [], "check", "approximate-web")
                with mock.patch.object(raster, "available_engines", return_value=[]):
                    shot = render_session()
                self.assertTrue(shot.read_bytes().startswith(b"\x89PNG"))
                record = json.loads((Path(tmp) / ".ui-session" / "target.json").read_text())
                self.assertEqual(record["raster"], "builtin")
            finally:
                os.chdir(cwd)


class FallbackPngTest(unittest.TestCase):
    def _png_size(self, data: bytes) -> tuple[int, int]:
        import struct

        return struct.unpack(">II", data[16:24])

    def test_bare_frame_is_just_the_screen_and_landscape_turns_it(self) -> None:
        from openswift.devices import get_device
        from openswift.parse import parse_swiftui
        from openswift.session import _write_preview_png

        tree = parse_swiftui('var body: some View { Text("hi") }')
        with tempfile.TemporaryDirectory() as tmp:
            bare = Path(tmp) / "bare.png"
            _write_preview_png(tree, bare, "iphone-12", "dark", "none", "portrait")
            device = get_device("iphone-12")
            self.assertEqual(self._png_size(bare.read_bytes()), (device.width, device.height))
            side = Path(tmp) / "side.png"
            _write_preview_png(tree, side, "iphone-15", "dark", "black", "landscape")
            turned = get_device("iphone-15", "landscape")
            self.assertEqual(
                self._png_size(side.read_bytes()),
                (turned.width + turned.bezel_side * 2, turned.height + turned.bezel_top + turned.bezel_bottom),
            )
