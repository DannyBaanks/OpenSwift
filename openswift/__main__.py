"""OpenSwift: one screen, one picture, one session.

Nothing here compiles Swift. `draw` writes an SVG. `focus` / `render` /
`status` keep a .ui-session folder so people and agents look at the same view.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import json

from openswift.parse import ParseError, parse_swiftui
from openswift.render import render_svg
from openswift.session import PROVIDERS, focus, render_session, status_text
from openswift.studio import serve, sketch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openswift")
    sub = parser.add_subparsers(dest="cmd", required=True)

    draw = sub.add_parser("draw", help="write one SVG from a SwiftUI sketch")
    draw.add_argument("source", type=Path)
    draw.add_argument("-o", "--output", type=Path, required=True)

    lock = sub.add_parser("focus", help="lock the table to one view")
    lock.add_argument("target", type=Path)
    lock.add_argument("--allow", action="append", default=[], help="dependency the agent may edit")
    lock.add_argument("--intent", required=True)
    lock.add_argument("--provider", default="approximate-web", choices=PROVIDERS)

    sub.add_parser("render", help="draw the locked view and keep the iteration")
    sub.add_parser("status", help="print the current lock")

    studio = sub.add_parser("studio", help="open the local editor and phone sketch")
    studio.add_argument("project", nargs="?", type=Path, default=Path("."))
    studio.add_argument("--port", type=int, default=8765)

    sketch_cmd = sub.add_parser("sketch", help="print the sketch as JSON")
    sketch_cmd.add_argument("source", type=Path, help="A .swift file, or - for stdin")
    sketch_cmd.add_argument("--device", default="iphone-14")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "draw":
            return _draw(args.source, args.output)
        if args.cmd == "focus":
            root = focus(args.target, args.allow, args.intent, args.provider)
            print(root)
            return 0
        if args.cmd == "render":
            print(render_session())
            return 0
        if args.cmd == "studio":
            serve(args.project.resolve(), port=args.port)
            return 0
        if args.cmd == "sketch":
            text = sys.stdin.read() if str(args.source) == "-" else args.source.read_text(encoding="utf-8")
            print(json.dumps(sketch(text, args.device)))
            return 0
        print(status_text())
        return 0
    except (ParseError, ValueError, FileNotFoundError, OSError) as exc:
        print(f"openswift: {exc}", file=sys.stderr)
        return 1


def _draw(source: Path, output: Path) -> int:
    root = parse_swiftui(source.read_text(encoding="utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_svg(root), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
