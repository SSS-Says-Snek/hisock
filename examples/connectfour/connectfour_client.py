import hisock
import _shared as shared

import pygame
import pygame_gui

WIDTH, HEIGHT = 800, 600

addr, name, _ = hisock.input_client_config(group_prompt=None)
running = True

client = hisock.ThreadedHiSockClient(addr, name)
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()


@client.on("start")
def on_start(data):
    print(data)


@client.on("disconn")
def on_disconn(reason: str):
    print(reason)


client.start()

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((0, 50, 140))

    clock.tick(30)
    pygame.display.update()

pygame.quit()
client.stop()
