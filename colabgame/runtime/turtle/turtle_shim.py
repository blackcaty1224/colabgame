"""colabgame: ブラウザ（Pyodide）上で動く turtle 互換モジュール。

標準の turtle は tkinter（デスクトップのウィンドウ）を使うのでブラウザでは動かない。
このモジュールは同じ名前・同じ使い方の命令を用意し、描画は HTML の canvas に任せる。
Python 側で状態を計算して「描画命令」を JavaScript に送り、JS 側がアニメーション表示する。
"""
import json as _json
import math as _math
import asyncio as _asyncio
import traceback as _tb

import js as _js
from pyodide.ffi import create_proxy as _create_proxy


class Terminator(Exception):
    """bye() のあとにタートルを動かそうとしたときに出る例外（標準の turtle と同じ）。"""


class TurtleGraphicsError(Exception):
    pass


class Vec2D(tuple):
    def __new__(cls, x, y):
        return tuple.__new__(cls, (x, y))

    def __add__(self, o):
        return Vec2D(self[0] + o[0], self[1] + o[1])

    def __sub__(self, o):
        return Vec2D(self[0] - o[0], self[1] - o[1])

    def __mul__(self, o):
        if isinstance(o, Vec2D):
            return self[0] * o[0] + self[1] * o[1]
        return Vec2D(self[0] * o, self[1] * o)

    def __rmul__(self, o):
        if isinstance(o, (int, float)):
            return Vec2D(self[0] * o, self[1] * o)
        return NotImplemented

    def __neg__(self):
        return Vec2D(-self[0], -self[1])

    def __abs__(self):
        return _math.hypot(self[0], self[1])

    def rotate(self, angle):
        a = _math.radians(angle)
        c, s = _math.cos(a), _math.sin(a)
        return Vec2D(self[0] * c - self[1] * s, self[0] * s + self[1] * c)

    def __getnewargs__(self):
        return (self[0], self[1])

    def __repr__(self):
        return "(%.2f,%.2f)" % self


def _circle_poly(r=10, n=20):
    return [[round(r * _math.sin(2 * _math.pi * i / n), 2), round(r * _math.cos(2 * _math.pi * i / n), 2)] for i in range(n)]


_SHAPES = {
    "arrow": [[-10, 0], [10, 0], [0, 10]],
    "turtle": [[0, 16], [-2, 14], [-1, 10], [-4, 7], [-7, 9], [-9, 8], [-6, 5], [-7, 1], [-5, -3], [-8, -6],
               [-6, -8], [-4, -5], [0, -7], [4, -5], [6, -8], [8, -6], [5, -3], [7, 1], [6, 5], [9, 8],
               [7, 9], [4, 7], [1, 10], [2, 14]],
    "circle": _circle_poly(),
    "square": [[10, -10], [10, 10], [-10, 10], [-10, -10]],
    "triangle": [[10, -5.77], [0, 11.55], [-10, -5.77]],
    "classic": [[0, 0], [-5, -9], [0, -7], [5, -9]],
    "blank": [],
}
_SPEEDS = {"fastest": 0, "fast": 10, "normal": 6, "slow": 3, "slowest": 1}

_screen_obj = None
_pen_obj = None


def _send(ev):
    if _screen_obj is not None and _screen_obj._closed:
        raise Terminator()
    _js.window.cgPush(_json.dumps(ev))


def _css(c):
    if isinstance(c, str):
        s = c.strip()
        return s if s.startswith("#") else s.replace(" ", "").lower()
    if isinstance(c, (tuple, list)) and len(c) == 3:
        r, g, b = c
        if _screen()._colormode == 1.0:
            r, g, b = r * 255, g * 255, b * 255
        return "rgb(%d,%d,%d)" % (round(r), round(g), round(b))
    raise TurtleGraphicsError("bad color sequence: %r" % (c,))


def _color_arg(args):
    if len(args) == 1:
        return args[0]
    if len(args) == 3:
        return tuple(args)
    raise TurtleGraphicsError("bad color arguments: %r" % (args,))


def _knorm(key):
    return key if key is None or len(key) == 1 else key.lower()


def _xy(x, y=None):
    if y is None:
        if isinstance(x, Turtle):
            return x._x, x._y
        return float(x[0]), float(x[1])
    return float(x), float(y)


# ----------------------------------------------------------------------------
# Screen
# ----------------------------------------------------------------------------
class _Screen:
    def __init__(self):
        self._closed = False
        self._w, self._h = 600, 600
        self._bg = "white"
        self._colormode = 1.0
        self._tracer = 1
        self._delay = 10
        self._mode = "standard"
        self._turtles = []
        self._tid = 0
        self._sid = 0
        self._fid = 0
        self._timer_id = 0
        self._shapes = {k: {"type": "polygon", "pts": v} for k, v in _SHAPES.items()}
        self._reset_handlers()

    def _reset_handlers(self):
        self._keypress = {}
        self._keyrelease = {}
        self._click = {}
        self._timers = {}
        self._dragging = None

    # --- 画面 ----------------------------------------------------------------
    def setup(self, width=0.5, height=0.75, startx=None, starty=None):
        w = int(width * 1200) if isinstance(width, float) and width <= 1 else int(width)
        h = int(height * 800) if isinstance(height, float) and height <= 1 else int(height)
        self._w, self._h = w, h
        _send({"op": "setup", "w": w, "h": h})

    def screensize(self, canvwidth=None, canvheight=None, bg=None):
        if canvwidth is None and canvheight is None and bg is None:
            return self._w, self._h
        if canvwidth or canvheight:
            self.setup(canvwidth or self._w, canvheight or self._h)
        if bg is not None:
            self.bgcolor(bg)

    def window_width(self):
        return self._w

    def window_height(self):
        return self._h

    def title(self, titlestring):
        _send({"op": "title", "t": str(titlestring)})

    def bgcolor(self, *args):
        if not args:
            return self._bg
        self._bg = _color_arg(args)
        _send({"op": "bg", "c": _css(self._bg)})

    def bgpic(self, picname=None):
        if picname is None:
            return getattr(self, "_bgpic", "nopic")
        self._bgpic = picname
        _send({"op": "bgpic", "src": None if picname == "nopic" else picname})

    def colormode(self, cmode=None):
        if cmode is None:
            return 255 if self._colormode == 255 else 1.0
        self._colormode = 255 if cmode == 255 else 1.0

    def mode(self, mode=None):
        if mode is None:
            return self._mode
        mode = mode.lower()
        if mode not in ("standard", "logo", "world"):
            raise TurtleGraphicsError("No turtle-graphics-mode %s" % mode)
        self._mode = mode
        if mode != "world":
            _send({"op": "world", "w": None})
        for t in self._turtles:
            t.reset()

    def setworldcoordinates(self, llx, lly, urx, ury):
        self._mode = "world"
        _send({"op": "world", "w": {"llx": llx, "lly": lly, "urx": urx, "ury": ury}})

    def tracer(self, n=None, delay=None):
        if n is None:
            return self._tracer
        self._tracer = int(n)
        if delay is not None:
            self._delay = delay

    def delay(self, delay=None):
        if delay is None:
            return self._delay
        self._delay = delay

    def update(self):
        _send({"op": "update"})

    def turtles(self):
        return list(self._turtles)

    def getcanvas(self):
        raise TurtleGraphicsError("ブラウザ版では getcanvas() は使えません")

    def register_shape(self, name, shape=None):
        if shape is None:
            d = {"type": "image", "src": name}
        else:
            if hasattr(shape, "_pts"):
                shape = shape._pts
            d = {"type": "polygon", "pts": [[float(x), float(y)] for x, y in shape]}
        self._shapes[name] = d
        _send({"op": "shape", "name": name, "def": d})

    addshape = register_shape

    def getshapes(self):
        return sorted(self._shapes)

    # --- 入力 ----------------------------------------------------------------
    def listen(self, xdummy=None, ydummy=None):
        pass

    def onkeyrelease(self, fun, key):
        k = _knorm(key)
        if fun is None:
            self._keyrelease.pop(k, None)
        else:
            self._keyrelease[k] = fun

    onkey = onkeyrelease

    def onkeypress(self, fun, key=None):
        k = _knorm(key)
        if fun is None:
            self._keypress.pop(k, None)
        else:
            self._keypress[k] = fun

    def onscreenclick(self, fun, btn=1, add=None):
        if fun is None:
            self._click.pop(btn, None)
        else:
            self._click[btn] = fun

    onclick = onscreenclick

    def ontimer(self, fun, t=0):
        self._timer_id += 1
        self._timers[self._timer_id] = fun
        _js.window.cgTimer(self._timer_id, int(t))

    def textinput(self, title, prompt):
        r = _js.window.prompt("%s\n%s" % (title, prompt))
        return None if r is None else str(r)

    def numinput(self, title, prompt, default=None, minval=None, maxval=None):
        while True:
            r = _js.window.prompt("%s\n%s" % (title, prompt), "" if default is None else str(default))
            if r is None:
                return None
            try:
                v = float(r)
            except ValueError:
                continue
            if (minval is None or v >= minval) and (maxval is None or v <= maxval):
                return v

    # --- 終了・リセット --------------------------------------------------------
    def mainloop(self):
        pass

    done = mainloop

    def exitonclick(self):
        self.onscreenclick(lambda x, y: self.bye())

    def bye(self):
        if not self._closed:
            _send({"op": "bye"})
            self._closed = True

    def clearscreen(self):
        global _pen_obj
        _send({"op": "clearscreen"})
        self._turtles = []
        self._bg = "white"
        self._tracer = 1
        self._mode = "standard"
        self._reset_handlers()
        _pen_obj = None

    clear = clearscreen

    def resetscreen(self):
        for t in self._turtles:
            t.reset()

    reset = resetscreen


TurtleScreen = _Screen


def Screen():
    global _screen_obj
    if _screen_obj is None:
        _screen_obj = _Screen()
        _send({"op": "setup", "w": _screen_obj._w, "h": _screen_obj._h})
    return _screen_obj


_screen = Screen


# ----------------------------------------------------------------------------
# Turtle
# ----------------------------------------------------------------------------
class Turtle:
    def __init__(self, shape="classic", undobuffersize=1000, visible=True):
        s = _screen()
        self.screen = s
        s._tid += 1
        self._id = s._tid
        self._init_state()
        self._shape = shape
        self._vis = visible
        self._click = self._drag = self._release = None
        s._turtles.append(self)
        self._send("new")

    def _init_state(self):
        self._x = self._y = 0.0
        self._a = 90.0 if self.screen._mode == "logo" else 0.0
        self._down = True
        self._width = 1
        self._pc = self._fc = "black"
        self._pcss = self._fcss = "black"
        self._speed = 3
        self._sw = self._sl = 1
        self._ol = 1
        self._tilt = 0.0
        self._filling = False
        self._fillpts = []
        self._fid = None
        self._stamps = []

    # --- 内部 ----------------------------------------------------------------
    def _snap(self):
        return {"h": self._a, "vis": self._vis, "shape": self._shape, "pc": self._pcss, "fc": self._fcss,
                "sw": self._sw, "sl": self._sl, "ol": self._ol, "tilt": self._tilt}

    def _send(self, op, **kw):
        ev = {"op": op, "id": self._id, "s": self._snap()}
        ev.update(kw)
        _send(ev)

    def _spd(self):
        tr = self.screen._tracer
        if tr <= 0 or self._speed == 0:
            return 0
        return self._speed * tr

    def _goto(self, x, y):
        kw = {"x": x, "y": y, "spd": self._spd()}
        if self._down:
            kw["line"] = [self._width, self._pcss]
        self._x, self._y = x, y
        if self._filling:
            self._fillpts.append((x, y))
        self._send("move", **kw)

    def _rotate(self, deg):
        self._a = (self._a + deg) % 360
        self._send("state")

    def _user_angle(self, a):
        return (90 - a) % 360 if self.screen._mode == "logo" else a % 360

    # --- 移動 ----------------------------------------------------------------
    def forward(self, distance):
        a = _math.radians(self._a)
        self._goto(self._x + distance * _math.cos(a), self._y + distance * _math.sin(a))

    fd = forward

    def back(self, distance):
        self.forward(-distance)

    bk = backward = back

    def left(self, angle):
        self._rotate(angle)

    lt = left

    def right(self, angle):
        self._rotate(-angle)

    rt = right

    def goto(self, x, y=None):
        self._goto(*_xy(x, y))

    setpos = setposition = goto

    def teleport(self, x=None, y=None, *, fill_gap=False):
        down, self._down = self._down, False
        self._goto(self._x if x is None else x, self._y if y is None else y)
        self._down = down

    def setx(self, x):
        self._goto(float(x), self._y)

    def sety(self, y):
        self._goto(self._x, float(y))

    def setheading(self, to_angle):
        self._a = (90 - to_angle) % 360 if self.screen._mode == "logo" else to_angle % 360
        self._send("state")

    seth = setheading

    def home(self):
        self.goto(0, 0)
        self.setheading(0)

    def circle(self, radius, extent=None, steps=None):
        if extent is None:
            extent = 360
        if steps is None:
            frac = abs(extent) / 360
            steps = 1 + int(min(11 + abs(radius) / 6.0, 59.0) * frac)
        w = 1.0 * extent / steps
        w2 = 0.5 * w
        length = 2.0 * radius * _math.sin(_math.radians(w2))
        if radius < 0:
            length, w, w2 = -length, -w, -w2
        self._a = (self._a + w2) % 360
        for _ in range(steps):
            self.forward(length)
            self._a = (self._a + w) % 360
        self._rotate(-w2)

    def dot(self, size=None, *color):
        if size is None:
            size = max(self._width + 4, self._width * 2)
        c = _css(_color_arg(color)) if color else self._pcss
        self._send("dot", x=self._x, y=self._y, r=size, c=c)

    def stamp(self):
        self.screen._sid += 1
        sid = self.screen._sid
        self._stamps.append(sid)
        self._send("stamp", sid=sid)
        return sid

    def clearstamp(self, stampid):
        if stampid in self._stamps:
            self._stamps.remove(stampid)
        self._send("clearstamp", sids=[stampid])

    def clearstamps(self, n=None):
        if n is None:
            ids = self._stamps[:]
        elif n >= 0:
            ids = self._stamps[:n]
        else:
            ids = self._stamps[n:]
        for i in ids:
            self._stamps.remove(i)
        self._send("clearstamp", sids=ids)

    def speed(self, speed=None):
        if speed is None:
            return self._speed
        if speed in _SPEEDS:
            speed = _SPEEDS[speed]
        self._speed = int(round(speed)) if 0.5 < speed < 10.5 else 0

    # --- 状態の取得 ------------------------------------------------------------
    def position(self):
        return Vec2D(self._x, self._y)

    pos = position

    def xcor(self):
        return self._x

    def ycor(self):
        return self._y

    def heading(self):
        return self._user_angle(self._a)

    def towards(self, x, y=None):
        tx, ty = _xy(x, y)
        return self._user_angle(_math.degrees(_math.atan2(ty - self._y, tx - self._x)))

    def distance(self, x, y=None):
        tx, ty = _xy(x, y)
        return _math.hypot(tx - self._x, ty - self._y)

    def degrees(self, fullcircle=360.0):
        if fullcircle != 360.0:
            raise TurtleGraphicsError("ブラウザ版では degrees(360) のみ対応しています")

    def radians(self):
        raise TurtleGraphicsError("ブラウザ版では radians() には対応していません")

    # --- ペン ----------------------------------------------------------------
    def pendown(self):
        self._down = True

    pd = down = pendown

    def penup(self):
        self._down = False

    pu = up = penup

    def isdown(self):
        return self._down

    def pensize(self, width=None):
        if width is None:
            return self._width
        self._width = width

    width = pensize

    def pencolor(self, *args):
        if not args:
            return self._pc
        self._pc = _color_arg(args)
        self._pcss = _css(self._pc)
        self._send("state")

    def fillcolor(self, *args):
        if not args:
            return self._fc
        self._fc = _color_arg(args)
        self._fcss = _css(self._fc)
        self._send("state")

    def color(self, *args):
        if not args:
            return self._pc, self._fc
        if len(args) == 1:
            pc = fc = args[0]
        elif len(args) == 2:
            pc, fc = args
        elif len(args) == 3:
            pc = fc = tuple(args)
        else:
            raise TurtleGraphicsError("bad color arguments")
        self._pc, self._pcss = pc, _css(pc)
        self._fc, self._fcss = fc, _css(fc)
        self._send("state")

    def filling(self):
        return self._filling

    def begin_fill(self):
        self.screen._fid += 1
        self._fid = self.screen._fid
        self._filling = True
        self._fillpts = [(self._x, self._y)]
        self._send("beginfill", fid=self._fid)

    def end_fill(self):
        if self._filling and len(self._fillpts) > 2:
            pts = [c for p in self._fillpts for c in p]
            self._send("fill", fid=self._fid, pts=pts, c=self._fcss)
        self._filling = False
        self._fillpts = []

    def write(self, arg, move=False, align="left", font=("Arial", 8, "normal")):
        family, size = font[0], font[1]
        style = font[2] if len(font) > 2 else "normal"
        css_style = " ".join(w for w in str(style).split() if w in ("bold", "italic"))
        css_font = "%s %dpx %s, sans-serif" % (css_style, round(size * 1.33), "'%s'" % family)
        text = str(arg)
        self._send("text", x=self._x, y=self._y, t=text, align=align, font=css_font.strip(), c=self._pcss)
        if move:
            w = float(_js.window.cgMeasure(text, css_font))
            self._goto(self._x + w, self._y)

    # --- 見た目 ----------------------------------------------------------------
    def showturtle(self):
        self._vis = True
        self._send("state")

    st = showturtle

    def hideturtle(self):
        self._vis = False
        self._send("state")

    ht = hideturtle

    def isvisible(self):
        return self._vis

    def shape(self, name=None):
        if name is None:
            return self._shape
        if name not in self.screen._shapes:
            raise TurtleGraphicsError("There is no shape named %s" % name)
        self._shape = name
        self._send("state")

    def shapesize(self, stretch_wid=None, stretch_len=None, outline=None):
        if stretch_wid is None and stretch_len is None and outline is None:
            return self._sw, self._sl, self._ol
        if stretch_wid is not None and stretch_len is None:
            stretch_len = stretch_wid
        if stretch_wid is not None:
            self._sw = stretch_wid
        if stretch_len is not None:
            self._sl = stretch_len
        if outline is not None:
            self._ol = outline
        self._send("state")

    turtlesize = shapesize

    def tilt(self, angle):
        self._tilt = (self._tilt + angle) % 360
        self._send("state")

    def tiltangle(self, angle=None):
        if angle is None:
            return self._tilt
        self._tilt = angle % 360
        self._send("state")

    settiltangle = tiltangle

    # --- その他 ----------------------------------------------------------------
    def clear(self):
        self._send("clear")

    def reset(self):
        self.clear()
        vis, shape = self._vis, self._shape
        self._init_state()
        self._vis, self._shape = vis, shape
        self._send("move", x=0.0, y=0.0, spd=0)

    def onclick(self, fun, btn=1, add=None):
        self._click = fun

    def ondrag(self, fun, btn=1, add=None):
        self._drag = fun

    def onrelease(self, fun, btn=1, add=None):
        self._release = fun

    def undo(self):
        pass

    def getscreen(self):
        return self.screen

    def getturtle(self):
        return self

    getpen = getturtle

    def clone(self):
        t = Turtle(shape=self._shape, visible=self._vis)
        for k in ("_down", "_width", "_pc", "_fc", "_pcss", "_fcss", "_speed", "_sw", "_sl", "_ol", "_tilt"):
            setattr(t, k, getattr(self, k))
        t._x, t._y, t._a = self._x, self._y, self._a
        t._send("move", x=t._x, y=t._y, spd=0)
        return t

    def _hit(self, x, y):
        r = 10 * max(self._sw, self._sl, 1)
        return self._vis and _math.hypot(x - self._x, y - self._y) <= r


Pen = RawTurtle = RawPen = Turtle


class Shape:
    def __init__(self, type_, data=None):
        if type_ != "polygon":
            raise TurtleGraphicsError("ブラウザ版の Shape は polygon のみ対応しています")
        self._pts = list(data or [])


def _getpen():
    global _pen_obj
    if _pen_obj is None:
        _pen_obj = Turtle()
    return _pen_obj


getpen = getturtle = _getpen


# ----------------------------------------------------------------------------
# ブラウザからのイベント受け取り
# ----------------------------------------------------------------------------
def _report():
    _js.window.cgError(_tb.format_exc())


async def _guard(coro):
    try:
        await coro
    except Terminator:
        pass
    except Exception:
        _report()


def _call(f, *args):
    r = f(*args)
    if _asyncio.iscoroutine(r):
        _asyncio.ensure_future(_guard(r))


def _dispatch(kind, a=None, b=None, c=None):
    s = _screen_obj
    if s is None or s._closed:
        return
    try:
        if kind == "keydown":
            for k in (_knorm(a), None):
                f = s._keypress.get(k)
                if f:
                    _call(f)
        elif kind == "keyup":
            f = s._keyrelease.get(_knorm(a))
            if f:
                _call(f)
        elif kind == "click":
            btn, x, y = int(a), float(b), float(c)
            for t in reversed(s._turtles):
                if t._click and t._hit(x, y):
                    _call(t._click, x, y)
                    break
            f = s._click.get(btn)
            if f:
                _call(f, x, y)
        elif kind == "down":
            x, y = float(b), float(c)
            s._dragging = next((t for t in reversed(s._turtles) if (t._drag or t._release) and t._hit(x, y)), None)
        elif kind == "move":
            t = s._dragging
            if t is not None and t._drag:
                _call(t._drag, float(b), float(c))
        elif kind == "up":
            t, s._dragging = s._dragging, None
            if t is not None and t._release:
                _call(t._release, float(b), float(c))
        elif kind == "timer":
            f = s._timers.pop(int(a), None)
            if f:
                _call(f)
    except Terminator:
        pass
    except Exception:
        _report()


_dispatch_proxy = _create_proxy(_dispatch)
_js.window.cgSetDispatcher(_dispatch_proxy)


async def _cg_frame():
    """1フレーム（描画待ちの命令がすべて画面に出るまで）待つ。colabgame が自動で挿入する。"""
    if _screen_obj is not None and _screen_obj._closed:
        raise Terminator()
    await _js.window.cgFrame()


# ----------------------------------------------------------------------------
# from turtle import * で使える関数
# ----------------------------------------------------------------------------
_SCREEN_FUNCS = ["addshape", "bgcolor", "bgpic", "bye", "clearscreen", "colormode", "delay", "exitonclick",
                 "getcanvas", "getshapes", "listen", "mainloop", "mode", "numinput", "onkey", "onkeypress",
                 "onkeyrelease", "onscreenclick", "ontimer", "register_shape", "resetscreen", "screensize",
                 "setup", "setworldcoordinates", "textinput", "title", "tracer", "turtles", "update",
                 "window_height", "window_width", "done"]
_TURTLE_FUNCS = ["back", "backward", "begin_fill", "bk", "circle", "clear", "clearstamp", "clearstamps", "clone",
                 "color", "degrees", "distance", "dot", "down", "end_fill", "fd", "fillcolor", "filling",
                 "forward", "goto", "heading", "hideturtle", "home", "ht", "isdown", "isvisible", "left", "lt",
                 "onclick", "ondrag", "onrelease", "pd", "pendown", "pencolor", "pensize",
                 "penup", "pos", "position", "pu", "radians", "reset", "right", "rt", "seth", "setheading",
                 "setpos", "setposition", "settiltangle", "setx", "sety", "shape", "shapesize", "showturtle",
                 "speed", "st", "stamp", "teleport", "tilt", "tiltangle", "towards", "turtlesize", "undo", "up",
                 "width", "write", "xcor", "ycor"]


def _make_screen_func(name):
    def f(*args, **kw):
        return getattr(_screen(), name)(*args, **kw)
    f.__name__ = name
    return f


def _make_turtle_func(name):
    def f(*args, **kw):
        return getattr(_getpen(), name)(*args, **kw)
    f.__name__ = name
    return f


for _n in _SCREEN_FUNCS:
    globals()[_n] = _make_screen_func(_n)
for _n in _TURTLE_FUNCS:
    globals()[_n] = _make_turtle_func(_n)

__all__ = (["Screen", "Turtle", "RawTurtle", "Pen", "RawPen", "TurtleScreen", "Vec2D", "Shape", "Terminator",
            "TurtleGraphicsError", "getpen", "getturtle"] + _SCREEN_FUNCS + _TURTLE_FUNCS)
