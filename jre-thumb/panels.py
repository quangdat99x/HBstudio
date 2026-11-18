"""Bake each thumbnail panel (left / right / centre) into its own image from a frames.py plan.

Canva's edit-design-v2 editor has no crop operation (only add_image at a box), so the crop that
frames.py computed as an imageBox is applied here, locally, and the result is uploaded and placed
at the panel's own geometry with add_image. The centre image gets the template's 12px green frame.

  panels.py <thumb_plan.json> <out_dir>
      -> <out_dir>/left.png  right.png  center.png   (sizes = the plan's element boxes)
  panels.py --tile <img> <w> <h> <fx> <fy> <out>
      -> one cover-cropped tile with the focus point (0..1) centred, e.g. for a 3-photo centre
  panels.py --stack <out> <tile1> <tile2> [<tile3> ...]   [--size 625x913]
      -> the tiles stacked vertically with green separators + green frame = a centre image

Plan: the JSON that `frames.py crop --plan` / `fill --plan` write (slots.left/right/center with
`img`, `element` {left,top,width,height} and `image_box` {left,top,width,height}).
Run: py -3.14 -X utf8 C:\\Tool\\jre-thumb\\panels.py thumb_plan.json DIR
"""
import json
import sys

from PIL import Image, ImageDraw

GREEN = (0, 191, 99)
FRAME = 12


def panel(src: str, element: dict, box: dict) -> Image.Image:
    """The element-sized view of `src` after Canva would scale/offset it by `box` (imageBox)."""
    im = Image.open(src).convert("RGB")
    w, h = round(element["width"]), round(element["height"])
    scaled = im.resize((max(1, round(box["width"])), max(1, round(box["height"]))), Image.LANCZOS)
    out = Image.new("RGB", (w, h), (0, 0, 0))
    out.paste(scaled, (round(box["left"]), round(box["top"])))
    return out


def tile(src: str, w: int, h: int, fx: float, fy: float) -> Image.Image:
    im = Image.open(src).convert("RGB")
    s = max(w / im.width, h / im.height)
    sc = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    left = min(max(0, sc.width * fx - w / 2), sc.width - w)
    top = min(max(0, sc.height * fy - h / 2), sc.height - h)
    return sc.crop((round(left), round(top), round(left) + w, round(top) + h))


def frame(im: Image.Image, weight: int = FRAME) -> Image.Image:
    d = ImageDraw.Draw(im)
    for i in range(weight):
        d.rectangle([i, i, im.width - 1 - i, im.height - 1 - i], outline=GREEN)
    return im


def stack(paths: list[str], size: tuple[int, int]) -> Image.Image:
    w, h = size
    n = len(paths)
    th = h // n
    out = Image.new("RGB", (w, h), (0, 0, 0))
    y = 0
    for i, p in enumerate(paths):
        hh = h - y if i == n - 1 else th
        out.paste(Image.open(p).convert("RGB").resize((w, hh), Image.LANCZOS), (0, y))
        y += hh
    d = ImageDraw.Draw(out)
    for k in range(1, n):
        d.rectangle([0, k * th - 2, w, k * th + 2], fill=GREEN)
    return frame(out)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--tile":
        src, w, h, fx, fy, out = argv[1:7]
        tile(src, int(w), int(h), float(fx), float(fy)).save(out, quality=95)
        print(out)
        return 0
    if argv[0] == "--stack":
        size = (625, 913)
        if "--size" in argv:
            i = argv.index("--size")
            size = tuple(int(x) for x in argv[i + 1].split("x"))
            argv = argv[:i] + argv[i + 2:]
        out, tiles = argv[1], argv[2:]
        stack(tiles, size).save(out)
        print(out, size)
        return 0
    plan = json.load(open(argv[0], encoding="utf-8"))
    out_dir = argv[1]
    for slot, s in plan["slots"].items():
        im = panel(s["img"], s["element"], s["image_box"])
        if slot == "center":
            im = frame(im)
        p = f"{out_dir}/{slot}.png"
        im.save(p)
        print(slot, im.size, p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
