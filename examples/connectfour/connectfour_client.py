import abc
import string

import hisock
import _shared as shared

import pygame
import pygame_gui

pygame.init()

WIDTH, HEIGHT = 800, 600

# addr, name, _ = hisock.input_client_config(group_prompt=None)
running = True

# client = hisock.ThreadedHiSockClient(addr, name)
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()


class FontCache:
    font_cache = {}


class DeltaTime:
    current = 0

    @classmethod
    def update(cls):
        cls.current = clock.tick(60)

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

        self.gui_manager.update(DeltaTime.current)
        self.gui_manager.draw_ui(screen)


class GameState(BaseState):
    def __init__(self):
        super().__init__()

        self.client = Data.client
        self.paired = False
        self.pairing_ticks = pygame.time.get_ticks()
        self.load_circles_loops = 0
        self.load_circles_idx = 0

        @self.client.on("start")
        def on_start(data):
            self.paired = True
            print(data)

        @self.client.on("disconn")
        def on_disconn(reason: str):
            print(reason)

        self.client.start()

    def draw(self):
        if not self.paired:
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

    def handle_event(self, event):
        pass


class Data:
    current_state = ConnectState()
    client = None


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

        DeltaTime.update()

    pygame.quit()

    if Data.client is not None:
        Data.client.close()

if __name__ == "__main__":
    run()