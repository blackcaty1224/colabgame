"""turtle: Pyodide（ブラウザで動く Python）と、canvas 版の turtle 互換モジュールで動かす。"""
import os
import shutil

from ..asyncify import asyncify, TurtleProfile

DEFAULT_HEIGHT = 720
RUNTIME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runtime", "turtle")


def transform(code: str) -> str:
    return asyncify(code, TurtleProfile)


def build(code: str, workdir: str, copy_assets) -> str:
    for name in ("index.html", "turtle_shim.py"):
        shutil.copy2(os.path.join(RUNTIME, name), os.path.join(workdir, name))
    with open(os.path.join(workdir, "main.py"), "w", encoding="utf-8") as f:
        f.write(transform(code))
    copy_assets(workdir)
    return os.path.join(workdir, "index.html")
