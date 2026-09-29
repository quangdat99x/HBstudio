"""The film folder of a project: a copy of the engine (so a film keeps working when the engine changes
later) plus a junction to the one shared node_modules install."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from .. import config
from .store import project_dir

log = logging.getLogger("studio.docfilm")
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
COPY_FILES = ("package.json", "tsconfig.json", "remotion.config.ts", "ENGINE.md", ".gitignore")
COPY_DIRS = ("src", "scripts")


def engine_dir() -> Path:
    return config.DOCFILM_ENGINE_DIR


CHROME = ("node_modules", ".remotion", "chrome-headless-shell", "win64", "chrome-headless-shell-win64", "chrome-headless-shell.exe")


def engine_ready() -> bool:
    nm = engine_dir() / "node_modules"
    return (nm / "remotion").exists() and (nm / "@remotion" / "three").exists() and (nm / "three").exists()


def chrome_ready() -> bool:
    return engine_dir().joinpath(*CHROME).exists()


def _npm_tool(name: str) -> list[str]:
    exe = shutil.which(name) or shutil.which(name + ".cmd")
    if not exe:
        raise RuntimeError(f"không tìm thấy {name} (cần Node.js)")
    return ["cmd", "/c", exe] if exe.lower().endswith(".cmd") else [exe]


def ensure_browser(update=None) -> None:
    """Download Chrome Headless Shell into the engine install once (renders reuse it through the junction)."""
    if update:
        update("tải Chrome Headless Shell cho engine (chỉ lần đầu)")
    res = subprocess.run(_npm_tool("npx") + ["remotion", "browser", "ensure"], cwd=str(engine_dir()), capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=1800, creationflags=_NO_WINDOW)
    if res.returncode != 0 or not chrome_ready():
        raise RuntimeError("tải Chrome Headless Shell lỗi: " + (res.stderr or res.stdout or "")[-800:])


def unlink_node_modules(project_folder: Path) -> None:
    """Remove the node_modules junction of a film (the link only) before the folder is trashed or deleted,
    so nothing that walks the folder can reach into the shared engine install."""
    link = project_folder / "film" / "node_modules"
    if link.exists() and (os.path.isjunction(link) or link.is_symlink()):
        os.rmdir(link)


def install_engine(update=None) -> None:
    """npm install in docfilm/engine (once per machine, ~1-2 minutes)."""
    if update:
        update("cài engine dựng phim (npm install, chỉ lần đầu)")
    res = subprocess.run(_npm_tool("npm") + ["install", "--no-audit", "--no-fund"], cwd=str(engine_dir()), capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=1800, creationflags=_NO_WINDOW)
    if res.returncode != 0 or not engine_ready():
        raise RuntimeError("npm install engine lỗi: " + (res.stderr or res.stdout or "")[-800:])


def _junction(link: Path, target: Path) -> None:
    if link.exists():
        return
    res = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True,
                         creationflags=_NO_WINDOW)
    if res.returncode != 0:
        raise RuntimeError(f"không tạo được liên kết node_modules: {res.stderr or res.stdout}")


def scaffold_film(p: dict, update=None) -> Path:
    """Create <project>/film from the engine if it does not exist yet; never overwrite Claude's work."""
    if not engine_ready():
        install_engine(update)
    if not chrome_ready():
        ensure_browser(update)
    film = project_dir(p) / "film"
    if not (film / "src" / "index.ts").exists():
        if update:
            update("dựng khung phim từ engine")
        film.mkdir(parents=True, exist_ok=True)
        src = engine_dir()
        for name in COPY_FILES:
            if (src / name).exists():
                shutil.copy2(src / name, film / name)
        for name in COPY_DIRS:
            shutil.copytree(src / name, film / name, dirs_exist_ok=True)
        pkg = json.loads((film / "package.json").read_text(encoding="utf-8"))
        pkg["name"] = f"film-{p['slug']}"[:200]
        pkg["description"] = f"{p['title']} (JRE Studio documentary)"
        (film / "package.json").write_text(json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8")
        for sub in ("public/img", "public/clips", "public/fx", "assets/raw", "assets/fx", "audio/voice", "out/stills"):
            (film / sub).mkdir(parents=True, exist_ok=True)
    _junction(film / "node_modules", engine_dir() / "node_modules")
    return film
