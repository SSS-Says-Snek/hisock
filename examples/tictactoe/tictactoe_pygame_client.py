import sys
import pathlib
import pygame

PATH = pathlib.Path(__file__)

# Import stuff, as this situation's a bit wonky
# This is not needed in usual hisock code. However, in this odd case (two same named directories),
# imports need to be configured first like this
sys.path.append(str(PATH.parent.parent.parent))  # Not needed usually; used to run examples

from hisock.client import (
    threaded_connect
)


# Data class, as to prevent using those dirty globals
class Data:
    def __init__(self):
        self.tictactoe_opponent = None  # Tic Tac Toe opponent name
        self.board = [' ' for _ in range(9)]  # Tic Tac Toe board
        self.letter = ''


def run():
    pygame.init()

    ip_input = input("Enter IP of where server is hosted: ")

    port_input = input("Enter port of server: ")
    while port_input == '':
        port_input = input("Enter port of server: ")
    port_input = int(port_input)

    name = input("Enter name (MAX LENGTH: 32): ")
    while name == '' or len(name) > 32:
        name = input("Enter name (MAX LENGTH: 32): ")

    print(f"Connecting to server at {ip_input}:{port_input}...", end=" ")

    server = threaded_connect((ip_input, port_input), name)
    print("SUCCESS!")

    @server.on("game_start")
    def game_start(opponent: str):
        pass

    screen = pygame.display.set_mode((400, 400))

    server.start_client()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                server.close()
                pygame.quit()
                sys.exit()

            screen.fill((51, 168, 12))
            pygame.draw.line(
                screen, (0, 0, 0),
                (133, 20), (133, 380),
                width=10
            )

            pygame.display.update()


if __name__ == "__main__":
    run()
