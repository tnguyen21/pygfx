"""Live playground: `pygfx-lab photo.jpg`

Sliders drive the pipeline; saving shaders.py in your editor hot-reloads it.
Keys: s = save full-res render + print its params, q/esc = quit.
"""

import argparse
import importlib
import os
import sys

import cv2

from pygfx import shaders

PALETTES = [  # (ink, paper) in BGR
    ((16, 8, 4), (235, 200, 140)),  # black on cyan
    ((90, 20, 60), (230, 175, 195)),  # purple on lavender
    ((45, 40, 40), (240, 240, 235)),  # ink on paper white
    ((30, 20, 120), (190, 225, 245)),  # brick red on cream
    ((60, 30, 10), (250, 250, 250)),  # navy on white
]
DITHERS = ["noise", "bayer2", "bayer4", "halftone"]

SLIDERS = {  # name: (max, default) -- trackbars are int-only, so strength is doubled
    "strength": (40, 16),
    "dither": (len(DITHERS) - 1, 0),
    "cell": (16, 6),
    "angle": (90, 15),
    "palette": (len(PALETTES) - 1, 0),
    "grain": (40, 0),
    "shift": (12, 0),
}


def render(img, p):
    x = shaders.tone_curve(img, strength=max(p["strength"], 1) / 2)
    kind = DITHERS[p["dither"]]
    if kind == "noise":
        mask = shaders.noise_dither(x)
    elif kind == "bayer2":
        mask = shaders.ordered_dither(x, shaders.BAYER2)
    elif kind == "bayer4":
        mask = shaders.ordered_dither(x, shaders.BAYER4)
    else:
        mask = shaders.halftone(x, cell=max(p["cell"], 2), angle=p["angle"])
    ink, paper = PALETTES[p["palette"]]
    out = shaders.duotone(mask, ink=ink, paper=paper)
    if p["grain"]:
        out = shaders.grain(out, amount=p["grain"])
    if p["shift"]:
        out = shaders.plate_shift(out, dx=p["shift"], dy=p["shift"] // 3)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--preview-width", type=int, default=800, help="Downscale preview for fast renders; saves use full res.")
    args = parser.parse_args()

    full = cv2.imread(args.image)
    if full is None:
        print(f"Error: could not read {args.image}")
        sys.exit(1)
    scale = min(1.0, args.preview_width / full.shape[1])
    preview = cv2.resize(full, None, fx=scale, fy=scale) if scale < 1.0 else full

    win = "pygfx lab  [s]ave [q]uit"
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)
    for name, (mx, default) in SLIDERS.items():
        cv2.createTrackbar(name, win, default, mx, lambda _v: None)

    last = None
    mtime = os.path.getmtime(shaders.__file__)
    saves = 0
    while True:
        key = cv2.waitKey(50) & 0xFF
        if key in (ord("q"), 27):
            break

        m = os.path.getmtime(shaders.__file__)
        if m != mtime:
            mtime = m
            try:
                importlib.reload(shaders)
                print("reloaded shaders.py")
                last = None
            except Exception as e:  # noqa: BLE001 -- keep the loop alive through mid-edit syntax errors
                print(f"reload failed: {e}")

        p = {name: cv2.getTrackbarPos(name, win) for name in SLIDERS}
        if p != last:
            try:
                cv2.imshow(win, render(preview, p))
            except Exception as e:  # noqa: BLE001 -- a broken reloaded shader shouldn't kill the window
                print(f"render failed: {e}")
            last = p

        if key == ord("s"):
            saves += 1
            out_path = args.image.rsplit(".", 1)[0] + f"_lab{saves}.png"
            cv2.imwrite(out_path, render(full, p))
            print(f"saved {out_path}  {p}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
