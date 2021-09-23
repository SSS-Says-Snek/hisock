import os
import sys
import pathlib

PATH = pathlib.Path('.')

sys.path.append(str(PATH.parent.parent))  # Not needed usually; used to run examples

try:
    from hisock import (
        connect,
        utils
    )
except ImportError as e:
    print("Because I'm dumb, run the example at the root of the package. Thank you!")
    sys.exit()


class Data:
    def __init__(self):
        self.tictactoe_opponent = None
        self.board = [' ' for _ in range(9)]
        self.board_layout = "{} |{} |{} \n--+--+--\n{} |{} |{} \n--+--+--\n{} |{} |{} \n"
        self.letter = ''


def clear():
    """Well, no pycharm support, so boo hoo"""
    if os.name == "nt":
        os.system("cls")
    elif os.name == "posix":
        os.system("clear")


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


@server.on("game_start")
def game_started(opponent: str):
    print(f"Pairing succeeded! Opponent: \"{opponent}\"")
    data.tictactoe_opponent = opponent
    goes_first = server.recv_raw()

    if goes_first == b"First":
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
        clear()
        print("You are X")
        print(data.board_layout.format(*data.board))

        server.send("player_turn", str(move_input - 1).encode())
    else:
        data.letter = "O"
        print("You are O")
        print(data.board_layout.format(*data.board))


@server.on("player_turn")
def player_turn(move: int):
    data.board[move] = "X" if data.letter == "O" else "O"
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

    clear()
    print(f"You are {data.letter}")
    print(data.board_layout.format(*data.board))

    server.send("player_turn", str(move_input - 1).encode())


@server.on("win")
def player_win(missing_move: int):
    if data.board[missing_move] == " ":
        data.board[missing_move] = "X" if data.letter == "O" else "O"
    clear()
    print("You win!")
    print(data.board_layout.format(*data.board))

    sys.exit()


@server.on("lose")
def player_lose(missing_move: int):
    if data.board[missing_move] == " ":
        data.board[missing_move] = "X" if data.letter == "O" else "O"
    clear()
    print("You lose!")
    print(data.board_layout.format(*data.board))

    sys.exit()


@server.on("tie")
def player_tie(missing_move: int):
    if data.board[missing_move] == " ":
        data.board[missing_move] = "X" if data.letter == "O" else "O"
    clear()
    print("You tied!")
    print(data.board_layout.format(*data.board))

    sys.exit()


@server.on("samename")
def same_name(_):
    print("You have the same name as someone! Aborting...")
    server.close()
    sys.exit()


while True:
    server.update()
