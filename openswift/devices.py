"""Phone frames the sketch can be drawn into.

The notch is the camera housing stuck to the top edge (iPhone 11 through 14
and 14 Plus). The floating pill, Dynamic Island, starts on iPhone 14 Pro.
Every iPhone 15 and later uses that pill.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    )
}


def get_device(device_id: str) -> Device:
    return DEVICES.get(device_id, DEVICES["iphone-14"])
