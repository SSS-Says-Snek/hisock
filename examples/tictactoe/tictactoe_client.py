import os
import sys
import pathlib

PATH = pathlib.Path(__file__)

# Import stuff, as this situation's a bit wonky
# This is not needed in usual hisock code. However, in this odd case,
# imports need to be configured first like this
sys.path.append(str(PATH.parent.parent.parent))  # Not needed usually; used to run examples

from hisock import (
    connect
)


# Data class, as to prevent using those dirty globals
class Data:
    def __init__(self):
        self.tictactoe_opponent = None  # Tic Tac Toe opponent name
        self.board = [' ' for _ in range(9)]  # Tic Tac Toe board
        self.board_layout = "{} |{} |{} \n--+--+--\n{} |{} |{} \n--+--+--\n{} |{} |{} \n"
        self.letter = ''


def clear():
    """Well, no pycharm support, so boo hoo"""
    if os.name == "nt":
        os.system("cls")
    elif os.name == "posix":
        os.system("clear")


def run():
    # IP, Port, and Name establishment
    ip_input = input("Enter IP of where server is hosted: ")

    port_input = input("Enter port of server: ")
    while port_input == '':
        port_input = input("Enter port of server: ")
    port_input = int(port_input)

    name = input("Enter name (MAX LENGTH: 32): ")
    while name == '' or len(name) > 32:
        name = input("Enter name (MAX LENGTH: 32): ")

    print(f"Connecting to server at {ip_input}:{port_input}...", end=" ")

    server = connect((ip_input, port_input), name)

    print("SUCCESS!")
    clear()
    print("Waiting for pairing... ")

    data = Data()

    # Hisock message receive decorators
    @server.on("game_start")
    def game_started(opponent: str):
        print(f"Pairing succeeded! Opponent: \"{opponent}\"")
        data.tictactoe_opponent = opponent
        goes_first = server.recv_raw()

        if goes_first == b"First":
            # Receives message from server; goes first, therefore is X
            data.letter = "X"
            print("You are X")
            print(data.board_layout.format(*data.board))
            move_input = input("Enter your move (1-9, left to right, top to bottom): ")
            while (
                    move_input == '' or not move_input.isdigit() or
                    (move_input.isdigit() and not 1 <= int(move_input) <= 9)
            ):
                move_input = input("Enter your move (1-9, left to right, top to bottom): ")
            move_input = int(move_input)
            data.board[move_input - 1] = "X"

            # Refreshes the screen
            clear()
            print("You are X")
            print(data.board_layout.format(*data.board))

            # Sends to server the index of the move
            server.send("player_turn", str(move_input - 1).encode())
        else:
            # Goes last, therefore is O
            data.letter = "O"
            print("You are O")
            print(data.board_layout.format(*data.board))

    @server.on("player_turn")
    def player_turn(move: int):
        # GETS CALLED EVERY TURN AFTER FIRST DETERMINATION

        data.board[move] = "X" if data.letter == "O" else "O"

        # Refreshes the screen
        clear()
        print(f"You are {data.letter}")
        print(data.board_layout.format(*data.board))

        move_input = input("Enter your move (1-9, left to right, top to bottom): ")
        while (
                move_input == '' or not move_input.isdigit() or
                (move_input.isdigit() and not 1 <= int(move_input) <= 9) or
                (move_input.isdigit() and data.board[int(move_input) - 1] != " ")
        ):
            move_input = input("Enter your move (1-9, left to right, top to bottom): ")
        move_input = int(move_input)
        data.board[move_input - 1] = data.letter

        # Refreshes the screen after input
        clear()
        print(f"You are {data.letter}")
        print(data.board_layout.format(*data.board))

        server.send("player_turn", str(move_input - 1).encode())

    @server.on("win")
    def player_win(missing_move: int):
        # Player won

        if data.board[missing_move] == " ":
            data.board[missing_move] = "X" if data.letter == "O" else "O"

        # Refreshes the screen
        clear()
        print("You win!")
        print(data.board_layout.format(*data.board))

        sys.exit()

    @server.on("lose")
    def player_lose(missing_move: int):
        # Player lost

        if data.board[missing_move] == " ":
            data.board[missing_move] = "X" if data.letter == "O" else "O"

        # Refreshes the screen
        clear()
        print("You lose!")
        print(data.board_layout.format(*data.board))

        sys.exit()

    @server.on("tie")
    def player_tie(missing_move: int):
        # Players tied

        if data.board[missing_move] == " ":
            data.board[missing_move] = "X" if data.letter == "O" else "O"

        # Refreshes the screen
        clear()
        print("You tied!")
        print(data.board_layout.format(*data.board))

        sys.exit()

    @server.on("opp_disc")
    def opponent_leave(opp_name: str):
        clear()
        print(f"Opponent \"{opp_name}\"disconnected; disconnecting from server...")
        raise SystemExit

    while True:
        # Updates server
        server.update()


if __name__ == "__main__":
    run()
