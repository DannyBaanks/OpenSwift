"""Paint a parsed sketch into one SVG picture of a phone screen."""

from __future__ import annotations

from dataclasses import dataclass

from openswift.devices import get_device
from openswift.parse import ViewNode


SCREEN_W = 390
SCREEN_H = 780
BEZEL = 28
_VERTICAL = {
    "VStack", "Form", "Section", "List", "ScrollView", "NavigationStack",
    "NavigationSplitView", "Group", "GroupBox",
}


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float
    node: ViewNode


def _text_width(text: str, size: float) -> float:
    return max(8, len(text) * size * 0.56)


def measure(node: ViewNode, max_w: float) -> tuple[float, float]:
    inner_w = max(0, max_w - node.pad_left - node.pad_right)
    if node.kind == "Text":
        width = min(_text_width(node.text or " ", node.font_size), inner_w)
        height = node.font_size * 1.35
    elif node.kind == "Spacer":
        width, height = 8, 8
    elif node.kind == "Divider":
        width, height = inner_w, 1
    elif node.kind in {"VStack", "HStack", "ZStack"} or node.kind in {
        "Form", "Section", "List", "ScrollView", "NavigationStack",
        "NavigationSplitView", "Group", "GroupBox",
    }:
        sizes = [measure(child, inner_w) for child in node.children]
        if node.kind in _VERTICAL:
            width = max((w for w, _ in sizes), default=0)
            gaps = node.spacing * max(0, len(sizes) - 1)
            height = sum(h for _, h in sizes) + gaps
        elif node.kind == "HStack":
            gaps = node.spacing * max(0, len(sizes) - 1)
            width = sum(w for w, _ in sizes) + gaps
            height = max((h for _, h in sizes), default=0)
        else:
            width = max((w for w, _ in sizes), default=0)
            height = max((h for _, h in sizes), default=0)
    elif node.kind == "Button":
        label = node.text or (node.children[0].text if node.children else "Button")
        width = _text_width(label, 15) + 28
        height = 44
    else:
        width, height = min(inner_w, 160), 28
    if node.frame_max_width:
        width = inner_w
    if node.frame_height:
        height = min(node.frame_height, 640)
    width = min(width + node.pad_left + node.pad_right, max_w)
    height = height + node.pad_top + node.pad_bottom
    return width, height


def _place(node: ViewNode, x: float, y: float, w: float, h: float, out: list[Box]) -> None:
    # The sketch stays inside the phone. A wide title or a max frame cannot
    # paint past the screen edge.
    right = BEZEL + SCREEN_W - 10
    bottom = BEZEL + SCREEN_H - 10
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
            child_w = iw if child.frame_max_width or node.alignment == "leading" else min(cw, iw)
            child_x = ix if node.alignment == "leading" else ix + (iw - child_w) / 2
            _place(child, child_x, cursor, child_w, drawn_h, out)
            cursor += drawn_h + node.spacing
    elif node.kind == "HStack":
        sizes = [measure(child, iw) for child in node.children]
        cursor = ix
        for child, (cw, ch) in zip(node.children, sizes):
            _place(child, cursor, iy, cw, ch, out)
            cursor += cw + node.spacing
    elif node.kind == "ZStack":
        for child in node.children:
            cw, ch = measure(child, iw)
            _place(child, ix, iy, min(cw, iw), min(ch, ih), out)


def _sensor(island: bool) -> str:
    if island:
        width, height = 126, 36
        x = BEZEL + (SCREEN_W - width) / 2
        y = BEZEL + 16
        return (
            f'<rect id="island" x="{x:.1f}" y="{y:.1f}" width="{width}" height="{height}" '
            f'rx="18" fill="#0a0a0a"/>'
        )
    notch_w, notch_h = 174, 36
    x = BEZEL + (SCREEN_W - notch_w) / 2
    y = BEZEL
    return (
        f'<path id="notch" fill="#0a0a0a" d="M {x:.1f} {y} h {notch_w} '
        f'v {notch_h - 14} q 0 14 -14 14 h -{notch_w - 28} q -14 0 -14 -14 z"/>'
    )


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_svg(root: ViewNode, device_id: str = "iphone-14") -> str:
    device = get_device(device_id)
    global SCREEN_W, SCREEN_H
    SCREEN_W = device.width
    SCREEN_H = device.height
    root.frame_max_width = True
    boxes: list[Box] = []
    content_w = SCREEN_W - 36
    content_h = SCREEN_H - 88
    _, rh = measure(root, content_w)
    _place(root, BEZEL + 18, BEZEL + 54, content_w, max(rh, content_h), boxes)
    width = SCREEN_W + BEZEL * 2
    height = SCREEN_H + BEZEL * 2
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#1c1c1e"/>',
        f'<rect x="8" y="8" width="{width - 16}" height="{height - 16}" rx="54" fill="#0a0a0a"/>',
        f'<rect x="{BEZEL}" y="{BEZEL}" width="{SCREEN_W}" height="{SCREEN_H}" rx="40" fill="#000000"/>',
        _sensor(device.island),
        f'<text x="{BEZEL + 22}" y="{BEZEL + 28}" fill="#fff" font-family="ui-sans-serif,system-ui" font-size="13" font-weight="600">9:41</text>',
    ]
    for box in boxes:
        node = box.node
        if node.background:
            parts.append(
                f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.w:.1f}" height="{box.h:.1f}" rx="{node.corner:.1f}" fill="{node.background}" opacity="{node.opacity:.2f}"/>'
            )
        if node.kind == "Text" or (node.kind == "Button" and node.text):
            label = node.text
            size = 15 if node.kind == "Button" else node.font_size
            color = "#111111" if node.kind == "Button" and node.background in {None, "#ffffff"} else node.color
            if node.kind == "Button" and not node.background:
                parts.append(
                    f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.w:.1f}" height="{box.h:.1f}" rx="10" fill="#ffffff"/>'
                )
                color = "#111111"
            weight = "700" if node.weight == "bold" else "400"
            parts.append(
                f'<text x="{box.x + node.pad_left + 8:.1f}" y="{box.y + node.pad_top + size + 4:.1f}" fill="{color}" opacity="{node.opacity:.2f}" font-family="ui-monospace,monospace" font-size="{size:.0f}" font-weight="{weight}">{_esc(label)}</text>'
            )
        elif node.kind == "Divider":
            parts.append(
                f'<rect x="{box.x:.1f}" y="{box.y + box.h / 2:.1f}" width="{box.w:.1f}" height="1" fill="#333"/>'
            )
        elif node.kind not in {"VStack", "HStack", "ZStack", "Spacer", "screen"} and not node.children:
            parts.append(
                f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{max(box.w, 80):.1f}" height="24" rx="4" fill="#222"/>'
            )
            parts.append(
                f'<text x="{box.x + 6:.1f}" y="{box.y + 16:.1f}" fill="#aaa" font-family="ui-monospace,monospace" font-size="11">{_esc(node.kind)}</text>'
            )
        for note in node.notes[:1]:
            parts.append(
                f'<text x="{box.x:.1f}" y="{box.y + box.h + 11:.1f}" fill="#666" font-family="ui-monospace,monospace" font-size="9">.{_esc(note)}</text>'
            )
    parts.append(
        f'<text x="{BEZEL + 16}" y="{height - 18}" fill="#666" font-family="ui-monospace,monospace" font-size="11">OpenSwift sketch · not compiled Swift</text>'
    )
    parts.append("</svg>")
    _ = screen
    return "\n".join(parts)
