# 矢印キーで四角を動かしてコインを集めるゲーム（pygame版）
import pygame
import random

pygame.init()
screen = pygame.display.set_mode((640, 480))
pygame.display.set_caption("コインあつめ")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 40)

player = pygame.Rect(300, 220, 40, 40)
coin = pygame.Rect(random.randint(20, 600), random.randint(20, 440), 20, 20)
score = 0
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()
    speed = 5
    if keys[pygame.K_LEFT]:
        player.x -= speed
    if keys[pygame.K_RIGHT]:
        player.x += speed
    if keys[pygame.K_UP]:
        player.y -= speed
    if keys[pygame.K_DOWN]:
        player.y += speed
    player.clamp_ip(screen.get_rect())

    if player.colliderect(coin):
        score += 1
        coin.topleft = (random.randint(20, 600), random.randint(20, 440))

    screen.fill((30, 30, 50))
    pygame.draw.rect(screen, (80, 200, 255), player)
    pygame.draw.ellipse(screen, (255, 210, 0), coin)
    screen.blit(font.render(f"SCORE: {score}", True, (255, 255, 255)), (10, 10))
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
