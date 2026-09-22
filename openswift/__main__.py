"""Draw a SwiftUI sketch to an SVG. Nothing is compiled."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openswift.parse import ParseError, parse_swiftui
from openswift.render import render_svg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openswift",
        description="Draw a picture of a small SwiftUI sketch. Does not compile Swift.",
    )
    parser.add_argument("source", type=Path, help="A .swift file with one view body")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Where to write the SVG")
    args = parser.parse_args(argv)
    source = args.source.read_text(encoding="utf-8")
    try:
        root = parse_swiftui(source)
    except ParseError as exc:
        print(f"openswift: {exc}", file=sys.stderr)
        return 1
    svg = render_svg(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
