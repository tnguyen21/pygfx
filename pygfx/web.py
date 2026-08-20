"""Mutation-grid explorer: `pygfx-web photo.jpg`

Serves a 3x3 grid: top-left is the current parent, the rest are random
perturbations of it. Click a tile to make it the new parent and re-mutate.
Save writes a full-res PNG next to the source image and prints the params.
"""

import argparse
import json
import random
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

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

SLIDERS = {  # name: (max, default) -- strength is doubled so ints give half-steps
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

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>pygfx explorer</title>
<style>
  body { background:#14161a; color:#ccc; font:14px system-ui; margin:16px; }
  #grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
  figure { margin:0; }
  img { width:100%; display:block; cursor:pointer; border:2px solid transparent; }
  figure.parent img { border-color:#6cf; }
  figcaption { font:11px monospace; color:#889; padding:4px 0; display:flex; justify-content:space-between; }
  button { background:#2a2e36; color:#ccc; border:0; padding:2px 8px; cursor:pointer; }
  #bar { margin-bottom:12px; display:flex; gap:16px; align-items:center; }
</style>
<div id="bar">
  <label>wildness <input id="wild" type="range" min="1" max="10" value="3"></label>
  <button onclick="mutate()">mutate</button>
  <button onclick="mutate(true)">full random</button>
  <span>click a tile to make it the parent</span>
</div>
<div id="grid"></div>
<script>
async function mutate(rand) {
  const wild = document.getElementById('wild').value;
  const tiles = await (await fetch(`/grid?wild=${wild}${rand ? '&random=1' : ''}`)).json();
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  for (const t of tiles) {
    const fig = document.createElement('figure');
    if (t.parent) fig.className = 'parent';
    fig.innerHTML = `<img src="/img/${t.id}">
      <figcaption><span>${t.label}</span><button>save</button></figcaption>`;
    fig.querySelector('img').onclick = async () => { await fetch(`/pick/${t.id}`); mutate(); };
    fig.querySelector('button').onclick = async () => alert(await (await fetch(`/save/${t.id}`)).text());
    grid.appendChild(fig);
  }
}
mutate();
</script>
"""

STATE = {"parent": {name: default for name, (_mx, default) in SLIDERS.items()}, "tiles": {}, "next_id": 0, "saves": 0}
IMAGES = {}  # "full" / "preview" / "path", set in main()


def mutated(parent, wild):
    p = dict(parent)
    for name, (mx, _default) in SLIDERS.items():
        if name in ("dither", "palette"):
            if random.random() < wild / 12:
                p[name] = random.randint(0, mx)
        else:
            p[name] = min(mx, max(0, p[name] + round(random.gauss(0, mx * wild / 25))))
    return p


def label(p):
    return " ".join(f"{k[:2]}{v}" for k, v in p.items())


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _reply(self, body, ctype="text/plain"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        parts = url.path.strip("/").split("/")

        if url.path == "/":
            self._reply(PAGE, "text/html")
        elif url.path == "/grid":
            q = parse_qs(url.query)
            wild = int(q.get("wild", ["3"])[0])
            full_random = "random" in q
            tiles = []
            for i in range(9):
                if full_random:
                    p = {name: random.randint(0, mx) for name, (mx, _d) in SLIDERS.items()}
                else:
                    p = STATE["parent"] if i == 0 else mutated(STATE["parent"], wild)
                tid = STATE["next_id"] = STATE["next_id"] + 1
                STATE["tiles"][tid] = p
                tiles.append({"id": tid, "label": label(p), "parent": not full_random and i == 0})
            self._reply(json.dumps(tiles), "application/json")
        elif parts[0] in ("img", "pick", "save") and len(parts) == 2 and (p := STATE["tiles"].get(int(parts[1]))):
            if parts[0] == "img":
                _ok, buf = cv2.imencode(".png", render(IMAGES["preview"], p))
                self._reply(buf.tobytes(), "image/png")
            elif parts[0] == "pick":
                STATE["parent"] = p
                self._reply("ok")
            else:
                STATE["saves"] += 1
                out_path = IMAGES["path"].rsplit(".", 1)[0] + f"_x{STATE['saves']}.png"
                cv2.imwrite(out_path, render(IMAGES["full"], p))
                print(f"saved {out_path}  {p}")
                self._reply(f"saved {out_path}\n{p}")
        else:
            self.send_error(404)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--port", type=int, default=8712)
    parser.add_argument("--preview-width", type=int, default=420, help="Tile render width; saves use full res.")
    args = parser.parse_args()

    full = cv2.imread(args.image)
    if full is None:
        print(f"Error: could not read {args.image}")
        sys.exit(1)
    scale = min(1.0, args.preview_width / full.shape[1])
    IMAGES.update(full=full, preview=cv2.resize(full, None, fx=scale, fy=scale) if scale < 1.0 else full, path=args.image)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"http://127.0.0.1:{args.port}")
    webbrowser.open(f"http://127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
