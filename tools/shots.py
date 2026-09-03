"""Regenerate design/screenshots/ from the card itself.

The originals came out of the design tool and had a family's names rendered
into the pixels. These come from the real card and the real mock data, so they
can be regenerated whenever the card changes — and they cannot drift from it.

    python3 -m http.server 8765 &
    .venv/bin/python tools/shots.py

Needs google-chrome and Pillow. The clock is pinned to 2:39 PM inside
dev/shot.html, so the output is byte-stable across runs.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "design" / "screenshots"
BASE = "http://localhost:8765/dev/shot.html?state="

SHOTS = {
    "ordinary": "01-card-ordinary.png",
    "empty": "02-card-empty-day.png",
    "stale": "03-card-stale-source.png",
    "busy": "07-card-busy-day.png",
}

# Tall enough for the longest state; the transparent remainder is cropped off.
WINDOW = (520, 2400)


def chrome() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium"):
        path = shutil.which(name)
        if path:
            return path
    sys.exit("no chrome on PATH")


def capture(state: str, dest: pathlib.Path, binary: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        raw = pathlib.Path(tmp) / "raw.png"
        subprocess.run(
            [
                binary,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                # Transparent page background is what makes the crop possible.
                "--default-background-color=00000000",
                f"--window-size={WINDOW[0]},{WINDOW[1]}",
                "--virtual-time-budget=4000",
                f"--user-data-dir={tmp}/profile",
                f"--screenshot={raw}",
                BASE + state,
            ],
            check=True,
            capture_output=True,
        )
        img = Image.open(raw).convert("RGBA")
        box = img.getbbox()  # everything that is not fully transparent
        if box is None:
            sys.exit(f"{state}: captured nothing — is the harness being served?")
        img.crop(box).save(dest)
        print(f"{dest.relative_to(ROOT)}  {box[2] - box[0]}×{box[3] - box[1]}")


def main() -> None:
    binary = chrome()
    OUT.mkdir(parents=True, exist_ok=True)
    for state, name in SHOTS.items():
        capture(state, OUT / name, binary)


if __name__ == "__main__":
    main()
