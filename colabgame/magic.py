"""Jupyter / Colab のセルマジック %%game と %game_file。"""
from IPython.core.magic import Magics, magics_class, cell_magic, line_magic
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring

from .core import play, play_file


def _common(f):
    for dec in reversed([
        magic_arguments(),
        argument("--height", type=int, default=None, help="表示エリアの高さ（ピクセル）"),
        argument("--assets", default=None, help="一緒に読み込むファイル（カンマ区切り）"),
        argument("--window", action="store_true", help="別タブで開くリンクも表示する"),
        argument("--show-code", action="store_true", help="ブラウザ用に書き換えたコードを表示する"),
    ]):
        f = dec(f)
    return f


def _opts(args):
    assets = [a.strip() for a in args.assets.split(",") if a.strip()] if args.assets else None
    return dict(height=args.height, assets=assets, new_tab=args.window, show_code=args.show_code)


@magics_class
class GameMagics(Magics):
    @_common
    @argument("backend", nargs="?", default=None, help="pygame / pyxel / turtle（省略すると自動判定）")
    @cell_magic
    def game(self, line, cell):
        """セルのコードをゲームとして実行する。例: %%game  /  %%game turtle --height 500"""
        args = parse_argstring(self.game, line)
        play(cell, backend=args.backend, **_opts(args))

    @_common
    @argument("path", help="実行する .py ファイル")
    @argument("--backend", default=None, help="pygame / pyxel / turtle（省略すると自動判定）")
    @line_magic
    def game_file(self, line):
        """ファイルをゲームとして実行する。例: %game_file mygame.py"""
        args = parse_argstring(self.game_file, line)
        play_file(args.path, backend=args.backend, **_opts(args))


def register(ipython):
    ipython.register_magics(GameMagics)
