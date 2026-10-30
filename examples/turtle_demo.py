# 矢印キーでタートルを動かして、赤い点を集めるゲーム（turtle版）
import turtle
import random
import time

wn = turtle.Screen()
wn.title("タートルで点あつめ")
wn.setup(600, 500)
wn.bgcolor("#dff3e4")
wn.tracer(0)

player = turtle.Turtle()
player.shape("turtle")
player.color("#2e7d32")
player.penup()
player.shapesize(1.5)

food = turtle.Turtle()
food.shape("circle")
food.color("crimson")
food.penup()
food.goto(100, 100)

pen = turtle.Turtle()
pen.hideturtle()
pen.penup()
pen.goto(-280, 210)

score = 0
keys = set()

def show_score():
    pen.clear()
    pen.write(f"スコア: {score}", font=("Arial", 18, "bold"))

for k in ("Up", "Down", "Left", "Right"):
    wn.onkeypress(lambda k=k: keys.add(k), k)
    wn.onkeyrelease(lambda k=k: keys.discard(k), k)
wn.listen()
show_score()

while True:
    if "Left" in keys:
        player.left(5)
    if "Right" in keys:
        player.right(5)
    if "Up" in keys:
        player.forward(4)
    if "Down" in keys:
        player.backward(3)
    x, y = player.position()
    if abs(x) > 290 or abs(y) > 240:
        player.goto(max(-290, min(290, x)), max(-240, min(240, y)))
    if player.distance(food) < 20:
        score += 1
        food.goto(random.randint(-260, 260), random.randint(-200, 200))
        show_score()
    wn.update()
    time.sleep(1 / 60)
