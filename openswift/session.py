"""One screen at a time. The session folder is the shared table."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from openswift.parse import parse_swiftui
from openswift.png import fill, write_png
from openswift.render import BEZEL, SCREEN_H, SCREEN_W, measure, render_svg, _place

PROVIDERS = ("approximate-web", "miniswift", "xcode-preview")
SESSION_DIR = ".ui-session"


def session_root(cwd: Path | None = None) -> Path:
    return (cwd or Path.cwd()) / SESSION_DIR


def focus(target: Path, allowed: list[str], intent: str, provider: str, cwd: Path | None = None) -> Path:
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider}")
    if provider != "approximate-web":
        raise ValueError(f"{provider} is named, not wired. Use approximate-web.")
    target = target.resolve()
    if not target.is_file():
        raise FileNotFoundError(target)
    root = session_root(cwd)
    iterations = root / "iterations"
    iterations.mkdir(parents=True, exist_ok=True)
    record = {
        "target": str(target),
        "allowed": allowed,
        "provider": provider,
        "read_only": "everything except target and allowed",
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (root / "target.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (root / "intent.md").write_text(intent.strip() + "\n", encoding="utf-8")
    (root / "source.swift").write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    return root


def load(cwd: Path | None = None) -> tuple[Path, dict]:
    root = session_root(cwd)
    path = root / "target.json"
    if not path.is_file():
        raise FileNotFoundError("no .ui-session here. Run focus first.")
    return root, json.loads(path.read_text(encoding="utf-8"))


def render_session(cwd: Path | None = None) -> Path:
    root, record = load(cwd)
    if record.get("provider") != "approximate-web":
        raise ValueError(record.get("provider"))
    target = Path(record["target"])
    source = target.read_text(encoding="utf-8")
    (root / "source.swift").write_text(source, encoding="utf-8")
    tree = parse_swiftui(source)
    svg = render_svg(tree)
    (root / "preview.svg").write_text(svg, encoding="utf-8")
    png_path = root / "preview.png"
    _write_preview_png(tree, png_path)
    digest = hashlib.sha256(png_path.read_bytes()).hexdigest()
    (root / "preview.sha256").write_text(digest + "\n", encoding="utf-8")
    iterations = root / "iterations"
    iterations.mkdir(exist_ok=True)
    existing = sorted(iterations.glob("*.png"))
    number = len(existing) + 1
    shot = iterations / f"{number:03d}.png"
    shot.write_bytes(png_path.read_bytes())
    (iterations / f"{number:03d}.sha256").write_text(digest + "\n", encoding="utf-8")
    record["iteration"] = number
    record["preview_sha256"] = digest
    (root / "target.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return shot


def status_text(cwd: Path | None = None) -> str:
    root, record = load(cwd)
    lines = [
        f"target: {record['target']}",
        f"provider: {record.get('provider')}",
        f"allowed: {', '.join(record.get('allowed') or []) or '(none)'}",
        f"read only: {record.get('read_only')}",
        f"iteration: {record.get('iteration', 0)}",
        f"session: {root}",
    ]
    intent = root / "intent.md"
    if intent.is_file():
        lines.append("intent: " + intent.read_text(encoding="utf-8").strip())
    return "\n".join(lines)


def _write_preview_png(tree, path: Path) -> None:
    width = SCREEN_W + BEZEL * 2
    height = SCREEN_H + BEZEL * 2
    rgb = bytearray([28, 28, 30]) * (width * height)
    fill(rgb, width, 8, 8, width - 16, height - 16, (10, 10, 10))
    fill(rgb, width, BEZEL, BEZEL, SCREEN_W, SCREEN_H, (0, 0, 0))
    boxes: list = []
    content_w = SCREEN_W - 36
    _, rh = measure(tree, content_w)
    tree.frame_max_width = True
    _place(tree, BEZEL + 18, BEZEL + 54, content_w, max(rh, SCREEN_H - 88), boxes)
    for box in boxes:
        node = box.node
        if node.background:
            fill(rgb, width, int(box.x), int(box.y), int(box.w), int(box.h), _hex(node.background))
        label = node.text if node.kind in {"Text", "Button"} else ""
        if node.kind == "Button" and label:
            fill(rgb, width, int(box.x), int(box.y), int(box.w), max(int(box.h), 8), (255, 255, 255))
        if label:
            _stamp(rgb, width, int(box.x + 8), int(box.y + 8), label, (255, 255, 255) if node.kind != "Button" else (17, 17, 17))
        elif node.kind not in {"VStack", "HStack", "ZStack", "Spacer"}:
            fill(rgb, width, int(box.x), int(box.y), max(int(box.w), 48), 16, (34, 34, 34))
            _stamp(rgb, width, int(box.x + 4), int(box.y + 4), node.kind, (170, 170, 170))
    write_png(path, width, height, rgb)


def _hex(value: str) -> tuple[int, int, int]:
    value = value.removeprefix("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


# 3x5 glyphs for the labels that have to be readable in the PNG.
_GLYPHS = {
    " ": ["000", "000", "000", "000", "000"],
    "a": ["000", "010", "101", "111", "101"],
    "c": ["011", "100", "100", "100", "011"],
    "e": ["111", "100", "110", "100", "111"],
    "n": ["000", "110", "101", "101", "101"],
    "o": ["010", "101", "101", "101", "010"],
    "p": ["110", "101", "110", "100", "100"],
    "t": ["111", "010", "010", "010", "010"],
}


def _stamp(rgb: bytearray, width: int, x: int, y: int, text: str, color: tuple[int, int, int]) -> None:
    cursor = x
    for ch in text.lower():
        glyph = _GLYPHS.get(ch, ["111", "101", "101", "101", "111"])
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "1":
                    fill(rgb, width, cursor + col, y + row, 1, 1, color)
        cursor += 4
