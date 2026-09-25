"""Paint a parsed sketch into one SVG picture of a phone screen."""

from __future__ import annotations

from dataclasses import dataclass

from openswift.devices import get_device, NotchType
from openswift.parse import ViewNode


@dataclass
class Box:
	x: float
	y: float
	w: float
	h: float
	node: ViewNode


def _text_width(text: str, size: float) -> float:
	return max(8, len(text) * size * 0.56)


_VERTICAL = {
	"VStack", "Form", "Section", "List", "ScrollView", "NavigationStack",
	"NavigationSplitView", "Group", "GroupBox",
}


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


def _sensor(device, x: float, y: float, screen_w: int) -> str:
	if device.notch_type == NotchType.DYNAMIC_ISLAND:
		width, height = 126, 36
		island_x = x + (screen_w - width) / 2
		island_y = y + 6
		return (
			f'<rect id="island" x="{island_x:.1f}" y="{island_y:.1f}" '
			f'width="{width}" height="{height}" rx="18" fill="#0a0a0a"/>'
		)
	elif device.notch_type == NotchType.CLASSIC:
		notch_w, notch_h = 194, 32
		notch_x = x + (screen_w - notch_w) / 2
		notch_y = y
		return (
			f'<path id="notch" fill="#0a0a0a" '
			f'd="M {notch_x:.1f} {notch_y} h {notch_w} '
			f'v {notch_h - 10} q 0 10 -10 10 h -{notch_w - 20} '
			f'q -10 0 -10 -10 z"/>'
		)
	elif device.notch_type == NotchType.REDUCED:
		notch_w, notch_h = 156, 32
		notch_x = x + (screen_w - notch_w) / 2
		notch_y = y
		return (
			f'<path id="notch" fill="#0a0a0a" '
			f'd="M {notch_x:.1f} {notch_y} h {notch_w} '
			f'v {notch_h - 10} q 0 10 -10 10 h -{notch_w - 20} '
			f'q -10 0 -10 -10 z"/>'
		)
	return ""


def _status_icons(device, x: float, y: float, screen_w: int) -> str:
	parts = []
	time_x = x + 16
	time_y = y + device.status_bar_height - 14
	parts.append(
		f'<text x="{time_x:.1f}" y="{time_y:.1f}" fill="#fff" '
		f'font-family="ui-sans-serif,system-ui" font-size="13" font-weight="600">9:41</text>'
	)
	if device.notch_type == NotchType.DYNAMIC_ISLAND:
		icon_x = x + screen_w - 100
	else:
		icon_x = x + screen_w - 80
	icon_y = y + device.status_bar_height - 14
	parts.append(
		f'<rect x="{icon_x:.1f}" y="{icon_y - 6:.1f}" width="24" height="12" rx="2" fill="none" stroke="#fff" stroke-width="1"/>'
	)
	parts.append(
		f'<rect x="{icon_x + 24:.1f}" y="{icon_y - 4:.1f}" width="4" height="8" fill="#fff"/>'
	)
	signal_x = icon_x - 30
	for i in range(4):
		h = 4 + i * 3
		parts.append(
			f'<rect x="{signal_x + i * 5:.1f}" y="{icon_y - h:.1f}" width="3" height="{h}" fill="#fff" opacity="{0.5 + i * 0.125}"/>'
		)
	wifi_x = signal_x - 20
	parts.append(
		f'<path d="M {wifi_x:.1f} {icon_y + 2:.1f} a 8 8 0 0 1 16 0" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"/>'
	)
	parts.append(
		f'<path d="M {wifi_x + 4:.1f} {icon_y + 6:.1f} a 4 4 0 0 1 8 0" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>'
	)
	return "\n".join(parts)


def _home_indicator(device, x: float, y: float, screen_w: int, screen_h: int) -> str:
	indicator_w = 136
	indicator_h = 5
	indicator_x = x + (screen_w - indicator_w) / 2
	indicator_y = y + screen_h - indicator_h - 8
	return (
		f'<rect x="{indicator_x:.1f}" y="{indicator_y:.1f}" '
		f'width="{indicator_w}" height="{indicator_h}" rx="{indicator_h/2}" fill="#fff" opacity="0.36"/>'
	)


def _esc(text: str) -> str:
    return (
        text.replace("&", "&")
        .replace("<", "<")
        .replace(">", ">")
        .replace('"', '"')
    )
SCREEN_W = 390
SCREEN_H = 780
BEZEL = 28


def render_svg(root: ViewNode, device_id: str = "iphone-14") -> str:
	device = get_device(device_id)
	global SCREEN_W, SCREEN_H, BEZEL
	SCREEN_W = device.width
	SCREEN_H = device.height
	BEZEL = device.bezel_side
	root.frame_max_width = True
	boxes: list[Box] = []
	content_w = SCREEN_W - 36
	content_h = SCREEN_H - 88
	_, rh = measure(root, content_w)
	_place(root, BEZEL + 18, BEZEL + 54, content_w, max(rh, content_h), boxes)
	phone_w = SCREEN_W + device.bezel_side * 2
	phone_h = SCREEN_H + device.bezel_top + device.bezel_bottom
	screen_x = device.bezel_side
	screen_y = device.bezel_top
	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" width="{phone_w}" height="{phone_h}" viewBox="0 0 {phone_w} {phone_h}">',
		f'<rect width="100%" height="100%" fill="#1c1c1e"/>',
		f'<rect x="4" y="4" width="{phone_w - 8}" height="{phone_h - 8}" rx="{device.corner_radius}" fill="#0a0a0a"/>',
		f'<rect x="{screen_x}" y="{screen_y}" width="{SCREEN_W}" height="{SCREEN_H}" rx="{device.screen_radius}" fill="#000000"/>',
	]
	parts.append(_sensor(device, screen_x, screen_y, SCREEN_W))
	parts.append(_status_icons(device, screen_x, screen_y, SCREEN_W))
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
	parts.append(_home_indicator(device, screen_x, screen_y, SCREEN_W, SCREEN_H))
	power_y = screen_y + 140
	parts.append(
		f'<rect x="{screen_x + SCREEN_W + device.bezel_side - 6:.1f}" y="{power_y:.1f}" '
		f'width="4" height="48" rx="2" fill="#2a2a2e"/>'
	)
	if device.has_action_button:
		parts.append(
			f'<rect x="{screen_x + SCREEN_W + device.bezel_side - 6:.1f}" y="{power_y - 60:.1f}" '
			f'width="4" height="28" rx="2" fill="#2a2a2e"/>'
		)
	if device.has_camera_control:
		parts.append(
			f'<rect x="{screen_x + SCREEN_W + device.bezel_side - 6:.1f}" y="{power_y + 60:.1f}" '
			f'width="4" height="28" rx="2" fill="#2a2a2e"/>'
		)
	vol_y = screen_y + 140
	parts.append(
		f'<rect x="{screen_x - device.bezel_side + 2:.1f}" y="{vol_y:.1f}" '
		f'width="3" height="48" rx="1.5" fill="#2a2a2e"/>'
	)
	parts.append(
		f'<rect x="{screen_x - device.bezel_side + 2:.1f}" y="{vol_y + 65:.1f}" '
		f'width="3" height="48" rx="1.5" fill="#2a2a2e"/>'
	)
	parts.append(
		f'<rect x="{screen_x - device.bezel_side + 1:.1f}" y="{vol_y - 30:.1f}" '
		f'width="5" height="20" rx="2" fill="#2a2a2e"/>'
	)
	parts.append(
		f'<text x="{screen_x + 16}" y="{phone_h - 18}" fill="#666" font-family="ui-monospace,monospace" font-size="11">OpenSwift sketch \xb7 not compiled Swift</text>'
	)
	parts.append("</svg>")
	return "\n".join(parts)
