"""Paint a parsed sketch into one SVG picture of a phone screen."""

from __future__ import annotations

import copy
import html
from dataclasses import dataclass

from openswift.devices import NotchType, get_device
from openswift.parse import ViewNode

APPEARANCES = ("dark", "light")

# Case colors. "none" draws the screen alone, without a phone around it.
FRAMES = {
    "black": {"body": "#0a0a0a", "edge": "#2a2a2e", "backdrop": "none"},
    "natural": {"body": "#8c867b", "edge": "#6e695f", "backdrop": "none"},
    "white": {"body": "#e9e7e2", "edge": "#c9c6bf", "backdrop": "none"},
    "blue": {"body": "#3d4b5e", "edge": "#2d3846", "backdrop": "none"},
    "none": {"body": "none", "edge": "none", "backdrop": "none"},
}

_PALETTE = {
    "dark": {
        "screen": "#000000", "primary": "#ffffff", "secondary": "#8e8e93",
        "divider": "#38383a", "field": "#1c1c1e", "card": "#2c2c2e", "status": "#ffffff",
    },
    "light": {
        "screen": "#ffffff", "primary": "#000000", "secondary": "#8e8e93",
        "divider": "#c6c6c8", "field": "#f2f2f7", "card": "#f2f2f7", "status": "#000000",
    },
}
_BLUE = "#0a84ff"
_WEIGHTS = {
    "ultraLight": 200, "thin": 300, "light": 300, "regular": 400, "medium": 500,
    "semibold": 600, "bold": 700, "heavy": 800, "black": 900,
}
_FONT = "-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',ui-sans-serif,system-ui,sans-serif"
_SAFE_BOTTOM = 34


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float
    node: ViewNode


def _text_width(text: str, size: float) -> float:
    return max(8, len(text) * size * 0.54)


_VERTICAL = {
    "VStack", "Form", "Section", "List", "ScrollView", "NavigationStack",
    "NavigationSplitView", "Group", "GroupBox",
}
_CONTAINERS = _VERTICAL | {"HStack", "ZStack"}
_FULL_ROW = {"TextField", "SecureField", "Toggle"}


def measure(node: ViewNode, max_w: float) -> tuple[float, float]:
    inner_w = max(0, max_w - node.pad_left - node.pad_right)
    if node.kind == "Text":
        width = min(_text_width(node.text or " ", node.font_size), inner_w)
        height = node.font_size * 1.35
    elif node.kind == "Spacer":
        width, height = 8, 8
    elif node.kind == "Divider":
        width, height = inner_w, 1
    elif node.kind in _CONTAINERS:
        sizes = [measure(child, inner_w) for child in node.children]
        if node.kind in _VERTICAL:
            width = max((w for w, _ in sizes), default=0)
            gaps = node.spacing * max(0, len(sizes) - 1)
            height = sum(h for _, h in sizes) + gaps
        elif node.kind == "HStack":
            gaps = node.spacing * max(0, len(sizes) - 1)
            width = sum(w for w, _ in sizes) + gaps
            if any(child.kind == "Spacer" or child.frame_max_width for child in node.children):
                width = inner_w
            height = max((h for _, h in sizes), default=0)
        else:
            width = max((w for w, _ in sizes), default=0)
            height = max((h for _, h in sizes), default=0)
    elif node.kind == "Button":
        label = node.text or _first_text(node) or "Button"
        width = _text_width(label, 17) + (32 if node.background or node.button_style in {"bordered", "borderedProminent"} else 8)
        height = 44 if node.background or node.button_style in {"bordered", "borderedProminent"} else 28
    elif node.kind in _FULL_ROW:
        width, height = inner_w, 44
    elif node.kind == "Label":
        width, height = min(_text_width(node.text or "Label", 17) + 36, inner_w), 28
    elif node.kind == "Image":
        width, height = 28, 28
    else:
        width, height = min(inner_w, 160), 28
    if node.frame_max_width:
        width = inner_w
    if node.frame_width:
        width = min(node.frame_width, 640)
    if node.frame_height:
        height = min(node.frame_height, 640)
    width = min(width + node.pad_left + node.pad_right, max_w)
    height = height + node.pad_top + node.pad_bottom
    return width, height


def _first_text(node: ViewNode) -> str:
    for child in node.children:
        if child.text:
            return child.text
        found = _first_text(child)
        if found:
            return found
    return ""


def _place(node: ViewNode, x: float, y: float, w: float, h: float, out: list[Box]) -> None:
    right = BEZEL + SCREEN_W
    bottom = SCREEN_TOP + SCREEN_H
    if x >= right or y >= bottom:
        return
    w = max(0, min(w, right - x))
    h = max(0, min(h, bottom - y))
    out.append(Box(x, y, w, h, node))
    ix = x + node.pad_left
    iy = y + node.pad_top
    iw = max(0, w - node.pad_left - node.pad_right)
    ih = max(0, h - node.pad_top - node.pad_bottom)
    if node.kind in _VERTICAL:
        sizes = [measure(child, iw) for child in node.children]
        fixed = sum(sh for child, (_, sh) in zip(node.children, sizes) if child.kind != "Spacer")
        spacers = sum(1 for child in node.children if child.kind == "Spacer")
        gaps = node.spacing * max(0, len(node.children) - 1)
        extra = max(0, ih - fixed - gaps)
        share = extra / spacers if spacers else 0
        cursor = iy
        for child, (cw, ch) in zip(node.children, sizes):
            drawn_h = share if child.kind == "Spacer" else ch
            child_w = iw if child.frame_max_width or child.kind == "Divider" else min(cw, iw)
            if node.alignment == "leading":
                child_x = ix
            elif node.alignment == "trailing":
                child_x = ix + iw - child_w
            else:
                child_x = ix + (iw - child_w) / 2
            _place(child, child_x, cursor, child_w, drawn_h, out)
            cursor += drawn_h + node.spacing
    elif node.kind == "HStack":
        sizes = [measure(child, iw) for child in node.children]
        flex = [child for child in node.children if child.frame_max_width and child.kind != "Spacer"]
        spacers = sum(1 for child in node.children if child.kind == "Spacer")
        fixed = sum(cw for child, (cw, _) in zip(node.children, sizes) if child.kind != "Spacer" and child not in flex)
        gaps = node.spacing * max(0, len(node.children) - 1)
        left = max(0, iw - fixed - gaps)
        # frame(maxWidth: .infinity) children split what is left; Spacers get it only when none do.
        flex_share = left / len(flex) if flex else 0
        share = left / spacers if spacers and not flex else 0
        cursor = ix
        for child, (cw, ch) in zip(node.children, sizes):
            if child.kind == "Spacer":
                drawn_w = share
            elif child in flex:
                drawn_w = flex_share
            else:
                drawn_w = cw
            top = iy + max(0, (ih - ch) / 2)
            _place(child, cursor, top, drawn_w, ch, out)
            cursor += drawn_w + node.spacing
    elif node.kind == "ZStack":
        for child in node.children:
            cw, ch = measure(child, iw)
            _place(child, ix + (iw - min(cw, iw)) / 2, iy + (ih - min(ch, ih)) / 2, min(cw, iw), min(ch, ih), out)


def _sensor(device, x: float, y: float, screen_w: int) -> str:
    if device.notch_type == NotchType.DYNAMIC_ISLAND:
        width, height = 126, 36
        island_x = x + (screen_w - width) / 2
        island_y = y + 11
        return (
            f'<rect id="island" x="{island_x:.1f}" y="{island_y:.1f}" '
            f'width="{width}" height="{height}" rx="18" fill="#000"/>'
            f'<circle cx="{island_x + width - 20:.1f}" cy="{island_y + height / 2:.1f}" r="5" fill="#0c0c14"/>'
        )
    if device.notch_type in (NotchType.CLASSIC, NotchType.REDUCED):
        notch_w = 194 if device.notch_type == NotchType.CLASSIC else 156
        notch_h = 32
        notch_x = x + (screen_w - notch_w) / 2
        return (
            f'<path id="notch" fill="#000" '
            f'd="M {notch_x:.1f} {y} h {notch_w} '
            f'v {notch_h - 10} q 0 10 -10 10 h -{notch_w - 20} '
            f'q -10 0 -10 -10 z"/>'
        )
    return ""


def _status_icons(device, x: float, y: float, screen_w: int, ink: str) -> str:
    """Clock on the left, signal, wifi and battery on the right of the status bar."""
    parts = []
    baseline = y + device.status_bar_height - 16
    clock_x = x + (46 if device.notch_type != NotchType.DYNAMIC_ISLAND else 52)
    parts.append(
        f'<text x="{clock_x:.1f}" y="{baseline:.1f}" fill="{ink}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="16" font-weight="600">9:41</text>'
    )
    right = x + screen_w - 22
    battery_x = right - 27
    parts.append(f'<rect x="{battery_x:.1f}" y="{baseline - 11:.1f}" width="25" height="12" rx="3.5" fill="none" stroke="{ink}" stroke-opacity="0.4"/>')
    parts.append(f'<rect x="{battery_x + 2:.1f}" y="{baseline - 9:.1f}" width="17" height="8" rx="2" fill="{ink}"/>')
    parts.append(f'<rect x="{battery_x + 26:.1f}" y="{baseline - 7:.1f}" width="1.6" height="4" rx="0.8" fill="{ink}" opacity="0.4"/>')
    wifi_x = battery_x - 22
    for i, r in enumerate((11, 7.5, 4)):
        parts.append(
            f'<path d="M {wifi_x + 8 - r:.1f} {baseline - 1 - i * 1.2:.1f} a {r} {r} 0 0 1 {2 * r} 0" '
            f'fill="none" stroke="{ink}" stroke-width="1.7" stroke-linecap="round" transform="translate(0 {-i * 0.2})"/>'
        )
    signal_x = wifi_x - 26
    for i in range(4):
        h = 4 + i * 2.6
        parts.append(f'<rect x="{signal_x + i * 4.6:.1f}" y="{baseline - h + 1:.1f}" width="3" height="{h:.1f}" rx="0.9" fill="{ink}"/>')
    return "\n".join(parts)


def _home_indicator(x: float, y: float, screen_w: int, screen_h: int, ink: str) -> str:
    width, height = 136, 5
    return (
        f'<rect x="{x + (screen_w - width) / 2:.1f}" y="{y + screen_h - height - 8:.1f}" '
        f'width="{width}" height="{height}" rx="{height / 2}" fill="{ink}" opacity="0.9"/>'
    )


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


SCREEN_W = 390
SCREEN_H = 780
SCREEN_TOP = 28
BEZEL = 28


def layout(root: ViewNode, device_id: str = "iphone-14") -> list[Box]:
    """Place the sketch on a screen. The root fills the screen under the status bar."""
    global SCREEN_W, SCREEN_H, SCREEN_TOP, BEZEL
    device = get_device(device_id)
    SCREEN_W, SCREEN_H = device.width, device.height
    SCREEN_TOP, BEZEL = device.bezel_top, device.bezel_side
    placed = copy.copy(root)
    placed.frame_max_width = True
    placed.frame_width = None
    placed.frame_height = None
    placed.pad_top += device.status_bar_height + 6
    placed.pad_bottom += _SAFE_BOTTOM
    boxes: list[Box] = []
    _place(placed, BEZEL, SCREEN_TOP, SCREEN_W, SCREEN_H, boxes)
    return boxes


def render_svg(root: ViewNode, device_id: str = "iphone-14", appearance: str = "dark", frame: str = "black") -> str:
    device = get_device(device_id)
    palette = _PALETTE.get(appearance, _PALETTE["dark"])
    case = FRAMES.get(frame, FRAMES["black"])
    boxes = layout(root, device_id)
    bare = frame == "none"
    bezel_x, bezel_t, bezel_b = (0, 0, 0) if bare else (device.bezel_side, device.bezel_top, device.bezel_bottom)
    # layout() works in framed coordinates; shift for a frameless export.
    dx, dy = (-device.bezel_side, -device.bezel_top) if bare else (0, 0)
    phone_w = SCREEN_W + bezel_x * 2
    phone_h = SCREEN_H + bezel_t + bezel_b
    screen_x = bezel_x
    screen_y = bezel_t
    defs: list[str] = [
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">'
        '<feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000" flood-opacity="0.35"/></filter>'
    ]
    body: list[str] = []
    if not bare:
        body.append(f'<rect width="100%" height="100%" fill="{case["backdrop"]}"/>')
        body.append(f'<rect x="4" y="4" width="{phone_w - 8}" height="{phone_h - 8}" rx="{device.corner_radius}" fill="{case["body"]}"/>')
        body.append(
            f'<rect x="7" y="7" width="{phone_w - 14}" height="{phone_h - 14}" rx="{device.corner_radius - 3}" '
            f'fill="none" stroke="{case["edge"]}" stroke-width="1.2"/>'
        )
        body.append(f'<rect x="{screen_x - 3}" y="{screen_y - 3}" width="{SCREEN_W + 6}" height="{SCREEN_H + 6}" rx="{device.screen_radius + 3}" fill="#000"/>')
    clip_id = "screen-clip"
    defs.append(
        f'<clipPath id="{clip_id}"><rect x="{screen_x}" y="{screen_y}" width="{SCREEN_W}" height="{SCREEN_H}" rx="{device.screen_radius}"/></clipPath>'
    )
    body.append(f'<rect x="{screen_x}" y="{screen_y}" width="{SCREEN_W}" height="{SCREEN_H}" rx="{device.screen_radius}" fill="{palette["screen"]}"/>')
    body.append(f'<g clip-path="url(#{clip_id})">')
    for index, box in enumerate(boxes):
        body.extend(_paint(box, index, defs, palette, dx, dy))
    body.append("</g>")
    body.append(_sensor(device, screen_x, screen_y, SCREEN_W))
    body.append(_status_icons(device, screen_x, screen_y, SCREEN_W, palette["status"]))
    body.append(_home_indicator(screen_x, screen_y, SCREEN_W, SCREEN_H, palette["status"]))
    if not bare:
        body.extend(_side_buttons(device, screen_x, screen_y, case["edge"]))
        body.append(
            f'<text x="{screen_x + 16}" y="{phone_h - 8}" fill="#8e8e93" opacity="0.7" '
            f'font-family="{_FONT}" font-size="9">OpenSwift sketch \xb7 not compiled Swift</text>'
        )
    head = f'<svg xmlns="http://www.w3.org/2000/svg" width="{phone_w}" height="{phone_h}" viewBox="0 0 {phone_w} {phone_h}">'
    return "\n".join([head, "<defs>" + "".join(defs) + "</defs>", *body, "</svg>"])


def _side_buttons(device, screen_x: int, screen_y: int, color: str) -> list[str]:
    right = screen_x + SCREEN_W + device.bezel_side - 6
    left = screen_x - device.bezel_side + 2
    power_y = screen_y + 140
    parts = [f'<rect x="{right:.1f}" y="{power_y:.1f}" width="4" height="48" rx="2" fill="{color}"/>']
    if device.has_action_button:
        parts.append(f'<rect x="{left - 1:.1f}" y="{screen_y + 80:.1f}" width="5" height="20" rx="2" fill="{color}"/>')
    if device.has_camera_control:
        parts.append(f'<rect x="{right:.1f}" y="{power_y + 60:.1f}" width="4" height="28" rx="2" fill="{color}"/>')
    parts.append(f'<rect x="{left:.1f}" y="{screen_y + 140:.1f}" width="3" height="48" rx="1.5" fill="{color}"/>')
    parts.append(f'<rect x="{left:.1f}" y="{screen_y + 205:.1f}" width="3" height="48" rx="1.5" fill="{color}"/>')
    return parts


def _paint(box: Box, index: int, defs: list[str], palette: dict, dx: float, dy: float) -> list[str]:
    node = box.node
    x, y, w, h = box.x + dx, box.y + dy, box.w, box.h
    out: list[str] = []
    radius = min(node.corner, min(w, h) / 2)
    primary = node.color or palette["primary"]
    shadow = ' filter="url(#shadow)"' if node.shadow else ""
    if node.background and node.kind != "Button":
        out.append(_fill_rect(x, y, w, h, radius, node, index, defs, shadow))
    if node.border:
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius:.1f}" fill="none" stroke="{node.border}" stroke-width="1.5"/>')
    ix = x + node.pad_left
    iy = y + node.pad_top
    iw = max(0, w - node.pad_left - node.pad_right)
    ih = max(0, h - node.pad_top - node.pad_bottom)
    if node.kind == "Text":
        out.append(_text(node.text, ix, iy, iw, node.font_size, node.weight, primary, node.opacity, node.text_align))
    elif node.kind == "Button":
        out.extend(_button(node, x, y, w, h, radius, index, defs, palette))
    elif node.kind in {"TextField", "SecureField"}:
        out.append(f'<rect x="{ix:.1f}" y="{iy:.1f}" width="{iw:.1f}" height="{ih:.1f}" rx="{node.corner or 12}" fill="{node.background or palette["field"]}"/>')
        placeholder = node.text or ("Password" if node.kind == "SecureField" else "Text")
        shown = "•" * 8 if node.kind == "SecureField" else placeholder
        out.append(_text(shown, ix + 14, iy + (ih - 17 * 1.35) / 2, iw - 28, 17, "regular", palette["secondary"], 1, "leading"))
    elif node.kind == "Toggle":
        out.append(_text(node.text, ix, iy + (ih - 17 * 1.35) / 2, iw - 70, 17, "regular", primary, node.opacity, "leading"))
        out.append(f'<rect x="{ix + iw - 51:.1f}" y="{iy + ih / 2 - 15.5:.1f}" width="51" height="31" rx="15.5" fill="#30d158"/>')
        out.append(f'<circle cx="{ix + iw - 17.5:.1f}" cy="{iy + ih / 2:.1f}" r="13.5" fill="#fff"/>')
    elif node.kind == "Label":
        out.append(_icon(ix, iy + (ih - 24) / 2, 24, node.color or _BLUE))
        out.append(_text(node.text, ix + 34, iy + (ih - 17 * 1.35) / 2, iw - 34, 17, "regular", primary, node.opacity, "leading"))
    elif node.kind == "Image":
        size = min(iw, ih) or 28
        out.append(_icon(ix, iy, size, node.color or _BLUE))
    elif node.kind == "Divider":
        out.append(f'<rect x="{x:.1f}" y="{y + h / 2:.1f}" width="{w:.1f}" height="1" fill="{palette["divider"]}"/>')
    elif node.kind not in _CONTAINERS and node.kind != "Spacer" and not node.children:
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 80):.1f}" height="24" rx="6" fill="{palette["field"]}" stroke="{palette["divider"]}"/>')
        out.append(_text(node.kind, x + 8, y + 3, max(w, 80) - 16, 12, "regular", palette["secondary"], 1, "leading"))
    for note in node.notes[:1]:
        out.append(
            f'<text x="{x:.1f}" y="{y + h + 11:.1f}" fill="#8e8e93" opacity="0.6" font-family="ui-monospace,monospace" font-size="9">.{_esc(note)}</text>'
        )
    return out


def _fill_rect(x, y, w, h, radius, node, index, defs, shadow="") -> str:
    fill = node.background
    if node.gradient:
        gid = f"grad{index}"
        stops = len(node.gradient) - 1
        stop_xml = "".join(
            f'<stop offset="{i / stops:.2f}" stop-color="{color}"/>' for i, color in enumerate(node.gradient)
        )
        defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">{stop_xml}</linearGradient>')
        fill = f"url(#{gid})"
    opacity = node.bg_opacity * (node.opacity if node.opacity < 1 else 1)
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius:.1f}" '
        f'fill="{fill}" opacity="{opacity:.2f}"{shadow}/>'
    )


def _text(text: str, x: float, y: float, width: float, size: float, weight: str, color: str, opacity: float, align: str) -> str:
    if not text:
        return ""
    anchor, tx = "start", x
    if align == "center":
        anchor, tx = "middle", x + width / 2
    elif align == "trailing":
        anchor, tx = "end", x + width
    return (
        f'<text x="{tx:.1f}" y="{y + size * 1.0:.1f}" fill="{color}" opacity="{opacity:.2f}" text-anchor="{anchor}" '
        f'font-family="{_FONT}" font-size="{size:.0f}" font-weight="{_WEIGHTS.get(weight, 400)}">{_esc(text)}</text>'
    )


def _icon(x: float, y: float, size: float, color: str) -> str:
    """SF Symbols are not drawn; a tinted rounded square stands in."""
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{size:.1f}" height="{size:.1f}" rx="{size * 0.26:.1f}" fill="{color}" opacity="0.9"/>'
        f'<circle cx="{x + size / 2:.1f}" cy="{y + size / 2:.1f}" r="{size * 0.2:.1f}" fill="#fff" opacity="0.9"/>'
    )


def _button(node: ViewNode, x, y, w, h, radius, index, defs, palette) -> list[str]:
    label = node.text or _first_text(node) or "Button"
    style = node.button_style
    out: list[str] = []
    if node.background:
        out.append(_fill_rect(x, y, w, h, radius or 12, node, index, defs, ' filter="url(#shadow)"' if node.shadow else ""))
        ink = node.color or "#ffffff"
    elif style == "borderedProminent":
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius or 12}" fill="{_BLUE}"/>')
        ink = node.color or "#ffffff"
    elif style == "bordered":
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius or 12}" fill="{_BLUE}" opacity="0.18"/>')
        ink = node.color or _BLUE
    else:
        ink = node.color or _BLUE
    top = y + node.pad_top
    inner_h = h - node.pad_top - node.pad_bottom
    text_y = top + (inner_h - 17) / 2 - 1
    out.append(_text(label, x + node.pad_left, text_y, w - node.pad_left - node.pad_right, 17, node.weight if node.weight != "regular" else ("semibold" if node.background or style == "borderedProminent" else "regular"), ink, node.opacity, "center"))
    return out
