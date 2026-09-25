"""One screen at a time. The session folder is the shared table."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from openswift.devices import get_device
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


def render_session(cwd: Path | None = None, device_id: str = "iphone-14") -> Path:
    root, record = load(cwd)
    if record.get("provider") != "approximate-web":
        raise ValueError(record.get("provider"))
    target = Path(record["target"])
    source = target.read_text(encoding="utf-8")
    (root / "source.swift").write_text(source, encoding="utf-8")
    tree = parse_swiftui(source)
    svg = render_svg(tree, device_id)
    (root / "preview.svg").write_text(svg, encoding="utf-8")
    png_path = root / "preview.png"
    _write_preview_png(tree, png_path, device_id)
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


def _write_preview_png(tree, path: Path, device_id: str = "iphone-14") -> None:
    device = get_device(device_id)
    SCREEN_W = device.width
    SCREEN_H = device.height
    BEZEL = device.bezel_side
    
    # Phone physical dimensions
    phone_w = SCREEN_W + device.bezel_side * 2
    phone_h = SCREEN_H + device.bezel_top + device.bezel_bottom
    
    # Screen position within phone
    screen_x = device.bezel_side
    screen_y = device.bezel_top
    
    width = phone_w
    height = phone_h
    rgb = bytearray([28, 28, 30]) * (width * height)
    
    # Phone body
    fill(rgb, width, 4, 4, width - 8, height - 8, (10, 10, 10))
    # Screen area
    fill(rgb, width, screen_x, screen_y, SCREEN_W, SCREEN_H, (0, 0, 0))
    
    # Notch or Dynamic Island
    _draw_notch_png(rgb, width, device, screen_x, screen_y, SCREEN_W)
    
    # Status bar time
    _stamp(rgb, width, screen_x + 16, screen_y + device.status_bar_height - 14, "9:41", (255, 255, 255))
    
    # Content boxes
    boxes: list = []
    content_w = SCREEN_W - 36
    _, rh = measure(tree, content_w)
    tree.frame_max_width = True
    _place(tree, screen_x + 18, screen_y + 54, content_w, max(rh, SCREEN_H - 88), boxes)
    
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
    
    # Home indicator
    _draw_home_indicator_png(rgb, width, device, screen_x, screen_y, SCREEN_W, SCREEN_H)
    
    # Side buttons
    _draw_side_buttons_png(rgb, width, device, screen_x, screen_y, SCREEN_W, SCREEN_H)
    
    write_png(path, width, height, rgb)


def _draw_notch_png(rgb: bytearray, width: int, device, screen_x: int, screen_y: int, screen_w: int) -> None:
    """Draw notch or Dynamic Island on PNG."""
    from openswift.devices import NotchType
    
    if device.notch_type == NotchType.DYNAMIC_ISLAND:
        # Dynamic Island - pill shape
        island_w, island_h = 126, 36
        island_x = screen_x + (screen_w - island_w) // 2
        island_y = screen_y + 6
        # Draw rounded rect approximation
        for y in range(island_y, island_y + island_h):
            for x in range(island_x, island_x + island_w):
                # Simple rounded corners
                dx = min(x - island_x, island_x + island_w - 1 - x)
                dy = min(y - island_y, island_y + island_h - 1 - y)
                if dx < 18 and dy < 18 and dx*dx + dy*dy < 18*18:
                    continue
                if x < width and y < len(rgb) // (width * 3):
                    fill(rgb, width, x, y, 1, 1, (10, 10, 10))
    elif device.notch_type in (NotchType.CLASSIC, NotchType.REDUCED):
        # Notch - trapezoid with rounded bottom
        if device.notch_type == NotchType.CLASSIC:
            notch_w, notch_h = 194, 32
        else:
            notch_w, notch_h = 156, 32
        notch_x = screen_x + (screen_w - notch_w) // 2
        notch_y = screen_y
        for y in range(notch_y, notch_y + notch_h):
            # Width decreases at bottom for rounded corners
            if y >= notch_y + notch_h - 10:
                # Rounded bottom corners
                inset = int((10 - (y - (notch_y + notch_h - 10))) * 1.5)
                row_x = notch_x + inset
                row_w = notch_w - 2 * inset
            else:
                row_x = notch_x
                row_w = notch_w
            fill(rgb, width, row_x, y, row_w, 1, (10, 10, 10))


def _draw_home_indicator_png(rgb: bytearray, width: int, device, screen_x: int, screen_y: int, screen_w: int, screen_h: int) -> None:
    """Draw home indicator bar at bottom of screen."""
    indicator_w = 136
    indicator_h = 5
    indicator_x = screen_x + (screen_w - indicator_w) // 2
    indicator_y = screen_y + screen_h - indicator_h - 8
    fill(rgb, width, indicator_x, indicator_y, indicator_w, indicator_h, (92, 92, 92))  # dimmed white ~0.36 opacity


def _draw_side_buttons_png(rgb: bytearray, width: int, device, screen_x: int, screen_y: int, screen_w: int, screen_h: int) -> None:
    """Draw side buttons on PNG."""
    button_color = (42, 42, 46)  # #2a2a2e
    
    # Right side power button
    power_y = screen_y + 140
    fill(rgb, width, screen_x + screen_w + device.bezel_side - 6, power_y, 4, 48, button_color)
    
    # Action button (iPhone 15 Pro/16 Pro)
    if device.has_action_button:
        fill(rgb, width, screen_x + screen_w + device.bezel_side - 6, power_y - 60, 4, 28, button_color)
    
    # Camera Control (iPhone 16/16 Pro)
    if device.has_camera_control:
        fill(rgb, width, screen_x + screen_w + device.bezel_side - 6, power_y + 60, 4, 28, button_color)
    
    # Left side volume buttons
    vol_y = screen_y + 140
    fill(rgb, width, screen_x - device.bezel_side + 2, vol_y, 3, 48, button_color)
    fill(rgb, width, screen_x - device.bezel_side + 2, vol_y + 65, 3, 48, button_color)
    
    # Mute switch
    fill(rgb, width, screen_x - device.bezel_side + 1, vol_y - 30, 5, 20, button_color)


def _hex(value: str) -> tuple[int, int, int]:
    value = value.removeprefix("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


# 5x7 glyphs for the labels that have to be readable in the PNG.
_GLYPHS = {
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    '"': ["01010", "01010", "01010", "00000", "00000", "00000", "00000"],
    "#": ["00000", "01010", "11111", "01010", "11111", "01010", "00000"],
    "$": ["00100", "01110", "10101", "01110", "10101", "01110", "00100"],
    "%": ["11000", "11001", "00100", "01000", "10011", "10011", "00000"],
    "&": ["01100", "10010", "10100", "01000", "10101", "10010", "01101"],
    "'": ["00100", "01000", "01000", "00000", "00000", "00000", "00000"],
    "(": ["00010", "00100", "01000", "01000", "01000", "00100", "00010"],
    ")": ["01000", "00100", "00010", "00010", "00010", "00100", "01000"],
    "*": ["00000", "01010", "00100", "11111", "00100", "01010", "00000"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    ",": ["00000", "00000", "00000", "00000", "00100", "01000", "01000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "00100", "00100"],
    "/": ["00001", "00010", "00100", "01000", "10000", "00000", "00000"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00110", "01000", "10000", "11111"],
    "3": ["11111", "00001", "00110", "00001", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    ":": ["00000", "00100", "00100", "00000", "00100", "00100", "00000"],
    ";": ["00000", "00100", "00100", "00000", "00100", "01000", "01000"],
    "<": ["00010", "00100", "01000", "10000", "01000", "00100", "00010"],
    "=": ["00000", "00000", "11111", "00000", "11111", "00000", "00000"],
    ">": ["10000", "01000", "00100", "00010", "00100", "01000", "10000"],
    "?": ["01110", "10001", "00001", "00110", "00100", "00000", "00100"],
    "@": ["01110", "10001", "10111", "10101", "10101", "10000", "01110"],
    "a": ["00000", "01110", "00001", "01111", "10001", "01111", "00000"],
    "b": ["10000", "10000", "10110", "11001", "10001", "11001", "00000"],
    "c": ["00000", "00000", "01110", "10001", "10000", "10001", "01110"],
    "d": ["00001", "00001", "01101", "10001", "10001", "01111", "00000"],
    "e": ["00000", "01110", "10001", "11111", "10000", "10001", "01110"],
    "f": ["00110", "01000", "01000", "11100", "01000", "01000", "00000"],
    "g": ["00000", "01110", "10001", "01111", "00001", "10001", "01110"],
    "h": ["10000", "10000", "10110", "11001", "10001", "10001", "00000"],
    "i": ["01000", "00000", "01100", "00100", "00100", "00100", "01110"],
    "j": ["00010", "00000", "00110", "00010", "00010", "10010", "01100"],
    "k": ["10000", "10000", "10100", "11000", "10100", "10010", "00000"],
    "l": ["01100", "00100", "00100", "00100", "00100", "00100", "01110"],
    "m": ["00000", "00000", "11010", "10101", "10101", "10001", "00000"],
    "n": ["00000", "00000", "10110", "11001", "10001", "10001", "00000"],
    "o": ["00000", "00000", "01110", "10001", "10001", "10001", "01110"],
    "p": ["00000", "00000", "11110", "10001", "11110", "10000", "10000"],
    "q": ["00000", "00000", "01111", "10001", "10001", "01111", "00001"],
    "r": ["00000", "00000", "10110", "11001", "10000", "10000", "00000"],
    "s": ["00000", "01110", "10000", "01110", "00001", "10001", "01110"],
    "t": ["00100", "00100", "01110", "00100", "00100", "00101", "00110"],
    "u": ["00000", "00000", "10001", "10001", "10001", "10001", "01110"],
    "v": ["00000", "00000", "10001", "10001", "10001", "01010", "00100"],
    "w": ["00000", "00000", "10001", "10101", "10101", "10101", "01010"],
    "x": ["00000", "00000", "10001", "01010", "00100", "01010", "10001"],
    "y": ["00000", "00000", "10001", "10001", "10001", "01111", "00001"],
    "z": ["00000", "00000", "11111", "00010", "00100", "01000", "11111"],
    "[": ["01110", "01000", "01000", "01000", "01000", "01000", "01110"],
    "\\": ["00000", "10000", "01000", "00100", "00010", "00001", "00000"],
    "]": ["01110", "00010", "00010", "00010", "00010", "00010", "01110"],
    "^": ["00100", "01010", "10001", "00000", "00000", "00000", "00000"],
    "_": ["00000", "00000", "00000", "00000", "00000", "00000", "11111"],
    "`": ["00100", "01000", "01000", "00000", "00000", "00000", "00000"],
    "{": ["00010", "00100", "00100", "01000", "00100", "00100", "00010"],
    "|": ["00100", "00100", "00100", "00100", "00100", "00100", "00100"],
    "}": ["10000", "01000", "01000", "00100", "01000", "01000", "10000"],
    "~": ["00000", "00000", "01101", "10010", "00000", "00000", "00000"],
}


def _stamp(rgb: bytearray, width: int, x: int, y: int, text: str, color: tuple[int, int, int]) -> None:
    cursor = x
    for ch in text.lower():
        glyph = _GLYPHS.get(ch, _GLYPHS["?"])
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "1":
                    fill(rgb, width, cursor + col, y + row, 1, 1, color)
        cursor += 6  # 5 pixels wide + 1 pixel spacing
