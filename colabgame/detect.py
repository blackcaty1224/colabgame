"""コードの import を見て、どのライブラリ用のゲームかを判定する。"""
import ast
import re

BACKENDS = ("pyxel", "pygame", "turtle")


def imported_modules(code: str) -> set:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set(re.findall(r"^\s*(?:import|from)\s+(\w+)", code, re.M))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module.split(".")[0])
    return mods


def detect_backend(code: str) -> str:
    mods = imported_modules(code)
    for name in BACKENDS:
        if name in mods:
            return name
    raise ValueError(
        "pygame / pyxel / turtle のどれを使うコードか判定できませんでした。"
        "`%%game pygame` のようにライブラリ名を指定してください。")
