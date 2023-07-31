"""HiSock TicTacToe client side (no GUI)"""

### Setup ###
from __future__ import annotations

from os import name as os_name
from os import system

from shared import connect_to_server, log_error

# HiSock setup
print("TicTacToe Client - NO GUI")
client = connect_to_server()

### Classes ###
class TicTacToe:
    board = [
        [" ", " ", " "],
        [" ", " ", " "],
        [" ", " ", " "],
    ]

    @staticmethod
    def display_board():
        system("cls" if os_name == "nt" else "clear")

        row_sep = "---+---+---"
        for row_idx, row in enumerate(TicTacToe.board):
            for col_idx, col in enumerate(row):
                print("{:^3}".format(col), end="")
                if col_idx < 2:
                    print("|", end="")
            print(end="\n")
            if row_idx < 2:
                print(row_sep)


### Functions ###
def ask_go_again() -> bool:
    """Asks the user if they want to play again and returns it"""
    while True:
        answer = input("Do you want to play again? (Y/n): ")

        response = None
        response = True if answer.lower() in ["y", "yes", ""] else response
        response = False if answer.lower() in ["n", "no"] else response
        if response is not None:
            break

        print('Please enter "y" or "n"')

    return response


def get_move() -> tuple:
    """Asks the user for a move and returns it"""

    while True:
        move: str = input("Enter a move (1-9): ")

        if move == "":
            print("The move cannot be blank")
            continue
        if not move.isnumeric():
            print("The move must be a number")
            continue

        move = int(move)
        if move < 1 or move > 9:
            print("The move must be between 1 and 9")
            continue

        # Check if the move is available
        move_indexes = ((move - 1) // 3, (move - 1) % 3)
        if TicTacToe.board[move_indexes[0]][move_indexes[1]] != " ":
            print("The move is already taken")
            continue

        break

    return move_indexes


### HiSock listeners ###

# Joining
@client.on("join_result")
def join_result(game_info: dict):
    if not game_info["worked"]:
        print(f"Couldn't connect to server!\n{game_info['message']}")
        raise StopIteration

    print(game_info["message"])


@client.on("client_joined")
def client_joined(client_info: dict):
    print(f'{client_info["name"]} joined the game!')


# Disconnecting
@client.on("force_disconnect")
def force_disconnect():
    raise SystemExit


@client.on("game_ended")
def game_ended(end_info: dict):
    print(f"Game ended because {end_info['reason']}")

    # Ask to go again
    if not end_info["can_go_again"]:
        raise KeyboardInterrupt  # Can't go again, leave

    if ask_go_again():
        client.send("go_again", {"go_again": True})
        print("Waiting for other player to respond...")
        return

    # Tell the server we're done
    client.send("go_again", {"go_again": False})
    raise StopIteration


@client.on("client_left")
def client_left(client_info: dict):
    print(f'{client_info["name"]} left the game!')
    # If the client is us, then stop
    if client_info["name"] == client.name:
        raise StopIteration


# Actual TicTacToe stuffs
@client.on("update_board")
def update_board(board_information: dict):
    TicTacToe.board = board_information["board"]
    TicTacToe.display_board()


@client.on("make_move")
def make_move(_: bytes):
    move = get_move()
    client.send("made_move", {"move": move})


### Run ###
def run():
    while True:
        try:
            client.update()
        except (SystemExit, BrokenPipeError):
            # This is raised when the server is closed
            print("\nThe server has stopped, exiting!")
            raise
        except KeyboardInterrupt:
            print("\nExiting gracefully", end="... ")
            client.send("leave", b"simply left the game")
            break
        except StopIteration:
            # This is raised when the player already left ("leave" sent)
            break
        except Exception as error:
            log_error(error)
            break

    try:
        # Close the client
        client.close(emit_leave=False)
    except KeyboardInterrupt:
        print("FORCING")
    finally:
        raise SystemExit(0)


if __name__ == "__main__":
    run()
