"""pyxel: 公式の Web 出力機能（pyxel package → pyxel app2html）を使う。"""
import os
import shutil
import sys

from ._util import ensure_package, run

DEFAULT_HEIGHT = 520


def transform(code: str) -> str:
    return code  # pyxel.run() はもともとブラウザ版に対応しているので書き換え不要


def _pyxel_cmd():
    exe = shutil.which("pyxel")
    if exe:
        return [exe]
    return [sys.executable, "-c", "import sys, pyxel.cli; sys.argv[0] = 'pyxel'; pyxel.cli.cli()"]


def build(code: str, workdir: str, copy_assets) -> str:
    ensure_package("pyxel")
    app = os.path.join(workdir, "game")
    os.makedirs(app)
    with open(os.path.join(app, "main.py"), "w", encoding="utf-8") as f:
        f.write(transform(code))
    copy_assets(app)
    cmd = _pyxel_cmd()
    run(cmd + ["package", "game", os.path.join("game", "main.py")], cwd=workdir)
    run(cmd + ["app2html", "game.pyxapp"], cwd=workdir)
    src = os.path.join(workdir, "game.html")
    index = os.path.join(workdir, "index.html")
    with open(src, encoding="utf-8") as f:
        html = f.read()
    style = ("<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
             "<style>html,body{margin:0;height:100%;background:#000;overflow:hidden}</style>\n")
    with open(index, "w", encoding="utf-8") as f:
        f.write(html.replace("<!doctype html>", "<!doctype html>\n" + style, 1))
    return index
