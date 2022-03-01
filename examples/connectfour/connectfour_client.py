import abc
import string
import time

import hisock
import _shared as shared

import pygame
import pygame.gfxdraw
import pygame_gui

pygame.init()

WIDTH, HEIGHT = 800, 600

running = True

screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

pygame.display.set_caption("HiSock Connect Four")


class FontCache:
    font_cache = {}


class Button:
    def __init__(
        self, rect, color, txt, txt_color, font_size,
        hover_color=None, center=False, func_when_clicked=None
    ):
        self.rect = rect
        self.color = color
        self.txt = txt
        self.txt_color = txt_color

        if font_size in FontCache.font_cache:
            self.font = FontCache.font_cache[font_size]
        else:
            self.font = pygame.font.Font("ThaleahFat.ttf", font_size)
            FontCache.font_cache[font_size] = self.font

        self.txt_surf = self.font.render(txt, True, txt_color)
        self.func_when_clicked = func_when_clicked

        if hover_color is None:
            self.hover_color = color
        else:
            self.hover_color = hover_color
        if center:
            self.rect.center = (rect.x, rect.y)

    def draw(self):
        if self.rect.collidepoint(pygame.mouse.get_pos()):
            pygame.draw.rect(screen, self.hover_color, self.rect)
        else:
            pygame.draw.rect(screen, self.color, self.rect)

        screen.blit(
            self.txt_surf, (
                self.rect.centerx - self.txt_surf.get_width() // 2,
                self.rect.centery - self.txt_surf.get_height() // 2
            )
        )

    def handle_event(self, event):
        if (
            event.type == pygame.MOUSEBUTTONDOWN and
            self.rect.collidepoint(event.pos) and
            self.func_when_clicked
        ):
            self.func_when_clicked()


class BaseState(abc.ABC):
    def __init__(self):
        self.fontname = "ThaleahFat.ttf"

    def draw(self):
        pass

    def handle_event(self, event):
        pass

    def blit_text(self, text, pos, size, color, center=False):
        if size not in FontCache.font_cache:
            font = pygame.font.Font(self.fontname, size)
            FontCache.font_cache[size] = font
        else:
            font = FontCache.font_cache[size]

        surf = font.render(
            text, True, color
        )
        if center:
            surf_rect = surf.get_rect(center=pos)
        else:
            surf_rect = surf.get_rect(topleft=pos)

        screen.blit(surf, surf_rect)


class ConnectState(BaseState):
    def __init__(self):
        super().__init__()

        self.gui_manager = pygame_gui.UIManager((WIDTH, HEIGHT))

        self.username_input_rect = pygame.Rect(0, 0, WIDTH * 0.9, 75)
        self.username_input_rect.center = (WIDTH // 2, 100)
        self.username_input = pygame_gui.elements.ui_text_entry_line.UITextEntryLine(
            relative_rect=self.username_input_rect, manager=self.gui_manager
        )

        self.server_input_rect = pygame.Rect(0, 0, WIDTH * 0.9, 75)
        self.server_input_rect.center = (WIDTH // 2, 350)
        self.server_input = pygame_gui.elements.ui_text_entry_line.UITextEntryLine(
            relative_rect=self.server_input_rect, manager=self.gui_manager
        )

        self.conn_button = Button(
            pygame.Rect(WIDTH // 2, 500, 200, 50), (0, 128, 0),
            "Connect", (0, 0, 0), 30, hover_color=(0, 170, 0), center=True,
            func_when_clicked=self.connect_to_server
        )

        self.txt_inputs = (self.username_input, self.server_input)
        allowed_chars = list(string.ascii_letters + string.digits + "_")

        self.username_input.set_allowed_characters(allowed_chars)
        self.username_input.set_text_length_limit(20)
        self.server_input.set_allowed_characters(allowed_chars + [".", ":"])

    def connect_to_server(self):
        ip, port = hisock.utils.ipstr_to_tup(self.server_input.text)
        name = self.username_input.text

        Data.client = hisock.ThreadedHiSockClient((ip, port), name=name)
        Data.current_state = GameState()

    def handle_event(self, event):
        self.username_input.process_event(event)
        self.server_input.process_event(event)

        self.conn_button.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN:
            for i, txt_input in enumerate(self.txt_inputs):
                if txt_input.relative_rect.collidepoint(*event.pos):
                    txt_input.focus()
                    self.txt_inputs[int(not i)].unfocus()
                else:
                    txt_input.unfocus()

    def draw(self):
        self.blit_text("Enter username:", (WIDTH // 2, 40), 48, (255, 255, 255), center=True)
        self.blit_text("Enter server IP:", (WIDTH // 2, 290), 48, (255, 255, 255), center=True)

        self.conn_button.draw()

        self.gui_manager.update(Data.deltatime)
        self.gui_manager.draw_ui(screen)


class GameState(BaseState):
    def __init__(self):
        super().__init__()

        self.client = Data.client
        self.paired = False
        self.pairing_ticks = pygame.time.get_ticks()
        self.load_circles_loops = 0
        self.load_circles_idx = 0

        self.is_turn = False
        self.opponent_name = None
        self.arrow_column = None
        self.piece_type = None
        self.hover_piece_type = None
        self.hover_piece_idx = None
        self.turn_no = 1
        self.start_time = None
        self.game_status = "in_progress"

        self.board = shared.Board()

        self.down_arrow = pygame.image.load("downarrow.png").convert_alpha()

        self.board_rect = pygame.Rect(0, 0, 585, 445)
        self.board_rect.bottomleft = (30, 580)

        @self.client.on("start")
        def on_start(data: dict):
            print(data, type(data))

            self.paired = True
            self.is_turn = True if data["turn"] == "first" else False
            self.piece_type = shared.BoardEnum.RED if self.is_turn else shared.BoardEnum.YELLOW
            self.hover_piece_type = shared.BoardEnum.HOVER_RED if self.is_turn else shared.BoardEnum.HOVER_YELLOW
            self.opponent_name = data["opp_name"]
            self.start_time = time.time()

        @self.client.on("new_move")
        def on_new_move(data: dict):
            x, y = data["opp_move"][0], data["opp_move"][1]

            # self.turn_no = data["turn"]
            self.board.board[y][x] = data["opp_piece"]
            self.is_turn = True

        @self.client.on("new_turn")  # JUST SYNCS THE TURN COUNTER, NOTHING ELSE!!!
        def on_new_turn(turn_no: int):
            self.turn_no = turn_no
        
        @self.client.on("win")
        def on_win():
            self.game_status = "win"
            print("You win!!!!")

        @self.client.on("lose")
        def on_lose():
            self.game_status = "lose"
            print("You lose :(((")

        @self.client.on("disconn")
        def on_disconn(reason: str):
            print(reason)

        self.client.start()

    @staticmethod
    def format_secs(secs):
        return f"{(secs // 60):02d}:{(secs % 60):02d}"

    @staticmethod
    def update_piece(x, y, piece):
        pygame.gfxdraw.aacircle(
            screen, 80 + 80 * x, 180 + 70 * y, 30,
            shared.PIECE_COLORS[piece]
        )
        pygame.gfxdraw.filled_circle(
            screen, 80 + 80 * x, 180 + 70 * y, 30,
            shared.PIECE_COLORS[piece]
        )

    def pos_to_coord(self, mouse_x, mouse_y):
        x = (mouse_x - self.board_rect.x) * 7 // self.board_rect.width
        y = (mouse_y - self.board_rect.y) * 6 // self.board_rect.height

        return x, y

    def draw(self):
        if not self.paired:
            # Waiting
            sec_elapsed = self.load_circles_loops * 3 + self.load_circles_idx

            self.blit_text(
                "Waiting for opponent...",
                (WIDTH // 2, 40), 48, (255, 255, 255), center=True
            )
            self.blit_text(
                f"Time elapsed: {sec_elapsed} seconds",
                (WIDTH // 2, 95), 24, (255, 255, 255), center=True
            )

            if pygame.time.get_ticks() - self.pairing_ticks >= 1000:
                self.load_circles_idx += 1
                quotient, self.load_circles_idx = divmod(self.load_circles_idx, 3)

                if quotient == 1:
                    self.load_circles_loops += 1
                self.pairing_ticks = pygame.time.get_ticks()

            for i in range(3):
                if i != self.load_circles_idx:
                    circ_color = (80, 80, 80)
                else:
                    circ_color = (128, 128, 128)

                pygame.draw.circle(
                    screen, circ_color, (250 + i * 150, 250), 50
                )
        else:
            mouse_pos = pygame.mouse.get_pos()

            # Actual game draw
            self.blit_text(
                f"{self.client.name} (YOU)",
                (WIDTH // 2, 10), 25, (255, 255, 255), center=True
            )
            self.blit_text(
                "VS",
                (WIDTH // 2, 35), 25, (255, 255, 255), center=True
            )
            self.blit_text(
                f"{self.opponent_name} (OPPONENT)",
                (WIDTH // 2, 60), 25, (160, 160, 160), center=True
            )

            self.blit_text(
                f"Turn: {self.turn_no}",
                (650, 130), 25, (255, 255, 255)
            )
            self.blit_text(
                f"Time: {self.format_secs(int(time.time() - self.start_time))}",
                (650, 170), 25, (255, 255, 255)
            )

            if self.is_turn:
                self.blit_text(
                    "YOUR TURN",
                    (650, 500), 30, (255, 255, 255)
                )
            else:
                self.blit_text(
                    "OPP TURN",
                    (650, 500), 30, (160, 160, 160)
                )

            pygame.draw.rect(
                screen, (0, 110, 210), self.board_rect, border_radius=5
            )

            for y, row in enumerate(self.board.board):
                for x, piece in enumerate(row):
                    # IDC about performance
                    self.update_piece(x, y, piece)
                    
            if self.hover_piece_idx is not None:
                self.update_piece(*self.hover_piece_idx, self.hover_piece_type)

            if self.board_rect.collidepoint(mouse_pos):
                self.arrow_column = (mouse_pos[0] - self.board_rect.x) * 7 // self.board_rect.width
                screen.blit(
                    self.down_arrow, (
                        60 + self.arrow_column * (self.board_rect.width - 20) // 7, 80
                    )
                )

    def handle_event(self, event):
        mp = pygame.mouse.get_pos()
        x, _ = self.pos_to_coord(*mp)  # Y is not used cuz it's a loser
        
        if self.board_rect.collidepoint(mp):
            column = [row[x] for row in self.board.board]
            hover_y = column.count(shared.BoardEnum.NO_PIECE) - 1
            self.hover_piece_idx = [x, hover_y]
        else:
            self.hover_piece_idx = None

        if event.type == pygame.MOUSEBUTTONDOWN and self.is_turn:  # Player turn
            hov_x, hov_y = self.hover_piece_idx
            if self.board.board[hov_y][hov_x] == shared.BoardEnum.NO_PIECE:
                self.board.board[hov_y][hov_x] = self.piece_type

                self.client.send("turn_made", {"x": hov_x, "y": hov_y, "piece": self.piece_type})
                self.is_turn = False

            print(hov_x, hov_y)


class Data:
    current_state = ConnectState()
    font_cache = {}
    client = None
    deltatime = 0

    @classmethod
    def update_deltatime(cls):
        cls.deltatime = clock.tick(60)


def run():
    # client.start()
    running = True

    while running:

        for event in pygame.event.get():
            Data.current_state.handle_event(event)

            if event.type == pygame.QUIT:
                running = False

        screen.fill((50, 50, 50))

        Data.current_state.draw()
        pygame.display.update()

        Data.update_deltatime()

    pygame.quit()

    if Data.client is not None:
        Data.client.close()

if __name__ == "__main__":
    run()