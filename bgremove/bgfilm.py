"""Build a public folder for The Watchers with one method's cutouts swapped in, so the same frames can be rendered
with the Higgsfield cutouts and with the local ones (scripts/stills.mjs with PUBLIC_DIR)."""
import shutil, sys
from pathlib import Path

SRC = Path(r"K:\VideoLab\watchers-v2\public")
OUT = Path(r"K:\VideoLab\bgtest")
method = sys.argv[1]
dst = OUT / f"public_{method}"
if not dst.exists():
    shutil.copytree(SRC, dst)
for p in (OUT / method).glob("*.png"):
    target = dst / "img" / p.name
    if target.exists():
        shutil.copyfile(p, target)
        print("swapped", p.name)
