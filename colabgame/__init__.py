"""colabgame — Google Colab で pygame / pyxel / turtle のゲームを動かすライブラリ。

使い方（Colab のセル）::

    import colabgame

    %%game
    import pygame
    ...

コードはブラウザで動く形（WebAssembly）にビルドされ、出力欄の中で動きます。
"""
from .core import build, play, play_file, transform

__version__ = "0.1.0"
__all__ = ["play", "play_file", "build", "transform", "__version__"]


def load_ipython_extension(ipython):
    from .magic import register
    register(ipython)


try:  # import するだけで %%game が使えるようにする
    from IPython import get_ipython as _get_ipython
    _ip = _get_ipython()
    if _ip is not None:
        load_ipython_extension(_ip)
except Exception:  # IPython の外で使われた場合は何もしない
    pass
