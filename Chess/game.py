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

        self.frame_size = 24     # pixel border around board for coordinate labels

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
            'stroke':  '#9880C8',  # soft lavender outline
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
            for color_name, colours in self.ICON_COLOURS.items():
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

        font  = pygame.font.Font('freesansbold.ttf', 18)
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
            # Text with drop shadow
            shadow_s = font.render(label, True, (0, 0, 0))
            text_s   = font.render(label, True, tc)
            self.screen.blit(shadow_s, shadow_s.get_rect(center=(rect.centerx + 1, rect.centery + 1)))
            self.screen.blit(text_s,   text_s.get_rect(center=rect.center))

    def draw_board_frame(self):
        """Draw the dark surround + teal border + coordinate labels (a-h / 1-n)."""
        f  = self.frame_size
        sq = self.square_size
        n  = self.board_size
        board_px = sq * n
        # Dark background behind the frame area
        pygame.draw.rect(self.screen, (8, 8, 18), (0, 0, self.window_size, self.window_size))
        # Teal outer border + dark inner border around the board
        pygame.draw.rect(self.screen, Colours.HIGH,   (f - 4, f - 4, board_px + 8, board_px + 8), 2)
        pygame.draw.rect(self.screen, (30, 25, 55), (f - 2, f - 2, board_px + 4, board_px + 4), 2)
        # File labels (a–z) top and bottom
        lbl_font = pygame.font.SysFont(None, max(f - 4, 12))
        files = 'abcdefghijklmnopqrstuvwxyz'[:n]
        for i, ch in enumerate(files):
            cx = f + i * sq + sq // 2
            lbl = lbl_font.render(ch, True, Colours.GOLD)
            self.screen.blit(lbl, lbl.get_rect(centerx=cx, centery=f // 2))
            self.screen.blit(lbl, lbl.get_rect(centerx=cx, centery=f + board_px + f // 2))
        # Rank labels (1–n) left and right
        for i in range(n):
            cy = f + i * sq + sq // 2
            lbl = lbl_font.render(str(n - i), True, Colours.GOLD)
            self.screen.blit(lbl, lbl.get_rect(centerx=f // 2, centery=cy))
            self.screen.blit(lbl, lbl.get_rect(centerx=f + board_px + f // 2, centery=cy))

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
        """
        sq = self.square_size
        bevel = max(2, sq // 16)
        LIGHT_HI = (240, 210, 150)
        LIGHT_LO = (168, 132,  72)
        DARK_HI  = (128,  78,  42)
        DARK_LO  = ( 52,  22,   4)
        HOLE_BG  = ( 35,  35,  55)
        HOLE_SHD = ( 20,  20,  35)
        HOLE_HI  = ( 55,  55,  80)

        for x in xrange(self.board_size):
            for y in xrange(self.board_size):
                sq_obj = board.matrix[int(x)][int(y)]
                rx, ry = x * sq + self.frame_size, y * sq + self.frame_size
                if sq_obj.is_hole:
                    pygame.draw.rect(self.screen, HOLE_BG,  (rx, ry, sq, sq))
                    # Sunken bevel: dark top/left, bright bottom/right
                    pygame.draw.rect(self.screen, HOLE_SHD, (rx, ry, sq, bevel))
                    pygame.draw.rect(self.screen, HOLE_SHD, (rx, ry, bevel, sq))
                    pygame.draw.rect(self.screen, HOLE_HI,  (rx, ry + sq - bevel, sq, bevel))
                    pygame.draw.rect(self.screen, HOLE_HI,  (rx + sq - bevel, ry, bevel, sq))
                    continue
                pygame.draw.rect(self.screen, sq_obj.color, (rx, ry, sq, sq))
                is_light = sq_obj.color == Colours.CREAM
                hi = LIGHT_HI if is_light else DARK_HI
                lo = LIGHT_LO if is_light else DARK_LO
                # Raised bevel: bright top/left, dark bottom/right
                pygame.draw.rect(self.screen, hi, (rx, ry, sq, bevel))
                pygame.draw.rect(self.screen, hi, (rx, ry, bevel, sq))
                pygame.draw.rect(self.screen, lo, (rx, ry + sq - bevel, sq, bevel))
                pygame.draw.rect(self.screen, lo, (rx + sq - bevel, ry, bevel, sq))

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
        font = pygame.font.Font('freesansbold.ttf', 44)
        text = font.render(message, True, Colours.HIGH)
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
        font = pygame.font.Font('freesansbold.ttf', 36)
        text = font.render(message, True, (8, 8, 18))
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

    def _draw(self, defs, selected, piece_names, left_w, right_x, right_w,
              btn_y, btn_h, mouse, scroll_y, status_msg):
        self.screen.fill(self.BG)

        # Title
        title = self.title_font.render('Piece Editor', True, self.TITLE_COLOR)
        self.screen.blit(title, (self.PADDING, self.PADDING - 4))

        hint = self.tiny_font.render('Esc or ← Back = return to main menu', True, self.DIM_TEXT)
        self.screen.blit(hint, (self.w - hint.get_width() - self.PADDING, self.PADDING))

        # Left panel background
        pygame.draw.rect(self.screen, self.PANEL_BG,
                         (0, 50, left_w, btn_y - 50), border_radius=4)

        for name, rect in zip(piece_names, self._piece_rects(piece_names, left_w)):
            is_sel = (name == selected)
            bg = self.SEL_BG if is_sel else (self.BTN_HOV if rect.collidepoint(*mouse) else self.BTN_BG)
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            tc = self.SEL_TEXT if is_sel else self.TEXT
            label = self.label_font.render(name, True, tc)
            self.screen.blit(label, label.get_rect(centery=rect.centery, left=rect.left + 8))

        # Right panel
        pygame.draw.rect(self.screen, self.PANEL_BG,
                         (right_x - self.PADDING, 50, right_w + self.PADDING, btn_y - 50),
                         border_radius=4)

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
                rm_bg   = (180, 65, 65) if rm_hov else (110, 45, 45)
                pygame.draw.rect(self.screen, rm_bg, rm_rect, border_radius=3)
                rm_lbl = self.tiny_font.render('×', True, (240, 200, 200))
                self.screen.blit(rm_lbl, rm_lbl.get_rect(center=rm_rect.center))

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
                    bg = self.ON_COLOR if is_active else self.OFF_COLOR
                    if is_hov:
                        bg = tuple(min(c + 40, 255) for c in bg)
                    pygame.draw.rect(self.screen, bg, rect, border_radius=2)
                    if is_hov:
                        pygame.draw.rect(self.screen, (220, 225, 235),
                                         rect, width=1, border_radius=2)

                # ── Flag toggles (below the grid) ────────────────────────
                toggle_rects = self._rule_toggle_rects(rule, y, right_x, right_w)
                for flag, rect in toggle_rects.items():
                    val    = rule.get(flag, False)
                    is_hov = rect.collidepoint(*mouse)
                    if is_hov:
                        hovered_flag = flag
                    bg = self.ON_COLOR if val else self.OFF_COLOR
                    if is_hov:
                        bg = tuple(min(c + 30, 255) for c in bg)
                    pygame.draw.rect(self.screen, bg, rect, border_radius=4)
                    if is_hov:
                        pygame.draw.rect(self.screen, (220, 225, 235),
                                         rect, width=1, border_radius=4)
                    ft = self.tiny_font.render(flag, True,
                                              (10, 10, 10) if val else (160, 165, 175))
                    self.screen.blit(ft, ft.get_rect(center=rect.center))

                y += self.RULE_H

            # ── Add Rule button ───────────────────────────────────────────
            add_rect = self._add_rule_rect(piece_def, right_x, scroll_y)
            add_hov  = add_rect.collidepoint(*mouse)
            add_bg   = (60, 105, 140) if add_hov else (45, 78, 105)
            pygame.draw.rect(self.screen, add_bg, add_rect, border_radius=4)
            add_lbl = self.small_font.render('+ Add Rule', True, self.TEXT)
            self.screen.blit(add_lbl, add_lbl.get_rect(center=add_rect.center))

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
            pygame.draw.rect(self.screen, (40, 45, 62), tip_bg, border_radius=4)
            pygame.draw.rect(self.screen, (90, 100, 130), tip_bg, width=1, border_radius=4)
            self.screen.blit(tip_surf, (tx + 6, ty + 4))

        # Buttons
        btn_colors = {
            '← Back': (70, 55, 70),
            'Clone': self.BTN_BG,
            'Reset': self.BTN_RESET,
            'Save':  self.BTN_SAVE,
            'Play':  self.BTN_PLAY,
        }
        for label, rect in self._button_rects(btn_y, btn_h).items():
            hov = rect.collidepoint(*mouse)
            base = btn_colors[label]
            bg = tuple(min(c + 25, 255) for c in base) if hov else base
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            txt = self.label_font.render(label, True, self.TEXT)
            self.screen.blit(txt, txt.get_rect(center=rect.center))

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

    def __init__(self):
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

        # Piece icon rendering (for palette + board preview)
        pieces_defs = AllPieces().pieces_defs
        sq = self._board_sq_size(8)  # icons always cached at standard 8×8 size
        self.piece_icons = {}
        icon_colours = {
            'white': {'fill': '#EAD9B0', 'fill_hi': '#F8EFD0', 'fill_lo': '#B89660',
                      'stroke': '#2A1808', 'accent': '#D4A020'},
            'black': {'fill': '#1C1630', 'fill_hi': '#342C50', 'fill_lo': '#0C0818',
                      'stroke': '#9880C8', 'accent': '#6040A8'},
        }
        for piece_type, defn in pieces_defs.items():
            path = defn.get('icon')
            if not path:
                continue
            try:
                template = open(path).read()
            except (FileNotFoundError, OSError):
                continue
            for color_name, colours in icon_colours.items():
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
        Show the editor.  Returns (layout_dict | None, saved_path | None).
        layout_dict is the board matrix serialised like Board.to_dict(),
        or None if the default layout should be used.
        saved_path is set if the user hit Save.
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
            _, oy = self._board_origin()
            btn_h  = 40
            btn_y  = self._btn_y(board_size)

            for event in pygame.event.get():
                if event.type == locals.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == locals.KEYDOWN and event.key == locals.K_ESCAPE:
                    return layout, saved_path

                if event.type == locals.MOUSEBUTTONDOWN:
                    mx, my = event.pos

                    # Board click: place/remove piece or toggle hole
                    sq_coord = self._board_sq_from_pixel(mx, my, board_size)
                    if sq_coord is not None:
                        bx, by = sq_coord
                        cell = layout['matrix'][bx][by]
                        if event.button == 3:
                            # Right-click: always clear (removes pieces and holes)
                            layout['matrix'][bx][by] = None
                        elif event.button == 1:
                            if selected == 'hole':
                                # Toggle hole: punch in or restore to empty
                                layout['matrix'][bx][by] = None if cell == 'hole' else 'hole'
                            else:
                                color_str, piece_type = selected
                                if (isinstance(cell, dict)
                                        and cell['piece_type'] == piece_type
                                        and cell['color'] == color_str):
                                    # Same piece clicked again → remove
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

                    # Palette click: change selection
                    for color_str, piece_type, rect in self._palette_rects(board_size):
                        if rect.collidepoint(mx, my):
                            selected = 'hole' if color_str == 'hole' else (color_str, piece_type)

                    # Preset button clicks
                    for preset_name, rect in self._preset_rects(btn_y, btn_h, board_size).items():
                        if rect.collidepoint(mx, my):
                            layout = self._make_preset(preset_name)
                            status_msg = f'Loaded preset: {preset_name}'
                            status_until = pygame.time.get_ticks() + 2500

                    # Button clicks
                    for label, rect in self._button_rects(btn_y, btn_h, board_size).items():
                        if rect.collidepoint(mx, my):
                            if label == '← Back':
                                return layout, saved_path
                            elif label == 'Reset':
                                layout = self._default_layout()
                                saved_path = None
                                status_msg = 'Reset to default starting position'
                                status_until = pygame.time.get_ticks() + 2500
                            elif label == 'Save':
                                self._save(layout)
                                saved_path = _CUSTOM_LAYOUT_PATH
                                status_msg = 'Saved to defs/custom_layout.json'
                                status_until = pygame.time.get_ticks() + 2500
                            elif label == 'Play':
                                return layout, saved_path

            self._draw(layout, selected, mouse, btn_y, btn_h,
                       status_msg if pygame.time.get_ticks() < status_until else '')
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

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw(self, layout, selected, mouse, btn_y, btn_h, status_msg):
        board_size = layout.get('board_size', 8)
        self.screen.fill(self.BG)

        # Title
        title = self.title_font.render('Board Layout Editor', True, self.TITLE_COLOR)
        self.screen.blit(title, (self.PADDING, 8))
        hint = self.tiny_font.render('Left-click: place  •  Right-click: clear  •  Esc: back',
                                     True, self.DIM_TEXT)
        self.screen.blit(hint, (self._panel_x(board_size), 8))

        sq = self._board_sq_size(board_size)
        ox, oy = self._board_origin()

        # Board squares with pixel art bevel
        _bevel = max(2, sq // 16)
        _LIGHT_HI = (240, 210, 150)
        _LIGHT_LO = (168, 132,  72)
        _DARK_HI  = (128,  78,  42)
        _DARK_LO  = ( 52,  22,   4)
        _HOLE_BG  = ( 35,  35,  55)
        _HOLE_SHD = ( 20,  20,  35)
        _HOLE_HI  = ( 55,  55,  80)
        for x in range(board_size):
            for y in range(board_size):
                cell = layout['matrix'][x][y]
                rect = self._board_sq_rect(x, y, board_size)
                sq_coord = self._board_sq_from_pixel(*mouse, board_size)
                hovering = sq_coord == (x, y)
                if cell == 'hole':
                    pygame.draw.rect(self.screen, _HOLE_BG, rect)
                    pygame.draw.rect(self.screen, _HOLE_SHD, (rect.x, rect.y, rect.w, _bevel))
                    pygame.draw.rect(self.screen, _HOLE_SHD, (rect.x, rect.y, _bevel, rect.h))
                    pygame.draw.rect(self.screen, _HOLE_HI,  (rect.x, rect.y + rect.h - _bevel, rect.w, _bevel))
                    pygame.draw.rect(self.screen, _HOLE_HI,  (rect.x + rect.w - _bevel, rect.y, _bevel, rect.h))
                else:
                    base_color = self.CREAM if (x + y) % 2 == 0 else self.BROWN
                    if hovering:
                        base_color = tuple(min(c + 30, 255) for c in base_color)
                    pygame.draw.rect(self.screen, base_color, rect)
                    is_light = (x + y) % 2 == 0
                    hi = _LIGHT_HI if is_light else _DARK_HI
                    lo = _LIGHT_LO if is_light else _DARK_LO
                    pygame.draw.rect(self.screen, hi, (rect.x, rect.y, rect.w, _bevel))
                    pygame.draw.rect(self.screen, hi, (rect.x, rect.y, _bevel, rect.h))
                    pygame.draw.rect(self.screen, lo, (rect.x, rect.y + rect.h - _bevel, rect.w, _bevel))
                    pygame.draw.rect(self.screen, lo, (rect.x + rect.w - _bevel, rect.y, _bevel, rect.h))

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

        # Board border (pixel art teal accent)
        pygame.draw.rect(self.screen, (60, 50, 100),
                         pygame.Rect(ox, oy, sq * board_size, sq * board_size), 2)

        # Right panel — palette
        px = self._panel_x(board_size)
        pw = self.w - px - self.PADDING
        pygame.draw.rect(self.screen, self.PANEL_BG,
                         pygame.Rect(px - self.PADDING // 2, oy,
                                     pw + self.PADDING, btn_y - oy - self.PADDING),
                         border_radius=4)
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
            bg = self.BTN_HOV if hov else (self.BTN_BG if enabled else (45, 48, 58))
            tc = self.TEXT if enabled else (70, 75, 85)
            pygame.draw.rect(self.screen, bg, rect, border_radius=4)
            t = self.label_font.render(label, True, tc)
            self.screen.blit(t, t.get_rect(center=rect.center))

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
            pygame.draw.rect(self.screen, bg, rect, border_radius=5)

            icon_x = rect.left + 4
            if is_hole_entry:
                # Draw a small grey swatch for the hole tool
                swatch = pygame.Rect(icon_x, rect.centery - 10, 24, 20)
                pygame.draw.rect(self.screen, Colours.HOLE, swatch, border_radius=2)
                pygame.draw.rect(self.screen, (45, 45, 55),
                                 swatch.inflate(-6, -6), border_radius=1)
                lbl = self.small_font.render('Hole  (toggle)', True, tc)
            else:
                # Mini piece icon in the palette row
                icon = self.piece_icons.get((piece_type, color_str))
                if icon:
                    small = pygame.transform.smoothscale(icon, (24, 24))
                    self.screen.blit(small, small.get_rect(centery=rect.centery, left=icon_x))
                lbl_text = f"{color_str}  {piece_type}"
                lbl = self.small_font.render(lbl_text, True, tc)
            self.screen.blit(lbl, lbl.get_rect(centery=rect.centery, left=icon_x + 28))

        # Preset buttons (row above the action buttons)
        preset_rects = self._preset_rects(btn_y, btn_h, board_size)
        preset_lbl = self.tiny_font.render('Presets:', True, self.DIM_TEXT)
        if preset_rects:
            first_rect = next(iter(preset_rects.values()))
            self.screen.blit(preset_lbl, (ox, first_rect.y - 18))
        for name, rect in preset_rects.items():
            hov = rect.collidepoint(*mouse)
            bg = self.BTN_HOV if hov else self.BTN_BG
            pygame.draw.rect(self.screen, bg, rect, border_radius=0)
            txt = self.tiny_font.render(name, True, self.TEXT)
            self.screen.blit(txt, txt.get_rect(center=rect.center))

        # Bottom action buttons
        btn_colors = {
            '← Back': self.BTN_BG,
            'Reset':   self.BTN_RST,
            'Save':    self.BTN_SAVE,
            'Play':    self.BTN_PLAY,
        }
        for label, rect in self._button_rects(btn_y, btn_h, board_size).items():
            hov = rect.collidepoint(*mouse)
            base = btn_colors[label]
            bg = tuple(min(c + 25, 255) for c in base) if hov else base
            pygame.draw.rect(self.screen, bg, rect, border_radius=0)
            txt = self.label_font.render(label, True, self.TEXT)
            self.screen.blit(txt, txt.get_rect(center=rect.center))

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
    mega_font  = pygame.font.Font('freesansbold.ttf', 72)
    sub_font   = pygame.font.Font('freesansbold.ttf', 16)
    btn_font   = pygame.font.Font('freesansbold.ttf', 24)
    clock = pygame.time.Clock()
    bw, bh = 210, 56
    gap = 16
    total_w = bw * 3 + gap * 2
    x0 = w // 2 - total_w // 2
    btns = {
        'Play':         pygame.Rect(x0,            h * 2 // 3, bw, bh),
        'Edit Pieces':  pygame.Rect(x0 + bw + gap, h * 2 // 3, bw, bh),
        'Edit Layout':  pygame.Rect(x0 + (bw + gap) * 2, h * 2 // 3, bw, bh),
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

    # Pre-build scanline overlay (CRT retro effect)
    scanlines = pygame.Surface((w, h), pygame.SRCALPHA)
    for sy in range(0, h, 2):
        pygame.draw.line(scanlines, (0, 0, 0, 80), (0, sy), (w, sy))

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
        screen.blit(scanlines, (0, 0))

        # Stacked two-colour pixel art title: MEGA (gold) + CHESS (teal)
        mega_surf  = mega_font.render('MEGA',  True, Colours.GOLD)
        chess_surf = mega_font.render('CHESS', True, Colours.HIGH)
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
        # Render titles centred inside box
        cx = bx + bw2 // 2
        screen.blit(mega_surf,  mega_surf.get_rect(centerx=cx,  top=frame_y + pad))
        screen.blit(chess_surf, chess_surf.get_rect(centerx=cx, top=frame_y + pad + mega_surf.get_height() + 4))

        # Blinking cursor prompt
        blink = (pygame.time.get_ticks() // 500) % 2
        hint_str = 'PRESS ENTER TO PLAY' + (' _' if blink else '  ')
        hint_s = sub_font.render(hint_str, True, (140, 130, 170))
        screen.blit(hint_s, hint_s.get_rect(centerx=w // 2, top=frame_y + title_h + pad * 2 + 24))

        sub = sub_font.render('E = edit pieces   •   L = edit layout', True, (100, 90, 130))
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
            shadow_s = btn_font.render(label, True, (0, 0, 0))
            txt_s    = btn_font.render(label, True, (220, 225, 235))
            screen.blit(shadow_s, shadow_s.get_rect(center=(rect.centerx + 1, rect.centery + 1)))
            screen.blit(txt_s,    txt_s.get_rect(center=rect.center))

        pygame.display.update()
        clock.tick(60)


def main():
    pygame.init()
    info = pygame.display.Info()
    w = h = min(info.current_w, info.current_h)
    screen = pygame.display.set_mode((w, h))

    custom_defs   = None
    # Load previously saved custom layout, if any
    custom_layout = None
    if os.path.exists(_CUSTOM_LAYOUT_PATH):
        try:
            with open(_CUSTOM_LAYOUT_PATH) as _f:
                custom_layout = json.load(_f)
        except (OSError, json.JSONDecodeError):
            pass
    while True:
        choice = _start_menu(screen, w, h)
        if choice == 'edit_pieces':
            defs, saved_path = PieceEditor().run()
            if saved_path:
                custom_defs = defs
        elif choice == 'edit_layout':
            layout, saved_path = BoardLayoutEditor().run()
            if saved_path:
                custom_layout = layout
        else:
            game = Game()
            if custom_defs is not None:
                game.board.pieces_defs = custom_defs
            if custom_layout is not None:
                game.board.from_dict(custom_layout)
                game.graphics.set_board_size(game.board.board_size)
            game.main()


if __name__ == "__main__":
    main()
