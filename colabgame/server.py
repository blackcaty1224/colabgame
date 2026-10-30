"""ビルドしたゲームを配信する小さな Web サーバーと、Colab への表示。"""
import functools
import http.server
import os
import tempfile
import threading
import uuid

ROOT = os.path.join(tempfile.gettempdir(), "colabgame")
_server = None


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".py": "text/plain; charset=utf-8",
        ".apk": "application/octet-stream",
        ".pyxapp": "application/octet-stream",
        ".html": "text/html; charset=utf-8",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass


def ensure_server() -> int:
    """サーバーをバックグラウンドで起動して、ポート番号を返す（2回目以降は使い回す）。"""
    global _server
    if _server is None:
        os.makedirs(ROOT, exist_ok=True)
        handler = functools.partial(_Handler, directory=ROOT)
        _server = http.server.ThreadingHTTPServer(("", 0), handler)
        threading.Thread(target=_server.serve_forever, daemon=True).start()
    return _server.server_address[1]


def new_build_dir() -> str:
    path = os.path.join(ROOT, uuid.uuid4().hex[:12])
    os.makedirs(path)
    return path


def show(index_path: str, height: int = 600, new_tab: bool = False) -> str:
    """ROOT 以下のファイルを Colab（またはローカルの Jupyter）に表示する。"""
    port = ensure_server()
    rel = "/" + os.path.relpath(index_path, ROOT).replace(os.sep, "/")
    try:
        from google.colab import output  # type: ignore
    except ImportError:
        output = None

    if output is not None:
        output.serve_kernel_port_as_iframe(port, path=rel, height=str(height))
        if new_tab:
            output.serve_kernel_port_as_window(port, path=rel, anchor_text="別のタブで開く")
        return rel

    url = f"http://localhost:{port}{rel}"
    try:
        from IPython.display import IFrame, display
        display(IFrame(url, width="100%", height=height))
    except ImportError:
        pass
    print("ゲームのURL:", url)
    return url
