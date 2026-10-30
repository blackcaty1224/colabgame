"""asyncify の動作テスト（デスクトップの pygame を画面なしモードで動かして確認する）。"""
import os, sys, textwrap
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from colabgame.asyncify import asyncify, TurtleProfile

# 30 回画面を更新したら QUIT イベントを送る
_orig_flip, _orig_update = pygame.display.flip, pygame.display.update
_count = {"n": 0}
def _fake(*a, **k):
    _count["n"] += 1
    if _count["n"] == 30:
        pygame.event.post(pygame.event.Event(pygame.QUIT))
    return _orig_flip()
pygame.display.flip = pygame.display.update = _fake

def run(src):
    _count["n"] = 0
    out = asyncify(textwrap.dedent(src))
    compile(out, "<t>", "exec")
    g = {"__name__": "__main__"}
    try:
        exec(out, g)
    except SystemExit:
        pass
    return out, g

TOPLEVEL = """
import pygame, sys
pygame.init()
screen = pygame.display.set_mode((200, 100))
clock = pygame.time.Clock()
x = 0
running = True
while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
    x += 1
    screen.fill((0, 0, 0))
    pygame.display.flip()
    clock.tick(1000)
pygame.quit()
result = x
"""

FUNCS = """
import pygame
from pygame.locals import *
score = 0
def add():
    global score
    score += 1
def game_over():
    pygame.time.wait(10)
def main():
    pygame.init()
    s = pygame.display.set_mode((100, 100))
    while True:
        for e in pygame.event.get():
            if e.type == QUIT:
                game_over()
                return
        add()
        pygame.display.update()
if __name__ == "__main__":
    main()
"""

CLASSY = """
import pygame
class Game:
    def __init__(self):
        pygame.init()
        self.s = pygame.display.set_mode((100, 100))
        self.frames = 0
    def run(self):
        while True:
            if any(e.type == pygame.QUIT for e in pygame.event.get()):
                break
            self.frames += 1
            pygame.display.flip()
g = Game()
g.run()
frames = g.frames
"""

def test_all():
    out, g = run(TOPLEVEL)
    assert "async def _cg_main" in out and g["result"] == 31, (out, g.get("result"))
    out, g = run(FUNCS)
    assert "async def main" in out and "await game_over()" in out and g["score"] == 30, out
    out, g = run(CLASSY)
    assert "async def run" in out and "await g.run()" in out and g["frames"] == 30, out
    t = asyncify("import turtle, time\nwn=turtle.Screen()\nwn.tracer(0)\nwhile True:\n    wn.update()\n    time.sleep(0.01)\nwhile True:\n    wn.update()\n", TurtleProfile)
    assert "await _cg_asyncio.sleep(0.01)" in t and t.count("await _cg_frame()") == 1, t
    print("ok")

if __name__ == "__main__":
    test_all()
    print(asyncify(textwrap.dedent(FUNCS)))
