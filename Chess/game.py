"""
The main game control.
"""
import glob
import json
import os
import pygame
import sys
from pygame import locals

from board import Board
from common import Colours, Directions
from pieces import AllPieces
from svg_renderer import render_svg
from win_conditions import ChessWinCondition, CheckersWinCondition

try:
    # Python 2
    xrange
except NameError:
    # Python 3, xrange is now named range
    xrange = range

_WIN_CONDITIONS = {
    'chess': ChessWinCondition,
    'checkers': CheckersWinCondition,
}

_LAYOUTS_DIR = os.path.join(os.path.dirname(__file__), 'defs', 'layouts')


def _load_layouts():
    """Return list of layout dicts found in defs/layouts/, sorted by name."""
    layouts = []
    for path in sorted(glob.glob(os.path.join(_LAYOUTS_DIR, '*.json'))):
        try:
            with open(path) as f:
                layouts.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            pass
    return layouts


class Game:

    def __init__(self, layout=None):
        """
        The main game control.
        layout: a layout dict (from defs/layouts/*.json). If None, uses standard chess.
        """
        self.graphics = Graphics()
        self.board = Board()

        self.turn = Colours.WHITE
        self.selected_piece = None  # a board location.
        self.selected_legal_moves = []
        self.click = False
        self.pixel_mouse_pos = (0, 0)

        if layout is not None:
            self.board.load_layout(layout)
            wc_cls = _WIN_CONDITIONS.get(layout.get('win_condition', 'chess'), ChessWinCondition)
            self.win_condition = wc_cls()
        else:
            self.win_condition = ChessWinCondition()

    def setup(self):
        """Draws the window and board at the beginning of the game"""
        self.graphics.setup_window()
        self.graphics.load_piece_icons(self.board.pieces_defs)

    def event_loop(self):
        """
        The event loop. This is where events are triggered
        (like a mouse click) and then effect the game state.
        """
        self.pixel_mouse_pos = pygame.mouse.get_pos()
        self.mouse_pos = self.graphics.board_coords(self.pixel_mouse_pos)
        if self.selected_piece != None:
            self.selected_legal_moves = self.win_condition.safe_moves(self.board, self.selected_piece)

        for event in pygame.event.get():

            if event.type == locals.QUIT:
                self.terminate_game()

            if event.type == locals.KEYDOWN:
                if event.key == locals.K_s:
                    self.save()
                elif event.key == locals.K_l:
                    self.load()

            self.click = event.type == locals.MOUSEBUTTONDOWN

            if self.click:
                px, py = self.pixel_mouse_pos

                # Button bar clicks (below the board)
                if py >= self.graphics.window_size:
                    if self.graphics.save_btn_rect.collidepoint(px, py):
                        self.save()
                    elif self.graphics.load_btn_rect.collidepoint(px, py):
                        self.load()
                    continue

                # Promotion picker takes priority over all other board input
                if self.board.promotion_pending:
                    choice = self.graphics.promotion_pick(self.mouse_pos)
                    if choice:
                        ppx, ppy = self.board.promotion_pending
                        self.board.matrix[ppx][ppy].occupant.piece_type = choice
                        self.board.promotion_pending = None
                        self.end_turn()

                elif self.board.location(self.mouse_pos).occupant != None and self.board.location(
                        self.mouse_pos).occupant.color == self.turn:
                    self.selected_piece = self.mouse_pos

                elif self.selected_piece != None and self.mouse_pos in self.win_condition.safe_moves(self.board, self.selected_piece):
                    self.board.move_piece(self.selected_piece, self.mouse_pos)
                    # If the move triggered promotion, wait for picker before ending turn
                    if not self.board.promotion_pending:
                        self.end_turn()

    def update(self):
        """Calls on the graphics class to update the game display."""
        save_exists = os.path.exists(self._DEFAULT_SAVE_PATH)
        self.graphics.update_display(self.board,
                                     self.selected_legal_moves,
                                     self.selected_piece,
                                     self.mouse_pos,
                                     self.click,
                                     mouse_px=self.pixel_mouse_pos,
                                     save_exists=save_exists)
        if self.board.promotion_pending:
            px, py = self.board.promotion_pending
            pawn = self.board.matrix[px][py].occupant
            color_key = 'white' if pawn and pawn.color == Colours.WHITE else 'black'
            self.graphics.draw_promotion_picker(color_key)
        pygame.display.update()

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    _WIN_CONDITION_KEY = {
        'chess': ChessWinCondition,
        'checkers': CheckersWinCondition,
    }
    _DEFAULT_SAVE_PATH = os.path.join(os.path.dirname(__file__), 'saves', 'autosave.json')

    def _win_condition_name(self):
        for name, cls in self._WIN_CONDITION_KEY.items():
            if isinstance(self.win_condition, cls):
                return name
        return 'chess'

    def save(self, path=None):
        """Save the current game state to a JSON file."""
        path = path or self._DEFAULT_SAVE_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            'board': self.board.to_dict(),
            'turn': 'white' if self.turn == Colours.WHITE else 'black',
            'win_condition': self._win_condition_name(),
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        self.graphics.draw_timed_message('GAME SAVED', duration_ms=2000)

    def load(self, path=None):
        """Load a previously saved game state from a JSON file."""
        path = path or self._DEFAULT_SAVE_PATH
        if not os.path.exists(path):
            return
        with open(path) as f:
            data = json.load(f)
        self.board.from_dict(data['board'])
        self.turn = Colours.WHITE if data.get('turn') == 'white' else Colours.PIECE_BLACK
        wc_cls = self._WIN_CONDITION_KEY.get(data.get('win_condition', 'chess'), ChessWinCondition)
        self.win_condition = wc_cls()
        self.selected_piece = None
        self.selected_legal_moves = []
        self.graphics.message = False
        self.graphics.load_piece_icons(self.board.pieces_defs)
        self.graphics.draw_timed_message('GAME LOADED', duration_ms=2000)

    def terminate_game(self):
        """Quits the program and ends the game."""
        pygame.quit()
        sys.exit()

    def main(self):
        """"This executes the game and controls its flow."""
        self.setup()

        while True:  # main game loop
            self.event_loop()
            self.update()

    def end_turn(self):
        """
        End the turn. Switches the current player, then asks the active
        win condition whether the game is over.
        """
        if self.turn == Colours.WHITE:
            self.turn = Colours.PIECE_BLACK
        else:
            self.turn = Colours.WHITE

        self.selected_piece = None
        self.selected_legal_moves = []

        result = self.win_condition.check(self)
        if result:
            if result.permanent:
                self.graphics.draw_message(result.message)
            else:
                self.graphics.draw_timed_message(result.message)


class Graphics:
    def __init__(self):
        self.caption = "megaChess"

        self.fps = 60
        self.clock = pygame.time.Clock()

        pygame.init()
        info = pygame.display.Info()
        self.window_size = min(info.current_w, info.current_h)
        self.button_bar_height = 48
        self.screen = pygame.display.set_mode(
            (self.window_size, self.window_size + self.button_bar_height)
        )

        self.square_size = self.window_size // 8
        self.piece_size = self.square_size // 2
        self.piece_font = pygame.font.SysFont(None, self.piece_size)

        self.message = False

        self.timed_message_surface = None
        self.timed_message_rect = None
        self.timed_message_until = 0  # pygame.time.get_ticks() expiry

        self.piece_icons = {}  # (piece_type, 'white'|'black') -> scaled Surface

        self.highlights = False

    # Hex colours used to colorize SVG templates for each side
    ICON_COLOURS = {
        'white': {'fill': '#F0F0E6', 'stroke': '#3C3C3C'},
        'black': {'fill': '#281E1E', 'stroke': '#C8C8C8'},
    }

    def load_piece_icons(self, pieces_defs):
        """
        For each piece definition that has an "icon" SVG path, render a
        colourised copy for white and black by substituting {fill}/{stroke}
        template variables, converting via cairosvg, and loading the result
        into a pygame Surface.  Missing files are silently skipped; the
        circle+letter fallback in draw_board_pieces handles those pieces.
        """
        self.piece_icons = {}
        px = self.square_size - 8
        for piece_type, defn in pieces_defs.items():
            path = defn.get('icon')
            if not path:
                continue
            try:
                template = open(path).read()
            except (FileNotFoundError, OSError):
                continue
            for color_name, colours in self.ICON_COLOURS.items():
                try:
                    svg = template.replace('{fill}',   colours['fill']) \
                                  .replace('{stroke}', colours['stroke'])
                    self.piece_icons[(piece_type, color_name)] = render_svg(svg, (px, px))
                except Exception:
                    pass

    def setup_window(self):
        """
        This initializes the window and sets the caption at the top.
        """
        pygame.init()
        pygame.display.set_caption(self.caption)

    @property
    def save_btn_rect(self):
        pad = 8
        bw = self.window_size // 2 - pad * 2
        bh = self.button_bar_height - pad * 2
        return pygame.Rect(pad, self.window_size + pad, bw, bh)

    @property
    def load_btn_rect(self):
        pad = 8
        bw = self.window_size // 2 - pad * 2
        bh = self.button_bar_height - pad * 2
        return pygame.Rect(self.window_size // 2 + pad, self.window_size + pad, bw, bh)

    def draw_button_bar(self, mouse_px, save_exists):
        """Draw the Save / Load button strip below the board."""
        bar_rect = pygame.Rect(0, self.window_size, self.window_size, self.button_bar_height)
        pygame.draw.rect(self.screen, (30, 32, 42), bar_rect)

        font = pygame.font.Font('freesansbold.ttf', 18)

        for label, rect, enabled in [
            ('Save  [S]', self.save_btn_rect, True),
            ('Load  [L]', self.load_btn_rect, save_exists),
        ]:
            hovered = rect.collidepoint(*mouse_px) and enabled
            if not enabled:
                bg = (45, 48, 58)
                tc = (80, 85, 95)
            elif hovered:
                bg = (90, 120, 170)
                tc = (240, 245, 255)
            else:
                bg = (55, 70, 100)
                tc = (190, 205, 230)
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            txt = font.render(label, True, tc)
            self.screen.blit(txt, txt.get_rect(center=rect.center))

    def update_display(self, board, legal_moves, selected_piece, mouse_pos, click,
                       mouse_px=(0, 0), save_exists=False):
        """
        This updates the current display.
        mouse_px: raw pixel mouse position (for button bar hover).
        save_exists: whether an autosave file is present (enables Load button).
        """
        self.draw_board_squares(board)
        if click:
            self.highlight_squares(legal_moves, self.pixel_coords(mouse_pos))
        elif not click and self.highlights:
            self.highlights = False

        self.draw_board_pieces(board)

        if self.message:
            self.screen.blit(self.text_surface_obj, self.text_rect_obj)

        if self.timed_message_surface and pygame.time.get_ticks() < self.timed_message_until:
            self.screen.blit(self.timed_message_surface, self.timed_message_rect)

        self.draw_button_bar(mouse_px, save_exists)

        # pygame.display.update() is called by Game.update() after any overlays are drawn
        self.clock.tick(self.fps)

    def draw_board_squares(self, board):
        """
        Takes a board object and draws all of its squares to the display
        """
        for x in xrange(8):
            for y in xrange(8):
                pygame.draw.rect(self.screen, board.matrix[int(x)][int(y)].color,
                                 (x * self.square_size, y * self.square_size, self.square_size, self.square_size), )

    def draw_board_pieces(self, board):
        """
        Takes a board object and draws all of its pieces to the display.
        Uses icon images when available, falls back to circle+letter otherwise.
        """
        piece_labels = {'pawn': 'P', 'rook': 'R', 'knight': 'N', 'bishop': 'B', 'queen': 'Q', 'king': 'K'}
        for x in xrange(8):
            for y in xrange(8):
                piece = board.matrix[int(x)][int(y)].occupant
                if piece is not None:
                    center = self.pixel_coords((x, y))
                    color_key = 'white' if piece.color == Colours.WHITE else 'black'
                    icon = self.piece_icons.get((piece.piece_type, color_key))
                    if icon:
                        self.screen.blit(icon, icon.get_rect(center=center))
                    else:
                        pygame.draw.circle(self.screen, piece.color, center, self.piece_size)
                        outline = Colours.BLACK if piece.color == Colours.WHITE else Colours.WHITE
                        pygame.draw.circle(self.screen, outline, center, self.piece_size, 2)
                        label = piece_labels.get(piece.piece_type, '?')
                        text_color = Colours.BLACK if piece.color == Colours.WHITE else Colours.WHITE
                        text_surf = self.piece_font.render(label, True, text_color)
                        self.screen.blit(text_surf, text_surf.get_rect(center=center))

    def pixel_coords(self, board_coords):
        """
        Takes in a tuple of board coordinates (x,y)
        and returns the pixel coordinates of the center of the square at that location.
        """
        return ((board_coords[0] * self.square_size) + self.piece_size, (board_coords[1] * self.square_size) + self.piece_size)

    def board_coords(self, pixel_coords_tuple):
        """
        Does the reverse of pixel_coords(). Takes in a tuple of of pixel coordinates and returns what square they are in.
        """
        pixel_x, pixel_y = pixel_coords_tuple
        x = min(max(pixel_x // self.square_size, 0), 7)
        y = min(max(pixel_y // self.square_size, 0), 7)
        return (x, y)

    def highlight_squares(self, squares, origin):
        """
        Squares is a list of board coordinates.
        highlight_squares highlights them.
        """
        self.highlighted_squares = squares
        for square in squares:
            pygame.draw.rect(self.screen, Colours.HIGH, (
                square[0] * self.square_size, square[1] * self.square_size, 
                self.square_size, self.square_size))

        if origin != None:
            pygame.draw.rect(self.screen, Colours.HIGH, (
                origin[0] * self.square_size, origin[1] * self.square_size, 
                self.square_size, self.square_size))
        
        self.highlights = True

    def del_highlight_squares(self, board):
        self.draw_board_squares(board)
        self.highlights = False

    def draw_message(self, message):
        """Draws a permanent centred message (win / stalemate)."""
        self.message = True
        self.font_obj = pygame.font.Font('freesansbold.ttf', 44)
        self.text_surface_obj = self.font_obj.render(message, True, Colours.HIGH, Colours.BLACK)
        self.text_rect_obj = self.text_surface_obj.get_rect()
        self.text_rect_obj.center = (self.window_size / 2, self.window_size / 2)

    def draw_timed_message(self, message, duration_ms=3000):
        """Draws a temporary message near the top of the board that expires after duration_ms."""
        font = pygame.font.Font('freesansbold.ttf', 36)
        self.timed_message_surface = font.render(message, True, Colours.BLACK, Colours.HIGH)
        self.timed_message_rect = self.timed_message_surface.get_rect()
        self.timed_message_rect.center = (self.window_size // 2, self.square_size // 2)
        self.timed_message_until = pygame.time.get_ticks() + duration_ms

    # Board columns used for the promotion picker (centred on the board)
    PROMOTION_PIECES = ['queen', 'rook', 'bishop', 'knight']
    PROMOTION_COLS   = [2, 3, 4, 5]   # x indices; row is always 3 (middle)
    PROMOTION_ROW    = 3

    def draw_promotion_picker(self, color_key):
        """
        Draws a centred 4-square overlay letting the player pick a promotion piece.
        The four choices are queen / rook / bishop / knight.
        """
        row = self.PROMOTION_ROW
        # Dark border behind the four squares
        border_x = self.PROMOTION_COLS[0] * self.square_size - 4
        border_y = row * self.square_size - 4
        border_w = len(self.PROMOTION_COLS) * self.square_size + 8
        border_h = self.square_size + 8
        pygame.draw.rect(self.screen, Colours.BLACK,
                         (border_x, border_y, border_w, border_h), border_radius=6)

        for piece_type, col in zip(self.PROMOTION_PIECES, self.PROMOTION_COLS):
            sx = col * self.square_size
            sy = row * self.square_size
            pygame.draw.rect(self.screen, Colours.HIGH,
                             (sx, sy, self.square_size, self.square_size))
            icon = self.piece_icons.get((piece_type, color_key))
            center = self.pixel_coords((col, row))
            if icon:
                self.screen.blit(icon, icon.get_rect(center=center))
            else:
                label = piece_type[0].upper()
                text_surf = self.piece_font.render(label, True, Colours.BLACK)
                self.screen.blit(text_surf, text_surf.get_rect(center=center))

    def promotion_pick(self, mouse_pos):
        """
        Returns the piece type the player clicked in the promotion picker, or None.
        mouse_pos is in board coordinates (col, row).
        """
        mx, my = mouse_pos
        if my != self.PROMOTION_ROW:
            return None
        for piece_type, col in zip(self.PROMOTION_PIECES, self.PROMOTION_COLS):
            if mx == col:
                return piece_type
        return None


class LayoutMenu:
    """Pre-game layout picker. Shows available layouts and returns the chosen one."""

    BG_COLOR       = (30, 30, 40)
    TEXT_COLOR     = (220, 220, 220)
    HIGHLIGHT_BG   = Colours.HIGH
    HIGHLIGHT_TEXT = (20, 20, 20)
    TITLE_COLOR    = (255, 215, 0)
    PADDING        = 20
    ROW_HEIGHT     = 60

    def __init__(self):
        pygame.init()
        info = pygame.display.Info()
        self.window_size = min(info.current_w, info.current_h)
        self.screen = pygame.display.set_mode((self.window_size, self.window_size))
        pygame.display.set_caption('megaChess — choose a layout')
        self.title_font = pygame.font.Font('freesansbold.ttf', 40)
        self.item_font  = pygame.font.Font('freesansbold.ttf', 28)
        self.sub_font   = pygame.font.Font('freesansbold.ttf', 18)

    @property
    def _play_btn_rect(self):
        bw, bh = 200, 46
        return pygame.Rect(
            (self.window_size - bw) // 2,
            self.window_size - self.PADDING * 3 - bh,
            bw, bh,
        )

    def run(self, layouts):
        """
        Block until the player picks a layout. Returns the chosen layout dict.
        Falls back to the first layout if only one exists.
        """
        if not layouts:
            return None
        if len(layouts) == 1:
            return layouts[0]

        clock = pygame.time.Clock()
        hovered = 0

        while True:
            mouse_x, mouse_y = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == locals.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == locals.KEYDOWN:
                    if event.key == locals.K_UP:
                        hovered = (hovered - 1) % len(layouts)
                    elif event.key == locals.K_DOWN:
                        hovered = (hovered + 1) % len(layouts)
                    elif event.key in (locals.K_RETURN, locals.K_SPACE):
                        return layouts[hovered]
                if event.type == locals.MOUSEBUTTONDOWN:
                    if self._play_btn_rect.collidepoint(mouse_x, mouse_y):
                        return layouts[hovered]
                    for i, rect in enumerate(self._item_rects(len(layouts))):
                        if rect.collidepoint(mouse_x, mouse_y):
                            return layouts[i]

            # Update hover from mouse
            for i, rect in enumerate(self._item_rects(len(layouts))):
                if rect.collidepoint(mouse_x, mouse_y):
                    hovered = i

            self._draw(layouts, hovered, (mouse_x, mouse_y))
            pygame.display.update()
            clock.tick(60)

    def _item_rects(self, n):
        top = self.window_size // 4
        rects = []
        for i in range(n):
            rect = pygame.Rect(
                self.PADDING,
                top + i * (self.ROW_HEIGHT + 10),
                self.window_size - self.PADDING * 2,
                self.ROW_HEIGHT,
            )
            rects.append(rect)
        return rects

    def _draw(self, layouts, hovered, mouse_pos=(0, 0)):
        self.screen.fill(self.BG_COLOR)

        title = self.title_font.render('megaChess', True, self.TITLE_COLOR)
        subtitle = self.sub_font.render('Select a layout to start playing', True, self.TEXT_COLOR)
        self.screen.blit(title,    title.get_rect(centerx=self.window_size // 2, y=self.PADDING))
        self.screen.blit(subtitle, subtitle.get_rect(centerx=self.window_size // 2, y=self.PADDING + 55))

        for i, (layout, rect) in enumerate(zip(layouts, self._item_rects(len(layouts)))):
            is_hovered = (i == hovered)
            bg = self.HIGHLIGHT_BG if is_hovered else (50, 55, 70)
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            tc = self.HIGHLIGHT_TEXT if is_hovered else self.TEXT_COLOR
            text = self.item_font.render(layout.get('name', '?'), True, tc)
            wc = layout.get('win_condition', 'chess')
            sub  = self.sub_font.render(f'win condition: {wc}', True, tc)
            self.screen.blit(text, text.get_rect(left=rect.left + 16, centery=rect.centery - 10))
            self.screen.blit(sub,  sub.get_rect(left=rect.left + 16,  centery=rect.centery + 16))

        # Play button
        btn = self._play_btn_rect
        btn_hovered = btn.collidepoint(*mouse_pos)
        btn_bg = (90, 140, 90) if btn_hovered else (60, 110, 60)
        pygame.draw.rect(self.screen, btn_bg, btn, border_radius=8)
        btn_txt = self.item_font.render('▶  Play', True, (220, 240, 220))
        self.screen.blit(btn_txt, btn_txt.get_rect(center=btn.center))

        hint = self.sub_font.render('↑↓ navigate   Enter / Space / click row or Play button', True, (120, 120, 140))
        self.screen.blit(hint, hint.get_rect(centerx=self.window_size // 2,
                                              y=self.window_size - self.PADDING - 20))


def main():
    layouts = _load_layouts()
    layout = LayoutMenu().run(layouts) if layouts else None
    game = Game(layout=layout)
    game.main()

if __name__ == "__main__":
    main()
