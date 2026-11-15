"""Layered scenes: the image model paints each depth layer separately, the engine stacks them and flies a camera.

Each scene in the spec lists 2-4 layers, back to front. The back layer is a full painting of what is far away
(nothing in front of it). Every nearer layer is painted on a flat plain grey backdrop, with the back layer as a
reference image so light, horizon and perspective match, then cut out on this machine (scripts/cutout.py).
Every layer keeps the full frame (the subject stays where it was composed), so at the start pose of the camera
the stack looks like one picture; when the camera moves, the layers separate by their depth.

spec.json (one entry per scene):
  [{"scene": "sc29", "aspect": "3:2", "quality": "high",
    "style": "<the film's style string>",
    "light": "night, cold blue moonlight from the upper left",           # shared by every layer prompt
    "layers": [
      {"name": "far",  "z": 60, "prompt": "...far cliffs, mist, sky..."},                         # back: full
      {"name": "mid",  "z": 9,  "prompt": "...the ledge with the two men...", "refs": ["film/assets/raw/raphael.png"]},
      {"name": "fg",   "z": 3,  "prompt": "...a dark boulder in the lower left corner..."}]}]

Run in the project folder:  "$CREATER_PYTHON" "$LAYERKIT_PY" 3_scenes/scenes.json [--only sc29] [--redo sc29:mid]
(scenes.json: every scene that has a "layers" list; or a spec.json list as above)
Writes film/assets/layers/<scene>/<layer>.png (raw), film/public/layers/<scene>/<layer>.png (cut out) and
film/public/layers/<scene>/layers.json (depths, files) for the engine (src/staged/LayerScene.tsx).
"""
import argparse
import json
import os
import subprocess
import sys

_CREATER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # <Tool>/Creater Vid
GEN = os.environ.get("GEN_PY") or os.path.join(_CREATER, "gen.py")
PY = os.environ.get("CREATER_PYTHON") or sys.executable
BG = os.environ.get("BGREMOVE_PY") or os.path.join(os.path.dirname(_CREATER), "bgremove", ".venv", "Scripts", "python.exe")

GREY = ("Paint ONLY what is described, on a perfectly flat plain mid-grey (#808080) studio backdrop: no sky, no "
        "distant landscape, no horizon, no floor beyond the described ground. Keep the same camera, horizon height, "
        "perspective, scale and lighting as the reference landscape image, so this layer sits exactly in front of it "
        "in the same frame.")
NOTEXT = "No text, no letters, no frame, no border, no watermark."
# the film shows a 2.2:1 band of this 3:2 picture: the top and bottom sixths are cut off on screen
FRAMING = ("Cinematic widescreen framing: the top 16% and the bottom 16% of the image will be cropped off, so keep every "
           "head, raised hand, face and foot and everything important between 18% and 82% of the image height, with a "
           "little room above the heads.")


def gen(prompt, out, refs, aspect, quality, what):
    cmd = [PY, GEN, "image", "--model", "openai", "--quality", quality, "--aspect", aspect, "--out", out, "--what", what,
           "--prompt", prompt]
    for r in refs:
        cmd += ["--ref", r]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = (r.stdout or "").strip().splitlines()[-1:] or [r.stderr[-300:]]
    print(f"  {what}: {tail[0]}", flush=True)
    if r.returncode != 0:
        raise RuntimeError(f"gen.py failed for {what}: {r.stderr[-500:] or r.stdout[-500:]}")


def build(sc, redo, film):
    key = sc["scene"]
    raw_dir = os.path.join("film", "assets", "layers", key)
    pub_dir = os.path.join("film", "public", "layers", key)
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(pub_dir, exist_ok=True)
    aspect, quality = sc.get("aspect", "3:2"), sc.get("quality", "high")
    shared = " ".join(x for x in (sc.get("light", ""), FRAMING, sc.get("style", ""), NOTEXT) if x)
    layers = sc["layers"]
    back = os.path.join(raw_dir, layers[0]["name"] + ".png")
    out_layers = []
    for i, L in enumerate(layers):
        raw = os.path.join(raw_dir, L["name"] + ".png")
        if not os.path.exists(raw) or f"{key}:{L['name']}" in redo or key in redo:
            if i == 0:
                prompt = f"{L['prompt']} Nothing in the foreground: no people, no near rocks. {shared}"
                refs = L.get("refs", [])
            else:
                nobody = "" if L.get("refs") or L.get("people") else " No people, no figures, no animals in this layer."
                prompt = f"The first image is the far landscape of this shot, for reference only. {L['prompt']}{nobody} {GREY} {shared}"
                refs = [back] + L.get("refs", [])
            gen(prompt, raw, refs, aspect, quality, f"layer_{key}_{L['name']}")
        pub = os.path.join(pub_dir, L["name"] + ".png")
        if i == 0:
            import shutil
            shutil.copyfile(raw, pub)
        else:
            if L.get("cut", "grey") == "grey":
                # remove exactly the flat grey backdrop: ground, people and props all stay
                subprocess.run([BG, os.path.join(os.path.dirname(os.path.abspath(__file__)), "greykey.py"), raw, pub], check=True, capture_output=True)
            else:
                # an isolated object with no ground (a bird, a lamp): salient-object cut-out
                subprocess.run([BG, os.path.join("scripts", "cutout.py"), os.path.abspath(raw), "--out", os.path.abspath(pub_dir)],
                               cwd=film, check=True, capture_output=True)
        out_layers.append({"name": L["name"], "file": f"layers/{key}/{L['name']}.png", "z": L["z"], "cutout": i > 0})
    import struct
    with open(back, "rb") as fh:          # PNG header: width, height (no image library in this Python)
        fh.read(16)
        w, h = struct.unpack(">II", fh.read(8))
    json.dump({"scene": key, "aspect": w / h, "layers": out_layers}, open(os.path.join(pub_dir, "layers.json"), "w"), indent=1)
    print(f"{key}: {len(out_layers)} layers -> {pub_dir}", flush=True)


def load_spec(path):
    """A list of scenes (spec.json), or the project's 3_scenes/scenes.json: every scene with a "layers" list."""
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, list):
        return data
    style = ""
    for src in ("project.json", os.path.join("1_script", "script.json")):
        try:
            style = style or (json.load(open(src, encoding="utf-8")).get("style") or "")
        except (OSError, ValueError):
            pass
    out = []
    for sc in data.get("scenes", []):
        if not sc.get("layers"):
            continue
        out.append({"scene": sc["id"], "aspect": sc.get("aspect", "3:2"), "quality": sc.get("quality", "high"),
                    "style": sc.get("style") or style, "light": sc.get("light", ""), "layers": sc["layers"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--redo", nargs="*", default=[], help="scene or scene:layer to paint again")
    a = ap.parse_args()
    film = os.path.abspath("film")
    for sc in load_spec(a.spec):
        if a.only and sc["scene"] not in a.only:
            continue
        build(sc, set(a.redo), film)


if __name__ == "__main__":
    main()
