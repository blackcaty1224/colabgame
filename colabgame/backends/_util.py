import importlib.util
import subprocess
import sys


def ensure_package(module: str, pip_name: str = None):
    """パッケージが入っていなければ pip でインストールする。"""
    if importlib.util.find_spec(module) is None:
        print(f"{pip_name or module} をインストールしています（初回だけ少し時間がかかります）…")
        run([sys.executable, "-m", "pip", "install", "-q", pip_name or module], what="インストール")


def run(cmd, cwd=None, what="ビルド", timeout=900):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{what}が時間内に終わりませんでした: {' '.join(cmd)}")
    if r.returncode != 0:
        log = (r.stdout + "\n" + r.stderr).strip().splitlines()
        raise RuntimeError(f"{what}に失敗しました: {' '.join(cmd)}\n" + "\n".join(log[-30:]))
    return r
