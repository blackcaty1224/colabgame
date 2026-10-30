"""colabgame の本体: コードを受け取り → ビルドして → 画面に表示する。"""
import os

from . import server
from .assets import copy_assets
from .backends import BUILDERS
from .detect import detect_backend


def _resolve_backend(code, backend):
    name = (backend or detect_backend(code)).lower()
    if name not in BUILDERS:
        raise ValueError(f"未対応のライブラリです: {name}（対応: {', '.join(BUILDERS)}）")
    return name


def transform(code: str, backend: str = None) -> str:
    """ブラウザ用に書き換えたコードを返す（動作の確認・デバッグ用）。"""
    return BUILDERS[_resolve_backend(code, backend)].transform(code)


def build(code: str, backend: str = None, assets=None, base_dir: str = None) -> str:
    """ゲームをビルドして、index.html のパスを返す。"""
    name = _resolve_backend(code, backend)
    workdir = server.new_build_dir()
    base = base_dir or os.getcwd()

    def _copy(dest):
        copied = copy_assets(code, dest, extra=assets, base=base)
        if copied:
            print("いっしょに読み込むファイル:", ", ".join(copied))

    return BUILDERS[name].build(code, workdir, _copy)


def play(code: str, backend: str = None, height: int = None, assets=None, new_tab: bool = False,
         show_code: bool = False, base_dir: str = None):
    """コード（文字列）をビルドして、Colab の出力欄でゲームを動かす。"""
    name = _resolve_backend(code, backend)
    if show_code:
        print(BUILDERS[name].transform(code))
    index = build(code, name, assets=assets, base_dir=base_dir)
    server.show(index, height=height or BUILDERS[name].DEFAULT_HEIGHT, new_tab=new_tab)
    print("ゲーム画面を一度クリックすると、キーボード操作が効くようになります。")


def play_file(path: str, **kw):
    """.py ファイルを読み込んで play() する。画像などはそのファイルと同じフォルダから探す。"""
    with open(path, encoding="utf-8") as f:
        code = f.read()
    kw.setdefault("base_dir", os.path.dirname(os.path.abspath(path)))
    return play(code, **kw)
