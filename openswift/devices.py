"""Phone frames the sketch can be drawn into.

The notch is the camera housing stuck to the top edge (iPhone 11 through 14
and 14 Plus). The floating pill, Dynamic Island, starts on iPhone 14 Pro.
Every iPhone 15 and later uses that pill.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    width: int
    height: int
    island: bool


DEVICES: dict[str, Device] = {
    item.id: item
    for item in (
        Device("iphone-11", "iPhone 11", 414, 896, False),
        Device("iphone-12", "iPhone 12", 390, 844, False),
        Device("iphone-13", "iPhone 13", 390, 844, False),
        Device("iphone-14", "iPhone 14", 390, 844, False),
        Device("iphone-14-plus", "iPhone 14 Plus", 428, 926, False),
        Device("iphone-14-pro", "iPhone 14 Pro", 393, 852, True),
        Device("iphone-15", "iPhone 15", 393, 852, True),
        Device("iphone-16", "iPhone 16", 393, 852, True),
        Device("iphone-16-pro", "iPhone 16 Pro", 402, 874, True),
    )
}


def get_device(device_id: str) -> Device:
    return DEVICES.get(device_id, DEVICES["iphone-14"])
