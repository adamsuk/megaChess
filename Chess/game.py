"""
The main game control.
"""
import copy
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


def _pixel_text(text, size, color, bold=False):
    """Return a pygame Surface with genuine pixel-art text.
    Renders at half size with no antialiasing, then scales up 2x with
    pygame.transform.scale (nearest-neighbour) for a chunky retro look."""
    font = pygame.font.Font('freesansbold.ttf' if bold else None, max(size // 2, 6))
    surf = font.render(text, False, color)
    w, h = surf.get_size()
    return pygame.transform.scale(surf, (w * 2, h * 2))


class Game:

    def __init__(self):
        """
        The main game control.
        """
        self.graphics = Graphics()
        self.board = Board()

        self.turn = Colours.WHITE
        self.selected_piece = None  # a board location.
        self.selected_legal_moves = []
        self.click = False
        self.pixel_mouse_pos = (0, 0)

        # Swap this to change how the game is won (e.g. CheckersWinCondition()).
        self.win_condition = ChessWinCondition()

    def setup(self):
        """Draws the window and board at the beginning of the game"""
        self.graphics.setup_window()
        self.graphics.set_board_size(self.board.board_size)
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
                elif event.key == locals.K_h:
                    self._toggle_hints()

            self.click = event.type == locals.MOUSEBUTTONDOWN

            if self.click:
                px, py = self.pixel_mouse_pos

                # Button bar clicks (below the board)
                if py >= self.graphics.window_size:
                    if self.graphics.save_btn_rect.collidepoint(px, py):
                        self.save()
                    elif self.graphics.load_btn_rect.collidepoint(px, py):
                        self.load()
                    elif self.graphics.hints_btn_rect.collidepoint(px, py):
                        self._toggle_hints()
                    self.click = False  # consumed; don't treat as a board click
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

    def _toggle_hints(self):
        """Toggle piece selection and legal-move highlighting on/off."""
        self.graphics.show_hints = not self.graphics.show_hints
        if not self.graphics.show_hints:
            self.graphics.highlights = False

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

        self.board_size = 8
        self.square_size = self.window_size // self.board_size
        self.piece_size = self.square_size // 2
        self.piece_font = pygame.font.SysFont(None, self.piece_size)

        self.message = False

        self.timed_message_surface = None
        self.timed_message_rect = None
        self.timed_message_until = 0  # pygame.time.get_ticks() expiry

        self.piece_icons = {}  # (piece_type, 'white'|'black') -> scaled Surface

        self.highlights = False
        self.show_hints = True   # toggle: show piece selection + legal-move highlighting

        self.frame_size = 28     # pixel border around board for coordinate labels
        self.board_theme = 'Classic'
        self.piece_theme = 'Classic'

    # Hex colours used to colorize SVG templates for each side (pixel art tonal palette)
    ICON_COLOURS = {
        'white': {
            'fill':    '#EAD9B0',  # warm ivory base
            'fill_hi': '#F8EFD0',  # bright cream highlight
            'fill_lo': '#B89660',  # tan shadow
            'stroke':  '#2A1808',  # dark brown outline
            'accent':  '#D4A020',  # gold accent / gems
        },
        'black': {
            'fill':    '#1C1630',  # deep indigo base
            'fill_hi': '#342C50',  # purple highlight
            'fill_lo': '#0C0818',  # near-black shadow
            'stroke':  '#4A3870',  # dark purple outline
            'accent':  '#6040A8',  # purple gem accent
        },
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
            for color_name, colours in PIECE_THEMES[self.piece_theme].items():
                try:
                    svg = (template
                           .replace('{fill}',    colours['fill'])
                           .replace('{fill_hi}', colours['fill_hi'])
                           .replace('{fill_lo}', colours['fill_lo'])
                           .replace('{stroke}',  colours['stroke'])
                           .replace('{accent}',  colours['accent']))
                    self.piece_icons[(piece_type, color_name)] = render_svg(svg, (px, px))
                except Exception:
                    pass

    def set_board_size(self, n):
        """Update rendering parameters when the board changes size."""
        self.board_size = n
        board_px = self.window_size - self.frame_size * 2
        self.square_size = board_px // n
        self.piece_size = self.square_size // 2
        self.piece_font = pygame.font.SysFont(None, self.piece_size)

    def setup_window(self):
        """
        This initializes the window and sets the caption at the top.
        """
        pygame.init()
        pygame.display.set_caption(self.caption)

    def _btn_layout(self):
        """Returns (button_width, button_height, padding) for the 3-button bar."""
        pad = 8
        bw = (self.window_size - pad * 4) // 3
        bh = self.button_bar_height - pad * 2
        return bw, bh, pad

    @property
    def save_btn_rect(self):
        bw, bh, pad = self._btn_layout()
        return pygame.Rect(pad, self.window_size + pad, bw, bh)

    @property
    def load_btn_rect(self):
        bw, bh, pad = self._btn_layout()
        return pygame.Rect(pad * 2 + bw, self.window_size + pad, bw, bh)

    @property
    def hints_btn_rect(self):
        bw, bh, pad = self._btn_layout()
        return pygame.Rect(pad * 3 + bw * 2, self.window_size + pad, bw, bh)

    def draw_button_bar(self, mouse_px, save_exists, show_hints=True):
        """Draw the Save / Load / Hints button strip below the board — pixel art style."""
        bar_rect = pygame.Rect(0, self.window_size, self.window_size, self.button_bar_height)
        pygame.draw.rect(self.screen, (8, 8, 18), bar_rect)
        # Pixel art divider: bright top line + dark second line
        pygame.draw.line(self.screen, (60, 50, 100),
                         (0, self.window_size), (self.window_size, self.window_size), 2)
        pygame.draw.line(self.screen, (20, 15, 40),
                         (0, self.window_size + 2), (self.window_size, self.window_size + 2), 1)

        BEVEL = 2

        for label, rect, enabled, toggled in [
            ('Save  [S]',  self.save_btn_rect,  True,        True),
            ('Load  [L]',  self.load_btn_rect,  save_exists, True),
            ('Hints  [H]', self.hints_btn_rect, True,        show_hints),
        ]:
            hovered = rect.collidepoint(*mouse_px) and enabled
            if not enabled:
                bg, tc  = (30, 25, 55), (70, 60, 90)
                bhi, blo = (45, 38, 75), (12, 8, 25)
            elif not toggled:
                # Hints-off: red-tinted
                bg  = (90, 35, 35) if hovered else (65, 22, 22)
                tc  = (220, 160, 160)
                bhi = (130, 55, 55)
                blo = (30, 8, 8)
            elif hovered:
                bg, tc  = (50, 80, 160), (240, 240, 255)
                bhi, blo = (80, 120, 200), (20, 40, 90)
            else:
                bg, tc  = (30, 45, 110), (180, 195, 240)
                bhi, blo = (50, 70, 150), (12, 20, 60)

            # Button body (square corners = pixel art)
            pygame.draw.rect(self.screen, bg, rect, border_radius=0)
            # Pixel art bevel: top/left lighter, bottom/right darker
            pygame.draw.line(self.screen, bhi, rect.topleft,    rect.topright,    BEVEL)
            pygame.draw.line(self.screen, bhi, rect.topleft,    rect.bottomleft,  BEVEL)
            pygame.draw.line(self.screen, blo, rect.bottomleft, rect.bottomright, BEVEL)
            pygame.draw.line(self.screen, blo, rect.topright,   rect.bottomright, BEVEL)
            # Text with drop shadow — pixel art (blocky, no antialiasing)
            shadow_s = _pixel_text(label, 18, (0, 0, 0), bold=True)
            text_s   = _pixel_text(label, 18, tc,        bold=True)
            self.screen.blit(shadow_s, shadow_s.get_rect(center=(rect.centerx + 1, rect.centery + 1)))
            self.screen.blit(text_s,   text_s.get_rect(center=rect.center))

    def draw_board_frame(self):
        """Draw dark surround + pixel-art teal border + coordinate labels (a-h / 1-n).
        Labels use freesansbold with drop shadow for a retro pixel art look."""
        f  = self.frame_size
        sq = self.square_size
        n  = self.board_size
        board_px = sq * n
        # Dark background behind the frame area
        pygame.draw.rect(self.screen, (8, 8, 18), (0, 0, self.window_size, self.window_size))

        # Pixel art double-border: bright teal outer (3px) + dark inner (2px)
        pygame.draw.rect(self.screen, Colours.HIGH, (f - 5, f - 5, board_px + 10, board_px + 10), 3)
        pygame.draw.rect(self.screen, (30, 25, 55), (f - 2, f - 2, board_px +  4, board_px +  4), 2)

        # Corner pixel accent squares in each corner of the frame
        for cx_off, cy_off in [(0, 0), (board_px + 4, 0),
                                (0, board_px + 4), (board_px + 4, board_px + 4)]:
            pygame.draw.rect(self.screen, Colours.HIGH,
                             (f - 5 + cx_off, f - 5 + cy_off, 6, 6))

        # Coordinate labels — pixel art style (blocky, no antialiasing)
        fsize = max(f - 10, 9)
        files = 'abcdefghijklmnopqrstuvwxyz'[:n]
        for i, ch in enumerate(files):
            cx = f + i * sq + sq // 2
            shadow = _pixel_text(ch, fsize, (0, 0, 0), bold=True)
            lbl    = _pixel_text(ch, fsize, Colours.GOLD, bold=True)
            for centery in (f // 2, f + board_px + f // 2):
                r = lbl.get_rect(centerx=cx, centery=centery)
                self.screen.blit(shadow, r.move(1, 1))
                self.screen.blit(lbl, r)
        for i in range(n):
            cy = f + i * sq + sq // 2
            ch = str(n - i)
            shadow = _pixel_text(ch, fsize, (0, 0, 0), bold=True)
            lbl    = _pixel_text(ch, fsize, Colours.GOLD, bold=True)
            for centerx in (f // 2, f + board_px + f // 2):
                r = lbl.get_rect(centerx=centerx, centery=cy)
                self.screen.blit(shadow, r.move(1, 1))
                self.screen.blit(lbl, r)

    def update_display(self, board, legal_moves, selected_piece, mouse_pos, click,
                       mouse_px=(0, 0), save_exists=False):
        """
        This updates the current display.
        mouse_px: raw pixel mouse position (for button bar hover).
        save_exists: whether an autosave file is present (enables Load button).
        """
        self.draw_board_frame()
        self.draw_board_squares(board)
        # Highlight the selected piece and its legal moves whenever a piece is
        # selected and hints are enabled.  Basing this on `selected_piece`
        # (not `click`) avoids two bugs:
        #   1. `click` is overwritten by any subsequent event (e.g. MOUSEMOTION)
        #      in the same frame, so highlights would vanish almost immediately.
        #   2. pixel_coords(mouse_pos) returned pixel-space coords which
        #      highlight_squares would then multiply by square_size again,
        #      placing the origin square far off-screen.
        if selected_piece is not None and self.show_hints:
            self.highlight_squares(legal_moves, selected_piece)
        else:
            self.highlights = False

        self.draw_board_pieces(board)

        if self.message:
            self.screen.blit(self.text_surface_obj, self.text_rect_obj)

        if self.timed_message_surface and pygame.time.get_ticks() < self.timed_message_until:
            self.screen.blit(self.timed_message_surface, self.timed_message_rect)

        self.draw_button_bar(mouse_px, save_exists, self.show_hints)

        # pygame.display.update() is called by Game.update() after any overlays are drawn
        self.clock.tick(self.fps)

    def draw_board_squares(self, board):
        """
        Takes a board object and draws all of its squares to the display.
        Each square gets a pixel art bevel: bright highlight on top/left edges,
        dark shadow on bottom/right edges, giving a raised-tile 3D effect.
        Hole squares are drawn sunken (inverted bevel).
        Board theme colours are read from BOARD_THEMES[self.board_theme].
        """
        sq = self.square_size
        bevel = max(2, sq // 16)
        t = BOARD_THEMES[self.board_theme]

        for x in xrange(self.board_size):
            for y in xrange(self.board_size):
                sq_obj = board.matrix[int(x)][int(y)]
                rx, ry = x * sq + self.frame_size, y * sq + self.frame_size
                if sq_obj.is_hole:
                    pygame.draw.rect(self.screen, t['hole'],    (rx, ry, sq, sq))
                    # Sunken bevel: dark top/left, bright bottom/right
                    pygame.draw.rect(self.screen, t['hole_lo'], (rx, ry, sq, bevel))
                    pygame.draw.rect(self.screen, t['hole_lo'], (rx, ry, bevel, sq))
                    pygame.draw.rect(self.screen, t['hole_hi'], (rx, ry + sq - bevel, sq, bevel))
                    pygame.draw.rect(self.screen, t['hole_hi'], (rx + sq - bevel, ry, bevel, sq))
                    continue
                is_light = sq_obj.color == Colours.CREAM
                base_col = t['light'] if is_light else t['dark']
                hi       = t['light_hi'] if is_light else t['dark_hi']
                lo       = t['light_lo'] if is_light else t['dark_lo']
                pygame.draw.rect(self.screen, base_col, (rx, ry, sq, sq))
                # Raised bevel: bright top/left, dark bottom/right
                pygame.draw.rect(self.screen, hi, (rx, ry, sq, bevel))
                pygame.draw.rect(self.screen, hi, (rx, ry, bevel, sq))
                pygame.draw.rect(self.screen, lo, (rx, ry + sq - bevel, sq, bevel))
                pygame.draw.rect(self.screen, lo, (rx + sq - bevel, ry, bevel, sq))

        # Pixel art grid lines — thin 1-px dark separators between tiles
        grid_col = (0, 0, 0, 80)  # semi-transparent; draw as opaque approximation
        sep = (8, 8, 18)
        f = self.frame_size
        board_px = sq * self.board_size
        for i in range(1, self.board_size):
            pygame.draw.line(self.screen, sep,
                             (f + i * sq, f), (f + i * sq, f + board_px))
            pygame.draw.line(self.screen, sep,
                             (f, f + i * sq), (f + board_px, f + i * sq))

    def draw_board_pieces(self, board):
        """
        Takes a board object and draws all of its pieces to the display.
        Uses icon images when available, falls back to circle+letter otherwise.
        """
        piece_labels = {'pawn': 'P', 'rook': 'R', 'knight': 'N', 'bishop': 'B', 'queen': 'Q', 'king': 'K'}
        for x in xrange(self.board_size):
            for y in xrange(self.board_size):
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
        return (
            board_coords[0] * self.square_size + self.frame_size + self.piece_size,
            board_coords[1] * self.square_size + self.frame_size + self.piece_size,
        )

    def board_coords(self, pixel_coords_tuple):
        """
        Does the reverse of pixel_coords(). Takes in a tuple of of pixel coordinates and returns what square they are in.
        """
        pixel_x, pixel_y = pixel_coords_tuple
        N = self.board_size - 1
        x = min(max((pixel_x - self.frame_size) // self.square_size, 0), N)
        y = min(max((pixel_y - self.frame_size) // self.square_size, 0), N)
        return (x, y)

    def highlight_squares(self, squares, origin):
        """
        Pixel art move indicators: teal dot for legal move squares,
        teal border outline for the selected piece square.
        """
        self.highlighted_squares = squares
        dot_r  = max(6, self.square_size // 7)
        border = max(3, self.square_size // 12)
        DOT_RING = (40, 180, 180)

        for square in squares:
            cx = square[0] * self.square_size + self.frame_size + self.square_size // 2
            cy = square[1] * self.square_size + self.frame_size + self.square_size // 2
            pygame.draw.circle(self.screen, Colours.HIGH, (cx, cy), dot_r)
            pygame.draw.circle(self.screen, DOT_RING,     (cx, cy), dot_r, 2)

        if origin is not None:
            ox, oy = origin
            pygame.draw.rect(self.screen, Colours.HIGH,
                             (ox * self.square_size + self.frame_size,
                              oy * self.square_size + self.frame_size,
                              self.square_size, self.square_size), border)

        self.highlights = True

    def del_highlight_squares(self, board):
        self.draw_board_squares(board)
        self.highlights = False

    def draw_message(self, message):
        """Draws a permanent centred message (win / stalemate) with pixel art border box."""
        self.message = True
        text = _pixel_text(message, 44, Colours.HIGH, bold=True)
        pad = 16
        tw = text.get_width() + pad * 2
        th = text.get_height() + pad
        # Teal outer border + dark inner background
        bg = pygame.Surface((tw + 8, th + 8))
        bg.fill(Colours.HIGH)
        pygame.draw.rect(bg, (8, 8, 18), pygame.Rect(4, 4, tw, th))
        bg.blit(text, (pad, pad // 2))
        self.text_surface_obj = bg
        self.text_rect_obj = bg.get_rect(center=(self.window_size // 2, self.window_size // 2))

    def draw_timed_message(self, message, duration_ms=3000):
        """Draws a temporary message near the top of the board — pixel art teal banner."""
        text = _pixel_text(message, 36, (8, 8, 18), bold=True)
        tw = text.get_width() + 24
        th = text.get_height() + 12
        bg = pygame.Surface((tw + 6, th + 6))
        bg.fill(Colours.HIGH)
        pygame.draw.rect(bg, (30, 220, 220), pygame.Rect(3, 3, tw, th))
        bg.blit(text, (12, 6))
        self.timed_message_surface = bg
        self.timed_message_rect = bg.get_rect(center=(self.window_size // 2, self.square_size // 2))
        self.timed_message_until = pygame.time.get_ticks() + duration_ms

    # Board columns used for the promotion picker (centred on the board)
    PROMOTION_PIECES = ['queen', 'rook', 'bishop', 'knight']

    def _promotion_cols_row(self):
        """Return (cols_list, row) centred on the current board."""
        start = (self.board_size - 4) // 2
        cols = [start + i for i in range(4)]
        row = self.board_size // 2 - 1
        return cols, row

    def draw_promotion_picker(self, color_key):
        """
        Draws a centred 4-square overlay letting the player pick a promotion piece.
        The four choices are queen / rook / bishop / knight.
        """
        cols, row = self._promotion_cols_row()
        # Pixel art bordered box behind the four squares
        border_x = cols[0] * self.square_size - 4
        border_y = row * self.square_size - 4
        border_w = len(cols) * self.square_size + 8
        border_h = self.square_size + 8
        pygame.draw.rect(self.screen, (8, 8, 18),
                         (border_x, border_y, border_w, border_h), border_radius=0)
        pygame.draw.rect(self.screen, Colours.HIGH,
                         (border_x, border_y, border_w, border_h), 3, border_radius=0)

        for piece_type, col in zip(self.PROMOTION_PIECES, cols):
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
        cols, promo_row = self._promotion_cols_row()
        mx, my = mouse_pos
        if my != promo_row:
            return None
        for piece_type, col in zip(self.PROMOTION_PIECES, cols):
            if mx == col:
                return piece_type
        return None


_CUSTOM_PIECES_PATH = os.path.join(os.path.dirname(__file__), 'defs', 'custom_pieces.json')
_DEFAULT_PIECES_PATH = os.path.join(os.path.dirname(__file__), 'defs', 'pieces_defs.json')
_CUSTOM_LAYOUT_PATH = os.path.join(os.path.dirname(__file__), 'defs', 'custom_layout.json')
_CUSTOM_THEME_PATH  = os.path.join(os.path.dirname(__file__), 'defs', 'custom_theme.json')

# ── Board and piece colour theme presets ─────────────────────────────────────
BOARD_THEMES = {
    'Classic':  {'light': (210, 175, 110), 'dark':  ( 95,  55,  25),
                 'light_hi': (240, 210, 150), 'light_lo': (168, 132,  72),
                 'dark_hi':  (128,  78,  42), 'dark_lo':  ( 52,  22,   4),
                 'hole': (35, 35, 55), 'hole_hi': (55, 55, 80), 'hole_lo': (20, 20, 35)},
    'Arctic':   {'light': (200, 220, 240), 'dark':  ( 60,  90, 140),
                 'light_hi': (230, 245, 255), 'light_lo': (150, 180, 210),
                 'dark_hi':  ( 90, 130, 180), 'dark_lo':  ( 30,  55, 100),
                 'hole': (20, 30, 55), 'hole_hi': (40, 55, 80), 'hole_lo': (10, 15, 35)},
    'Forest':   {'light': (170, 200, 140), 'dark':  ( 50, 100,  50),
                 'light_hi': (210, 235, 175), 'light_lo': (120, 160, 100),
                 'dark_hi':  ( 80, 140,  80), 'dark_lo':  ( 25,  65,  25),
                 'hole': (20, 35, 20), 'hole_hi': (40, 60, 40), 'hole_lo': (10, 18, 10)},
    'Obsidian': {'light': (150, 140, 130), 'dark':  ( 40,  35,  30),
                 'light_hi': (200, 190, 180), 'light_lo': (100,  95,  85),
                 'dark_hi':  ( 70,  60,  55), 'dark_lo':  ( 20,  15,  10),
                 'hole': (25, 22, 20), 'hole_hi': (45, 40, 35), 'hole_lo': (12, 10,  8)},
    'Candy':    {'light': (255, 200, 215), 'dark':  (160,  50, 100),
                 'light_hi': (255, 230, 240), 'light_lo': (220, 155, 175),
                 'dark_hi':  (210,  90, 140), 'dark_lo':  (100,  25,  65),
                 'hole': (55, 20, 40), 'hole_hi': (80, 40, 65), 'hole_lo': (25,  8, 20)},
}

PIECE_THEMES = {
    'Classic':  {
        'white': {'fill': '#EAD9B0', 'fill_hi': '#F8EFD0', 'fill_lo': '#B89660',
                  'stroke': '#2A1808', 'accent': '#D4A020'},
        'black': {'fill': '#1C1630', 'fill_hi': '#342C50', 'fill_lo': '#0C0818',
                  'stroke': '#2C2244', 'accent': '#6040A8'},
    },
    'Arctic':   {
        'white': {'fill': '#D8EEF8', 'fill_hi': '#F0F8FF', 'fill_lo': '#90BCD8',
                  'stroke': '#102840', 'accent': '#40C0E0'},
        'black': {'fill': '#102848', 'fill_hi': '#203860', 'fill_lo': '#081428',
                  'stroke': '#1E3A62', 'accent': '#2070C0'},
    },
    'Forest':   {
        'white': {'fill': '#C8D8A0', 'fill_hi': '#E0ECC0', 'fill_lo': '#88A860',
                  'stroke': '#182808', 'accent': '#80C040'},
        'black': {'fill': '#183018', 'fill_hi': '#284828', 'fill_lo': '#0C1808',
                  'stroke': '#223C1C', 'accent': '#406020'},
    },
    'Obsidian': {
        'white': {'fill': '#D0C8C0', 'fill_hi': '#F0E8E0', 'fill_lo': '#908880',
                  'stroke': '#181410', 'accent': '#C8A020'},
        'black': {'fill': '#201C18', 'fill_hi': '#382F28', 'fill_lo': '#100C08',
                  'stroke': '#2E2620', 'accent': '#806030'},
    },
    'Candy':    {
        'white': {'fill': '#FFD0E0', 'fill_hi': '#FFF0F5', 'fill_lo': '#E090B0',
                  'stroke': '#481028', 'accent': '#FF40A0'},
        'black': {'fill': '#480820', 'fill_hi': '#781038', 'fill_lo': '#280410',
                  'stroke': '#641228', 'accent': '#C02060'},
    },
}

# Boolean flags that can be toggled per move_rule
_RULE_FLAGS = ['sliding', 'directional', 'move_only', 'capture_only', 'jump_capture']

# Maps keyword strings used in pieces_defs.json to explicit [dx, dy] lists
_KEYWORD_DELTAS = {
    'diagonal': [[1, 1], [1, -1], [-1, 1], [-1, -1]],
    'straight': [[1, 0], [-1, 0], [0, 1], [0, -1]],
}


def _expand_keywords(defs):
    """
    Replace keyword strings ('diagonal', 'straight') in every rule's deltas
    with their explicit [dx, dy] lists.  Called when defs are loaded into
    the editor so all editing works on uniform lists.
    """
    for piece_def in defs.values():
        for rule in piece_def.get('move_rules', []):
            expanded = []
            for d in rule.get('deltas', []):
                if isinstance(d, str):
                    expanded.extend(_KEYWORD_DELTAS.get(d, []))
                else:
                    expanded.append(d)
            rule['deltas'] = expanded
    return defs


class PieceEditor:
    """
    In-game piece rules editor.
    Left panel: list of piece types.
    Right panel: move_rules for the selected piece with toggleable flags.
    Bottom buttons: ← Back / Clone / Reset / Save / Play.
    """

    BG          = ( 10,   8,  20)
    PANEL_BG    = ( 22,  18,  42)
    SEL_BG      = ( 80, 215, 215)   # teal (matches Colours.HIGH)
    SEL_TEXT    = (  5,   5,  15)
    TEXT        = (200, 192, 230)
    DIM_TEXT    = (100,  90, 130)
    BTN_BG      = ( 30,  25,  58)
    BTN_HOV     = ( 50,  42,  90)
    BTN_SAVE    = ( 30, 110,  55)
    BTN_PLAY    = ( 30,  75, 150)
    BTN_RESET   = (120,  40,  40)
    TITLE_COLOR = (220, 170,  40)   # gold
    ON_COLOR    = ( 60, 200,  90)
    OFF_COLOR   = ( 50,  45,  70)
    PADDING     = 16

    # One-line explanations shown as a tooltip when hovering a flag toggle
    FLAG_DESCRIPTIONS = {
        'sliding':      'Sliding — keeps moving in this direction until blocked (rook / bishop style)',
        'directional':  'Directional — delta is NOT mirrored for the other colour (e.g. pawn moves forward only)',
        'move_only':    'Move only — this pattern lets the piece MOVE but cannot capture on that square',
        'capture_only': 'Capture only — this pattern is used ONLY to capture, not to move (e.g. pawn diagonal)',
        'jump_capture': 'Jump capture — jumps over an enemy to land beyond it, capturing it (checkers style)',
    }

    # How tall each flag toggle button is drawn / hit-tested (px)
    TOGGLE_H = 26

    # Delta grid geometry
    CELL       = 16    # grid cell size (px)
    CELL_GAP   = 2     # gap between cells (px)
    GRID_RANGE = 2     # grid spans ±GRID_RANGE → 5×5
    GRID_CELLS = 5     # 2 * GRID_RANGE + 1
    GRID_SIZE  = 90    # GRID_CELLS * (CELL + CELL_GAP)

    # Y-offset within a rule block at which the flag row starts
    # (rule label height + grid height + gap)
    FLAG_Y_OFF = 120   # 24 + GRID_SIZE + 6

    # Total vertical space allocated per rule in the right panel
    RULE_H = 200

    def __init__(self):
        pygame.init()
        info = pygame.display.Info()
        self.w = min(info.current_w, info.current_h)
        self.h = self.w
        self.screen = pygame.display.set_mode((self.w, self.h))
        pygame.display.set_caption('megaChess — piece editor')
        self.title_font = pygame.font.Font('freesansbold.ttf', 32)
        self.label_font = pygame.font.Font('freesansbold.ttf', 22)
        self.small_font = pygame.font.Font('freesansbold.ttf', 16)
        self.tiny_font  = pygame.font.Font('freesansbold.ttf', 13)

    def run(self):
        """
        Show the editor. Returns (pieces_defs, saved_path | None).
        pieces_defs is the final state; saved_path is set if the user hit Save.
        """
        all_pieces = AllPieces()
        defs = _expand_keywords(copy.deepcopy(all_pieces.pieces_defs))
        # Load any previously saved custom defs
        if os.path.exists(_CUSTOM_PIECES_PATH):
            try:
                with open(_CUSTOM_PIECES_PATH) as f:
                    defs = _expand_keywords(json.load(f))
            except (OSError, json.JSONDecodeError):
                pass

        selected = list(defs.keys())[0]
        saved_path = None
        clock = pygame.time.Clock()
        scroll_y = 0        # scroll offset for right panel
        status_msg = ''
        status_until = 0

        while True:
            mouse = pygame.mouse.get_pos()
            piece_names = list(defs.keys())

            # Layout geometry
            left_w  = self.w // 3
            right_x = left_w + self.PADDING
            right_w = self.w - right_x - self.PADDING
            btn_h   = 42
            btn_y   = self.h - btn_h - self.PADDING

            for event in pygame.event.get():
                if event.type == locals.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == locals.KEYDOWN and event.key == locals.K_ESCAPE:
                    return defs, saved_path

                if event.type == locals.MOUSEBUTTONDOWN:
                    mx, my = event.pos

                    # Left panel — select piece
                    if mx < left_w:
                        item_rects = self._piece_rects(piece_names, left_w)
                        for name, rect in zip(piece_names, item_rects):
                            if rect.collidepoint(mx, my):
                                selected = name
                                scroll_y = 0

                    # Right panel — delta grid, rule add/remove, flag toggles
                    elif mx >= right_x and my < btn_y:
                        if selected in defs:
                            piece_def = defs[selected]
                            rules = piece_def['move_rules']

                            delta_hit = self._find_delta_click(
                                piece_def, mx, my, right_x, scroll_y)
                            if delta_hit is not None:
                                rule_idx, dx, dy = delta_hit
                                deltas = rules[rule_idx]['deltas']
                                d = [dx, dy]
                                if d in deltas:
                                    deltas.remove(d)
                                else:
                                    deltas.append(d)
                            else:
                                remove_hit = self._find_remove_rule(
                                    piece_def, mx, my, right_x, right_w, scroll_y)
                                if remove_hit is not None and len(rules) > 1:
                                    rules.pop(remove_hit)
                                elif self._add_rule_rect(
                                        piece_def, right_x, scroll_y).collidepoint(mx, my):
                                    rules.append({'deltas': []})
                                else:
                                    toggle = self._find_toggle(
                                        piece_def, mx, my, right_x, right_w, scroll_y)
                                    if toggle is not None:
                                        rule_idx, flag = toggle
                                        rules[rule_idx][flag] = not rules[rule_idx].get(flag, False)

                    # Bottom buttons
                    for label, rect in self._button_rects(btn_y, btn_h).items():
                        if rect.collidepoint(mx, my):
                            if label == '← Back':
                                return defs, saved_path
                            elif label == 'Clone' and selected:
                                new_name = selected + '_custom'
                                if new_name not in defs:
                                    defs[new_name] = copy.deepcopy(defs[selected])
                                selected = new_name
                                status_msg = f'Cloned → {new_name}'
                                status_until = pygame.time.get_ticks() + 2500
                            elif label == 'Reset':
                                defs = _expand_keywords(copy.deepcopy(AllPieces().pieces_defs))
                                selected = list(defs.keys())[0]
                                saved_path = None
                                status_msg = 'Reset to defaults'
                                status_until = pygame.time.get_ticks() + 2500
                            elif label == 'Save':
                                ap = AllPieces()
                                ap.pieces_defs = defs
                                ap.save(_CUSTOM_PIECES_PATH)
                                saved_path = _CUSTOM_PIECES_PATH
                                status_msg = 'Saved to defs/custom_pieces.json'
                                status_until = pygame.time.get_ticks() + 2500
                            elif label == 'Play':
                                return defs, saved_path

                if event.type == locals.MOUSEWHEEL:
                    if selected in defs:
                        n_rules = len(defs[selected].get('move_rules', []))
                        content_h = 32 + n_rules * self.RULE_H + 40
                        visible_h = btn_y - 55
                        max_scroll = max(0, content_h - visible_h)
                    else:
                        max_scroll = 0
                    scroll_y = max(0, min(scroll_y - event.y * 20, max_scroll))

            self._draw(defs, selected, piece_names, left_w, right_x, right_w,
                       btn_y, btn_h, mouse, scroll_y,
                       status_msg if pygame.time.get_ticks() < status_until else '')
            pygame.display.update()
            clock.tick(60)

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _piece_rects(self, names, left_w):
        top = 60
        rects = []
        for i in range(len(names)):
            rects.append(pygame.Rect(self.PADDING, top + i * 44, left_w - self.PADDING * 2, 38))
        return rects

    def _button_rects(self, btn_y, btn_h):
        labels = ['← Back', 'Clone', 'Reset', 'Save', 'Play']
        total_btn_w = self.w - self.PADDING * 2
        bw = (total_btn_w - self.PADDING * (len(labels) - 1)) // len(labels)
        rects = {}
        for i, label in enumerate(labels):
            x = self.PADDING + i * (bw + self.PADDING)
            rects[label] = pygame.Rect(x, btn_y, bw, btn_h)
        return rects

    def _rule_toggle_rects(self, rule, rule_y, right_x, right_w):
        """Returns {flag: pygame.Rect} for toggleable boolean flags of a rule."""
        rects = {}
        x = right_x
        tw = 116
        # Flags live below the delta grid — use FLAG_Y_OFF instead of 24
        base_y = rule_y + self.FLAG_Y_OFF
        for flag in _RULE_FLAGS:
            rect = pygame.Rect(x, base_y, tw - 4, self.TOGGLE_H)
            rects[flag] = rect
            x += tw
            if x + tw > right_x + right_w:
                x = right_x
                base_y += self.TOGGLE_H + 6
        return rects

    def _delta_grid_rects(self, rule_y, right_x):
        """
        Returns {(dx, dy): pygame.Rect} for the 5×5 delta-choice grid.
        (0, 0) — the piece's own square — is excluded.
        """
        rects = {}
        step = self.CELL + self.CELL_GAP
        grid_top  = rule_y + 24
        grid_left = right_x
        for col in range(self.GRID_CELLS):
            dx = col - self.GRID_RANGE
            for row in range(self.GRID_CELLS):
                dy = row - self.GRID_RANGE
                if dx == 0 and dy == 0:
                    continue
                rects[(dx, dy)] = pygame.Rect(
                    grid_left + col * step,
                    grid_top  + row * step,
                    self.CELL,
                    self.CELL,
                )
        return rects

    def _remove_rule_rect(self, rule_y, right_x, right_w):
        """Small '×' button at the top-right of a rule block."""
        return pygame.Rect(right_x + right_w - 24, rule_y + 2, 22, 18)

    def _add_rule_rect(self, piece_def, right_x, scroll_y):
        """'+ Add Rule' button positioned below the last rule."""
        n = len(piece_def.get('move_rules', []))
        y = 92 - scroll_y + n * self.RULE_H
        return pygame.Rect(right_x, y, 110, 24)

    def _find_toggle(self, piece_def, mx, my, right_x, right_w, scroll_y):
        """Return (rule_idx, flag) if the click / hover lands on a toggle, else None."""
        # y must match _draw: header starts at 60-scroll_y, then += 32 before first rule
        y = 92 - scroll_y
        for i, rule in enumerate(piece_def.get('move_rules', [])):
            toggle_rects = self._rule_toggle_rects(rule, y, right_x, right_w)
            for flag, rect in toggle_rects.items():
                if rect.collidepoint(mx, my):
                    return (i, flag)
            y += self.RULE_H
        return None

    def _find_delta_click(self, piece_def, mx, my, right_x, scroll_y):
        """Return (rule_idx, dx, dy) if the click lands on a delta grid cell, else None."""
        y = 92 - scroll_y
        for i, rule in enumerate(piece_def.get('move_rules', [])):
            for (dx, dy), rect in self._delta_grid_rects(y, right_x).items():
                if rect.collidepoint(mx, my):
                    return (i, dx, dy)
            y += self.RULE_H
        return None

    def _find_remove_rule(self, piece_def, mx, my, right_x, right_w, scroll_y):
        """Return rule index if the click lands on a remove-rule button, else None."""
        y = 92 - scroll_y
        for i in range(len(piece_def.get('move_rules', []))):
            if self._remove_rule_rect(y, right_x, right_w).collidepoint(mx, my):
                return i
            y += self.RULE_H
        return None

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_pixel_btn(self, surf, rect, base_color, hovered, text, font, text_color,
                        bevel=2):
        """Draw a pixel-art bevelled button (square corners)."""
        bg = tuple(min(c + 30, 255) for c in base_color) if hovered else base_color
        hi = tuple(min(c + 55, 255) for c in base_color)
        lo = tuple(max(c - 25,   0) for c in base_color)
        pygame.draw.rect(surf, bg, rect, border_radius=0)
        pygame.draw.line(surf, hi, rect.topleft,    rect.topright,    bevel)
        pygame.draw.line(surf, hi, rect.topleft,    rect.bottomleft,  bevel)
        pygame.draw.line(surf, lo, rect.bottomleft, rect.bottomright, bevel)
        pygame.draw.line(surf, lo, rect.topright,   rect.bottomright, bevel)
        if text:
            shd = font.render(text, True, (0, 0, 0))
            lbl = font.render(text, True, text_color)
            surf.blit(shd, shd.get_rect(center=(rect.centerx + 1, rect.centery + 1)))
            surf.blit(lbl, lbl.get_rect(center=rect.center))

    def _draw(self, defs, selected, piece_names, left_w, right_x, right_w,
              btn_y, btn_h, mouse, scroll_y, status_msg):
        self.screen.fill(self.BG)

        # Title with drop-shadow
        shd = self.title_font.render('Piece Editor', True, (0, 0, 0))
        title = self.title_font.render('Piece Editor', True, self.TITLE_COLOR)
        self.screen.blit(shd,   (self.PADDING + 2, self.PADDING - 2))
        self.screen.blit(title, (self.PADDING,      self.PADDING - 4))

        hint = self.tiny_font.render('Esc or ← Back = return to main menu', True, self.DIM_TEXT)
        self.screen.blit(hint, (self.w - hint.get_width() - self.PADDING, self.PADDING))

        # Left panel — pixel art frame (square corners, teal outer + dark inner)
        left_panel = pygame.Rect(0, 50, left_w, btn_y - 50)
        pygame.draw.rect(self.screen, self.PANEL_BG, left_panel, border_radius=0)
        pygame.draw.rect(self.screen, Colours.HIGH,  left_panel, 2)
        pygame.draw.rect(self.screen, (30, 25, 55),  left_panel.inflate(-4, -4), 1)

        for name, rect in zip(piece_names, self._piece_rects(piece_names, left_w)):
            is_sel = (name == selected)
            hov    = rect.collidepoint(*mouse)
            base   = self.SEL_BG if is_sel else (self.BTN_HOV if hov else self.BTN_BG)
            tc     = self.SEL_TEXT if is_sel else self.TEXT
            self._draw_pixel_btn(self.screen, rect, base, False, name, self.label_font, tc)
            if is_sel:
                pygame.draw.rect(self.screen, Colours.HIGH, rect, 2)

        # Right panel — pixel art frame
        right_panel = pygame.Rect(right_x - self.PADDING, 50,
                                  right_w + self.PADDING, btn_y - 50)
        pygame.draw.rect(self.screen, self.PANEL_BG, right_panel, border_radius=0)
        pygame.draw.rect(self.screen, Colours.HIGH,  right_panel, 2)
        pygame.draw.rect(self.screen, (30, 25, 55),  right_panel.inflate(-4, -4), 1)

        clip = pygame.Rect(right_x - self.PADDING, 55, right_w + self.PADDING, btn_y - 60)
        self.screen.set_clip(clip)

        hovered_flag  = None
        hovered_delta = None
        step = self.CELL + self.CELL_GAP

        if selected and selected in defs:
            piece_def = defs[selected]
            y = 60 - scroll_y
            hdr = self.label_font.render(f'{selected}  —  move rules', True, self.TEXT)
            self.screen.blit(hdr, (right_x, y))
            y += 32

            for i, rule in enumerate(piece_def.get('move_rules', [])):
                # ── Rule label + remove button ────────────────────────────
                lbl_txt = self.small_font.render(f'Rule {i + 1}', True, self.DIM_TEXT)
                self.screen.blit(lbl_txt, (right_x, y + 4))

                rm_rect = self._remove_rule_rect(y, right_x, right_w)
                rm_hov  = rm_rect.collidepoint(*mouse)
                self._draw_pixel_btn(self.screen, rm_rect, (110, 45, 45), rm_hov,
                                     '×', self.tiny_font, (240, 200, 200))

                # ── Delta grid ────────────────────────────────────────────
                active_deltas = {tuple(d) for d in rule.get('deltas', [])
                                 if isinstance(d, (list, tuple))}
                # Centre cell (0,0): the piece's own square — always disabled
                cx = right_x + self.GRID_RANGE * step
                cy = y + 24 + self.GRID_RANGE * step
                pygame.draw.rect(self.screen, (50, 53, 68),
                                 pygame.Rect(cx, cy, self.CELL, self.CELL))

                for (dx, dy), rect in self._delta_grid_rects(y, right_x).items():
                    is_active = (dx, dy) in active_deltas
                    is_hov    = rect.collidepoint(*mouse)
                    if is_hov:
                        hovered_delta = (dx, dy)
                    base_c = self.ON_COLOR if is_active else self.OFF_COLOR
                    # Pixel art bevel on each grid cell (square)
                    bg  = tuple(min(c + 40, 255) for c in base_c) if is_hov else base_c
                    hi  = tuple(min(c + 55, 255) for c in base_c)
                    lo  = tuple(max(c - 25,   0) for c in base_c)
                    pygame.draw.rect(self.screen, bg, rect, border_radius=0)
                    pygame.draw.line(self.screen, hi, rect.topleft,    rect.topright,    1)
                    pygame.draw.line(self.screen, hi, rect.topleft,    rect.bottomleft,  1)
                    pygame.draw.line(self.screen, lo, rect.bottomleft, rect.bottomright, 1)
                    pygame.draw.line(self.screen, lo, rect.topright,   rect.bottomright, 1)
                    if is_hov:
                        pygame.draw.rect(self.screen, (220, 225, 235), rect, width=1)

                # ── Flag toggles (below the grid) ────────────────────────
                toggle_rects = self._rule_toggle_rects(rule, y, right_x, right_w)
                for flag, rect in toggle_rects.items():
                    val    = rule.get(flag, False)
                    is_hov = rect.collidepoint(*mouse)
                    if is_hov:
                        hovered_flag = flag
                    base_c = self.ON_COLOR if val else self.OFF_COLOR
                    tc_flag = (10, 10, 10) if val else (160, 165, 175)
                    self._draw_pixel_btn(self.screen, rect, base_c, is_hov,
                                        flag, self.tiny_font, tc_flag)

                y += self.RULE_H

            # ── Add Rule button ───────────────────────────────────────────
            add_rect = self._add_rule_rect(piece_def, right_x, scroll_y)
            add_hov  = add_rect.collidepoint(*mouse)
            self._draw_pixel_btn(self.screen, add_rect, (45, 78, 105), add_hov,
                                 '+ Add Rule', self.small_font, self.TEXT)

        self.screen.set_clip(None)

        # ── Tooltip ───────────────────────────────────────────────────────
        tooltip = None
        if hovered_flag and hovered_flag in self.FLAG_DESCRIPTIONS:
            tooltip = self.FLAG_DESCRIPTIONS[hovered_flag]
        elif hovered_delta:
            dx, dy = hovered_delta
            tooltip = f'delta ({dx:+d}, {dy:+d})  — click to toggle this move direction'
        if tooltip:
            tip_surf = self.tiny_font.render(tooltip, True, (220, 225, 235))
            tip_bg = pygame.Rect(0, 0, tip_surf.get_width() + 12, tip_surf.get_height() + 8)
            tx = max(right_x, min(mouse[0], self.w - tip_bg.width - 4))
            ty = min(mouse[1] + 18, btn_y - tip_bg.height - 4)
            tip_bg.topleft = (tx, ty)
            pygame.draw.rect(self.screen, (40, 45, 62), tip_bg, border_radius=0)
            pygame.draw.rect(self.screen, Colours.HIGH, tip_bg, width=1)
            self.screen.blit(tip_surf, (tx + 6, ty + 4))

        # Buttons — pixel art bevel
        btn_colors = {
            '← Back': (70, 55, 70),
            'Clone':  self.BTN_BG,
            'Reset':  self.BTN_RESET,
            'Save':   self.BTN_SAVE,
            'Play':   self.BTN_PLAY,
        }
        for label, rect in self._button_rects(btn_y, btn_h).items():
            hov = rect.collidepoint(*mouse)
            self._draw_pixel_btn(self.screen, rect, btn_colors[label], hov,
                                 label, self.label_font, self.TEXT)

        # Status message
        if status_msg:
            sm = self.small_font.render(status_msg, True, Colours.GOLD)
            self.screen.blit(sm, (self.PADDING, btn_y - 28))


class BoardLayoutEditor:
    """
    Interactive board layout editor.

    Left side: 8×8 chess board showing the current starting layout.
    Right panel: piece palette — click a colour+type to select, then click
                 a board square to place it.  Click an occupied square with
                 the same piece selected to remove it.  Right-click any
                 square to clear it.

    Bottom buttons: ← Back / Reset / Save / Play.
    Saved layout is written to defs/custom_layout.json and loaded by
    Board.new_board() whenever that file exists.
    """

    BG          = ( 10,   8,  20)
    PANEL_BG    = ( 22,  18,  42)
    TEXT        = (200, 192, 230)
    DIM_TEXT    = (100,  90, 130)
    BTN_BG      = ( 30,  25,  58)
    BTN_HOV     = ( 50,  42,  90)
    BTN_SAVE    = ( 30, 110,  55)
    BTN_PLAY    = ( 30,  75, 150)
    BTN_RST     = (120,  40,  40)
    TITLE_COLOR = (220, 170,  40)   # gold
    CREAM       = Colours.CREAM
    BROWN       = Colours.BROWN
    HIGH        = Colours.HIGH
    PADDING     = 14

    # Piece types in palette order
    PALETTE_PIECES = ['king', 'queen', 'rook', 'bishop', 'knight', 'pawn']

    # Shade control rows: (label, 'board'/'piece', sub-key or None, [color-keys])
    _SHADE_CONTROLS = [
        ('Light Squares', 'board', None,    ['light', 'light_hi', 'light_lo']),
        ('Dark Squares',  'board', None,    ['dark',  'dark_hi',  'dark_lo']),
        ('Holes',         'board', None,    ['hole',  'hole_hi',  'hole_lo']),
        ('White Pieces',  'piece', 'white', ['fill', 'fill_hi', 'fill_lo', 'stroke', 'accent']),
        ('Black Pieces',  'piece', 'black', ['fill', 'fill_hi', 'fill_lo', 'stroke', 'accent']),
    ]
    SHADE_STEP = 12

    def __init__(self, board_theme='Classic', piece_theme='Classic',
                 custom_board=None, custom_piece=None):
        pygame.init()
        info = pygame.display.Info()
        self.w = min(info.current_w, info.current_h)
        self.h = self.w
        self.screen = pygame.display.set_mode((self.w, self.h))
        pygame.display.set_caption('megaChess — board layout editor')
        self.title_font = pygame.font.Font('freesansbold.ttf', 28)
        self.label_font = pygame.font.Font('freesansbold.ttf', 18)
        self.small_font = pygame.font.Font('freesansbold.ttf', 14)
        self.tiny_font  = pygame.font.Font('freesansbold.ttf', 12)

        self.board_theme = board_theme if board_theme in BOARD_THEMES else 'Classic'
        self.piece_theme = piece_theme if piece_theme in PIECE_THEMES else 'Classic'

        # Custom shade overrides (None = use the selected theme's colours as-is)
        self.custom_board = copy.deepcopy(custom_board) if custom_board else None
        self.custom_piece = copy.deepcopy(custom_piece) if custom_piece else None

        # Piece icon rendering (for palette + board preview)
        self._pieces_defs = AllPieces().pieces_defs
        self.piece_icons = {}
        self._reload_icons()

    def _reload_icons(self):
        """Re-render piece icons using current piece colours (custom or theme)."""
        sq = self._board_sq_size(8)
        self.piece_icons = {}
        colors = self.custom_piece if self.custom_piece else PIECE_THEMES[self.piece_theme]
        for piece_type, defn in self._pieces_defs.items():
            path = defn.get('icon')
            if not path:
                continue
            try:
                template = open(path).read()
            except (FileNotFoundError, OSError):
                continue
            for color_name, colours in colors.items():
                try:
                    svg = (template
                           .replace('{fill}',    colours['fill'])
                           .replace('{fill_hi}', colours['fill_hi'])
                           .replace('{fill_lo}', colours['fill_lo'])
                           .replace('{stroke}',  colours['stroke'])
                           .replace('{accent}',  colours['accent']))
                    px = sq - 6
                    self.piece_icons[(piece_type, color_name)] = render_svg(svg, (px, px))
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Shade helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hex_to_rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def _rgb_to_hex(r, g, b):
        return '#{:02X}{:02X}{:02X}'.format(r, g, b)

    @staticmethod
    def _clamp_rgb(rgb, delta):
        return tuple(max(0, min(255, c + delta)) for c in rgb)

    def _adjust_hex(self, h, delta):
        return self._rgb_to_hex(*self._clamp_rgb(self._hex_to_rgb(h), delta))

    def _apply_shade_delta(self, ctrl_idx, delta):
        """Brighten or darken one shade category by delta steps."""
        _, kind, sub, keys = self._SHADE_CONTROLS[ctrl_idx]
        if kind == 'board':
            if self.custom_board is None:
                self.custom_board = copy.deepcopy(BOARD_THEMES[self.board_theme])
            for k in keys:
                if k in self.custom_board:
                    self.custom_board[k] = self._clamp_rgb(self.custom_board[k], delta)
        else:
            if self.custom_piece is None:
                self.custom_piece = copy.deepcopy(PIECE_THEMES[self.piece_theme])
            for k in keys:
                if k in self.custom_piece.get(sub, {}):
                    self.custom_piece[sub][k] = self._adjust_hex(
                        self.custom_piece[sub][k], delta)
            self._reload_icons()

    def _shade_rects(self, panel_x, panel_w, start_y):
        """Return list of (minus_rect, swatch_rect, plus_rect) for each shade row."""
        btn_w = max(20, panel_w // 9)
        sw_w  = max(18, panel_w // 7)
        row_h = 28
        gap   = 5
        rects = []
        for i in range(len(self._SHADE_CONTROLS)):
            y  = start_y + i * (row_h + gap)
            cy = y + row_h // 2
            mr = pygame.Rect(panel_x + panel_w - btn_w * 2 - sw_w - 8,
                             cy - 11, btn_w, 22)
            sr = pygame.Rect(mr.right + 4, cy - 9, sw_w, 18)
            pr = pygame.Rect(sr.right + 4, cy - 11, btn_w, 22)
            rects.append((mr, sr, pr))
        return rects

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def _board_sq_size(self, board_size=8):
        """Size of each board square in pixels."""
        board_area = self.w * 3 // 4   # board uses left 3/4 of the window
        return board_area // board_size

    def _board_origin(self):
        """Top-left pixel corner of the board."""
        return (0, 44)

    def _panel_x(self, board_size=8):
        sq = self._board_sq_size(board_size)
        ox, _ = self._board_origin()
        return ox + sq * board_size + self.PADDING

    def _board_sq_rect(self, x, y, board_size=8):
        sq = self._board_sq_size(board_size)
        ox, oy = self._board_origin()
        return pygame.Rect(ox + x * sq, oy + y * sq, sq, sq)

    def _board_sq_from_pixel(self, px, py, board_size=8):
        """Return (x, y) board coordinate for pixel (px, py), or None if outside."""
        sq = self._board_sq_size(board_size)
        ox, oy = self._board_origin()
        bx = (px - ox) // sq
        by = (py - oy) // sq
        if 0 <= bx < board_size and 0 <= by < board_size:
            return (bx, by)
        return None

    def _palette_rects(self, board_size=8):
        """Return list of (color_str, piece_type, pygame.Rect) for the palette.
        The last entry is the hole tool: ('hole', 'hole', rect).
        """
        px = self._panel_x(board_size)
        pw = self.w - px - self.PADDING
        item_h = 30
        gap    = 4
        rects  = []
        y = 44 + 32  # below "Palette" label
        for color_str in ('white', 'black'):
            for piece_type in self.PALETTE_PIECES:
                rects.append((color_str, piece_type,
                               pygame.Rect(px, y, pw, item_h)))
                y += item_h + gap
            y += gap * 3  # extra gap between colour sections
        # Hole tool — separate section at the bottom of the palette
        y += gap * 2
        rects.append(('hole', 'hole', pygame.Rect(px, y, pw, item_h)))
        return rects

    def _button_rects(self, btn_y, btn_h, board_size=8):
        labels = ['← Back', 'Reset', 'Save', 'Play']
        sq = self._board_sq_size(board_size)
        total_w = sq * board_size   # buttons span the board width
        bw = (total_w - self.PADDING * (len(labels) - 1)) // len(labels)
        ox, _ = self._board_origin()
        rects = {}
        for i, label in enumerate(labels):
            x = ox + i * (bw + self.PADDING)
            rects[label] = pygame.Rect(x, btn_y, bw, btn_h)
        return rects

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self):
        """
        Show the editor.  Returns (layout_dict, saved_path, board_theme,
        piece_theme, custom_board, custom_piece).
        """
        layout = self._load_or_default()
        selected = ('white', 'pawn')
        saved_path = None
        status_msg = ''
        status_until = 0
        clock = pygame.time.Clock()

        while True:
            board_size = layout.get('board_size', 8)
            mouse = pygame.mouse.get_pos()
            btn_h  = 40
            btn_y  = self._btn_y(board_size)

            # Pre-compute panel geometry (needed for shade rects)
            px_th = self._panel_x(board_size)
            pw_th = self.w - px_th - self.PADDING
            pal_items = self._palette_rects(board_size)
            theme_start_y = pal_items[-1][2].bottom + 10 if pal_items else 44 + 10
            theme_rects_map = self._theme_rects(px_th, pw_th, theme_start_y)
            # shade section starts just below the theme section
            if theme_rects_map:
                last_tr = max(r.bottom for r in theme_rects_map.values())
                shade_start_y = last_tr + 12
            else:
                shade_start_y = theme_start_y + 100
            shade_rects = self._shade_rects(px_th, pw_th, shade_start_y)

            for event in pygame.event.get():
                if event.type == locals.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == locals.KEYDOWN and event.key == locals.K_ESCAPE:
                    return (layout, saved_path, self.board_theme, self.piece_theme,
                            self.custom_board, self.custom_piece)

                if event.type == locals.MOUSEBUTTONDOWN:
                    mx, my = event.pos

                    # Board click: place/remove piece or toggle hole
                    sq_coord = self._board_sq_from_pixel(mx, my, board_size)
                    if sq_coord is not None:
                        bx, by = sq_coord
                        cell = layout['matrix'][bx][by]
                        if event.button == 3:
                            layout['matrix'][bx][by] = None
                        elif event.button == 1:
                            if selected == 'hole':
                                layout['matrix'][bx][by] = None if cell == 'hole' else 'hole'
                            else:
                                color_str, piece_type = selected
                                if (isinstance(cell, dict)
                                        and cell['piece_type'] == piece_type
                                        and cell['color'] == color_str):
                                    layout['matrix'][bx][by] = None
                                else:
                                    layout['matrix'][bx][by] = {
                                        'piece_type': piece_type,
                                        'color': color_str,
                                        'has_moved': False,
                                    }

                    # Board size +/- buttons
                    minus_rect, plus_rect = self._size_rects(board_size)
                    if minus_rect.collidepoint(mx, my) and board_size > self.MIN_BOARD_SIZE:
                        layout = self._resize_layout(layout, board_size - 1)
                        status_msg = f'Board size: {board_size - 1}×{board_size - 1}'
                        status_until = pygame.time.get_ticks() + 2000
                    elif plus_rect.collidepoint(mx, my) and board_size < self.MAX_BOARD_SIZE:
                        layout = self._resize_layout(layout, board_size + 1)
                        status_msg = f'Board size: {board_size + 1}×{board_size + 1}'
                        status_until = pygame.time.get_ticks() + 2000

                    # Palette click
                    for color_str, piece_type, rect in pal_items:
                        if rect.collidepoint(mx, my):
                            selected = 'hole' if color_str == 'hole' else (color_str, piece_type)

                    # Preset button clicks
                    for preset_name, rect in self._preset_rects(btn_y, btn_h, board_size).items():
                        if rect.collidepoint(mx, my):
                            layout = self._make_preset(preset_name)
                            status_msg = f'Loaded preset: {preset_name}'
                            status_until = pygame.time.get_ticks() + 2500

                    # Theme selector clicks — reset custom shades when theme changes
                    for (kind, name), rect in theme_rects_map.items():
                        if rect.collidepoint(mx, my):
                            if kind == 'board':
                                self.board_theme = name
                                self.custom_board = None
                            else:
                                self.piece_theme = name
                                self.custom_piece = None
                                self._reload_icons()
                            self._save_theme_file()

                    # Shade +/- clicks
                    for i, (mr, sr, pr) in enumerate(shade_rects):
                        if mr.collidepoint(mx, my):
                            self._apply_shade_delta(i, -self.SHADE_STEP)
                        elif pr.collidepoint(mx, my):
                            self._apply_shade_delta(i, +self.SHADE_STEP)

                    # Button clicks
                    for label, rect in self._button_rects(btn_y, btn_h, board_size).items():
                        if rect.collidepoint(mx, my):
                            if label == '← Back':
                                return (layout, saved_path, self.board_theme,
                                        self.piece_theme, self.custom_board, self.custom_piece)
                            elif label == 'Reset':
                                layout = self._default_layout()
                                saved_path = None
                                status_msg = 'Reset to default starting position'
                                status_until = pygame.time.get_ticks() + 2500
                            elif label == 'Save':
                                self._save(layout)
                                self._save_theme_file()
                                saved_path = _CUSTOM_LAYOUT_PATH
                                status_msg = 'Saved'
                                status_until = pygame.time.get_ticks() + 2500
                            elif label == 'Play':
                                return (layout, saved_path, self.board_theme,
                                        self.piece_theme, self.custom_board, self.custom_piece)

            self._draw(layout, selected, mouse, btn_y, btn_h,
                       status_msg if pygame.time.get_ticks() < status_until else '',
                       shade_rects, shade_start_y, px_th, pw_th,
                       theme_rects_map, theme_start_y)
            pygame.display.update()
            clock.tick(60)

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _default_layout(self):
        """Return the standard chess starting position as a layout dict."""
        return _preset_standard()

    def _make_preset(self, name):
        """Return a preset layout dict by name."""
        if name == 'Diamond 8×8':
            return _preset_diamond()
        elif name == 'Hexagon 12×12':
            return _preset_hexagon()
        return _preset_standard()

    def _btn_y(self, board_size=8):
        """Return the y-pixel of the action buttons row (consistent with run())."""
        sq = self._board_sq_size(board_size)
        _, oy = self._board_origin()
        preset_btn_h = 32
        return oy + sq * board_size + self.PADDING * 2 + preset_btn_h + 18

    MIN_BOARD_SIZE = 4
    MAX_BOARD_SIZE = 12

    def _size_rects(self, board_size=8):
        """Return (minus_rect, plus_rect) for the board-size +/- buttons in the panel."""
        px = self._panel_x(board_size)
        pw = self.w - px - self.PADDING
        btn_w = 28
        y = 44 + 6   # near top of panel, same baseline as palette header
        minus_rect = pygame.Rect(px + pw - btn_w * 2 - 4, y, btn_w, 22)
        plus_rect  = pygame.Rect(px + pw - btn_w,          y, btn_w, 22)
        return minus_rect, plus_rect

    @staticmethod
    def _resize_layout(layout, new_size):
        """
        Return a new layout dict with board_size=new_size.
        Cells within the new bounds are preserved; cells outside are dropped.
        New cells (expanded rows/columns) are filled with None.
        """
        old_size = layout.get('board_size', 8)
        old_matrix = layout['matrix']
        new_matrix = []
        for x in range(new_size):
            col = []
            for y in range(new_size):
                if x < old_size and y < old_size:
                    col.append(old_matrix[x][y])
                else:
                    col.append(None)
            new_matrix.append(col)
        return {
            'board_size': new_size,
            'matrix': new_matrix,
            'en_passant_target': None,
            'promotion_pending': None,
        }

    def _preset_rects(self, btn_y, btn_h, board_size=8):
        """Return dict of preset_name → pygame.Rect, above the bottom buttons."""
        names = ['Standard 8×8', 'Diamond 8×8', 'Hexagon 12×12']
        sq = self._board_sq_size(board_size)
        ox, _ = self._board_origin()
        total_w = sq * board_size
        preset_btn_h = 32
        preset_y = btn_y - preset_btn_h - self.PADDING
        bw = (total_w - self.PADDING * (len(names) - 1)) // len(names)
        rects = {}
        for i, name in enumerate(names):
            x = ox + i * (bw + self.PADDING)
            rects[name] = pygame.Rect(x, preset_y, bw, preset_btn_h)
        return rects

    def _load_or_default(self):
        if os.path.exists(_CUSTOM_LAYOUT_PATH):
            try:
                with open(_CUSTOM_LAYOUT_PATH) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        return self._default_layout()

    def _save(self, layout):
        os.makedirs(os.path.dirname(_CUSTOM_LAYOUT_PATH), exist_ok=True)
        with open(_CUSTOM_LAYOUT_PATH, 'w') as f:
            json.dump(layout, f, indent=2)

    def _save_theme_file(self):
        os.makedirs(os.path.dirname(_CUSTOM_THEME_PATH), exist_ok=True)
        data = {'board_theme': self.board_theme, 'piece_theme': self.piece_theme}
        if self.custom_board is not None:
            data['custom_board'] = {k: list(v) for k, v in self.custom_board.items()}
        if self.custom_piece is not None:
            data['custom_piece'] = self.custom_piece
        with open(_CUSTOM_THEME_PATH, 'w') as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_pixel_btn(self, surf, rect, base_color, hovered, text, font, text_color,
                        bevel=2):
        """Draw a pixel-art bevelled button (square corners, bright top/left, dark bottom/right)."""
        bg = tuple(min(c + 30, 255) for c in base_color) if hovered else base_color
        hi = tuple(min(c + 55, 255) for c in base_color)
        lo = tuple(max(c - 25,   0) for c in base_color)
        pygame.draw.rect(surf, bg, rect, border_radius=0)
        pygame.draw.line(surf, hi, rect.topleft,    rect.topright,    bevel)
        pygame.draw.line(surf, hi, rect.topleft,    rect.bottomleft,  bevel)
        pygame.draw.line(surf, lo, rect.bottomleft, rect.bottomright, bevel)
        pygame.draw.line(surf, lo, rect.topright,   rect.bottomright, bevel)
        if text:
            shd = font.render(text, True, (0, 0, 0))
            lbl = font.render(text, True, text_color)
            surf.blit(shd, shd.get_rect(center=(rect.centerx + 1, rect.centery + 1)))
            surf.blit(lbl, lbl.get_rect(center=rect.center))

    def _theme_rects(self, panel_x, panel_w, start_y):
        """Return dict of (kind, name) → pygame.Rect for theme selector buttons."""
        bw, bh, gap = 64, 22, 4
        rects = {}
        # Board theme row
        y = start_y + 20
        for i, name in enumerate(BOARD_THEMES):
            x = panel_x + i * (bw + gap)
            rects[('board', name)] = pygame.Rect(x, y, bw, bh)
        # Piece theme row
        y += bh + gap + 20
        for i, name in enumerate(PIECE_THEMES):
            x = panel_x + i * (bw + gap)
            rects[('piece', name)] = pygame.Rect(x, y, bw, bh)
        return rects

    def _draw(self, layout, selected, mouse, btn_y, btn_h, status_msg,
              shade_rects, shade_start_y, _panel_x_unused, _panel_w_unused,
              theme_rects_map, theme_start_y):
        board_size = layout.get('board_size', 8)
        self.screen.fill(self.BG)

        # Title with drop-shadow
        shd = self.title_font.render('Board Layout Editor', True, (0, 0, 0))
        title = self.title_font.render('Board Layout Editor', True, self.TITLE_COLOR)
        self.screen.blit(shd,   (self.PADDING + 2, 10))
        self.screen.blit(title, (self.PADDING,      8))
        hint = self.tiny_font.render('Left-click: place  •  Right-click: clear  •  Esc: back',
                                     True, self.DIM_TEXT)
        self.screen.blit(hint, (self._panel_x(board_size), 8))

        sq = self._board_sq_size(board_size)
        ox, oy = self._board_origin()
        t = self.custom_board if self.custom_board else BOARD_THEMES[self.board_theme]

        # Pixel art frame around board: teal outer + dark inner + corner accents
        board_px = sq * board_size
        pygame.draw.rect(self.screen, Colours.HIGH,  (ox - 5, oy - 5, board_px + 10, board_px + 10), 3)
        pygame.draw.rect(self.screen, (30, 25, 55),  (ox - 2, oy - 2, board_px +  4, board_px +  4), 2)
        for cx_off, cy_off in [(0,0),(board_px+4,0),(0,board_px+4),(board_px+4,board_px+4)]:
            pygame.draw.rect(self.screen, Colours.HIGH, (ox - 5 + cx_off, oy - 5 + cy_off, 6, 6))

        # Coordinate labels around the board (pixel art style with drop shadow)
        lbl_font = pygame.font.Font('freesansbold.ttf', max(sq // 4, 10))
        files = 'abcdefghijklmnopqrstuvwxyz'[:board_size]
        for i, ch in enumerate(files):
            cx = ox + i * sq + sq // 2
            shd_s = lbl_font.render(ch, True, (0, 0, 0))
            lbl_s = lbl_font.render(ch, True, Colours.GOLD)
            r = lbl_s.get_rect(centerx=cx, centery=oy - 12)
            self.screen.blit(shd_s, r.move(1, 1))
            self.screen.blit(lbl_s, r)
        for i in range(board_size):
            cy = oy + i * sq + sq // 2
            ch = str(board_size - i)
            shd_s = lbl_font.render(ch, True, (0, 0, 0))
            lbl_s = lbl_font.render(ch, True, Colours.GOLD)
            r = lbl_s.get_rect(centerx=ox - 12, centery=cy)
            self.screen.blit(shd_s, r.move(1, 1))
            self.screen.blit(lbl_s, r)

        # Board squares with board-theme bevel
        _bevel = max(2, sq // 16)
        sq_coord_hover = self._board_sq_from_pixel(*mouse, board_size)
        for x in range(board_size):
            for y in range(board_size):
                cell = layout['matrix'][x][y]
                rect = self._board_sq_rect(x, y, board_size)
                hovering = sq_coord_hover == (x, y)
                if cell == 'hole':
                    pygame.draw.rect(self.screen, t['hole'], rect)
                    pygame.draw.rect(self.screen, t['hole_lo'], (rect.x, rect.y, rect.w, _bevel))
                    pygame.draw.rect(self.screen, t['hole_lo'], (rect.x, rect.y, _bevel, rect.h))
                    pygame.draw.rect(self.screen, t['hole_hi'], (rect.x, rect.y + rect.h - _bevel, rect.w, _bevel))
                    pygame.draw.rect(self.screen, t['hole_hi'], (rect.x + rect.w - _bevel, rect.y, _bevel, rect.h))
                else:
                    is_light = (x + y) % 2 == 0
                    base_color = t['light'] if is_light else t['dark']
                    if hovering:
                        base_color = tuple(min(c + 30, 255) for c in base_color)
                    hi = t['light_hi'] if is_light else t['dark_hi']
                    lo = t['light_lo'] if is_light else t['dark_lo']
                    pygame.draw.rect(self.screen, base_color, rect)
                    pygame.draw.rect(self.screen, hi, (rect.x, rect.y, rect.w, _bevel))
                    pygame.draw.rect(self.screen, hi, (rect.x, rect.y, _bevel, rect.h))
                    pygame.draw.rect(self.screen, lo, (rect.x, rect.y + rect.h - _bevel, rect.w, _bevel))
                    pygame.draw.rect(self.screen, lo, (rect.x + rect.w - _bevel, rect.y, _bevel, rect.h))

        # Pixel art grid lines between squares
        sep = (8, 8, 18)
        for i in range(1, board_size):
            pygame.draw.line(self.screen, sep, (ox + i*sq, oy), (ox + i*sq, oy + board_px))
            pygame.draw.line(self.screen, sep, (ox, oy + i*sq), (ox + board_px, oy + i*sq))

        # Board pieces
        piece_labels = {'pawn': 'P', 'rook': 'R', 'knight': 'N',
                        'bishop': 'B', 'queen': 'Q', 'king': 'K'}
        for x in range(board_size):
            for y in range(board_size):
                cell = layout['matrix'][x][y]
                if cell is None or cell == 'hole':
                    continue
                rect = self._board_sq_rect(x, y, board_size)
                cx, cy = rect.centerx, rect.centery
                color_key = cell['color']
                icon = self.piece_icons.get((cell['piece_type'], color_key))
                if icon:
                    icon_scaled = pygame.transform.smoothscale(icon, (sq - 6, sq - 6))
                    self.screen.blit(icon_scaled, icon_scaled.get_rect(center=(cx, cy)))
                else:
                    c = Colours.WHITE if color_key == 'white' else Colours.PIECE_BLACK
                    r = sq // 2 - 2
                    pygame.draw.circle(self.screen, c, (cx, cy), r)
                    outline = Colours.BLACK if color_key == 'white' else Colours.WHITE
                    pygame.draw.circle(self.screen, outline, (cx, cy), r, 2)
                    lbl = self.small_font.render(piece_labels.get(cell['piece_type'], '?'),
                                                 True, outline)
                    self.screen.blit(lbl, lbl.get_rect(center=(cx, cy)))

        # Right panel — pixel art frame + palette + themes
        px = self._panel_x(board_size)
        pw = self.w - px - self.PADDING
        panel_rect = pygame.Rect(px - self.PADDING // 2, oy - 2,
                                 pw + self.PADDING, btn_y - oy + 2 - self.PADDING)
        pygame.draw.rect(self.screen, self.PANEL_BG, panel_rect, border_radius=0)
        pygame.draw.rect(self.screen, Colours.HIGH,  panel_rect, 2)
        pygame.draw.rect(self.screen, (30, 25, 55),  panel_rect.inflate(-4, -4), 1)

        pal_hdr = self.label_font.render('Palette', True, self.TITLE_COLOR)
        self.screen.blit(pal_hdr, (px, oy + 6))

        # Board size controls: "Size: N  [−] [+]"
        minus_rect, plus_rect = self._size_rects(board_size)
        size_lbl = self.tiny_font.render(f'Size: {board_size}', True, self.TEXT)
        self.screen.blit(size_lbl, size_lbl.get_rect(
            centery=minus_rect.centery, right=minus_rect.left - 6))
        for rect, label, enabled in [
            (minus_rect, '−', board_size > self.MIN_BOARD_SIZE),
            (plus_rect,  '+', board_size < self.MAX_BOARD_SIZE),
        ]:
            hov = rect.collidepoint(*mouse) and enabled
            base = self.BTN_HOV if enabled else (45, 48, 58)
            tc = self.TEXT if enabled else (70, 75, 85)
            self._draw_pixel_btn(self.screen, rect, base, hov,
                                 label, self.label_font, tc)

        for color_str, piece_type, rect in self._palette_rects(board_size):
            is_hole_entry = (color_str == 'hole')
            is_sel = (selected == 'hole' if is_hole_entry
                      else selected == (color_str, piece_type))
            hov    = rect.collidepoint(*mouse)
            if is_sel:
                bg = self.HIGH
                tc = (20, 20, 20)
            elif hov:
                bg = self.BTN_HOV
                tc = self.TEXT
            else:
                bg = self.BTN_BG
                tc = self.TEXT
            # Palette row: pixel art bevel + selected teal border
            self._draw_pixel_btn(self.screen, rect, bg, False, None, None, None)
            if is_sel:
                pygame.draw.rect(self.screen, Colours.HIGH, rect, 2)

            icon_x = rect.left + 4
            if is_hole_entry:
                swatch = pygame.Rect(icon_x, rect.centery - 10, 24, 20)
                pygame.draw.rect(self.screen, Colours.HOLE, swatch, border_radius=0)
                pygame.draw.rect(self.screen, (45, 45, 55), swatch.inflate(-6, -6))
                lbl = self.small_font.render('Hole  (toggle)', True, tc)
            else:
                icon = self.piece_icons.get((piece_type, color_str))
                if icon:
                    small = pygame.transform.smoothscale(icon, (24, 24))
                    self.screen.blit(small, small.get_rect(centery=rect.centery, left=icon_x))
                lbl_text = f"{color_str}  {piece_type}"
                lbl = self.small_font.render(lbl_text, True, tc)
            self.screen.blit(lbl, lbl.get_rect(centery=rect.centery, left=icon_x + 28))

        # ── Themes panel ─────────────────────────────────────────────────
        if theme_rects_map:
            thdr = self.tiny_font.render('BOARD THEME', True, self.TITLE_COLOR)
            self.screen.blit(thdr, (px, theme_start_y + 2))
            phdr = self.tiny_font.render('PIECE THEME', True, self.TITLE_COLOR)
            bh_row = list(BOARD_THEMES.keys())[0]
            phdr_y = theme_rects_map[('board', bh_row)].bottom + 6
            self.screen.blit(phdr, (px, phdr_y))

        for (kind, name), rect in theme_rects_map.items():
            active = (name == self.board_theme if kind == 'board'
                      else name == self.piece_theme)
            hov = rect.collidepoint(*mouse)
            base = (40, 160, 160) if active else self.BTN_BG
            tc   = (5, 5, 15) if active else self.TEXT
            self._draw_pixel_btn(self.screen, rect, base, hov,
                                 name, self.tiny_font, tc)
            if active:
                pygame.draw.rect(self.screen, Colours.HIGH, rect, 2)

        # ── Shade controls ────────────────────────────────────────────────
        shade_hdr = self.tiny_font.render('SHADES  [ - darker   + brighter ]',
                                          True, self.TITLE_COLOR)
        if shade_rects:
            self.screen.blit(shade_hdr, (px, shade_start_y - 14))
        for i, (label, kind, sub, keys) in enumerate(self._SHADE_CONTROLS) if shade_rects else []:
            mr, sr, pr = shade_rects[i]
            # Label
            ls = self.tiny_font.render(label, True, self.TEXT)
            self.screen.blit(ls, (px, mr.centery - ls.get_height() // 2))
            # Swatch colour sample
            if kind == 'board':
                bc = self.custom_board if self.custom_board else BOARD_THEMES[self.board_theme]
                swatch_col = bc[keys[0]]
            else:
                pc = self.custom_piece if self.custom_piece else PIECE_THEMES[self.piece_theme]
                r, g, b = self._hex_to_rgb(pc[sub][keys[0]])
                swatch_col = (r, g, b)
            # Minus button
            hm = mr.collidepoint(*mouse)
            pygame.draw.rect(self.screen, (60, 30, 30) if hm else (40, 20, 20), mr)
            pygame.draw.rect(self.screen, (140, 70, 70), mr, 1)
            ms = self.tiny_font.render('-', True, (220, 140, 140))
            self.screen.blit(ms, ms.get_rect(center=mr.center))
            # Colour swatch
            pygame.draw.rect(self.screen, swatch_col, sr)
            pygame.draw.rect(self.screen, (70, 70, 100), sr, 1)
            # Plus button
            hp = pr.collidepoint(*mouse)
            pygame.draw.rect(self.screen, (30, 60, 30) if hp else (20, 40, 20), pr)
            pygame.draw.rect(self.screen, (70, 140, 70), pr, 1)
            ps = self.tiny_font.render('+', True, (140, 220, 140))
            self.screen.blit(ps, ps.get_rect(center=pr.center))

        # Preset buttons (row above the action buttons)
        preset_rects = self._preset_rects(btn_y, btn_h, board_size)
        preset_lbl = self.tiny_font.render('Presets:', True, self.DIM_TEXT)
        if preset_rects:
            first_rect = next(iter(preset_rects.values()))
            self.screen.blit(preset_lbl, (ox, first_rect.y - 18))
        for name, rect in preset_rects.items():
            hov = rect.collidepoint(*mouse)
            self._draw_pixel_btn(self.screen, rect, self.BTN_BG, hov,
                                 name, self.tiny_font, self.TEXT)

        # Bottom action buttons (pixel art bevel)
        btn_colors = {
            '← Back': self.BTN_BG,
            'Reset':   self.BTN_RST,
            'Save':    self.BTN_SAVE,
            'Play':    self.BTN_PLAY,
        }
        for label, rect in self._button_rects(btn_y, btn_h, board_size).items():
            hov = rect.collidepoint(*mouse)
            self._draw_pixel_btn(self.screen, rect, btn_colors[label], hov,
                                 label, self.label_font, self.TEXT)

        # Status message
        if status_msg:
            sm = self.small_font.render(status_msg, True, Colours.GOLD)
            self.screen.blit(sm, (ox, btn_y - 22))


def _make_layout(board_size, matrix):
    """Build a layout dict with the given board_size and matrix."""
    return {'board_size': board_size, 'matrix': matrix,
            'en_passant_target': None, 'promotion_pending': None}


def _preset_standard():
    """Standard chess starting position on an 8×8 board."""
    back_rank = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook']
    matrix = [[None] * 8 for _ in range(8)]
    for x in range(8):
        matrix[x][0] = {'piece_type': back_rank[x], 'color': 'black', 'has_moved': False}
        matrix[x][1] = {'piece_type': 'pawn',        'color': 'black', 'has_moved': False}
        matrix[x][6] = {'piece_type': 'pawn',        'color': 'white', 'has_moved': False}
        matrix[x][7] = {'piece_type': back_rank[x],  'color': 'white', 'has_moved': False}
    return _make_layout(8, matrix)


def _preset_diamond():
    """
    Diamond (rhombus) board on 8×8.  Holes where abs(2*x - 7) + abs(2*y - 7) > 10
    leave a diamond shape (52 playable squares) symmetric about both the
    horizontal and vertical midlines.

    Playable squares per row:
      y=0,7 → x=2..5 (4 squares)
      y=1,6 → x=1..6 (6 squares)
      y=2..5 → x=0..7 (8 squares)

    White back rank at y=7: rook(2), queen(3), king(4), rook(5)
    White pawns at y=6: x=1..6
    Black back rank at y=0: rook(2), queen(3), king(4), rook(5)
    Black pawns at y=1: x=1..6
    """
    N = 8

    def is_hole(x, y):
        return abs(2 * x - 7) + abs(2 * y - 7) > 10

    matrix = [['hole' if is_hole(x, y) else None for y in range(N)] for x in range(N)]

    # White back rank at y=7 (x=2..5 are playable)
    white_back = {2: 'rook', 3: 'queen', 4: 'king', 5: 'rook'}
    for x, pt in white_back.items():
        matrix[x][7] = {'piece_type': pt, 'color': 'white', 'has_moved': False}
    # White pawns at y=6, x=1..6
    for x in range(1, 7):
        matrix[x][6] = {'piece_type': 'pawn', 'color': 'white', 'has_moved': False}

    # Black back rank at y=0 (x=2..5 are playable)
    black_back = {2: 'rook', 3: 'queen', 4: 'king', 5: 'rook'}
    for x, pt in black_back.items():
        matrix[x][0] = {'piece_type': pt, 'color': 'black', 'has_moved': False}
    # Black pawns at y=1, x=1..6
    for x in range(1, 7):
        matrix[x][1] = {'piece_type': 'pawn', 'color': 'black', 'has_moved': False}

    return _make_layout(N, matrix)


def _preset_hexagon():
    """
    Approximate hexagon on a 12×12 board.
    Holes where: x+y < 3, x+y > 19, x-y > 8, or y-x > 8.
    Pieces on the valid back ranks at y=11 (white) and y=0 (black).
    """
    N = 12
    matrix = [[None] * N for _ in range(N)]

    def is_hole(x, y):
        return x + y < 3 or x + y > 19 or x - y > 8 or y - x > 8

    for x in range(N):
        for y in range(N):
            if is_hole(x, y):
                matrix[x][y] = 'hole'

    # White back rank at y=11 — valid x=3..8
    white_back = ['rook', 'knight', 'bishop', 'queen', 'king', 'rook']
    for i, x in enumerate(range(3, 9)):
        matrix[x][11] = {'piece_type': white_back[i], 'color': 'white', 'has_moved': False}
    # White pawns at y=10 — valid x=2..9
    for x in range(2, 10):
        if not is_hole(x, 10):
            matrix[x][10] = {'piece_type': 'pawn', 'color': 'white', 'has_moved': False}

    # Black back rank at y=0 — valid x=3..8
    black_back = ['rook', 'knight', 'bishop', 'queen', 'king', 'rook']
    for i, x in enumerate(range(3, 9)):
        matrix[x][0] = {'piece_type': black_back[i], 'color': 'black', 'has_moved': False}
    # Black pawns at y=1 — valid x=2..9
    for x in range(2, 10):
        if not is_hole(x, 1):
            matrix[x][1] = {'piece_type': 'pawn', 'color': 'black', 'has_moved': False}

    return _make_layout(N, matrix)


def _start_menu(screen, w, h):
    """
    Simple title screen.  Returns 'play', 'edit_pieces', or 'edit_layout'.
    """
    pygame.display.set_caption('megaChess')
    clock = pygame.time.Clock()
    bw, bh = 210, 56
    gap = 16
    total_w = bw * 3 + gap * 2
    x0 = w // 2 - total_w // 2
    btns = {
        'Play':         pygame.Rect(x0,                   h * 2 // 3, bw, bh),
        'Edit Pieces':  pygame.Rect(x0 + (bw + gap),      h * 2 // 3, bw, bh),
        'Edit Layout':  pygame.Rect(x0 + (bw + gap) * 2,  h * 2 // 3, bw, bh),
    }
    btn_colors = {
        'Play':        (30,  75, 150),
        'Edit Pieces': (30, 100,  55),
        'Edit Layout': (90,  40, 120),
    }
    key_map = {
        'Play':        'play',
        'Edit Pieces': 'edit_pieces',
        'Edit Layout': 'edit_layout',
    }

    # Pre-build pixel-art grid overlay (subtle tile grid)
    grid_overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    for gx in range(0, w, 16):
        pygame.draw.line(grid_overlay, (255, 255, 255, 12), (gx, 0), (gx, h))
    for gy in range(0, h, 16):
        pygame.draw.line(grid_overlay, (255, 255, 255, 12), (0, gy), (w, gy))

    # Pre-build scanline overlay (CRT retro effect)
    scanlines = pygame.Surface((w, h), pygame.SRCALPHA)
    for sy in range(0, h, 2):
        pygame.draw.line(scanlines, (0, 0, 0, 80), (0, sy), (w, sy))

    # Pre-build corner chess board decorations (4×4 grid of 14×14px squares)
    _cell = 14
    _t = BOARD_THEMES['Classic']
    _corner_surf = pygame.Surface((_cell * 4, _cell * 4))
    for _r in range(4):
        for _c in range(4):
            _col = _t['light'] if (_r + _c) % 2 == 0 else _t['dark']
            pygame.draw.rect(_corner_surf, _col,
                             (_c * _cell, _r * _cell, _cell, _cell))
    # bevel each mini-square
    _bv = 2
    for _r in range(4):
        for _c in range(4):
            _is_l = (_r + _c) % 2 == 0
            _hi = _t['light_hi'] if _is_l else _t['dark_hi']
            _lo = _t['light_lo'] if _is_l else _t['dark_lo']
            _rx, _ry = _c * _cell, _r * _cell
            pygame.draw.rect(_corner_surf, _hi, (_rx, _ry, _cell, _bv))
            pygame.draw.rect(_corner_surf, _hi, (_rx, _ry, _bv, _cell))
            pygame.draw.rect(_corner_surf, _lo, (_rx, _ry + _cell - _bv, _cell, _bv))
            pygame.draw.rect(_corner_surf, _lo, (_rx + _cell - _bv, _ry, _bv, _cell))
    _corner_w = _cell * 4
    pygame.draw.rect(_corner_surf, Colours.HIGH, (0, 0, _corner_w, _corner_w), 2)

    while True:
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == locals.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == locals.MOUSEBUTTONDOWN:
                for label, rect in btns.items():
                    if rect.collidepoint(mx, my):
                        return key_map[label]
            if event.type == locals.KEYDOWN:
                if event.key == locals.K_RETURN:
                    return 'play'
                if event.key == locals.K_e:
                    return 'edit_pieces'
                if event.key == locals.K_l:
                    return 'edit_layout'

        screen.fill((10, 8, 20))
        # Pixel-art grid + corner chess board decorations
        screen.blit(grid_overlay, (0, 0))
        margin = 16
        screen.blit(_corner_surf, (margin, margin))
        screen.blit(pygame.transform.flip(_corner_surf, True,  False), (w - _corner_w - margin, margin))
        screen.blit(pygame.transform.flip(_corner_surf, False, True),  (margin, h - _corner_w - margin))
        screen.blit(pygame.transform.flip(_corner_surf, True,  True),  (w - _corner_w - margin, h - _corner_w - margin))
        screen.blit(scanlines, (0, 0))

        # Stacked two-colour pixel art title: MEGA (gold) + CHESS (teal)
        mega_surf  = _pixel_text('MEGA',  72, Colours.GOLD, bold=True)
        chess_surf = _pixel_text('CHESS', 72, Colours.HIGH, bold=True)
        title_w  = max(mega_surf.get_width(), chess_surf.get_width())
        title_h  = mega_surf.get_height() + chess_surf.get_height() + 4
        frame_x  = w // 2 - title_w // 2 - 24
        frame_y  = h // 5
        pad = 16
        # Outer teal border + dark inner fill
        pygame.draw.rect(screen, Colours.HIGH,
                         (frame_x - 4, frame_y - 4, title_w + 56, title_h + pad * 2 + 8), 3)
        pygame.draw.rect(screen, (8, 8, 18),
                         (frame_x, frame_y, title_w + 48, title_h + pad * 2))
        # Bevel lines on title box
        bx, by, bw2, bh2 = frame_x, frame_y, title_w + 48, title_h + pad * 2
        pygame.draw.line(screen, (80, 215, 215), (bx, by), (bx + bw2, by), 1)
        pygame.draw.line(screen, (80, 215, 215), (bx, by), (bx, by + bh2), 1)
        pygame.draw.line(screen, (20, 40, 80), (bx, by + bh2), (bx + bw2, by + bh2), 1)
        pygame.draw.line(screen, (20, 40, 80), (bx + bw2, by), (bx + bw2, by + bh2), 1)
        # Pixel art corner dots on title box
        for _dx, _dy in [(bx, by), (bx + bw2 - 4, by), (bx, by + bh2 - 4), (bx + bw2 - 4, by + bh2 - 4)]:
            pygame.draw.rect(screen, Colours.GOLD, (_dx, _dy, 4, 4))
        # Render titles centred inside box
        cx = bx + bw2 // 2
        screen.blit(mega_surf,  mega_surf.get_rect(centerx=cx,  top=frame_y + pad))
        screen.blit(chess_surf, chess_surf.get_rect(centerx=cx, top=frame_y + pad + mega_surf.get_height() + 4))

        # Blinking cursor prompt — pixel art text
        blink = (pygame.time.get_ticks() // 500) % 2
        hint_str = 'PRESS ENTER TO PLAY' + (' _' if blink else '  ')
        hint_s = _pixel_text(hint_str, 16, (140, 130, 170), bold=True)
        screen.blit(hint_s, hint_s.get_rect(centerx=w // 2, top=frame_y + title_h + pad * 2 + 24))

        sub = _pixel_text('E = edit pieces   *   L = edit layout', 16, (100, 90, 130), bold=True)
        screen.blit(sub, sub.get_rect(centerx=w // 2, top=frame_y + title_h + pad * 2 + 52))

        BEVEL = 2
        for label, rect in btns.items():
            hov = rect.collidepoint(mx, my)
            base = btn_colors[label]
            bg = tuple(min(c + 35, 255) for c in base) if hov else base
            bhi = tuple(min(c + 55, 255) for c in base)
            blo = tuple(max(c - 20, 0) for c in base)
            pygame.draw.rect(screen, bg, rect, border_radius=0)
            pygame.draw.line(screen, bhi, rect.topleft,    rect.topright,    BEVEL)
            pygame.draw.line(screen, bhi, rect.topleft,    rect.bottomleft,  BEVEL)
            pygame.draw.line(screen, blo, rect.bottomleft, rect.bottomright, BEVEL)
            pygame.draw.line(screen, blo, rect.topright,   rect.bottomright, BEVEL)
            shadow_s = _pixel_text(label, 24, (0, 0, 0),       bold=True)
            txt_s    = _pixel_text(label, 24, (220, 225, 235),  bold=True)
            screen.blit(shadow_s, shadow_s.get_rect(center=(rect.centerx + 1, rect.centery + 1)))
            screen.blit(txt_s,    txt_s.get_rect(center=rect.center))

        pygame.display.update()
        clock.tick(60)


def main():
    pygame.init()
    info = pygame.display.Info()
    w = h = min(info.current_w, info.current_h)
    screen = pygame.display.set_mode((w, h))

    custom_defs    = None
    custom_layout  = None
    board_theme    = 'Classic'
    piece_theme    = 'Classic'
    custom_board   = None   # custom BOARD_THEMES entry (RGB tuple dict), or None
    custom_piece   = None   # custom PIECE_THEMES entry (hex string dict), or None

    # Load saved layout
    if os.path.exists(_CUSTOM_LAYOUT_PATH):
        try:
            with open(_CUSTOM_LAYOUT_PATH) as _f:
                custom_layout = json.load(_f)
        except (OSError, json.JSONDecodeError):
            pass

    # Load saved theme (includes optional custom colour data)
    if os.path.exists(_CUSTOM_THEME_PATH):
        try:
            with open(_CUSTOM_THEME_PATH) as _f:
                _td = json.load(_f)
            board_theme = _td.get('board_theme', 'Classic')
            piece_theme = _td.get('piece_theme', 'Classic')
            if board_theme not in BOARD_THEMES:
                board_theme = 'Classic'
            if piece_theme not in PIECE_THEMES:
                piece_theme = 'Classic'
            # Restore custom shade data if present
            if 'custom_board' in _td:
                _cb = _td['custom_board']
                custom_board = {k: tuple(v) for k, v in _cb.items()}
            if 'custom_piece' in _td:
                custom_piece = _td['custom_piece']
        except (OSError, json.JSONDecodeError):
            pass

    while True:
        choice = _start_menu(screen, w, h)
        if choice == 'edit_pieces':
            defs, saved_path = PieceEditor().run()
            if saved_path:
                custom_defs = defs
        elif choice == 'edit_layout':
            (layout, saved_path, board_theme, piece_theme,
             custom_board, custom_piece) = BoardLayoutEditor(
                board_theme=board_theme, piece_theme=piece_theme,
                custom_board=custom_board, custom_piece=custom_piece).run()
            if saved_path:
                custom_layout = layout
        else:
            game = Game()
            game.graphics.board_theme = board_theme
            game.graphics.piece_theme = piece_theme
            # Apply custom colours by temporarily patching the theme dicts
            _orig_board = BOARD_THEMES.get('_custom_')
            _orig_piece = PIECE_THEMES.get('_custom_')
            if custom_board is not None:
                BOARD_THEMES['_custom_'] = custom_board
                game.graphics.board_theme = '_custom_'
            if custom_piece is not None:
                PIECE_THEMES['_custom_'] = custom_piece
                game.graphics.piece_theme = '_custom_'
            if custom_defs is not None:
                game.board.pieces_defs = custom_defs
            if custom_layout is not None:
                game.board.from_dict(custom_layout)
                game.graphics.set_board_size(game.board.board_size)
            game.graphics.load_piece_icons(game.board.pieces_defs)
            game.main()
            # Clean up temporary custom entry
            if custom_board is not None:
                if _orig_board is not None:
                    BOARD_THEMES['_custom_'] = _orig_board
                else:
                    BOARD_THEMES.pop('_custom_', None)
            if custom_piece is not None:
                if _orig_piece is not None:
                    PIECE_THEMES['_custom_'] = _orig_piece
                else:
                    PIECE_THEMES.pop('_custom_', None)


if __name__ == "__main__":
    main()
