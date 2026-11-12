"""Phone frames the sketch can be drawn into.

The notch is the camera housing stuck to the top edge (iPhone 11 through 14
and 14 Plus). The floating pill, Dynamic Island, starts on iPhone 14 Pro.
Every iPhone 15 and later uses that pill.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class NotchType(Enum):
    NONE = "none"
    CLASSIC = "classic"       # iPhone 11, 12 (ancho)
    REDUCED = "reduced"       # iPhone 13, 14 (notch un 20% más estrecho)
    DYNAMIC_ISLAND = "dynamic_island"  # iPhone 14 Pro en adelante


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    width: int
    height: int
    notch_type: NotchType
    # Dimensiones físicas para render realista
    bezel_top: int       # bisel superior (incluye notch/isla)
    bezel_bottom: int    # bisel inferior
    bezel_side: int      # bisel lateral
    corner_radius: int   # radio de la carcasa externa
    screen_radius: int   # radio de la pantalla (esquinas recortadas)
    # Botones laterales
    has_action_button: bool       # iPhone 15 Pro / 16 Pro
    has_camera_control: bool      # iPhone 16 / 16 Pro
    # Posición de elementos (en puntos lógicos)
    status_bar_height: int
    home_indicator_height: int
    idiom: str = "phone"          # "phone" o "pad"


DEVICES: dict[str, Device] = {
    item.id: item
    for item in (
        # iPhone 11 - LCD, notch clásico ancho, bordes gruesos
        Device(
            "iphone-11", "iPhone 11", 414, 896,
            NotchType.CLASSIC,
            bezel_top=36, bezel_bottom=24, bezel_side=20,
            corner_radius=54, screen_radius=40,
            has_action_button=False, has_camera_control=False,
            status_bar_height=44, home_indicator_height=5
        ),
        # iPhone 12/12 mini - OLED, notch clásico, bordes planos pero gruesos
        Device(
            "iphone-12", "iPhone 12", 390, 844,
            NotchType.CLASSIC,
            bezel_top=34, bezel_bottom=22, bezel_side=18,
            corner_radius=48, screen_radius=36,
            has_action_button=False, has_camera_control=False,
            status_bar_height=47, home_indicator_height=5
        ),
        # iPhone 13/13 mini - notch reducido 20%
        Device(
            "iphone-13", "iPhone 13", 390, 844,
            NotchType.REDUCED,
            bezel_top=34, bezel_bottom=22, bezel_side=18,
            corner_radius=48, screen_radius=36,
            has_action_button=False, has_camera_control=False,
            status_bar_height=47, home_indicator_height=5
        ),
        # iPhone 14 - notch reducido
        Device(
            "iphone-14", "iPhone 14", 390, 844,
            NotchType.REDUCED,
            bezel_top=34, bezel_bottom=22, bezel_side=18,
            corner_radius=48, screen_radius=36,
            has_action_button=False, has_camera_control=False,
            status_bar_height=47, home_indicator_height=5
        ),
        # iPhone 14 Plus - notch reducido, más grande
        Device(
            "iphone-14-plus", "iPhone 14 Plus", 428, 926,
            NotchType.REDUCED,
            bezel_top=36, bezel_bottom=24, bezel_side=20,
            corner_radius=50, screen_radius=38,
            has_action_button=False, has_camera_control=False,
            status_bar_height=47, home_indicator_height=5
        ),
        # iPhone 14 Pro - primera Dynamic Island
        Device(
            "iphone-14-pro", "iPhone 14 Pro", 393, 852,
            NotchType.DYNAMIC_ISLAND,
            bezel_top=32, bezel_bottom=20, bezel_side=16,
            corner_radius=46, screen_radius=34,
            has_action_button=False, has_camera_control=False,
            status_bar_height=52, home_indicator_height=5
        ),
        # iPhone 15 - Dynamic Island base
        Device(
            "iphone-15", "iPhone 15", 393, 852,
            NotchType.DYNAMIC_ISLAND,
            bezel_top=30, bezel_bottom=18, bezel_side=14,
            corner_radius=44, screen_radius=32,
            has_action_button=False, has_camera_control=False,
            status_bar_height=52, home_indicator_height=5
        ),
        # iPhone 16 - Dynamic Island + Camera Control
        Device(
            "iphone-16", "iPhone 16", 393, 852,
            NotchType.DYNAMIC_ISLAND,
            bezel_top=30, bezel_bottom=18, bezel_side=14,
            corner_radius=44, screen_radius=32,
            has_action_button=False, has_camera_control=True,
            status_bar_height=52, home_indicator_height=5
        ),
        # iPhone 16 Pro - Dynamic Island + Action Button + Camera Control
        Device(
            "iphone-16-pro", "iPhone 16 Pro", 402, 874,
            NotchType.DYNAMIC_ISLAND,
            bezel_top=28, bezel_bottom=16, bezel_side=12,
            corner_radius=42, screen_radius=30,
            has_action_button=True, has_camera_control=True,
            status_bar_height=52, home_indicator_height=5
        ),
        # iPhone 15 Plus - Dynamic Island, pantalla grande
        Device(
            "iphone-15-plus", "iPhone 15 Plus", 430, 932,
            NotchType.DYNAMIC_ISLAND,
            bezel_top=30, bezel_bottom=18, bezel_side=14,
            corner_radius=46, screen_radius=34,
            has_action_button=False, has_camera_control=False,
            status_bar_height=52, home_indicator_height=5
        ),
        # iPhone 15 Pro - Dynamic Island + Action Button
        Device(
            "iphone-15-pro", "iPhone 15 Pro", 393, 852,
            NotchType.DYNAMIC_ISLAND,
            bezel_top=28, bezel_bottom=16, bezel_side=12,
            corner_radius=42, screen_radius=30,
            has_action_button=True, has_camera_control=False,
            status_bar_height=52, home_indicator_height=5
        ),
        # iPhone 16 Plus - Dynamic Island + Camera Control
        Device(
            "iphone-16-plus", "iPhone 16 Plus", 430, 932,
            NotchType.DYNAMIC_ISLAND,
            bezel_top=30, bezel_bottom=18, bezel_side=14,
            corner_radius=46, screen_radius=34,
            has_action_button=False, has_camera_control=True,
            status_bar_height=52, home_indicator_height=5
        ),
        # iPhone 16 Pro Max
        Device(
            "iphone-16-pro-max", "iPhone 16 Pro Max", 440, 956,
            NotchType.DYNAMIC_ISLAND,
            bezel_top=28, bezel_bottom=16, bezel_side=12,
            corner_radius=44, screen_radius=32,
            has_action_button=True, has_camera_control=True,
            status_bar_height=52, home_indicator_height=5
        ),
    )
}


ORIENTATIONS = ("portrait", "landscape")


def _ipad(id: str, name: str, width: int, height: int, radius: int) -> Device:
    return Device(
        id, name, width, height, NotchType.NONE,
        bezel_top=22, bezel_bottom=22, bezel_side=22,
        corner_radius=radius + 14, screen_radius=radius,
        has_action_button=False, has_camera_control=False,
        status_bar_height=24, home_indicator_height=5, idiom="pad",
    )


DEVICES.update({
    item.id: item
    for item in (
        _ipad("ipad-10", "iPad (10th gen)", 820, 1180, 22),
        _ipad("ipad-air-11", "iPad Air 11\"", 820, 1180, 24),
        _ipad("ipad-pro-11", "iPad Pro 11\"", 834, 1210, 24),
        _ipad("ipad-pro-13", "iPad Pro 13\"", 1032, 1376, 26),
    )
})


def expand_devices(spec: str) -> list[str]:
    """`iphone-15,ipad-pro-11`, or a preset: `phones`, `ipads`, `all`."""
    ids: list[str] = []
    for part in (item.strip() for item in spec.split(",") if item.strip()):
        if part == "all":
            ids.extend(DEVICES)
        elif part == "phones":
            ids.extend(i for i, d in DEVICES.items() if d.idiom == "phone")
        elif part == "ipads":
            ids.extend(i for i, d in DEVICES.items() if d.idiom == "pad")
        elif part in DEVICES:
            ids.append(part)
        else:
            raise ValueError(f"unknown device {part}. Known: {', '.join(DEVICES)}")
    return list(dict.fromkeys(ids)) or ["iphone-14"]


def get_device(device_id: str, orientation: str = "portrait") -> Device:
    """The device, turned on its side when orientation is landscape."""
    device = DEVICES.get(device_id, DEVICES["iphone-14"])
    if orientation != "landscape":
        return device
    return replace(
        device,
        width=device.height,
        height=device.width,
        bezel_top=device.bezel_side,
        bezel_bottom=device.bezel_side,
        bezel_side=device.bezel_top,
    )
