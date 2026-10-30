"""ゲームが使う画像や音などのファイルを、ビルド用フォルダにコピーする。"""
import ast
import os
import shutil

MAX_TOTAL = 200 * 1024 * 1024  # 自動で集めるのは合計 200MB まで


def _safe_rel(p: str):
    if not p or os.path.isabs(p):
        return None
    norm = os.path.normpath(p)
    if norm in (".", "") or norm.startswith(".."):
        return None
    return norm


def find_referenced_files(code: str, base: str):
    """コード中の文字列のうち、実在するファイル/フォルダを指しているものを探す。"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    found = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) < 260 and "\n" not in n.value:
            rel = _safe_rel(n.value)
            if rel and os.path.exists(os.path.join(base, rel)):
                found.append(rel)
    return sorted(set(found))


def _size(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(path) for f in fs)


def copy_assets(code: str, dest: str, extra=None, base=None):
    base = base or os.getcwd()
    auto = find_referenced_files(code, base)
    explicit = []
    for p in extra or []:
        rel = _safe_rel(p)
        if rel is None:
            raise ValueError(f"assets には今いるフォルダからの相対パスを指定してください: {p}")
        if not os.path.exists(os.path.join(base, rel)):
            raise FileNotFoundError(f"assets に指定したファイルが見つかりません: {p}")
        explicit.append(rel)

    total, copied = 0, []
    for rel in explicit + [a for a in auto if a not in explicit]:
        src, dst = os.path.join(base, rel), os.path.join(dest, rel)
        size = _size(src)
        if rel not in explicit and total + size > MAX_TOTAL:
            continue
        total += size
        os.makedirs(os.path.dirname(dst) or dest, exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        copied.append(rel)
    return copied
