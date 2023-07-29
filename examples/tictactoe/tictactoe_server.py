"""HiSock TicTacToe server side"""

### Setup ###
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join("..", "..")))

from shared import get_ip_addr_port, log_error

import hisock

# Setup server
print("TicTacToe Server")
ip_addr, port = get_ip_addr_port()
print(f"Starting server at {ip_addr}:{port}", end="... ")
try:
    server = hisock.start_server((ip_addr, port))
except Exception as error:
    print(f"fail!\n{error!s}")
    exit(1)
print("done!")

### Classes ###
class Data:
    paired_clients = []
    turn = "x"

    @staticmethod
    def add_player(client_info: dict, player_turn: str):
        Data.paired_clients.append(
            {
                "name": client_info["name"],
                "ip": client_info["ip"],
                "turn": player_turn,
                "playing": False,
            }
        )

    @staticmethod
    def get_client_info(name: str = None, turn: str = None) -> tuple[dict, int]:
        """
        Takes in a name (or turn) and returns the dictionary which the
        client is in and the index of the client in the paired_clients list.
        If the client is not found, returns (None, -1).
        """

        compare_to: str = name
        look_for: str = "name"
        if turn is not None:
            compare_to = turn
            look_for = "turn"

        return next(
            (
                (client, client_idx)
                for client_idx, client in enumerate(Data.paired_clients)
                if client[look_for] == compare_to
            ),
            (None, -1),
        )

    @staticmethod
    def switch_turn():
        Data.turn = "x" if Data.turn != "x" else "o"


class TicTacToe:
    """Game code for TicTacToe"""

    board = [
        [" ", " ", " "],
        [" ", " ", " "],
        [" ", " ", " "],
    ]
    turn = "x"

    @staticmethod
    def reset():
        TicTacToe.board = [
            [" ", " ", " "],
            [" ", " ", " "],
            [" ", " ", " "],
        ]
        TicTacToe.turn = "x"

    @staticmethod
    def check_win() -> str:
        """
        Returns the player who won (X or O)
        If no player one, returns an empty string
        """

        # Check all 8 possible win conditions

        # Horizontal (3/8)
        for row in range(3):
            if (
                (first_condition := TicTacToe.board[row][0])
                == TicTacToe.board[row][1]
                == TicTacToe.board[row][2]
                != " "
            ):
                return first_condition

        # Vertical (3/8)
        for col in range(3):
            if (
                (first_condition := TicTacToe.board[0][col])
                == TicTacToe.board[1][col]
                == TicTacToe.board[2][col]
                != " "
            ):
                return first_condition

        # Diagonal (2/8)
        if (first_condition := TicTacToe.board[0][0]) == TicTacToe.board[1][1] == TicTacToe.board[2][2] != " ":
            return first_condition
        if (first_condition := TicTacToe.board[0][2]) == TicTacToe.board[1][1] == TicTacToe.board[2][0] != " ":
            return first_condition

        return ""

    @staticmethod
    def check_lose() -> bool:
        """Returns if there is a tie / loss"""

        for row in TicTacToe.board:
            for col in row:
                if col == " ":
                    return False

        return True


### Functions ###


def emit_update_information():
    server.send_all_clients("update_board", {"board": TicTacToe.board})


def make_move():
    player = Data.get_client_info(turn=Data.turn)[0]
    print(f"Telling {player} to make a move")
    server.send_client(player["ip"], "make_move", b"")


def start_game():
    Data.turn = "x"
    emit_update_information()  # The board will be blank
    make_move()


def game_over(won: bool, winner_name: str = "", winner_turn: str = ""):
    server.send_all_clients(
        "game_ended",
        {
            "reason": (f"{winner_name} ({winner_turn}) won!" if won else "Tied!"),
            "can_go_again": True,
        },
    )
    TicTacToe.reset()

    # Set all playing to false
    for client in Data.paired_clients:
        client["playing"] = False


### HiSock listeners ###
@server.on("join")
def client_joined(client_info: dict):
    # Game full condition
    if len(Data.paired_clients) > 2:
        server.send_client(
            client_info["ip"],
            "join_result",
            {"worked": False, "message": "This server is full"},
        )

    # Pair client
    player_turn = "x" if len(Data.paired_clients) % 2 == 1 else "o"
    Data.paired_clients.append(
        {
            "name": client_info["name"],
            "ip": client_info["ip"],
            "turn": player_turn,
            "playing": True,
        }
    )

    # Emit join information
    server.send_client(
        client_info["ip"],
        "join_result",
        {
            "worked": True,
            "message": "Joined server",
            "player_info": {"name": client_info["name"]},
            "other_player": Data.paired_clients[0] if len(Data.paired_clients) > 1 else None,
        },
    )
    server.send_all_clients(
        "client_joined",
        {
            "name": client_info["name"],
            "turn": player_turn,
            "ip": client_info["ip"],
            "number_clients": len(Data.paired_clients),
        },
    )

    # Server print
    print(f'"{client_info["name"]}"' f'({hisock.utils.iptup_to_str(client_info["ip"])}) joined the server')

    # Start game if two players are paired
    if len(Data.paired_clients) != 2:
        return

    start_game()


@server.on("leave")
def client_left(client_info: dict):
    # Check if client has already left
    data_client_info = Data.get_client_info(name=client_info["name"])
    if data_client_info[1] == -1:
        return

    # reason: str = reason.decode("utf-8")

    Data.paired_clients.pop(data_client_info[1])

    # Emit leave information
    server.send_all_clients(
        "client_left",
        {
            "name": client_info["name"],
            "ip": client_info["ip"],
            "number_clients": len(Data.paired_clients),
            # "reason": reason,
        },
    )

    # Server print
    print(
        f'"{client_info["name"]}" ({hisock.utils.iptup_to_str(client_info["ip"])}) '
        # f"left the server because {reason}"
    )

    server.disconnect_client(client_info["ip"])

    # Other player left condition
    if len(Data.paired_clients) == 2:
        return

    server.send_all_clients(
        "game_ended",
        {
            "reason": "the other player left",
            "can_go_again": False,
        },
    )
    TicTacToe.reset()


@server.on("made_move")
def client_made_move(client_info: dict, move: dict):
    move: tuple = move["move"]  # Hisock doesn't have built-in tuple support

    # Update game
    turn = Data.get_client_info(client_info["name"])[0]["turn"]
    TicTacToe.board[move[0]][move[1]] = turn
    Data.switch_turn()
    emit_update_information()

    # Win condition
    if TicTacToe.check_win():
        game_over(True, client_info["name"], turn)

    # Lose condition
    elif TicTacToe.check_lose():
        game_over(won=False)

    else:
        make_move()
        return

    print("Game over!")


# TODO: Use `send_raw` and `recv_raw` instead of a whole new event
# The reason I'm not doing that is I can't think of an easy way to deal
# with having to receive a message from two clients (as `recv_raw` is
# blocking)
@server.on("go_again", threaded=True)
def go_again(client_info: dict, response: dict):
    if not response["go_again"] or len(Data.paired_clients) != 2:
        server.disconnect_all_clients()
        client_left(client_info, reason=b"didn't wanna go again")

    print(f"{client_info['name']} wants to play again")

    client_idx = Data.get_client_info(name=client_info["name"])[1]
    Data.paired_clients[client_idx]["playing"] = True

    # Both clients are playing check
    for client in Data.paired_clients:
        if not client["playing"]:
            return

    start_game()


### Run ###
def run():
    try:
        server.start()
    except Exception as e:
        log_error(e)

    try:
        print("\nShutting down gracefully", end="... ")
        server.disconnect_all_clients()
        server.close()
        print("done!")
    except KeyboardInterrupt:
        print("FORCING")
    finally:
        exit(0)


if __name__ == "__main__":
    run()
