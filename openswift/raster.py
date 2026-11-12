"""Turn the SVG into a PNG, so the picture is the one the renderer draws.

The PNG used to be painted by a second, hand-written pipeline that could
drift from the SVG. Now the SVG is the only drawing and a rasterizer reads it.
OpenSwift looks for one that is already installed; with none, it falls back to
a plain built-in painter and says so.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")


def _size(svg: str) -> tuple[int, int]:
    match = re.search(r'width="(\d+(?:\.\d+)?)" height="(\d+(?:\.\d+)?)"', svg)
    if not match:
        raise ValueError("svg has no size")
    return int(float(match.group(1))), int(float(match.group(2)))


def _chrome() -> str | None:
    override = os.environ.get("OPENSWIFT_BROWSER")
    if override and Path(override).is_file():
        return override
    for name in CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    for root in ("/opt/pw-browsers",):
        for candidate in sorted(Path(root).glob("chromium-*/chrome-linux*/chrome")):
            return str(candidate)
    return None


def available_engines() -> list[str]:
    engines = []
    try:
        import cairosvg  # noqa: F401

        engines.append("cairosvg")
    except ImportError:
        pass
    for tool in ("rsvg-convert", "inkscape"):
        if shutil.which(tool):
            engines.append(tool)
    if _chrome():
        engines.append("chrome")
    return engines


def svg_to_png(svg: str, path: Path, scale: int = 2) -> str | None:
    """Write `svg` to `path` as a PNG. Returns the engine used, or None if none could."""
    width, height = _size(svg)
    path.parent.mkdir(parents=True, exist_ok=True)
    for engine in available_engines():
        try:
            if _run(engine, svg, path, width, height, scale) and path.is_file() and path.stat().st_size > 0:
                return engine
        except (OSError, subprocess.SubprocessError, ValueError):
            continue
    return None


def _run(engine: str, svg: str, path: Path, width: int, height: int, scale: int) -> bool:
    if engine == "cairosvg":
        import cairosvg

        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(path), scale=scale)
        return True
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "sketch.svg"
        src.write_text(svg, encoding="utf-8")
        if engine == "rsvg-convert":
            cmd = ["rsvg-convert", "-z", str(scale), "-o", str(path), str(src)]
        elif engine == "inkscape":
            cmd = ["inkscape", str(src), "--export-type=png", f"--export-filename={path}", f"--export-width={width * scale}"]
        else:
            page = Path(tmp) / "sketch.html"
            page.write_text(
                f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;background:transparent}}'
                f"svg{{display:block}}</style>{svg}",
                encoding="utf-8",
            )
            cmd = [
                _chrome() or "chrome", "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                "--default-background-color=00000000", f"--force-device-scale-factor={scale}",
                f"--window-size={width},{height}", f"--screenshot={path}", page.as_uri(),
            ]
        done = subprocess.run(cmd, capture_output=True, timeout=60)
        return done.returncode == 0
