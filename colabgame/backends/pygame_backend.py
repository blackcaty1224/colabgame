"""pygame: pygbag で WebAssembly 版にビルドする。"""
import os
import sys

from ..asyncify import asyncify, PygameProfile
from ._util import ensure_package, run

DEFAULT_HEIGHT = 560


def transform(code: str) -> str:
    return asyncify(code, PygameProfile)


def build(code: str, workdir: str, copy_assets) -> str:
    ensure_package("pygbag")
    app = os.path.join(workdir, "game")
    os.makedirs(app)
    with open(os.path.join(app, "main.py"), "w", encoding="utf-8") as f:
        f.write(transform(code))
    copy_assets(app)
    print("pygbag でビルドしています…")
    run([sys.executable, "-m", "pygbag", "--build", app], cwd=workdir)
    index = os.path.join(app, "build", "web", "index.html")
    if not os.path.exists(index):
        raise RuntimeError("pygbag のビルド結果（index.html）が見つかりませんでした。"
                           "ネットワークにつながっているか確認してください。")
    return index
