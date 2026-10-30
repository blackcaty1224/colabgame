"""ブロッキングなゲームループを、ブラウザで動く非同期コードに書き換える AST 変換。

ブラウザの中の Python は「画面を描き直す」「キー入力を受け取る」ために、
ときどき処理をブラウザに返す（await する）必要がある。普通のデスクトップ用の
ゲームはそれをしないので、ここで自動的に ``await`` を差し込む。

やっていること:
  1. 画面更新（flip / update / tick など）を含むループの先頭に「1フレーム待つ」を入れる
  2. time.sleep() などのブロッキング待機を ``await asyncio.sleep()`` に置き換える
  3. 1 や 2 を含む関数を ``async def`` にし、その呼び出し元にも ``await`` を伝播させる
  4. （pygame 用）トップレベルに await が残る部分を ``async def _cg_main()`` に包む
"""
from __future__ import annotations

import ast

__all__ = ["asyncify", "PygameProfile", "TurtleProfile"]

_FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
_SCOPE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
_COMP_TYPES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _parts(func: ast.AST) -> list:
    """呼び出し先を ['pygame', 'display', 'flip'] のような名前の列にする。"""
    out = []
    while isinstance(func, ast.Attribute):
        out.append(func.attr)
        func = func.value
    out.append(func.id if isinstance(func, ast.Name) else None)
    return out[::-1]


def _direct_nodes(stmts):
    """ループ1周ぶんで直接実行されるノード（入れ子のループ本体・関数定義は除く）。"""
    stack = list(stmts)
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, _SCOPE_TYPES):
            continue
        if isinstance(n, (ast.For, ast.AsyncFor)):
            stack.extend([n.iter, n.target])
            continue
        if isinstance(n, ast.While):
            stack.append(n.test)
            continue
        stack.extend(ast.iter_child_nodes(n))


def _scope_nodes(stmts):
    """関数1つぶんのノード（入れ子の関数・クラス・lambda の中身は除く）。"""
    stack = list(stmts)
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, _SCOPE_TYPES):
            continue
        stack.extend(ast.iter_child_nodes(n))


class _Profile:
    """ライブラリごとの「何がフレーム更新で、何がブロッキング待機か」の定義。"""

    toplevel_await_ok = False
    prelude = "import asyncio as _cg_asyncio\n"

    def __init__(self, tree: ast.AST):
        self.time_mods = {"time"}
        self.sleep_names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    if a.name == "time":
                        self.time_mods.add(a.asname or "time")
            elif isinstance(n, ast.ImportFrom) and n.module == "time":
                for a in n.names:
                    if a.name == "sleep":
                        self.sleep_names.add(a.asname or "sleep")

    # --- サブクラスで上書き -------------------------------------------------
    def is_frame_call(self, call: ast.Call) -> bool:
        raise NotImplementedError

    def frame_await(self) -> ast.expr:
        return ast.Call(
            func=ast.Attribute(value=ast.Name("_cg_asyncio", ast.Load()), attr="sleep", ctx=ast.Load()),
            args=[ast.Constant(0)], keywords=[])

    def loop_extra(self, loop) -> bool:
        return False

    # --- 共通 ----------------------------------------------------------------
    def sleep_seconds(self, call: ast.Call):
        """ブロッキング待機なら「待つ秒数」の式を返す。違えば None。"""
        if not isinstance(call, ast.Call):
            return None
        p = _parts(call.func)
        arg = call.args[0] if call.args else ast.Constant(0)
        if len(p) == 2 and p[0] in self.time_mods and p[1] == "sleep":
            return arg
        if len(p) == 1 and p[0] in self.sleep_names:
            return arg
        return None

    def loop_needs_frame(self, loop) -> bool:
        body = list(loop.body)
        if isinstance(loop, ast.While):
            body.append(loop.test)
        has_frame = has_sleep = False
        for n in _direct_nodes(body):
            if isinstance(n, ast.Call):
                if self.sleep_seconds(n) is not None:
                    has_sleep = True
                elif self.is_frame_call(n):
                    has_frame = True
        if has_sleep:  # sleep 自体が await になるので二重に待たない
            return False
        return has_frame or self.loop_extra(loop)


class PygameProfile(_Profile):
    """pygame（pygbag 上で実行）用。"""

    FRAME = {("display", "flip"), ("display", "update"), ("event", "get"),
             ("event", "wait"), ("event", "poll"), ("event", "pump")}

    def is_frame_call(self, call):
        p = _parts(call.func)
        if len(p) >= 2 and (p[-2], p[-1]) in self.FRAME:
            return True
        return len(p) >= 2 and p[-1] in ("tick", "tick_busy_loop")

    def sleep_seconds(self, call):
        sec = super().sleep_seconds(call)
        if sec is not None:
            return sec
        p = _parts(call.func)
        if len(p) >= 3 and p[-2] == "time" and p[-1] in ("wait", "delay") and call.args:
            return ast.BinOp(left=call.args[0], op=ast.Div(), right=ast.Constant(1000))
        return None


class TurtleProfile(_Profile):
    """turtle（Pyodide 上で実行）用。Pyodide はトップレベル await が使える。"""

    toplevel_await_ok = True
    prelude = "import asyncio as _cg_asyncio\nfrom turtle import _cg_frame\n"

    def is_frame_call(self, call):
        p = _parts(call.func)
        return p[-1] == "update"

    def frame_await(self):
        return ast.Call(func=ast.Name("_cg_frame", ast.Load()), args=[], keywords=[])

    def loop_extra(self, loop):
        # while ループで何かを呼んでいる＝タートルを動かしている可能性が高い
        if not isinstance(loop, ast.While):
            return False
        return any(isinstance(n, ast.Call) for n in _direct_nodes(loop.body))


class _Transformer(ast.NodeTransformer):
    def __init__(self, profile, async_ids, fnames, mnames):
        self.p = profile
        self.async_ids = async_ids
        self.fnames = fnames
        self.mnames = mnames

    def _is_async_call(self, call):
        f = call.func
        if isinstance(f, ast.Name):
            return f.id in self.fnames
        if isinstance(f, ast.Attribute):
            return f.attr in self.mnames and not self.p.is_frame_call(call)
        return False

    def visit_FunctionDef(self, node):
        make_async = id(node) in self.async_ids
        self.generic_visit(node)
        if not make_async:
            return node
        fields = {f: getattr(node, f, None) for f in node._fields}
        if "type_params" in fields and fields["type_params"] is None:
            fields["type_params"] = []
        new = ast.AsyncFunctionDef(**fields)
        return ast.copy_location(new, node)

    def visit_Lambda(self, node):
        return node  # lambda の中には await を書けない

    def _loop(self, node):
        needs = self.p.loop_needs_frame(node)
        self.generic_visit(node)
        if needs:
            stmt = ast.Expr(ast.Await(self.p.frame_await()))
            node.body.insert(0, ast.copy_location(stmt, node.body[0]))
        return node

    visit_While = _loop
    visit_For = _loop

    def visit_Call(self, node):
        self.generic_visit(node)
        sec = self.p.sleep_seconds(node)
        if sec is not None:
            call = ast.Call(
                func=ast.Attribute(value=ast.Name("_cg_asyncio", ast.Load()), attr="sleep", ctx=ast.Load()),
                args=[sec], keywords=[])
            return ast.copy_location(ast.Await(call), node)
        if self._is_async_call(node):
            return ast.copy_location(ast.Await(node), node)
        return node


def _collect_funcs(tree):
    funcs = []

    def visit(node, in_class):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef):
                funcs.append((child, in_class))
                visit(child, False)
            elif isinstance(child, ast.ClassDef):
                visit(child, True)
            else:
                visit(child, in_class if not isinstance(child, ast.AsyncFunctionDef) else False)

    visit(tree, False)
    return funcs


def _has_await(stmt):
    return any(isinstance(n, (ast.Await, ast.AsyncFor, ast.AsyncWith)) for n in _scope_nodes([stmt]))


def _bound_names(stmts):
    names = set()
    stack = list(stmts)
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
            stack.extend(n.decorator_list)
            continue
        if isinstance(n, (ast.Lambda,) + _COMP_TYPES):
            continue
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        elif isinstance(n, ast.Import):
            for a in n.names:
                names.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name != "*":
                    names.add(a.asname or a.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            names.add(n.name)
        elif type(n).__name__ in ("MatchAs", "MatchStar") and getattr(n, "name", None):
            names.add(n.name)
        elif type(n).__name__ == "MatchMapping" and getattr(n, "rest", None):
            names.add(n.rest)
        stack.extend(ast.iter_child_nodes(n))
    return names


def _already_async(tree):
    for n in ast.walk(tree):
        if isinstance(n, (ast.Await, ast.AsyncFunctionDef, ast.AsyncFor, ast.AsyncWith)):
            return True
        if isinstance(n, ast.Call) and _parts(n.func)[-2:] == ["asyncio", "run"]:
            return True
    return False


def asyncify(code: str, profile_cls=PygameProfile) -> str:
    """コードを非同期版に書き換えて返す。すでに asyncio を使っているコードはそのまま返す。"""
    tree = ast.parse(code)
    profile = profile_cls(tree)
    if _already_async(tree):
        return profile.prelude + code if profile.toplevel_await_ok else code

    # 1) どの関数を async にするか（呼び出し関係をたどって伝播させる）
    funcs = _collect_funcs(tree)
    async_ids, fnames, mnames = set(), set(), set()
    probe = _Transformer(profile, async_ids, fnames, mnames)
    changed = True
    while changed:
        changed = False
        for fn, is_method in funcs:
            if id(fn) in async_ids:
                continue
            for n in _scope_nodes(fn.body):
                hit = False
                if isinstance(n, (ast.While, ast.For)) and profile.loop_needs_frame(n):
                    hit = True
                elif isinstance(n, ast.Call) and (profile.sleep_seconds(n) is not None or probe._is_async_call(n)):
                    hit = True
                if hit:
                    async_ids.add(id(fn))
                    (mnames if is_method else fnames).add(fn.name)
                    changed = True
                    break

    # 2) 書き換え
    tree = _Transformer(profile, async_ids, fnames, mnames).visit(tree)

    # 3) 先頭に必要な import を入れる（__future__ の後ろ）
    body = tree.body
    k = 0
    while k < len(body) and isinstance(body[k], ast.ImportFrom) and body[k].module == "__future__":
        k += 1
    future, body = body[:k], body[k:]
    prelude = ast.parse(profile.prelude).body

    # 4) トップレベル await が使えない環境では async def _cg_main() に包む
    if not profile.toplevel_await_ok:
        idx = next((i for i, s in enumerate(body) if _has_await(s)), None)
        if idx is not None:
            head, tail = body[:idx], body[idx:]
            star = [s for s in tail if isinstance(s, ast.ImportFrom) and any(a.name == "*" for a in s.names)]
            tail = [s for s in tail if all(s is not x for x in star)]
            tail = [s for s in tail if not isinstance(s, (ast.Global, ast.Nonlocal))]
            names = sorted(_bound_names(tail))
            fbody = ([ast.Global(names=names)] if names else []) + tail
            main = ast.parse("async def _cg_main():\n    pass\n").body[0]
            main.body = fbody
            run = ast.parse("_cg_asyncio.run(_cg_main())").body[0]
            body = head + star + [main, run]

    tree.body = future + prelude + body
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"
