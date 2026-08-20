"""Mutation-grid explorer + single-image editor: `pygfx-web photo.jpg`

Grid (/): top-left tile is the current parent, the rest are random
perturbations of it -- including added/dropped plates. Click a tile to make
it the new parent; "edit" opens it in the editor.

Edit (/edit): global sliders + paper color, and plates as table rows. A plate
is (tonal band, dither, screen geometry, ink hex) and plates composite in
order, later plates overprinting earlier ones. Save writes a full-res PNG
next to the source image and prints the params.

The params are just codegen: to_code(p) emits the python for the look and
render() execs it, so the editor's code box shows exactly what runs. Edit the
code and "run code" to go off-road ("none" dither / strength 0 turn stages off
from the controls side).
"""

import argparse
import json
import random
import re
import sys
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

DITHERS = ["noise", "bayer2", "bayer4", "halftone", "none"]  # "none" appended so saved param URLs keep their dither indices
GLOBALS = {"strength": (40, 16), "grain": (40, 0), "shift": (12, 0)}
PLATE = {"mid": (100, 50), "dither": (len(DITHERS) - 1, 3), "cell": (16, 6), "angle": (90, 15)}
HEX = re.compile(r"^#[0-9a-f]{6}$")


def bgr(hex_):
    return (int(hex_[5:7], 16), int(hex_[3:5], 16), int(hex_[1:3], 16))


def default_params():
    return {
        "strength": 16,
        "grain": 0,
        "shift": 0,
        "paper": "#8cc8eb",
        "paper_original": False,
        "plates": [
            {"mid": 65, "dither": 3, "cell": 6, "angle": 45, "ink": "#48687d", "original": False},
            {"mid": 35, "dither": 3, "cell": 6, "angle": 15, "ink": "#040810", "original": False},
        ],
    }


def _hex(v, fallback):
    return v.lower() if isinstance(v, str) and HEX.match(v.lower()) else fallback


def clean(p):
    """Clamp untrusted params into range and fill in anything missing."""
    out = {name: min(mx, max(0, int(p.get(name, d)))) for name, (mx, d) in GLOBALS.items()}
    out["paper"] = _hex(p.get("paper"), "#fafafa")
    out["paper_original"] = bool(p.get("paper_original"))
    plates = p.get("plates") or default_params()["plates"]
    out["plates"] = [
        {name: min(mx, max(0, int(pl.get(name, d)))) for name, (mx, d) in PLATE.items()}
        | {"ink": _hex(pl.get("ink"), "#111111"), "original": bool(pl.get("original"))}
        for pl in plates[:8]
    ]
    return out


def _mask_code(plate):
    kind = DITHERS[plate["dither"]]
    if kind == "noise":
        return "noise_dither(toned)"
    if kind in ("bayer2", "bayer4"):
        return f"ordered_dither(toned, {kind.upper()})"
    if kind == "none":
        return "threshold(toned)"
    return f"halftone(toned, cell={max(plate['cell'], 2)}, angle={plate['angle']})"


def to_code(p):
    """Emit the python that IS this look; render() execs it, the editor shows it."""
    base = "img.copy()  # paper: the image itself" if p["paper_original"] else f"np.full(img.shape, {bgr(p['paper'])}, np.uint8)  # paper {p['paper']}"
    lines = ["from pygfx.shaders import *", "", f"out = {base}"]
    for i, plate in enumerate(p["plates"]):
        lines.append(f"\n# plate {i + 1}: {'original color' if plate['original'] else 'ink ' + plate['ink']}")
        if p["strength"]:
            # higher mid crushes more tones dark -> heavier ink coverage on this plate
            lines.append(f"toned = tone_curve(img, strength={p['strength'] / 2}, mid={plate['mid'] / 100})")
        else:
            lines.append("toned = img  # strength 0: tone curve off (mid inert)")
        lines.append(f"m = {_mask_code(plate)}")
        lines.append(f"out[m == 0] = {'img[m == 0]' if plate['original'] else bgr(plate['ink'])}")
    if p["grain"]:
        lines.append(f"\nout = grain(out, amount={p['grain']})")
    if p["shift"]:
        lines.append(f"\nout = plate_shift(out, dx={p['shift']}, dy={p['shift'] // 3})")
    return "\n".join(lines) + "\n"


def run_code(code, img):
    # running arbitrary python is the feature: localhost-only, single-user tool
    ns = {"img": img}
    exec(code, ns)  # noqa: S102 -- running your own python is the feature
    return np.asarray(ns["out"], np.uint8)


def render(img, p):
    return run_code(to_code(p), img)


def _nudge(v, mx, wild):
    return min(mx, max(0, v + round(random.gauss(0, mx * wild / 25))))


def _nudge_hex(hex_, wild):
    ch = [min(255, max(0, c + round(random.gauss(0, 8 * wild)))) for c in reversed(bgr(hex_))]
    return "#{:02x}{:02x}{:02x}".format(*ch)


def _random_hex(lo=0, hi=255):
    return "#{:02x}{:02x}{:02x}".format(*(random.randint(lo, hi) for _ in range(3)))


def random_plate():
    return {name: random.randint(0, mx) for name, (mx, _d) in PLATE.items()} | {
        "ink": _random_hex(0, 160),
        "original": random.random() < 0.15,
    }


def random_params():
    return {name: random.randint(0, mx) for name, (mx, _d) in GLOBALS.items()} | {
        "paper": _random_hex(140, 255),
        "paper_original": random.random() < 0.15,
        "plates": [random_plate() for _ in range(random.randint(1, 3))],
    }


def mutated(parent, wild):
    p = json.loads(json.dumps(parent))
    for name, (mx, _d) in GLOBALS.items():
        p[name] = _nudge(p[name], mx, wild)
    p["paper"] = _nudge_hex(p["paper"], wild)
    if random.random() < wild / 25:
        p["paper_original"] = not p["paper_original"]
    for plate in p["plates"]:
        for name, (mx, _d) in PLATE.items():
            if name == "dither":
                if random.random() < wild / 12:
                    plate[name] = random.randint(0, mx)
            else:
                plate[name] = _nudge(plate[name], mx, wild)
        plate["ink"] = _nudge_hex(plate["ink"], wild)
        if random.random() < wild / 25:
            plate["original"] = not plate["original"]
    if random.random() < wild / 20 and len(p["plates"]) > 1:
        p["plates"].pop(random.randrange(len(p["plates"])))
    elif random.random() < wild / 20 and len(p["plates"]) < 4:
        p["plates"].append(random_plate())
    return p


def label(p):
    return f"st{p['strength']} gr{p['grain']} sh{p['shift']} · {len(p['plates'])} plate{'s' if len(p['plates']) > 1 else ''}"


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>pygfx explorer</title>
<style>
  body { background:#14161a; color:#ccc; font:14px system-ui; margin:16px; }
  #grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
  figure { margin:0; }
  img { width:100%; display:block; cursor:pointer; border:2px solid transparent; }
  figure.parent img { border-color:#6cf; }
  figcaption { font:11px monospace; color:#889; padding:4px 0; display:flex; justify-content:space-between; align-items:center; }
  button { background:#2a2e36; color:#ccc; border:0; padding:2px 8px; cursor:pointer; }
  #bar { margin-bottom:12px; display:flex; gap:16px; align-items:center; }
  a { color:#6cf; }
  i.chip { display:inline-block; width:10px; height:10px; border:1px solid #444; margin-right:2px; }
</style>
<div id="bar">
  <label>wildness <input id="wild" type="range" min="1" max="10" value="3"></label>
  <button onclick="mutate()">mutate</button>
  <button onclick="mutate(true)">full random</button>
  <span>click a tile to make it the parent</span>
  <a href="/edit" style="margin-left:auto">edit view →</a>
</div>
<div id="grid"></div>
<script>
function chips(p) {
  const colors = [p.paper_original ? null : p.paper, ...p.plates.map(pl => pl.original ? null : pl.ink)].filter(Boolean);
  return colors.map(c => `<i class="chip" style="background:${c}"></i>`).join('');
}
async function mutate(rand) {
  const wild = document.getElementById('wild').value;
  const tiles = await (await fetch(`/grid?wild=${wild}${rand ? '&random=1' : ''}`)).json();
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  for (const t of tiles) {
    const fig = document.createElement('figure');
    if (t.parent) fig.className = 'parent';
    const edit = `/edit?p=${encodeURIComponent(JSON.stringify(t.params))}`;
    fig.innerHTML = `<img src="/img/${t.id}">
      <figcaption><span>${chips(t.params)} ${t.label}</span><span><a href="${edit}">edit</a> <button>save</button></span></figcaption>`;
    fig.querySelector('img').onclick = async () => { await fetch(`/pick/${t.id}`); mutate(); };
    fig.querySelector('button').onclick = async () => alert(await (await fetch(`/save/${t.id}`)).text());
    grid.appendChild(fig);
  }
}
mutate();
</script>
"""

EDIT_PAGE = """<!doctype html>
<meta charset="utf-8">
<title>pygfx edit</title>
<style>
  body { background:#14161a; color:#ccc; font:14px system-ui; margin:16px; display:flex; gap:20px; }
  #panel { width:360px; flex-shrink:0; }
  label { display:flex; align-items:center; gap:6px; font:12px monospace; margin:4px 0; }
  label span { width:64px; flex-shrink:0; }
  input[type=range] { flex:1; min-width:0; }
  input[type=number] { width:44px; background:#2a2e36; color:#ccc; border:0; padding:2px 4px; }
  input[type=color] { width:36px; height:24px; border:0; background:none; padding:0; cursor:pointer; }
  input:disabled { opacity:.25; }
  select { background:#2a2e36; color:#ccc; border:0; padding:2px; }
  button { background:#2a2e36; color:#ccc; border:0; padding:4px 10px; cursor:pointer; margin:2px 2px 2px 0; }
  table { border-collapse:collapse; margin:10px 0; font:12px monospace; width:100%; }
  th, td { padding:3px 4px; text-align:left; border-bottom:1px solid #2a2e36; }
  th { color:#889; font-weight:normal; }
  img { max-width:calc(100% - 400px); align-self:flex-start; }
  a { color:#6cf; }
  textarea { width:100%; height:280px; box-sizing:border-box; background:#1a1d22; color:#9c9; border:1px solid #2a2e36;
             font:11px/1.5 monospace; padding:6px; margin-top:10px; }
  #mode { color:#c96; font:11px monospace; margin-left:6px; }
  #err { color:#e88; font:11px monospace; white-space:pre-wrap; }
</style>
<div id="panel">
  <a href="/">← grid view</a>
  <div id="globals"></div>
  <table>
    <thead><tr><th>ink</th><th>mid</th><th>dither</th><th>cell</th><th>angle</th><th>orig</th><th></th></tr></thead>
    <tbody id="plates"></tbody>
  </table>
  <button onclick="addPlate()">+ add plate</button>
  <button onclick="save()">save full res</button>
  <textarea id="code" spellcheck="false"></textarea>
  <button onclick="runCode()">run code</button><span id="mode"></span>
  <pre id="err"></pre>
</div>
<img id="view">
<script>
const SPEC = __SPEC__;
let P = JSON.parse(new URLSearchParams(location.search).get('p') || 'null') || SPEC.defaults;

let SYNCS = [];  // per-plate-row enable/disable updaters; global sliders re-run them (strength gates mid)
function slider(obj, name, mx) {
  const l = document.createElement('label');
  l.innerHTML = `<span>${name}</span><input type="range" min="0" max="${mx}" value="${obj[name]}">
    <input type="number" min="0" max="${mx}" value="${obj[name]}">`;
  const [r, n] = l.querySelectorAll('input');
  r.oninput = () => { n.value = r.value; obj[name] = +r.value; SYNCS.forEach(f => f()); refresh(); };
  n.oninput = () => { r.value = n.value; obj[name] = +n.value; SYNCS.forEach(f => f()); refresh(); };
  return l;
}
function build() {
  SYNCS = [];
  const g = document.getElementById('globals');
  const paper = document.createElement('label');
  paper.innerHTML = `<span>paper</span><input type="color" value="${P.paper}"><input type="checkbox" ${P.paper_original ? 'checked' : ''}> img`;
  const [pc, po] = paper.querySelectorAll('input');
  pc.disabled = P.paper_original;  // "img": plates print onto the photo instead of flat paper
  pc.oninput = e => { P.paper = e.target.value; refresh(); };
  po.oninput = e => { P.paper_original = e.target.checked; pc.disabled = e.target.checked; refresh(); };
  g.replaceChildren(slider(P, 'strength', SPEC.globals.strength), paper,
                    slider(P, 'grain', SPEC.globals.grain), slider(P, 'shift', SPEC.globals.shift));

  const tbody = document.getElementById('plates');
  tbody.innerHTML = '';
  P.plates.forEach((plate, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><input type="color" value="${plate.ink}"></td>
      <td><input type="number" min="0" max="100" value="${plate.mid}"></td>
      <td><select>${SPEC.dithers.map((o, j) => `<option value="${j}" ${j == plate.dither ? 'selected' : ''}>${o}</option>`).join('')}</select></td>
      <td><input type="number" min="2" max="16" value="${plate.cell}"></td>
      <td><input type="number" min="0" max="90" value="${plate.angle}"></td>
      <td><input type="checkbox" ${plate.original ? 'checked' : ''}></td>
      <td><button title="remove">×</button></td>`;
    const [ink, mid, cell, angle, orig] = tr.querySelectorAll('input');
    // gray out inputs the current settings make inert: cell/angle are halftone-only,
    // ink is unused when painting original color, mid feeds the tone curve (off at strength 0)
    const sync = () => {
      cell.disabled = angle.disabled = SPEC.dithers[plate.dither] !== 'halftone';
      ink.disabled = plate.original;
      mid.disabled = !P.strength;
    };
    SYNCS.push(sync); sync();
    ink.oninput = e => { plate.ink = e.target.value; refresh(); };
    mid.oninput = e => { plate.mid = +e.target.value; refresh(); };
    cell.oninput = e => { plate.cell = +e.target.value; refresh(); };
    angle.oninput = e => { plate.angle = +e.target.value; refresh(); };
    orig.oninput = e => { plate.original = e.target.checked; sync(); refresh(); };
    tr.querySelector('select').oninput = e => { plate.dither = +e.target.value; sync(); refresh(); };
    tr.querySelector('button').onclick = () => { P.plates.splice(i, 1); build(); refresh(); };
    tbody.append(tr);
  });
}
function addPlate() { P.plates.push({...SPEC.plate_default}); build(); refresh(); }

// the code box shows the python that render() actually execs; editing it detaches
// from the controls (touch any control to regenerate and reattach)
const codeEl = document.getElementById('code'), modeEl = document.getElementById('mode'), errEl = document.getElementById('err');
let custom = false;
codeEl.oninput = () => { custom = true; modeEl.textContent = 'edited — controls will regenerate'; };
async function runCode() {
  const r = await fetch('/run', {method: 'POST', body: codeEl.value});
  errEl.textContent = r.ok ? '' : await r.text();
  if (r.ok) document.getElementById('view').src = URL.createObjectURL(await r.blob());
}
let timer;
function refresh() {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const q = encodeURIComponent(JSON.stringify(P));
    document.getElementById('view').src = `/render?p=${q}`;
    history.replaceState(null, '', `/edit?p=${q}`);
    custom = false; modeEl.textContent = ''; errEl.textContent = '';
    codeEl.value = await (await fetch(`/code?p=${q}`)).text();
  }, 120);
}
async function save() {
  const r = custom ? await fetch('/runsave', {method: 'POST', body: codeEl.value})
                   : await fetch(`/saverender?p=${encodeURIComponent(JSON.stringify(P))}`);
  alert(await r.text());
}
build(); refresh();
</script>
"""

STATE = {"parent": default_params(), "tiles": {}, "next_id": 0, "saves": 0}
IMAGES = {}  # "full" / "preview" / "preview_lg" / "path", set in main()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _reply(self, body, ctype="text/plain", status=200):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _save(self, p):
        STATE["saves"] += 1
        out_path = IMAGES["path"].rsplit(".", 1)[0] + f"_x{STATE['saves']}.png"
        cv2.imwrite(out_path, render(IMAGES["full"], p))
        print(f"saved {out_path}  {json.dumps(p)}")
        self._reply(f"saved {out_path}\n{json.dumps(p)}")

    def do_GET(self):
        url = urlparse(self.path)
        parts = url.path.strip("/").split("/")
        q = parse_qs(url.query)

        if url.path == "/":
            self._reply(PAGE, "text/html")
        elif url.path == "/edit":
            spec = {
                "globals": {name: mx for name, (mx, _d) in GLOBALS.items()},
                "dithers": DITHERS,
                "defaults": default_params(),
                "plate_default": {name: d for name, (_mx, d) in PLATE.items()} | {"ink": "#111111", "original": False},
            }
            self._reply(EDIT_PAGE.replace("__SPEC__", json.dumps(spec)), "text/html")
        elif url.path == "/grid":
            wild = int(q.get("wild", ["3"])[0])
            full_random = "random" in q
            tiles = []
            for i in range(9):
                if full_random:
                    p = random_params()
                else:
                    p = STATE["parent"] if i == 0 else mutated(STATE["parent"], wild)
                tid = STATE["next_id"] = STATE["next_id"] + 1
                STATE["tiles"][tid] = p
                tiles.append({"id": tid, "label": label(p), "parent": not full_random and i == 0, "params": p})
            self._reply(json.dumps(tiles), "application/json")
        elif url.path == "/code":
            self._reply(to_code(clean(json.loads(q.get("p", ["{}"])[0]))))
        elif url.path in ("/render", "/saverender"):
            p = clean(json.loads(q.get("p", ["{}"])[0]))
            if url.path == "/render":
                _ok, buf = cv2.imencode(".png", render(IMAGES["preview_lg"], p))
                self._reply(buf.tobytes(), "image/png")
            else:
                self._save(p)
        elif parts[0] in ("img", "pick", "save") and len(parts) == 2 and (p := STATE["tiles"].get(int(parts[1]))):
            if parts[0] == "img":
                _ok, buf = cv2.imencode(".png", render(IMAGES["preview"], p))
                self._reply(buf.tobytes(), "image/png")
            elif parts[0] == "pick":
                STATE["parent"] = p
                self._reply("ok")
            else:
                self._save(p)
        else:
            self.send_error(404)

    def do_POST(self):
        code = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        try:
            out = run_code(code, IMAGES["full" if self.path == "/runsave" else "preview_lg"])
        except Exception:  # noqa: BLE001 -- surface any user-code error to the browser
            self._reply(traceback.format_exc(), status=400)
            return
        if self.path == "/runsave":
            STATE["saves"] += 1
            out_path = IMAGES["path"].rsplit(".", 1)[0] + f"_x{STATE['saves']}.png"
            cv2.imwrite(out_path, out)
            print(f"saved {out_path}\n{code}")
            self._reply(f"saved {out_path}")
        else:
            _ok, buf = cv2.imencode(".png", out)
            self._reply(buf.tobytes(), "image/png")


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

    def scaled(width):
        s = min(1.0, width / full.shape[1])
        return cv2.resize(full, None, fx=s, fy=s) if s < 1.0 else full

    IMAGES.update(full=full, preview=scaled(args.preview_width), preview_lg=scaled(1000), path=args.image)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"http://127.0.0.1:{args.port}")
    webbrowser.open(f"http://127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
