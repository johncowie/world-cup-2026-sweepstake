#!/usr/bin/env python3
"""Crops individual avatars from the team photo grid.

Run once whenever the source image changes:
    python3 extract_avatars.py
"""

import os
from PIL import Image, ImageEnhance

SOURCE = "Screenshot 2026-06-17 at 17.29.52.png"
OUT_DIR = "avatars"
SIZE = 120  # output square size in px

# Grid layout: (row, col) are 0-indexed in the 5-col x 4-row team photo
PLAYERS = {
    "micarla": (0, 0),
    "bill":    (0, 2),
    "felix":   (1, 0),
    "beth":    (1, 1),
    "corin":   (1, 3),
    "john":    (1, 4),
    "phil":    (2, 1),
    "aquiles": (2, 2),
    "liam":    (2, 4),
    "belen":   (3, 2),
}


def crop_avatar(img, row, col, cols=5, rows=4):
    w, h = img.size
    cell_w = w / cols
    cell_h = h / rows

    # Photo portrait sits at ~26.5% across and ~50% down the cell
    cx = col * cell_w + cell_w * 0.265
    cy = row * cell_h + cell_h * 0.50
    side = cell_w * 0.25

    crop = img.crop((cx - side / 2, cy - side * 0.60, cx + side / 2, cy + side * 0.60))
    crop = ImageEnhance.Brightness(crop).enhance(1.3)
    return crop.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    img = Image.open(SOURCE).convert("RGB")  # strip alpha for JPEG output

    for name, (row, col) in PLAYERS.items():
        avatar = crop_avatar(img, row, col)
        out_path = os.path.join(OUT_DIR, f"{name}.jpg")
        avatar.save(out_path, "JPEG", quality=85)
        print(f"Saved {out_path}")

    print(f"\nDone. {len(PLAYERS)} avatars saved to {OUT_DIR}/")


if __name__ == "__main__":
    main()
