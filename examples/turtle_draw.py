# アニメーションで図形を描く（turtle版）
import turtle

t = turtle.Turtle()
t.speed(8)
colors = ["red", "orange", "gold", "green", "blue", "purple"]
for i in range(36):
    t.pencolor(colors[i % 6])
    t.circle(80)
    t.left(10)
t.hideturtle()
turtle.done()
