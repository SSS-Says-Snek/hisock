import sys
import pathlib
import pygame

from functools import lru_cache

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
        self.turn = None
        self.game_start = False


@lru_cache
def load_font(size):
    return pygame.font.Font(None, size)


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

    data = Data()

    @server.on("game_start")
    def game_start(opponent: str):
        data.game_start = True
        data.tictactoe_opponent = opponent
        goes_first = server.recv_raw()

        if goes_first == b"First":
            data.turn = True
            data.letter = "X"
        else:
            data.turn = False
            data.letter = "O"

    screen = pygame.display.set_mode((400, 400))

    server.start_client()

    opp_font = load_font(20)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                server.stop_client()
                pygame.quit()
                sys.exit()
            elif (
                    event.type == pygame.MOUSEBUTTONDOWN and
                    data.game_start and
                    data.turn
            ):
                bod_idx = [
                    xy // 133 for xy in event.pos
                ]

                board_idx = bod_idx[0] * 3 + bod_idx[1]
                data.board[board_idx] = data.letter
                print(bod_idx)

            screen.fill((51, 168, 12))
            pygame.draw.line(
                screen, (0, 0, 0),
                (133, 20), (133, 380),
                width=10
            )
            pygame.draw.line(
                screen, (0, 0, 0),
                (266, 20), (266, 380),
                width=10
            )
            pygame.draw.line(
                screen, (0, 0, 0),
                (20, 133), (380, 133),
                width=10
            )
            pygame.draw.line(
                screen, (0, 0, 0),
                (20, 266), (380, 266),
                width=10
            )
            
            if data.tictactoe_opponent is None:
                opp_txt = opp_font.render("Waiting for opponent...", True, (0, 0, 0))
            else:
                opp_txt = opp_font.render(f"Opponent: {data.tictactoe_opponent}", True, (0, 0, 0))

            name_txt = opp_font.render(f"You are: {name}", True, (0, 0, 0))

            if data.turn:
                turn_txt = opp_font.render("Your turn", True, (0, 0, 0))
            elif data.turn is not None:
                turn_txt = opp_font.render("Opponent's Turn", True, (0, 0, 0))
            else:
                turn_txt = None

            screen.blit(opp_txt, (0, 0))
            screen.blit(name_txt, (0, 20))

            if turn_txt is not None:
                screen.blit(turn_txt, opp_txt.get_rect(topright=(380, 0)))

            pygame.display.update()


if __name__ == "__main__":
    run()
