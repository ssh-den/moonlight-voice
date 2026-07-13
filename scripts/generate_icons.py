#!/usr/bin/env python3
"""Render Moonlight Voice's Web UI moon-star SVG as rounded application icons.

Requires macOS's built-in ``sips`` command. The source SVG remains the single
source of truth for the moon-and-star mark used by the Web UI.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ICON = ROOT / "moonlight-voice/moonlight_voice/static/assets/icons/moon-star.svg"
TARGETS = {
    ROOT / "brand/icon.png": 512,
    ROOT / "moonlight-voice/icon.png": 512,
}
CANVAS_SIZE = 1024
CORNER_RADIUS = 224
ICON_SIZE = 600
BACKGROUND = "#17132a"


def _svg_mark(path: Path) -> tuple[str, str]:
    """Return the contents and root fill colour from an SVG icon."""
    source = path.read_text(encoding="utf-8")
    match = re.search(
        r"<svg\b(?P<attributes>[^>]*)>(?P<contents>.*)</svg>\s*$", source, flags=re.DOTALL
    )
    if not match:
        raise ValueError(f"Could not read SVG contents from {path}")
    fill = re.search(r"""\bfill=["'](?P<fill>[^"']+)["']""", match["attributes"])
    if not fill:
        raise ValueError(f"The root SVG element needs a fill colour: {path}")
    return match["contents"].strip(), fill["fill"]


def _app_icon_svg(mark: str, fill: str) -> str:
    """Place the Web UI mark on an rounded-square background."""
    offset = (CANVAS_SIZE - ICON_SIZE) // 2
    scale = ICON_SIZE / 24
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_SIZE}" height="{CANVAS_SIZE}" viewBox="0 0 {CANVAS_SIZE} {CANVAS_SIZE}">
  <rect width="{CANVAS_SIZE}" height="{CANVAS_SIZE}" rx="{CORNER_RADIUS}" fill="{BACKGROUND}"/>
  <g fill="{fill}" transform="translate({offset} {offset}) scale({scale})">
    {mark}
  </g>
</svg>
'''


def main() -> None:
    """Generate all application-icon PNG files."""
    mark, fill = _svg_mark(SOURCE_ICON)
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "moonlight-voice-app-icon.svg"
        source.write_text(_app_icon_svg(mark, fill), encoding="utf-8")
        for target, size in TARGETS.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [
                    "sips",
                    "--setProperty",
                    "format",
                    "png",
                    "--resampleHeightWidth",
                    str(size),
                    str(size),
                    str(source),
                    "--out",
                    str(target),
                ],
                check=True,
            )
            print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
