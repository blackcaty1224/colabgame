"""ライブラリごとのビルド方法。新しいライブラリに対応したいときはここにモジュールを足す。"""
from . import pygame_backend, pyxel_backend, turtle_backend

BUILDERS = {
    "pygame": pygame_backend,
    "pyxel": pyxel_backend,
    "turtle": turtle_backend,
}
