"""HiSock TicTacToe client side (GUI)"""

### Setup ###
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join("..", "..")))

import hisock
import pygame
import pygame_gui
from shared import connect_to_server, log_error
from typing import Union

# Pygame setup
SCREEN_SIZE = (400, 600)
BOARD_SIZE = (400, 400)
TOP_MARGIN = 200
BACKGROUND_COLOR = (128, 128, 0)
MARGIN = 20
pygame.init()
pygame.display.set_caption("TicTacToe")
screen = pygame.display.set_mode(SCREEN_SIZE)
clock = pygame.time.Clock()

### Classes ###
class DeltaTime:
    """A dataclass for the Pygame deltatime, don't question"""

    current = 0

    @staticmethod
    def update():
        DeltaTime.current = clock.tick(30)


class TicTacToe:
    board = [
        [" ", " ", " "],
        [" ", " ", " "],
        [" ", " ", " "],
    ]

    our_turn = False
    playing = False
    game_over = False
    game_over_message = ""


class Cache:
    text_cache = {}  # key will be a tuple of the position and the text
    buttons = {}  # key will be a tuple of the position


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


def move_made(position: tuple):
    """
    Send a move to the server
    :param position: The position of the button that was pressed
    """

    TicTacToe.our_turn = False

    # Convert button position to board position
    row_idx = (position[1] - TOP_MARGIN) // (BOARD_SIZE[1] // 3)
    col_idx = (position[0] - MARGIN) // (BOARD_SIZE[0] // 3)

    return row_idx, col_idx


### Pygame functions ###
def text_display(message: str, position: tuple, size: int = 48):
    """Display a text on the screen"""

    def get_text_rect_surf() -> tuple[pygame.Rect, pygame.Surface]:
        # Cache
        if (position, message) in Cache.text_cache:
            return Cache.text_cache[(position, message)]

        text_surface = pygame.font.SysFont("Arial", size).render(
            message, False, "black"
        )
        text_rect = text_surface.get_rect(center=position)

        # Add to cache
        Cache.text_cache[(position, message)] = (text_rect, text_surface)

        return text_rect, text_surface

    text_rect, text_surface = get_text_rect_surf()
    screen.blit(text_surface, text_rect)


def get_button_rect(position: tuple, size: tuple) -> pygame.Rect:
    # Cache
    if position in Cache.buttons:
        return Cache.buttons[position]

    button_rect = pygame.Surface(size).get_rect(center=position)

    # Add to cache
    Cache.buttons[position] = button_rect

    return button_rect


def button_display(
    position: tuple, size: tuple, color: Union[tuple, str], border_width: int = 0
):
    """
    Draw a button on the screen
    Returns if the button has been clicked or not
    """

    button_rect = get_button_rect(position, size)
    pygame.draw.rect(screen, color, button_rect, border_width)

    return (
        button_rect.collidepoint(pygame.mouse.get_pos())
        and pygame.mouse.get_pressed()[0]
    )


### Pygame states ###
class BaseState:
    """Base class for all Pygame states"""

    def event_handling(self, event: pygame.event.Event):
        # No event handling specified
        pass

    def draw(self):
        print(f"Warning: draw() not implemented in {self.__class__.__name__}")


class ConnectToServerState(BaseState):
    def __init__(self):
        self.gui_manager = pygame_gui.UIManager((SCREEN_SIZE[0], SCREEN_SIZE[1]))

        # Create username input
        self.username_input_rect = pygame.Rect(0, 0, SCREEN_SIZE[0] * 0.9, 50)
        self.username_input_rect.center = (SCREEN_SIZE[0] // 2, 100)
        self.username_input = pygame_gui.elements.ui_text_entry_line.UITextEntryLine(
            relative_rect=self.username_input_rect, manager=self.gui_manager
        )

        # Create server input
        self.server_input_rect = pygame.Rect(0, 0, SCREEN_SIZE[0] * 0.9, 50)
        self.server_input_rect.center = (SCREEN_SIZE[0] // 2, 200)
        self.server_input = pygame_gui.elements.ui_text_entry_line.UITextEntryLine(
            relative_rect=self.server_input_rect, manager=self.gui_manager
        )

        # Set allowed characters to be alphanum with an underscore
        alpha_num_underscore = [
            char
            for char in str(
                "abcdefghijklmnopqrstuvwxyz"
                + "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                + "0123456789"
                + "_"
            )
        ]
        self.username_input.set_allowed_characters(alpha_num_underscore)
        self.server_input.set_allowed_characters(alpha_num_underscore + [".", ":"])

    def focus_current_textbox(self):
        """A hacky solution to a dumb problem"""

        for text_element in (self.username_input, self.server_input):
            if text_element.relative_rect.collidepoint(pygame.mouse.get_pos()):
                text_element.focus()
                return
            text_element.unfocus()

    def draw(self):
        text_display("Username:", (SCREEN_SIZE[0] // 2, 48))
        text_display("Server IP:", (SCREEN_SIZE[0] // 2, 48 + 100))
        if button_display((SCREEN_SIZE[0] // 2, 48 + 200), (200, 50), "green"):
            # Connect to server
            print("Connecting to server...")
            self.connect_to_server(self.username_input.text, self.server_input.text)
        text_display("Connect", (SCREEN_SIZE[0] // 2, 48 + 200))
        self.gui_manager.update(DeltaTime.current)
        self.gui_manager.draw_ui(screen)

    def event_handling(self, event: pygame.event.Event):
        self.focus_current_textbox()
        self.username_input.process_event(event)
        self.server_input.process_event(event)
        self.username_input.enable()
        self.server_input.enable()

    def connect_to_server(self, username_input: str, server_input: str):
        try:
            # Convert the server input to a tuple
            server_input = server_input.split(":")
            server_input = (server_input[0], int(server_input[1]))
            client = connect_to_server(server_input, username_input, True)
        except Exception as error:
            log_error(error)
            return

        State.current = GameState(client)


class GameState(BaseState):
    def __init__(self, client: hisock.client.ThreadedHiSockClient):
        self.client = client

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
            if not end_info["can_go_again"]:
                raise KeyboardInterrupt  # Can't go again, leave

            TicTacToe.game_over = True
            TicTacToe.game_over_message = end_info["reason"]
            TicTacToe.playing = False

        @client.on("client_left")
        def client_left(client_info: dict):
            print(f'{client_info["name"]} left the game!')
            # If the client is us, then stop
            if client_info["name"] == client.name:
                raise StopIteration

        # Actual TicTacToe stuffs
        @client.on("update_board")
        def update_board(board_information: dict):
            # update_board is also called when the server starts the game
            TicTacToe.playing = True
            TicTacToe.board = board_information["board"]

        @client.on("make_move")
        def make_move(_: bytes):
            TicTacToe.our_turn = True

        # The client will be threaded, no need for `update` every iteration
        client.start()

    def draw_status_text(self):
        text_display(
            f"Your name: {self.client.name}", (SCREEN_SIZE[0] // 2, 24), size=24
        )
        if TicTacToe.our_turn:
            text_display(
                "Your turn, make a move!", (SCREEN_SIZE[0] // 2, 24 + 48), size=24
            )
        else:
            text_display(
                "Waiting for opponent move...", (SCREEN_SIZE[0] // 2, 24 + 48), size=24
            )

    def available_space_button(self, position: tuple):
        button_rect = get_button_rect(
            position, (BOARD_SIZE[0] // 3, BOARD_SIZE[1] // 3)
        )
        # Collision checking
        mouse_pos = pygame.mouse.get_pos()
        if pygame.mouse.get_pressed()[0] and button_rect.collidepoint(mouse_pos):
            row_idx, col_idx = move_made(position)
            self.client.send("made_move", {"move": [row_idx, col_idx]})

    def draw_board(self):
        for row_idx, row in enumerate(TicTacToe.board):
            for col_idx, col in enumerate(row):
                if col_idx < 2:
                    pygame.draw.line(
                        screen,
                        "black",
                        (
                            (BOARD_SIZE[0] // 3) * (col_idx + 1),
                            MARGIN + TOP_MARGIN,
                        ),
                        (
                            (BOARD_SIZE[0] // 3) * (col_idx + 1),
                            BOARD_SIZE[1] - MARGIN + TOP_MARGIN,
                        ),
                        width=10,
                    )

                position_center = (
                    (BOARD_SIZE[0] // 3) * (col_idx + 1) - BOARD_SIZE[0] // 6,
                    (BOARD_SIZE[1] // 3) * (row_idx + 1)
                    - BOARD_SIZE[1] // 6
                    + TOP_MARGIN,
                )

                # Draw an X or O
                if col != " ":
                    text_display(col, position_center, size=72)
                    continue

                # The space is blank, have a button the user can press if it's our turn
                if not TicTacToe.our_turn:
                    continue

                self.available_space_button(position_center)

            if row_idx < 2:
                pygame.draw.line(
                    screen,
                    "black",
                    (
                        MARGIN,
                        (BOARD_SIZE[1] // 3) * (row_idx + 1) + TOP_MARGIN,
                    ),
                    (
                        BOARD_SIZE[0] - MARGIN,
                        (BOARD_SIZE[1] // 3) * (row_idx + 1) + TOP_MARGIN,
                    ),
                    width=10,
                )

    @staticmethod
    def draw_waiting_room():
        text_display("Waiting for opponent...", (SCREEN_SIZE[0] // 2, 24), size=24)

    def draw_game_over(self):
        text_display("Game over!", (SCREEN_SIZE[0] // 2, 24), size=24)
        text_display(
            TicTacToe.game_over_message, (SCREEN_SIZE[0] // 2, 24 * 2), size=24
        )
        text_display("Go again?", (SCREEN_SIZE[0] // 2, 24 * 4), size=24)
        if button_display((SCREEN_SIZE[0] // 2, 24 * 6), size=(200, 50), color="red"):
            self.client.send("go_again", {"go_again": False})
            raise StopIteration
        text_display("No", (SCREEN_SIZE[0] // 2, 24 * 6), size=24)
        if button_display((SCREEN_SIZE[0] // 2, 24 * 8), size=(200, 50), color="green"):
            self.client.send("go_again", {"go_again": True})
            TicTacToe.game_over = False
            TicTacToe.playing = False
        text_display("Yes", (SCREEN_SIZE[0] // 2, 24 * 8), size=24)

    def draw(self):
        # Game over
        if TicTacToe.game_over:
            self.draw_game_over()
            return

        # We're not playing, so draw the waiting room
        if not TicTacToe.playing:
            self.draw_waiting_room()
            return

        self.draw_status_text()
        self.draw_board()


class State:
    """A dataclass for handling the state (no pesky globals)"""

    current = ConnectToServerState()


### Run ###
def run_pygame_loop():
    # Event handling
    for event in pygame.event.get():
        State.current.event_handling(event)
        if event.type == pygame.QUIT:
            raise KeyboardInterrupt

    screen.fill(BACKGROUND_COLOR)
    State.current.draw()
    pygame.display.flip()
    DeltaTime.update()


def run():
    while True:
        try:
            run_pygame_loop()
        except (SystemExit, BrokenPipeError):
            # This is raised when the server is closed
            print("\nThe server has stopped, exiting!")
            raise
        except KeyboardInterrupt:
            print("\nExiting gracefully", end="... ")
            if isinstance(State.current, GameState):
                State.current.client.send("leave", b"simply left the game")
                State.current.client.close()
            break
        except StopIteration:
            # This is raised when the player already left ("leave" sent)
            break
        except Exception as error:
            log_error(error)
            break

    pygame.quit()
    try:
        # Close the client
        # client.stop_client()
        pass
    except KeyboardInterrupt:
        print("FORCING")
    finally:
        raise SystemExit(0)


if __name__ == "__main__":
    run()
