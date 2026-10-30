# 矢印キーでプレイヤーを動かして、落ちてくる星をキャッチ（pyxel版）
import pyxel
import random


class App:
    def __init__(self):
        pyxel.init(160, 120, title="Star Catch")
        self.x = 72
        self.stars = []
        self.score = 0
        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btn(pyxel.KEY_LEFT):
            self.x = max(self.x - 2, 0)
        if pyxel.btn(pyxel.KEY_RIGHT):
            self.x = min(self.x + 2, pyxel.width - 16)
        if pyxel.frame_count % 20 == 0:
            self.stars.append([random.randint(0, pyxel.width - 4), 0])
        for s in self.stars:
            s[1] += 1.5
        caught = [s for s in self.stars if s[1] > 100 and self.x - 4 < s[0] < self.x + 16]
        self.score += len(caught)
        self.stars = [s for s in self.stars if s not in caught and s[1] < pyxel.height]

    def draw(self):
        pyxel.cls(1)
        for x, y in self.stars:
            pyxel.circ(x + 2, y, 2, 10)
        pyxel.rect(self.x, 104, 16, 6, 11)
        pyxel.text(4, 4, f"SCORE {self.score}", 7)


App()
