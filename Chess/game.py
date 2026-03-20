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


def _load_dotenv():
    """Load key=value pairs from a .env file next to game.py into os.environ."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            os.environ.setdefault(key.strip(), value.strip())

_load_dotenv()


def _on_android():
    """Return True when running on Android (Pydroid3, Buildozer, .env override, or any python-for-android env)."""
    return (
        os.environ.get('ANDROID', '').lower() in ('1', 'true')
        or 'ANDROID_ARGUMENT' in os.environ
        or os.path.exists('/system/build.prop')
    )


def _resize_event_size(event):
    """Return (w, h) from a pygame resize event, or None if the event is not a resize.

    Handles both pygame 1.x VIDEORESIZE (.w/.h) and pygame 2.x WINDOWRESIZED (.x/.y)
    so orientation-change code works across both versions.
    """
    if event.type == pygame.VIDEORESIZE:
        return event.w, event.h
    _wre = getattr(pygame, 'WINDOWRESIZED', None)
    if _wre is not None and event.type == _wre:
        return event.x, event.y
    return None


def _resize_needs_set_mode(event):
    """Return True only for VIDEORESIZE (pygame 1.x).

    On pygame 2.x, WINDOWRESIZED fires after the OS has already resized the
    underlying surface — calling set_mode() again is redundant and causes a
    brief blank / flicker frame.  VIDEORESIZE (pygame 1.x) does require a
    set_mode() call to obtain a correctly-sized surface.
    """
    return event.type == pygame.VIDEORESIZE


def _pixel_text(text, size, color, bold=False):
    """Return a pygame Surface with genuine pixel-art text.
    Renders at half size with no antialiasing, then scales up 2x with
    pygame.transform.scale (nearest-neighbour) for a chunky retro look."""
    font = pygame.font.Font('freesansbold.ttf' if bold else None, max(size // 2, 6))
    surf = font.render(text, False, color)
    w, h = surf.get_size()
    return pygame.transform.scale(surf, (w * 2, h * 2))


def _draw_icon(surf, name, cx, cy, sz, col):
    """Draw a pixel-art icon centred at (cx, cy) within a bounding box of sz×sz pixels.

    Supported names: play, back, save, load, hints, reset, clone, pieces, layout.
    All shapes are drawn with pygame.draw primitives for a chunky retro look.
    """
    h = sz // 2          # half-size shorthand
    q = max(sz // 4, 2)  # quarter-size

    if name == 'play':
        pts = [(cx - h + 2, cy - h + 3),
               (cx - h + 2, cy + h - 3),
               (cx + h - 2, cy)]
        pygame.draw.polygon(surf, col, pts)

    elif name == 'back':
        pts = [(cx + h - 2, cy - h + 3),
               (cx + h - 2, cy + h - 3),
               (cx - h + 2, cy)]
        pygame.draw.polygon(surf, col, pts)

    elif name == 'save':
        # Outer body
        pygame.draw.rect(surf, col, (cx - h + 1, cy - h + 1, sz - 2, sz - 2))
        # Slide-lock notch (top-right corner cut)
        notch = q
        pygame.draw.polygon(surf, (0, 0, 0),
                            [(cx + h - notch - 1, cy - h + 1),
                             (cx + h - 1,         cy - h + 1),
                             (cx + h - 1,         cy - h + notch + 1)])
        # Label strip at bottom
        pygame.draw.rect(surf, (0, 0, 0),
                         (cx - h + 3, cy + q - 1, sz - 6, h - q))

    elif name == 'load':
        # Folder tab on top-left
        pygame.draw.rect(surf, col,
                         (cx - h + 1, cy - h + 1 + q, sz - 2, sz - 2 - q))
        pygame.draw.rect(surf, col,
                         (cx - h + 1, cy - h + 1, q * 2 + 2, q + 1))

    elif name == 'hints':
        # Eye: outer ellipse
        pygame.draw.ellipse(surf, col,
                            (cx - h + 1, cy - q + 1, sz - 2, q * 2 - 2))
        # Pupil
        r = max(q - 2, 2)
        pygame.draw.circle(surf, (0, 0, 0), (cx, cy), r)
        pygame.draw.circle(surf, col,       (cx, cy), max(r - 2, 1))

    elif name == 'reset':
        # Two arcs forming a circular arrow
        import math
        r = h - 2
        pygame.draw.arc(surf, col,
                        (cx - r, cy - r, r * 2, r * 2),
                        math.radians(30), math.radians(330), max(sz // 6, 2))
        # Arrowhead at 30°
        tip_x = int(cx + r * math.cos(math.radians(30)))
        tip_y = int(cy - r * math.sin(math.radians(30)))
        pts = [(tip_x,     tip_y),
               (tip_x - q, tip_y - q),
               (tip_x + q // 2, tip_y + q // 2)]
        pygame.draw.polygon(surf, col, pts)

    elif name == 'clone':
        # Two overlapping open rects (offset by q)
        pygame.draw.rect(surf, col,
                         (cx - h + 1, cy - h + 1, sz - 2 - q, sz - 2 - q), 2)
        pygame.draw.rect(surf, col,
                         (cx - h + 1 + q, cy - h + 1 + q, sz - 2 - q, sz - 2 - q), 2)

    elif name == 'pieces':
        # Pawn: circle head + stem + wide base
        pygame.draw.circle(surf, col, (cx, cy - q), q)
        pygame.draw.rect(surf, col, (cx - 1, cy, 3, q))
        pygame.draw.rect(surf, col, (cx - q - 1, cy + q, q * 2 + 3, q))

    elif name == 'layout':
        # 2×2 grid of filled squares
        qs = q - 1
        for dy in (cy - h + 2, cy + 2):
            for dx in (cx - h + 2, cx + 2):
                pygame.draw.rect(surf, col, (dx, dy, qs, qs))


def _ui_scale(w, h):
    """Return a UI scale multiplier based on screen size.

    On Android, fonts/controls were designed for ~480px, so larger screens
    need proportional scaling (e.g. 1080px → 2.25×).  On desktop the
    system DPI keeps everything readable without scaling.
    """
    if not _on_android():
        return 1.0
    return min(min(w, h) / 480.0, 3.0)


def _fz(base, scale):
    """Scale base font size by scale, keeping at least base."""
    return max(base, int(round(base * scale)))


_FONT_CACHE = {}

def _fit_font(max_h, bold=True):
    """Return a cached Font whose rendered line height fits within max_h pixels.

    freesansbold linesize ≈ size * 1.22, so size = max_h / 1.22.
    Use this wherever text must fit inside a fixed-height container (e.g. buttons).
    """
    size = max(6, int(max_h / 1.22))
    key = (size, bold)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = pygame.font.Font('freesansbold.ttf' if bold else None, size)
    return _FONT_CACHE[key]


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

            _sz = _resize_event_size(event)
            if _sz:
                if _resize_needs_set_mode(event):
                    self.graphics._reinit_layout(*_sz)
                else:
                    self.graphics.screen = pygame.display.get_surface()
                    self.graphics._recompute_dims(*_sz)
                self.graphics.load_piece_icons(self.board.pieces_defs)
                continue

            if event.type == locals.KEYDOWN:
                if event.key == locals.K_ESCAPE:
                    self._quit_to_menu = True
                elif event.key == locals.K_s:
                    self.save()
                elif event.key == locals.K_l:
                    self.load()
                elif event.key == locals.K_h:
                    self._toggle_hints()

            if event.type == pygame.FINGERDOWN:
                tw, th = self.graphics.screen.get_size()
                self.pixel_mouse_pos = (int(event.x * tw), int(event.y * th))
                self.mouse_pos = self.graphics.board_coords(self.pixel_mouse_pos)

            self.click = event.type in (locals.MOUSEBUTTONDOWN, pygame.FINGERDOWN)

            if self.click:
                px, py = self.pixel_mouse_pos

                # Button bar clicks (below the board)
                if py >= self.graphics._bar_y():
                    if self.graphics.save_btn_rect.collidepoint(px, py):
                        self.save()
                    elif self.graphics.load_btn_rect.collidepoint(px, py):
                        self.load()
                    elif self.graphics.hints_btn_rect.collidepoint(px, py):
                        self._toggle_hints()
                    elif self.graphics.back_btn_rect.collidepoint(px, py):
                        self._quit_to_menu = True
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
        self._quit_to_menu = False
        self.setup()

        while not self._quit_to_menu:
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

        self.board_size = 8
        self.message = False
        self.timed_message_surface = None
        self.timed_message_rect = None
        self.timed_message_until = 0  # pygame.time.get_ticks() expiry
        self.piece_icons = {}  # (piece_type, 'white'|'black') -> scaled Surface
        self.highlights = False
        self.show_hints = True   # toggle: show piece selection + legal-move highlighting
        self.board_theme = 'Classic'
        self.piece_theme = 'Classic'

        pygame.init()
        info = pygame.display.Info()
        self._reinit_layout(info.current_w, info.current_h)

    def _recompute_dims(self, new_w, new_h):
        """Recompute all dimension variables from a new screen size, WITHOUT calling set_mode.

        Use this for pygame 2.x WINDOWRESIZED events where the OS has already
        resized the surface.  Call _reinit_layout instead when a set_mode() is
        also required (startup, or pygame 1.x VIDEORESIZE).
        """
        _android = _on_android()
        self._s = _ui_scale(new_w, new_h)
        self.button_bar_height = _fz(48, self._s)
        self.window_size = max(0, min(new_w, new_h - self.button_bar_height))
        if _android:
            self.screen_w = new_w
            self.screen_h = new_h
        else:
            self.screen_w = self.window_size
            self.screen_h = self.window_size + self.button_bar_height
        self.square_size = self.window_size // self.board_size
        self.piece_size = self.square_size // 2
        self.piece_font = pygame.font.SysFont(None, max(self.piece_size, 1))
        self.frame_size = min(48, _fz(28, self._s))
        self.board_y_offset = max(0, (self.screen_h - self.button_bar_height - self.window_size) // 2)

    def _reinit_layout(self, new_w, new_h):
        """Resize the pygame display surface then recompute all dimensions.

        Called at startup and for pygame 1.x VIDEORESIZE events.
        Board state (board_size, piece_icons, etc.) is preserved across calls.
        """
        _android = _on_android()
        _flags = pygame.FULLSCREEN if _android else 0
        self._recompute_dims(new_w, new_h)
        self.screen = pygame.display.set_mode((self.screen_w, self.screen_h), _flags)

    @classmethod
    def for_editor(cls, w, h, header_h, bar_h, board_size=8):
        """Create a Graphics instance attached to the current display surface (no set_mode).

        Positions the board immediately below the header.  Used by BoardLayoutEditor
        so the board is rendered by the same code path as the main game.
        """
        g = object.__new__(cls)
        g.fps = 60
        g.clock = pygame.time.Clock()
        g.board_size = board_size
        g.message = False
        g.timed_message_surface = None
        g.timed_message_rect = None
        g.timed_message_until = 0
        g.piece_icons = {}
        g.highlights = False
        g.show_hints = False
        g.board_theme = 'Classic'
        g.piece_theme = 'Classic'
        g.screen = pygame.display.get_surface()
        g.screen_w = w
        g.screen_h = h
        g._s = _ui_scale(w, h)
        g.button_bar_height = bar_h
        _portrait = h > w * 1.1
        available_h = h - header_h - bar_h
        if _portrait:
            # Portrait: board uses top half of content area, panel goes below
            board_avail_w = w
            board_avail_h = available_h // 2
        else:
            # Landscape: board uses left 60%, panel to the right
            board_avail_w = w * 3 // 5
            board_avail_h = available_h
        g.window_size = min(board_avail_w, board_avail_h)
        g.frame_size = min(48, _fz(28, g._s))
        g.square_size = max(1, (g.window_size - g.frame_size * 2) // board_size)
        g.piece_size = g.square_size // 2
        g.piece_font = pygame.font.SysFont(None, max(g.piece_size, 1))
        g.board_y_offset = header_h
        return g

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
        """Returns (button_width, button_height, padding) for the 4-button bar."""
        pad = 8
        bw = (self.window_size - pad * 5) // 4
        bh = self.button_bar_height - pad * 2
        return bw, bh, pad

    def _bar_y(self):
        """Y coordinate where the button bar begins — at the bottom of the full screen."""
        return self.screen_h - self.button_bar_height

    @property
    def save_btn_rect(self):
        bw, bh, pad = self._btn_layout()
        return pygame.Rect(pad, self._bar_y() + pad, bw, bh)

    @property
    def load_btn_rect(self):
        bw, bh, pad = self._btn_layout()
        return pygame.Rect(pad * 2 + bw, self._bar_y() + pad, bw, bh)

    @property
    def hints_btn_rect(self):
        bw, bh, pad = self._btn_layout()
        return pygame.Rect(pad * 3 + bw * 2, self._bar_y() + pad, bw, bh)

    @property
    def back_btn_rect(self):
        bw, bh, pad = self._btn_layout()
        return pygame.Rect(pad * 4 + bw * 3, self._bar_y() + pad, bw, bh)

    def draw_button_bar(self, mouse_px, save_exists, show_hints=True):
        """Draw the Save / Load / Hints button strip below the board — pixel art style."""
        bar_y = self._bar_y()
        bar_rect = pygame.Rect(0, bar_y, self.screen_w, self.button_bar_height)
        pygame.draw.rect(self.screen, (8, 8, 18), bar_rect)
        # Pixel art divider: bright top line + dark second line
        pygame.draw.line(self.screen, (60, 50, 100),
                         (0, bar_y), (self.screen_w, bar_y), 2)
        pygame.draw.line(self.screen, (20, 15, 40),
                         (0, bar_y + 2), (self.screen_w, bar_y + 2), 1)

        BEVEL = 2
        ICN = max(self.button_bar_height - 20, 12)   # icon size

        for icon_name, label, rect, enabled, toggled in [
            ('save',  'Save',  self.save_btn_rect,  True,        True),
            ('load',  'Load',  self.load_btn_rect,  save_exists, True),
            ('hints', 'Hints', self.hints_btn_rect, True,        show_hints),
            ('back',  'Back',  self.back_btn_rect,  True,        True),
        ]:
            hovered = rect.collidepoint(*mouse_px) and enabled
            if not enabled:
                bg, tc  = (30, 25, 55), (70, 60, 90)
                bhi, blo = (45, 38, 75), (12, 8, 25)
            elif icon_name == 'back':
                # Back button: warm amber to distinguish as "exit" action
                bg  = (155, 80, 30) if hovered else (110, 55, 20)
                tc  = (255, 220, 170)
                bhi, blo = (200, 120, 60), (60, 25, 5)
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
            # Icon + label centred in button — text sized to button height (not screen scale)
            _btn_text_sz = max(10, self.button_bar_height * 2 // 5)
            text_s   = _pixel_text(label, _btn_text_sz, tc,      bold=True)
            shadow_s = _pixel_text(label, _btn_text_sz, (0,0,0), bold=True)
            total_w = ICN + 4 + text_s.get_width()
            ix = rect.centerx - total_w // 2 + ICN // 2
            tx = rect.centerx - total_w // 2 + ICN + 4
            _draw_icon(self.screen, icon_name, ix, rect.centery, ICN, tc)
            self.screen.blit(shadow_s, shadow_s.get_rect(midleft=(tx + 1, rect.centery + 1)))
            self.screen.blit(text_s,   text_s.get_rect(midleft=(tx, rect.centery)))

    def draw_board_frame(self):
        """Draw dark surround + pixel-art teal border + coordinate labels (a-h / 1-n).
        Labels use freesansbold with drop shadow for a retro pixel art look."""
        f  = self.frame_size
        sq = self.square_size
        n  = self.board_size
        yo = self.board_y_offset
        board_px = sq * n
        # Dark background behind the frame area (fill full screen so portrait gap is covered)
        pygame.draw.rect(self.screen, (8, 8, 18), (0, 0, self.screen_w, self.screen_h))

        # Pixel art double-border: bright teal outer (3px) + dark inner (2px)
        pygame.draw.rect(self.screen, Colours.HIGH, (f - 5, yo + f - 5, board_px + 10, board_px + 10), 3)
        pygame.draw.rect(self.screen, (30, 25, 55), (f - 2, yo + f - 2, board_px +  4, board_px +  4), 2)

        # Corner pixel accent squares in each corner of the frame
        for cx_off, cy_off in [(0, 0), (board_px + 4, 0),
                                (0, board_px + 4), (board_px + 4, board_px + 4)]:
            pygame.draw.rect(self.screen, Colours.HIGH,
                             (f - 5 + cx_off, yo + f - 5 + cy_off, 6, 6))

        # Coordinate labels — pixel art style (blocky, no antialiasing)
        fsize = max(f - 10, 9)
        files = 'abcdefghijklmnopqrstuvwxyz'[:n]
        for i, ch in enumerate(files):
            cx = f + i * sq + sq // 2
            shadow = _pixel_text(ch, fsize, (0, 0, 0), bold=True)
            lbl    = _pixel_text(ch, fsize, Colours.GOLD, bold=True)
            for centery in (yo + f // 2, yo + f + board_px + f // 2):
                r = lbl.get_rect(centerx=cx, centery=centery)
                self.screen.blit(shadow, r.move(1, 1))
                self.screen.blit(lbl, r)
        for i in range(n):
            cy = yo + f + i * sq + sq // 2
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
                rx, ry = x * sq + self.frame_size, y * sq + self.frame_size + self.board_y_offset
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
        yo = self.board_y_offset
        board_px = sq * self.board_size
        for i in range(1, self.board_size):
            pygame.draw.line(self.screen, sep,
                             (f + i * sq, yo + f), (f + i * sq, yo + f + board_px))
            pygame.draw.line(self.screen, sep,
                             (f, yo + f + i * sq), (f + board_px, yo + f + i * sq))

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
            board_coords[1] * self.square_size + self.frame_size + self.piece_size + self.board_y_offset,
        )

    def board_coords(self, pixel_coords_tuple):
        """
        Does the reverse of pixel_coords(). Takes in a tuple of of pixel coordinates and returns what square they are in.
        """
        pixel_x, pixel_y = pixel_coords_tuple
        N = self.board_size - 1
        x = min(max((pixel_x - self.frame_size) // self.square_size, 0), N)
        y = min(max((pixel_y - self.frame_size - self.board_y_offset) // self.square_size, 0), N)
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
            cy = square[1] * self.square_size + self.frame_size + self.square_size // 2 + self.board_y_offset
            pygame.draw.circle(self.screen, Colours.HIGH, (cx, cy), dot_r)
            pygame.draw.circle(self.screen, DOT_RING,     (cx, cy), dot_r, 2)

        if origin is not None:
            ox, oy = origin
            pygame.draw.rect(self.screen, Colours.HIGH,
                             (ox * self.square_size + self.frame_size,
                              oy * self.square_size + self.frame_size + self.board_y_offset,
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
        self.text_rect_obj = bg.get_rect(center=(self.window_size // 2, self.board_y_offset + self.window_size // 2))

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
        self.timed_message_rect = bg.get_rect(center=(self.window_size // 2, self.board_y_offset + self.square_size // 2))
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
        yo = self.board_y_offset
        # Pixel art bordered box behind the four squares
        border_x = cols[0] * self.square_size - 4
        border_y = yo + row * self.square_size - 4
        border_w = len(cols) * self.square_size + 8
        border_h = self.square_size + 8
        pygame.draw.rect(self.screen, (8, 8, 18),
                         (border_x, border_y, border_w, border_h), border_radius=0)
        pygame.draw.rect(self.screen, Colours.HIGH,
                         (border_x, border_y, border_w, border_h), 3, border_radius=0)

        for piece_type, col in zip(self.PROMOTION_PIECES, cols):
            sx = col * self.square_size
            sy = yo + row * self.square_size
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
    HEADER_H    = 56   # reserved height for title + keystroke hint row

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
        self._piece_names_cache = []
        self._reinit_display(info.current_w, info.current_h)
        pygame.display.set_caption('megaChess — piece editor')

    def _reinit_display(self, new_w, new_h, set_mode=True):
        """Recompute screen dimensions and fonts after an orientation change.

        set_mode=False skips pygame.display.set_mode() — use this for pygame 2.x
        WINDOWRESIZED events where the OS has already resized the surface.
        """
        _android = _on_android()
        self.w = new_w if _android else min(new_w, new_h)
        self.h = new_h if _android else self.w
        if set_mode:
            _flags = pygame.FULLSCREEN if _android else 0
            self.screen = pygame.display.set_mode((self.w, self.h), _flags)
        else:
            self.screen = pygame.display.get_surface()
        _raw = _ui_scale(self.w, self.h)
        _font_s   = min(_raw, 2.0)
        _layout_s = min(_raw, 1.3)
        self.title_font = pygame.font.Font('freesansbold.ttf', _fz(32, _font_s))
        self.label_font = pygame.font.Font('freesansbold.ttf', _fz(22, _font_s))
        self.small_font = pygame.font.Font('freesansbold.ttf', _fz(16, _font_s))
        self.tiny_font  = pygame.font.Font('freesansbold.ttf', _fz(13, _font_s))
        self.PADDING  = _fz(16, _layout_s)
        self.HEADER_H = _fz(56, _layout_s)

    @property
    def _portrait(self):
        return self.h > self.w * 1.1

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
            self._piece_names_cache = piece_names

            # Layout geometry
            btn_h = 42
            btn_y = self.h - self._btn_area_h(btn_h) - self.PADDING
            if self._portrait:
                left_w  = 0
                right_x = self.PADDING
                right_w = self.w - 2 * self.PADDING
            else:
                left_w  = self.w // 3
                right_x = left_w + self.PADDING
                right_w = self.w - right_x - self.PADDING

            for event in pygame.event.get():
                if event.type == locals.QUIT:
                    pygame.quit()
                    sys.exit()

                _sz = _resize_event_size(event)
                if _sz:
                    self._reinit_display(*_sz, set_mode=_resize_needs_set_mode(event))
                    continue

                if event.type == locals.KEYDOWN and event.key == locals.K_ESCAPE:
                    return defs, saved_path

                if event.type == locals.MOUSEBUTTONDOWN:
                    mx, my = event.pos

                    # Piece selector — left panel (landscape) or top tabs (portrait)
                    item_rects = self._piece_rects(piece_names, left_w)
                    piece_clicked = False
                    for name, rect in zip(piece_names, item_rects):
                        if rect.collidepoint(mx, my):
                            selected = name
                            scroll_y = 0
                            piece_clicked = True
                            break

                    if not piece_clicked and mx >= right_x and my < btn_y:
                        # Right panel — delta grid, rule add/remove, flag toggles
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
                        if self._portrait:
                            tab_rects = self._piece_rects(piece_names, left_w)
                            top_y = (tab_rects[-1].bottom + self.PADDING) if tab_rects else 50
                        else:
                            top_y = 55
                        visible_h = btn_y - top_y
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
        if self._portrait:
            # Horizontal wrapping tabs across full width — start below header
            pad = self.PADDING
            tab_h = 36
            tab_w = max(80, min(160, (self.w - pad) // max(1, len(names))))
            rects = []
            x, y = pad, self.HEADER_H + 4
            for _ in names:
                if x + tab_w + pad > self.w:
                    x = pad
                    y += tab_h + 4
                rects.append(pygame.Rect(x, y, tab_w, tab_h))
                x += tab_w + 4
            return rects
        else:
            # Vertical list — start below header
            top = self.HEADER_H + 4
            rects = []
            for i in range(len(names)):
                rects.append(pygame.Rect(self.PADDING, top + i * 44, left_w - self.PADDING * 2, 38))
            return rects

    def _button_rects(self, btn_y, btn_h):
        labels = ['← Back', 'Clone', 'Reset', 'Save', 'Play']
        total_w = self.w - self.PADDING * 2
        pad = self.PADDING
        per_row = max(1, min(len(labels), (total_w + pad) // (90 + pad)))
        rows = [labels[i:i + per_row] for i in range(0, len(labels), per_row)]
        rects = {}
        for row_idx, row_labels in enumerate(reversed(rows)):
            y = btn_y - row_idx * (btn_h + pad)
            bw = (total_w - pad * (len(row_labels) - 1)) // len(row_labels)
            for col_idx, label in enumerate(row_labels):
                x = self.PADDING + col_idx * (bw + pad)
                rects[label] = pygame.Rect(x, y, bw, btn_h)
        return rects

    def _btn_area_h(self, btn_h):
        labels_count = 5
        total_w = self.w - self.PADDING * 2
        per_row = max(1, min(labels_count, (total_w + self.PADDING) // (90 + self.PADDING)))
        n_rows = (labels_count + per_row - 1) // per_row
        return n_rows * btn_h + (n_rows - 1) * self.PADDING

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
        y = self._rules_start_y(getattr(self, '_piece_names_cache', []), scroll_y) + n * self.RULE_H
        return pygame.Rect(right_x, y, 110, 24)

    def _rules_start_y(self, piece_names, scroll_y=0):
        """Y-coordinate of the first rule block in the right panel."""
        if self._portrait and piece_names:
            rects = self._piece_rects(piece_names, 0)
            return (rects[-1].bottom + self.PADDING + 32) - scroll_y if rects else (50 + 32 - scroll_y)
        return 92 - scroll_y

    def _find_toggle(self, piece_def, mx, my, right_x, right_w, scroll_y):
        """Return (rule_idx, flag) if the click / hover lands on a toggle, else None."""
        y = self._rules_start_y(getattr(self, '_piece_names_cache', []), scroll_y)
        for i, rule in enumerate(piece_def.get('move_rules', [])):
            toggle_rects = self._rule_toggle_rects(rule, y, right_x, right_w)
            for flag, rect in toggle_rects.items():
                if rect.collidepoint(mx, my):
                    return (i, flag)
            y += self.RULE_H
        return None

    def _find_delta_click(self, piece_def, mx, my, right_x, scroll_y):
        """Return (rule_idx, dx, dy) if the click lands on a delta grid cell, else None."""
        y = self._rules_start_y(getattr(self, '_piece_names_cache', []), scroll_y)
        for i, rule in enumerate(piece_def.get('move_rules', [])):
            for (dx, dy), rect in self._delta_grid_rects(y, right_x).items():
                if rect.collidepoint(mx, my):
                    return (i, dx, dy)
            y += self.RULE_H
        return None

    def _find_remove_rule(self, piece_def, mx, my, right_x, right_w, scroll_y):
        """Return rule index if the click lands on a remove-rule button, else None."""
        y = self._rules_start_y(getattr(self, '_piece_names_cache', []), scroll_y)
        for i in range(len(piece_def.get('move_rules', []))):
            if self._remove_rule_rect(y, right_x, right_w).collidepoint(mx, my):
                return i
            y += self.RULE_H
        return None

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_pixel_btn(self, surf, rect, base_color, hovered, text, font, text_color,
                        bevel=2, icon=None):
        """Draw a pixel-art bevelled button (square corners), with optional icon."""
        bg = tuple(min(c + 30, 255) for c in base_color) if hovered else base_color
        hi = tuple(min(c + 55, 255) for c in base_color)
        lo = tuple(max(c - 25,   0) for c in base_color)
        pygame.draw.rect(surf, bg, rect, border_radius=0)
        pygame.draw.line(surf, hi, rect.topleft,    rect.topright,    bevel)
        pygame.draw.line(surf, hi, rect.topleft,    rect.bottomleft,  bevel)
        pygame.draw.line(surf, lo, rect.bottomleft, rect.bottomright, bevel)
        pygame.draw.line(surf, lo, rect.topright,   rect.bottomright, bevel)
        if icon or text:
            icn_sz = rect.height - 10 if icon else 0
            # Use container-aware font so text always fits the button height
            _btn_font = _fit_font(rect.height - 6)
            lbl_surf = _btn_font.render(text, True, text_color) if text else None
            shd_surf = _btn_font.render(text, True, (0, 0, 0))  if text else None
            lbl_w = lbl_surf.get_width() if lbl_surf else 0
            gap = 4 if (icon and text) else 0
            total_w = icn_sz + gap + lbl_w
            ix = rect.centerx - total_w // 2 + icn_sz // 2
            tx = rect.centerx - total_w // 2 + icn_sz + gap
            if icon:
                _draw_icon(surf, icon, ix, rect.centery, icn_sz, text_color)
            if lbl_surf:
                surf.blit(shd_surf, shd_surf.get_rect(midleft=(tx + 1, rect.centery + 1)))
                surf.blit(lbl_surf, lbl_surf.get_rect(midleft=(tx,     rect.centery)))

    def _draw(self, defs, selected, piece_names, left_w, right_x, right_w,
              btn_y, btn_h, mouse, scroll_y, status_msg):
        self.screen.fill(self.BG)

        # Header bar with title + keystroke hint, separated from content by a line
        hdr = self.HEADER_H
        pygame.draw.rect(self.screen, (16, 12, 32), (0, 0, self.w, hdr))
        pygame.draw.line(self.screen, Colours.HIGH, (0, hdr - 1), (self.w, hdr - 1), 1)
        # Title centred vertically in header
        shd = self.title_font.render('Piece Editor', True, (0, 0, 0))
        title = self.title_font.render('Piece Editor', True, self.TITLE_COLOR)
        ty = hdr // 2 - title.get_height() // 2
        self.screen.blit(shd,   (self.PADDING + 1, ty + 1))
        self.screen.blit(title, (self.PADDING,      ty))
        hint = self.tiny_font.render('Esc / Back = main menu', True, self.DIM_TEXT)
        self.screen.blit(hint, (self.w - hint.get_width() - self.PADDING,
                                hdr // 2 - hint.get_height() // 2))

        # Piece selector (left panel in landscape, top tabs in portrait)
        tab_rects = self._piece_rects(piece_names, left_w)
        if self._portrait:
            tab_bottom = (tab_rects[-1].bottom + self.PADDING) if tab_rects else hdr + 4
        else:
            # Left panel — pixel art frame (square corners, teal outer + dark inner)
            left_panel = pygame.Rect(0, hdr, left_w, btn_y - hdr)
            pygame.draw.rect(self.screen, self.PANEL_BG, left_panel, border_radius=0)
            pygame.draw.rect(self.screen, Colours.HIGH,  left_panel, 2)
            pygame.draw.rect(self.screen, (30, 25, 55),  left_panel.inflate(-4, -4), 1)
            tab_bottom = hdr + 4

        for name, rect in zip(piece_names, tab_rects):
            is_sel = (name == selected)
            hov    = rect.collidepoint(*mouse)
            base   = self.SEL_BG if is_sel else (self.BTN_HOV if hov else self.BTN_BG)
            tc     = self.SEL_TEXT if is_sel else self.TEXT
            self._draw_pixel_btn(self.screen, rect, base, False, name, self.label_font, tc)
            if is_sel:
                pygame.draw.rect(self.screen, Colours.HIGH, rect, 2)

        # Right panel — pixel art frame
        if self._portrait:
            right_panel = pygame.Rect(self.PADDING // 2, tab_bottom,
                                      self.w - self.PADDING, btn_y - tab_bottom)
        else:
            right_panel = pygame.Rect(right_x - self.PADDING, hdr,
                                      right_w + self.PADDING, btn_y - hdr)
        pygame.draw.rect(self.screen, self.PANEL_BG, right_panel, border_radius=0)
        pygame.draw.rect(self.screen, Colours.HIGH,  right_panel, 2)
        pygame.draw.rect(self.screen, (30, 25, 55),  right_panel.inflate(-4, -4), 1)

        if self._portrait:
            clip = pygame.Rect(self.PADDING, tab_bottom, right_w, btn_y - tab_bottom)
        else:
            clip = pygame.Rect(right_x - self.PADDING, hdr + 4, right_w + self.PADDING, btn_y - hdr - 8)
        self.screen.set_clip(clip)

        hovered_flag  = None
        hovered_delta = None
        step = self.CELL + self.CELL_GAP

        if selected and selected in defs:
            piece_def = defs[selected]
            if self._portrait:
                hdr = self.label_font.render(f'{selected}  —  move rules', True, self.TEXT)
                self.screen.blit(hdr, (right_x, tab_bottom + self.PADDING // 2))
                y = tab_bottom + 32 - scroll_y
            else:
                hdr_lbl = self.label_font.render(f'{selected}  —  move rules', True, self.TEXT)
                self.screen.blit(hdr_lbl, (right_x, self.HEADER_H + 4 - scroll_y))
                y = self.HEADER_H + 36 - scroll_y

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

        # Buttons — pixel art bevel with icons
        btn_colors = {
            '← Back': (70, 55, 70),
            'Clone':  self.BTN_BG,
            'Reset':  self.BTN_RESET,
            'Save':   self.BTN_SAVE,
            'Play':   self.BTN_PLAY,
        }
        btn_icons = {
            '← Back': 'back',
            'Clone':  'clone',
            'Reset':  'reset',
            'Save':   'save',
            'Play':   'play',
        }
        btn_short = {
            '← Back': 'Back',
            'Clone':  'Clone',
            'Reset':  'Reset',
            'Save':   'Save',
            'Play':   'Play',
        }
        for label, rect in self._button_rects(btn_y, btn_h).items():
            hov = rect.collidepoint(*mouse)
            self._draw_pixel_btn(self.screen, rect, btn_colors[label], hov,
                                 btn_short.get(label, label), self.label_font,
                                 self.TEXT, icon=btn_icons.get(label))

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
    TITLE_COLOR = (220, 170,  40)
    HIGH        = Colours.HIGH
    PADDING     = 14
    HEADER_H    = 48
    BAR_H       = 48

    PALETTE_PIECES = ['king', 'queen', 'rook', 'bishop', 'knight', 'pawn']

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

        self.board_theme = board_theme if board_theme in BOARD_THEMES else 'Classic'
        self.piece_theme = piece_theme if piece_theme in PIECE_THEMES else 'Classic'
        self.custom_board = copy.deepcopy(custom_board) if custom_board else None
        self.custom_piece = copy.deepcopy(custom_piece) if custom_piece else None
        self._current_board_size = 8

        self._reinit_display(info.current_w, info.current_h)
        pygame.display.set_caption('megaChess — board layout editor')

    def _reinit_display(self, new_w, new_h, set_mode=True):
        _android = _on_android()
        self.w = new_w if _android else min(new_w, new_h)
        self.h = new_h if _android else self.w
        if set_mode:
            _flags = pygame.FULLSCREEN if _android else 0
            self.screen = pygame.display.set_mode((self.w, self.h), _flags)
        else:
            self.screen = pygame.display.get_surface()
        _raw = _ui_scale(self.w, self.h)
        _font_s   = min(_raw, 2.0)
        _layout_s = min(_raw, 1.3)
        self.title_font = pygame.font.Font('freesansbold.ttf', _fz(28, _font_s))
        self.label_font = pygame.font.Font('freesansbold.ttf', _fz(18, _font_s))
        self.small_font = pygame.font.Font('freesansbold.ttf', _fz(14, _font_s))
        self.tiny_font  = pygame.font.Font('freesansbold.ttf', _fz(12, _font_s))
        self.PADDING  = _fz(14, _layout_s)
        self.HEADER_H = _fz(48, _layout_s)
        self.BAR_H    = _fz(48, _layout_s)

        self._pieces_defs = AllPieces().pieces_defs
        self._gfx = Graphics.for_editor(
            self.w, self.h, self.HEADER_H, self.BAR_H,
            self._current_board_size)
        self._gfx.board_theme = self.board_theme
        self._gfx.piece_theme = self.piece_theme
        self._reload_icons()

    def _reload_icons(self):
        """Re-render piece icons into self._gfx.piece_icons."""
        sq = self._gfx.square_size
        self._gfx.piece_icons = {}
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
                    px = max(8, sq - 6)
                    self._gfx.piece_icons[(piece_type, color_name)] = render_svg(svg, (px, px))
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

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    MIN_BOARD_SIZE = 4
    MAX_BOARD_SIZE = 12

    def _panel_rect(self):
        """Rect for the scrollable options panel (right in landscape, below in portrait)."""
        g = self._gfx
        board_bottom = g.board_y_offset + g.frame_size * 2 + g.square_size * g.board_size
        board_right  = g.frame_size * 2 + g.square_size * g.board_size
        bar_top = self.h - self.BAR_H
        if self.h > self.w * 1.1:   # portrait
            return pygame.Rect(0, board_bottom, self.w, max(0, bar_top - board_bottom))
        else:                        # landscape
            return pygame.Rect(board_right, self.HEADER_H,
                               max(0, self.w - board_right),
                               max(0, bar_top - self.HEADER_H))

    def _bar_rect(self):
        return pygame.Rect(0, self.h - self.BAR_H, self.w, self.BAR_H)

    def _bar_btn_rects(self):
        labels = ['Back', 'Reset', 'Save', 'Play']
        bar_y = self.h - self.BAR_H
        pad = 8
        bh = self.BAR_H - pad * 2
        bw = (self.w - pad * (len(labels) + 1)) // len(labels)
        return {label: pygame.Rect(pad + i * (bw + pad), bar_y + pad, bw, bh)
                for i, label in enumerate(labels)}

    def _board_sq_from_pixel(self, px, py):
        g = self._gfx
        ox = g.frame_size
        oy = g.board_y_offset + g.frame_size
        bx = (px - ox) // max(g.square_size, 1)
        by = (py - oy) // max(g.square_size, 1)
        if 0 <= bx < g.board_size and 0 <= by < g.board_size:
            return (bx, by)
        return None

    def _compute_panel_layout(self, panel_rect, board_size, scroll_y, shade_expanded):
        """Return a SimpleNamespace of all interactive rects (screen coords) for the panel."""
        from types import SimpleNamespace
        L = SimpleNamespace()
        _s  = min(_ui_scale(self.w, self.h), 1.3)
        ITEM_H  = max(26, _fz(28, _s))
        PAL_H   = max(22, _fz(24, _s))
        GAP     = max(4,  self.PADDING // 2)
        SGAP    = self.PADDING
        BTN_W   = max(28, ITEM_H)
        THM_W   = max(56, _fz(60, _s))
        THM_H   = max(20, _fz(22, _s))
        THM_GAP = max(3,  GAP // 2)
        px  = panel_rect.x + self.PADDING
        pw  = max(1, panel_rect.width - self.PADDING * 2)
        pr  = panel_rect.right - self.PADDING
        y   = GAP  # content-space y relative to panel_rect.y (unscrolled)

        def sy(cy):
            return panel_rect.y + cy - scroll_y

        # Board size row
        _y = sy(y)
        L.minus_rect    = pygame.Rect(pr - BTN_W * 2 - GAP, _y, BTN_W, ITEM_H)
        L.plus_rect     = pygame.Rect(pr - BTN_W,            _y, BTN_W, ITEM_H)
        L.size_label_y  = _y
        y += ITEM_H + SGAP

        # Palette (2-column: white left, black right; hole full-width)
        col_w = max(1, (pw - GAP) // 2)
        L.palette_rects = []
        for piece_type in self.PALETTE_PIECES:
            _y = sy(y)
            L.palette_rects.append(('white', piece_type,
                                    pygame.Rect(px, _y, col_w, PAL_H)))
            L.palette_rects.append(('black', piece_type,
                                    pygame.Rect(px + col_w + GAP, _y, col_w, PAL_H)))
            y += PAL_H + GAP // 2
        _y = sy(y)
        L.palette_rects.append(('hole', 'hole', pygame.Rect(px, _y, pw, PAL_H)))
        y += PAL_H + SGAP

        # Preset buttons
        preset_names = ['Standard 8×8', 'Diamond 8×8', 'Hexagon 12×12']
        n_pre = len(preset_names)
        pre_bw = max(1, (pw - GAP * (n_pre - 1)) // n_pre)
        _y = sy(y)
        L.preset_rects = {}
        for i, name in enumerate(preset_names):
            L.preset_rects[name] = pygame.Rect(px + i * (pre_bw + GAP), _y, pre_bw, PAL_H)
        y += PAL_H + SGAP

        # Board theme row
        L.board_theme_label_y = sy(y)
        y += THM_H // 2
        _y = sy(y)
        L.theme_rects = {}
        for i, name in enumerate(BOARD_THEMES):
            L.theme_rects[('board', name)] = pygame.Rect(
                px + i * (THM_W + THM_GAP), _y, THM_W, THM_H)
        y += THM_H + GAP

        # Piece theme row
        L.piece_theme_label_y = sy(y)
        y += THM_H // 2
        _y = sy(y)
        for i, name in enumerate(PIECE_THEMES):
            L.theme_rects[('piece', name)] = pygame.Rect(
                px + i * (THM_W + THM_GAP), _y, THM_W, THM_H)
        y += THM_H + SGAP

        # Shade toggle button
        _y = sy(y)
        L.shade_toggle_rect = pygame.Rect(px, _y, pw, ITEM_H)
        y += ITEM_H + GAP

        # Shade rows (only when expanded)
        L.shade_rects = []
        if shade_expanded:
            btn_ws = max(20, pw // 9)
            sw_w   = max(18, pw // 7)
            for _ in range(len(self._SHADE_CONTROLS)):
                _y = sy(y)
                cy = _y + 11
                mr  = pygame.Rect(pr - btn_ws * 2 - sw_w - 8, cy - 11, btn_ws, 22)
                sr  = pygame.Rect(mr.right + 4,                cy -  9, sw_w,   18)
                pr2 = pygame.Rect(sr.right + 4,                cy - 11, btn_ws, 22)
                L.shade_rects.append((mr, sr, pr2))
                y += 22 + GAP

        L.total_content_h = y + GAP
        L.ITEM_H  = ITEM_H;  L.PAL_H  = PAL_H;  L.GAP   = GAP
        L.SGAP    = SGAP;    L.BTN_W  = BTN_W;  L.THM_W = THM_W
        L.THM_H   = THM_H;  L.THM_GAP = THM_GAP; L.px   = px;  L.pw = pw
        return L

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self):
        """Show the editor. Returns (layout_dict, saved_path, board_theme,
        piece_theme, custom_board, custom_piece)."""
        layout = self._load_or_default()
        selected = ('white', 'pawn')
        saved_path = None
        status_msg = ''
        status_until = 0
        scroll_y = 0
        shade_expanded = False
        clock = pygame.time.Clock()

        while True:
            board_size = layout.get('board_size', 8)
            self._current_board_size = board_size
            if self._gfx.board_size != board_size:
                self._gfx.set_board_size(board_size)
                self._reload_icons()
            mouse = pygame.mouse.get_pos()
            panel_rect = self._panel_rect()
            bar_btns   = self._bar_btn_rects()
            L = self._compute_panel_layout(panel_rect, board_size, scroll_y, shade_expanded)
            max_scroll = max(0, L.total_content_h - panel_rect.height)
            scroll_y = min(scroll_y, max_scroll)

            for event in pygame.event.get():
                if event.type == locals.QUIT:
                    pygame.quit()
                    sys.exit()

                _sz = _resize_event_size(event)
                if _sz:
                    self._reinit_display(*_sz, set_mode=_resize_needs_set_mode(event))
                    self._gfx.board_theme = self.board_theme
                    self._gfx.piece_theme = self.piece_theme
                    scroll_y = 0
                    continue

                if event.type == locals.KEYDOWN and event.key == locals.K_ESCAPE:
                    return (layout, saved_path, self.board_theme, self.piece_theme,
                            self.custom_board, self.custom_piece)

                if event.type == pygame.MOUSEWHEEL:
                    if panel_rect.collidepoint(*mouse):
                        scroll_y = max(0, min(scroll_y - event.y * 20, max_scroll))

                if event.type == locals.MOUSEBUTTONDOWN:
                    mx, my = event.pos

                    # Board click: place/remove piece or toggle hole
                    sq_coord = self._board_sq_from_pixel(mx, my)
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

                    # Panel clicks
                    if panel_rect.collidepoint(mx, my):
                        if L.minus_rect.collidepoint(mx, my) and board_size > self.MIN_BOARD_SIZE:
                            layout = self._resize_layout(layout, board_size - 1)
                            status_msg = f'Board size: {board_size - 1}×{board_size - 1}'
                            status_until = pygame.time.get_ticks() + 2000
                        elif L.plus_rect.collidepoint(mx, my) and board_size < self.MAX_BOARD_SIZE:
                            layout = self._resize_layout(layout, board_size + 1)
                            status_msg = f'Board size: {board_size + 1}×{board_size + 1}'
                            status_until = pygame.time.get_ticks() + 2000

                        for color_str, piece_type, rect in L.palette_rects:
                            if rect.collidepoint(mx, my):
                                selected = 'hole' if color_str == 'hole' else (color_str, piece_type)

                        for preset_name, rect in L.preset_rects.items():
                            if rect.collidepoint(mx, my):
                                layout = self._make_preset(preset_name)
                                status_msg = f'Loaded preset: {preset_name}'
                                status_until = pygame.time.get_ticks() + 2500

                        for (kind, name), rect in L.theme_rects.items():
                            if rect.collidepoint(mx, my):
                                if kind == 'board':
                                    self.board_theme = name
                                    self.custom_board = None
                                    self._gfx.board_theme = name
                                else:
                                    self.piece_theme = name
                                    self.custom_piece = None
                                    self._gfx.piece_theme = name
                                    self._reload_icons()
                                self._save_theme_file()

                        if L.shade_toggle_rect.collidepoint(mx, my):
                            shade_expanded = not shade_expanded

                        for i, (mr, sr, pr) in enumerate(L.shade_rects):
                            if mr.collidepoint(mx, my):
                                self._apply_shade_delta(i, -self.SHADE_STEP)
                            elif pr.collidepoint(mx, my):
                                self._apply_shade_delta(i, +self.SHADE_STEP)

                    # Bottom bar clicks
                    for label, rect in bar_btns.items():
                        if rect.collidepoint(mx, my):
                            if label == 'Back':
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

            self._draw(layout, selected, mouse, scroll_y, shade_expanded,
                       status_msg if pygame.time.get_ticks() < status_until else '',
                       panel_rect, bar_btns, L)
            pygame.display.update()
            clock.tick(60)

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _default_layout(self):
        return _preset_standard()

    def _make_preset(self, name):
        if name == 'Diamond 8×8':
            return _preset_diamond()
        elif name == 'Hexagon 12×12':
            return _preset_hexagon()
        return _preset_standard()

    @staticmethod
    def _resize_layout(layout, new_size):
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
        return {'board_size': new_size, 'matrix': new_matrix,
                'en_passant_target': None, 'promotion_pending': None}

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
                        bevel=2, icon=None):
        """Pixel-art bevelled button (square corners, bright top/left, dark bottom/right)."""
        bg = tuple(min(c + 30, 255) for c in base_color) if hovered else base_color
        hi = tuple(min(c + 55, 255) for c in base_color)
        lo = tuple(max(c - 25,   0) for c in base_color)
        pygame.draw.rect(surf, bg, rect, border_radius=0)
        pygame.draw.line(surf, hi, rect.topleft,    rect.topright,    bevel)
        pygame.draw.line(surf, hi, rect.topleft,    rect.bottomleft,  bevel)
        pygame.draw.line(surf, lo, rect.bottomleft, rect.bottomright, bevel)
        pygame.draw.line(surf, lo, rect.topright,   rect.bottomright, bevel)
        if icon or text:
            icn_sz = rect.height - 10 if icon else 0
            _btn_font = _fit_font(rect.height - 6)
            lbl_surf = _btn_font.render(text, True, text_color) if text else None
            shd_surf = _btn_font.render(text, True, (0, 0, 0))  if text else None
            lbl_w = lbl_surf.get_width() if lbl_surf else 0
            gap_i = 4 if (icon and text) else 0
            total_w = icn_sz + gap_i + lbl_w
            ix = rect.centerx - total_w // 2 + icn_sz // 2
            tx = rect.centerx - total_w // 2 + icn_sz + gap_i
            if icon:
                _draw_icon(surf, icon, ix, rect.centery, icn_sz, text_color)
            if lbl_surf:
                surf.blit(shd_surf, shd_surf.get_rect(midleft=(tx + 1, rect.centery + 1)))
                surf.blit(lbl_surf, lbl_surf.get_rect(midleft=(tx,     rect.centery)))

    def _draw(self, layout, selected, mouse, scroll_y, shade_expanded, status_msg,
              panel_rect, bar_btns, L):
        board_size = layout.get('board_size', 8)
        g  = self._gfx
        g.screen = self.screen
        t  = self.custom_board if self.custom_board else BOARD_THEMES[self.board_theme]

        # 1. Board frame (fills screen dark, draws border + coord labels via Graphics)
        g.draw_board_frame()

        # 2. Board squares (editor custom drawing using _gfx dimensions)
        sq  = g.square_size
        ox  = g.frame_size
        oy  = g.board_y_offset + g.frame_size
        _bv = max(2, sq // 16)
        sq_hover = self._board_sq_from_pixel(*mouse)
        for x in range(board_size):
            for yi in range(board_size):
                cell = layout['matrix'][x][yi]
                rect = pygame.Rect(ox + x * sq, oy + yi * sq, sq, sq)
                hov  = sq_hover == (x, yi)
                if cell == 'hole':
                    pygame.draw.rect(self.screen, t['hole'], rect)
                    pygame.draw.rect(self.screen, t['hole_lo'], (rect.x, rect.y, rect.w, _bv))
                    pygame.draw.rect(self.screen, t['hole_lo'], (rect.x, rect.y, _bv, rect.h))
                    pygame.draw.rect(self.screen, t['hole_hi'], (rect.x, rect.y + rect.h - _bv, rect.w, _bv))
                    pygame.draw.rect(self.screen, t['hole_hi'], (rect.x + rect.w - _bv, rect.y, _bv, rect.h))
                else:
                    is_light = (x + yi) % 2 == 0
                    bc = t['light'] if is_light else t['dark']
                    if hov:
                        bc = tuple(min(c + 30, 255) for c in bc)
                    hi = t['light_hi'] if is_light else t['dark_hi']
                    lo = t['light_lo'] if is_light else t['dark_lo']
                    pygame.draw.rect(self.screen, bc, rect)
                    pygame.draw.rect(self.screen, hi, (rect.x, rect.y, rect.w, _bv))
                    pygame.draw.rect(self.screen, hi, (rect.x, rect.y, _bv, rect.h))
                    pygame.draw.rect(self.screen, lo, (rect.x, rect.y + rect.h - _bv, rect.w, _bv))
                    pygame.draw.rect(self.screen, lo, (rect.x + rect.w - _bv, rect.y, _bv, rect.h))
        board_px = sq * board_size
        sep = (8, 8, 18)
        for i in range(1, board_size):
            pygame.draw.line(self.screen, sep, (ox + i*sq, oy), (ox + i*sq, oy + board_px))
            pygame.draw.line(self.screen, sep, (ox, oy + i*sq), (ox + board_px, oy + i*sq))

        # 3. Board pieces
        piece_labels = {'pawn': 'P', 'rook': 'R', 'knight': 'N',
                        'bishop': 'B', 'queen': 'Q', 'king': 'K'}
        for x in range(board_size):
            for yi in range(board_size):
                cell = layout['matrix'][x][yi]
                if cell is None or cell == 'hole':
                    continue
                cx = ox + x * sq + sq // 2
                cy = oy + yi * sq + sq // 2
                color_key = cell['color']
                icon = g.piece_icons.get((cell['piece_type'], color_key))
                if icon:
                    scaled = pygame.transform.smoothscale(icon, (sq - 6, sq - 6))
                    self.screen.blit(scaled, scaled.get_rect(center=(cx, cy)))
                else:
                    c = Colours.WHITE if color_key == 'white' else Colours.PIECE_BLACK
                    r2 = sq // 2 - 2
                    pygame.draw.circle(self.screen, c, (cx, cy), r2)
                    outline = Colours.BLACK if color_key == 'white' else Colours.WHITE
                    pygame.draw.circle(self.screen, outline, (cx, cy), r2, 2)
                    lbl = self.small_font.render(
                        piece_labels.get(cell['piece_type'], '?'), True, outline)
                    self.screen.blit(lbl, lbl.get_rect(center=(cx, cy)))

        # 4. Header (drawn on top of board frame)
        hdr = self.HEADER_H
        pygame.draw.rect(self.screen, (16, 12, 32), (0, 0, self.w, hdr))
        pygame.draw.line(self.screen, self.HIGH, (0, hdr - 1), (self.w, hdr - 1), 1)
        shd_s  = self.title_font.render('Board Layout Editor', True, (0, 0, 0))
        title  = self.title_font.render('Board Layout Editor', True, self.TITLE_COLOR)
        ty = hdr // 2 - title.get_height() // 2
        self.screen.blit(shd_s, (self.PADDING + 1, ty + 1))
        self.screen.blit(title, (self.PADDING,      ty))
        hint = self.tiny_font.render('L-click: place  •  R-click: clear  •  Esc: back',
                                     True, self.DIM_TEXT)
        self.screen.blit(hint, hint.get_rect(right=self.w - self.PADDING, centery=hdr // 2))

        # 5. Panel background
        pygame.draw.rect(self.screen, self.PANEL_BG, panel_rect)
        pygame.draw.line(self.screen, self.HIGH, panel_rect.topleft, panel_rect.topright, 1)

        # 5a. Panel content with clipping + scroll
        self.screen.set_clip(panel_rect)
        px  = L.px
        GAP = L.GAP

        # Board size row
        sl = self.label_font.render(f'Board size: {board_size}', True, self.TEXT)
        self.screen.blit(sl, (px, L.size_label_y + 4))
        for rect, label, enabled in [(L.minus_rect, '−', board_size > self.MIN_BOARD_SIZE),
                                      (L.plus_rect,  '+', board_size < self.MAX_BOARD_SIZE)]:
            hov  = rect.collidepoint(*mouse) and enabled
            base = self.BTN_HOV if hov else (self.BTN_BG if enabled else (35, 35, 45))
            tc   = self.TEXT if enabled else self.DIM_TEXT
            self._draw_pixel_btn(self.screen, rect, base, hov, label, self.label_font, tc)

        # Palette header
        if L.palette_rects:
            ph_y = L.palette_rects[0][2].y - GAP * 2
            ph = self.tiny_font.render('PALETTE  (white | black)', True, self.DIM_TEXT)
            self.screen.blit(ph, (px, ph_y))

        for color_str, piece_type, rect in L.palette_rects:
            is_hole = color_str == 'hole'
            is_sel  = (selected == 'hole') if is_hole else selected == (color_str, piece_type)
            hov     = rect.collidepoint(*mouse)
            if is_sel:
                bg, tc = self.HIGH, (20, 20, 20)
            elif hov:
                bg, tc = self.BTN_HOV, self.TEXT
            else:
                bg, tc = self.BTN_BG, self.TEXT
            self._draw_pixel_btn(self.screen, rect, bg, False, None, None, None)
            if is_sel:
                pygame.draw.rect(self.screen, Colours.HIGH, rect, 2)
            ix = rect.left + 4
            if is_hole:
                sw = pygame.Rect(ix, rect.centery - 8, 20, 16)
                pygame.draw.rect(self.screen, Colours.HOLE, sw)
                pygame.draw.rect(self.screen, (45, 45, 55), sw.inflate(-4, -4))
                lbl_s = self.tiny_font.render('Hole (toggle)', True, tc)
            else:
                icon = g.piece_icons.get((piece_type, color_str))
                icn_h = rect.height - 4
                if icon:
                    sm_icon = pygame.transform.smoothscale(icon, (icn_h, icn_h))
                    self.screen.blit(sm_icon, sm_icon.get_rect(centery=rect.centery, left=ix))
                lbl_s = self.tiny_font.render(
                    f'{"W" if color_str == "white" else "B"} {piece_type}', True, tc)
            self.screen.blit(lbl_s, lbl_s.get_rect(centery=rect.centery, left=ix + rect.height))

        # Presets
        if L.preset_rects:
            first_pr = next(iter(L.preset_rects.values()))
            pre_hdr = self.tiny_font.render('PRESETS', True, self.DIM_TEXT)
            self.screen.blit(pre_hdr, (px, first_pr.y - GAP * 2))
        for name, rect in L.preset_rects.items():
            hov = rect.collidepoint(*mouse)
            self._draw_pixel_btn(self.screen, rect, self.BTN_BG, hov,
                                 name, self.tiny_font, self.TEXT)

        # Theme rows
        bt_hdr = self.tiny_font.render('BOARD THEME', True, self.DIM_TEXT)
        self.screen.blit(bt_hdr, (px, L.board_theme_label_y))
        pt_hdr = self.tiny_font.render('PIECE THEME', True, self.DIM_TEXT)
        self.screen.blit(pt_hdr, (px, L.piece_theme_label_y))
        for (kind, name), rect in L.theme_rects.items():
            active = (name == self.board_theme if kind == 'board' else name == self.piece_theme)
            hov  = rect.collidepoint(*mouse)
            base = (40, 160, 160) if active else self.BTN_BG
            tc   = (5, 5, 15)    if active else self.TEXT
            self._draw_pixel_btn(self.screen, rect, base, hov, name, self.tiny_font, tc)
            if active:
                pygame.draw.rect(self.screen, Colours.HIGH, rect, 2)

        # Shade toggle
        tog_text = 'Customise colours ▴' if shade_expanded else 'Customise colours ▾'
        hov = L.shade_toggle_rect.collidepoint(*mouse)
        self._draw_pixel_btn(self.screen, L.shade_toggle_rect,
                             self.BTN_HOV if hov else self.BTN_BG, hov,
                             tog_text, self.small_font, self.TEXT)

        # Shade rows (only when expanded)
        if shade_expanded:
            for i, (label, kind, sub, keys) in enumerate(self._SHADE_CONTROLS):
                if i >= len(L.shade_rects):
                    break
                mr, sr, pr = L.shade_rects[i]
                ls = self.tiny_font.render(label, True, self.TEXT)
                self.screen.blit(ls, (px, mr.centery - ls.get_height() // 2))
                if kind == 'board':
                    bc2 = self.custom_board if self.custom_board else BOARD_THEMES[self.board_theme]
                    swatch_col = bc2[keys[0]]
                else:
                    pc2 = self.custom_piece if self.custom_piece else PIECE_THEMES[self.piece_theme]
                    r3, g3, b3 = self._hex_to_rgb(pc2[sub][keys[0]])
                    swatch_col = (r3, g3, b3)
                hm = mr.collidepoint(*mouse)
                pygame.draw.rect(self.screen, (60, 30, 30) if hm else (40, 20, 20), mr)
                pygame.draw.rect(self.screen, (140, 70, 70), mr, 1)
                ms = self.tiny_font.render('-', True, (220, 140, 140))
                self.screen.blit(ms, ms.get_rect(center=mr.center))
                pygame.draw.rect(self.screen, swatch_col, sr)
                pygame.draw.rect(self.screen, (70, 70, 100), sr, 1)
                hp = pr.collidepoint(*mouse)
                pygame.draw.rect(self.screen, (30, 60, 30) if hp else (20, 40, 20), pr)
                pygame.draw.rect(self.screen, (70, 140, 70), pr, 1)
                ps = self.tiny_font.render('+', True, (140, 220, 140))
                self.screen.blit(ps, ps.get_rect(center=pr.center))

        # Scrollbar
        if L.total_content_h > panel_rect.height > 0:
            ratio = panel_rect.height / L.total_content_h
            sb_h = max(20, int(panel_rect.height * ratio))
            sb_y = panel_rect.y + int((scroll_y / L.total_content_h) * panel_rect.height)
            pygame.draw.rect(self.screen, (80, 70, 120),
                             (panel_rect.right - 4, sb_y, 4, sb_h))

        self.screen.set_clip(None)

        # 6. Bottom bar
        bar_rect = self._bar_rect()
        bar_y = bar_rect.y
        pygame.draw.rect(self.screen, (8, 8, 18), bar_rect)
        pygame.draw.line(self.screen, (60, 50, 100), (0, bar_y), (self.w, bar_y), 2)
        pygame.draw.line(self.screen, (20, 15, 40), (0, bar_y + 2), (self.w, bar_y + 2), 1)
        btn_colors_m = {'Back': self.BTN_BG, 'Reset': self.BTN_RST,
                        'Save': self.BTN_SAVE, 'Play': self.BTN_PLAY}
        btn_icons_m  = {'Back': 'back', 'Reset': 'reset', 'Save': 'save', 'Play': 'play'}
        for label, rect in bar_btns.items():
            hov = rect.collidepoint(*mouse)
            self._draw_pixel_btn(self.screen, rect, btn_colors_m[label], hov,
                                 label, self.label_font, self.TEXT,
                                 icon=btn_icons_m[label])

        # Status message above bar
        if status_msg:
            sm = self.small_font.render(status_msg, True, Colours.GOLD)
            self.screen.blit(sm, (self.PADDING, bar_y - sm.get_height() - 4))


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
    Handles orientation changes (VIDEORESIZE / WINDOWRESIZED) by recomputing layout.
    """
    pygame.display.set_caption('megaChess')
    clock = pygame.time.Clock()
    _android = _on_android()

    def _build_layout(W, H):
        """Compute all layout variables and pre-built surfaces for screen size W×H."""
        import types
        L = types.SimpleNamespace()
        L._s = _ui_scale(W, H)
        L.gap = _fz(16, L._s)
        _portrait = H > W * 1.1
        eff_h = min(W, H)   # square region; still used for landscape button y
        _corner_sz = 14 * 4   # _cell * 4, matches corner decoration built below
        if _portrait:
            btn_scale = min(L._s, 1.3)
            L.bh = _fz(48, btn_scale)
            bw = W - L.gap * 2
            x0 = L.gap
            btn_gap = _fz(12, btn_scale)
            btn_area_h = L.bh * 3 + btn_gap * 2
            # Use full screen height H so corners/buttons reach the true bottom on tall phones
            L.frame_y = max(L.gap * 2, H // 12)
            L._btn_bottom_y = H - _corner_sz - 16
            y0 = L._btn_bottom_y - btn_gap - btn_area_h
            L.btns = {
                'Play':        pygame.Rect(x0, y0,                        bw, L.bh),
                'Edit Pieces': pygame.Rect(x0, y0 + (L.bh + btn_gap),    bw, L.bh),
                'Edit Layout': pygame.Rect(x0, y0 + (L.bh + btn_gap) * 2, bw, L.bh),
            }
        else:
            L.bh = _fz(56, L._s)
            bw = _fz(210, L._s)
            total_w = bw * 3 + L.gap * 2
            x0 = W // 2 - total_w // 2
            L.frame_y = eff_h // 5
            L.btns = {
                'Play':         pygame.Rect(x0,                    eff_h * 2 // 3, bw, L.bh),
                'Edit Pieces':  pygame.Rect(x0 + (bw + L.gap),    eff_h * 2 // 3, bw, L.bh),
                'Edit Layout':  pygame.Rect(x0 + (bw + L.gap) * 2, eff_h * 2 // 3, bw, L.bh),
            }
            L._btn_bottom_y = eff_h - _corner_sz - 16
        L.btn_colors = {
            'Play':        (30,  75, 150),
            'Edit Pieces': (30, 100,  55),
            'Edit Layout': (90,  40, 120),
        }
        L.key_map = {
            'Play':        'play',
            'Edit Pieces': 'edit_pieces',
            'Edit Layout': 'edit_layout',
        }
        L.W = W
        L.H = H

        # Pre-build pixel-art grid overlay (subtle tile grid)
        L.grid_overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        for gx in range(0, W, 16):
            pygame.draw.line(L.grid_overlay, (255, 255, 255, 12), (gx, 0), (gx, H))
        for gy in range(0, H, 16):
            pygame.draw.line(L.grid_overlay, (255, 255, 255, 12), (0, gy), (W, gy))

        # Pre-build scanline overlay (CRT retro effect)
        L.scanlines = pygame.Surface((W, H), pygame.SRCALPHA)
        for sy in range(0, H, 2):
            pygame.draw.line(L.scanlines, (0, 0, 0, 80), (0, sy), (W, sy))

        # Pre-build corner chess board decorations (4×4 grid of 14×14px squares)
        _cell = 14
        _t = BOARD_THEMES['Classic']
        L._corner_surf = pygame.Surface((_cell * 4, _cell * 4))
        for _r in range(4):
            for _c in range(4):
                _col = _t['light'] if (_r + _c) % 2 == 0 else _t['dark']
                pygame.draw.rect(L._corner_surf, _col, (_c * _cell, _r * _cell, _cell, _cell))
        _bv = 2
        for _r in range(4):
            for _c in range(4):
                _is_l = (_r + _c) % 2 == 0
                _hi = _t['light_hi'] if _is_l else _t['dark_hi']
                _lo = _t['light_lo'] if _is_l else _t['dark_lo']
                _rx, _ry = _c * _cell, _r * _cell
                pygame.draw.rect(L._corner_surf, _hi, (_rx, _ry, _cell, _bv))
                pygame.draw.rect(L._corner_surf, _hi, (_rx, _ry, _bv, _cell))
                pygame.draw.rect(L._corner_surf, _lo, (_rx, _ry + _cell - _bv, _cell, _bv))
                pygame.draw.rect(L._corner_surf, _lo, (_rx + _cell - _bv, _ry, _bv, _cell))
        L._corner_w = _cell * 4
        pygame.draw.rect(L._corner_surf, Colours.HIGH, (0, 0, L._corner_w, L._corner_w), 2)

        return L

    L = _build_layout(w, h)

    while True:
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == locals.QUIT:
                pygame.quit()
                sys.exit()
            _sz = _resize_event_size(event)
            if _sz:
                w, h = _sz
                if _resize_needs_set_mode(event):
                    screen = pygame.display.set_mode((w, h), pygame.FULLSCREEN if _android else 0)
                else:
                    screen = pygame.display.get_surface()
                L = _build_layout(w, h)
                continue
            if event.type == pygame.FINGERDOWN:
                tw, th = screen.get_size()
                mx, my = int(event.x * tw), int(event.y * th)
            if event.type in (locals.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                for label, rect in L.btns.items():
                    if rect.collidepoint(mx, my):
                        return L.key_map[label]
            if event.type == locals.KEYDOWN:
                if event.key == locals.K_RETURN:
                    return 'play'
                if event.key == locals.K_e:
                    return 'edit_pieces'
                if event.key == locals.K_l:
                    return 'edit_layout'

        screen.fill((10, 8, 20))
        # Pixel-art grid + corner chess board decorations
        screen.blit(L.grid_overlay, (0, 0))
        margin = 16
        screen.blit(L._corner_surf, (margin, margin))
        screen.blit(pygame.transform.flip(L._corner_surf, True,  False), (w - L._corner_w - margin, margin))
        screen.blit(pygame.transform.flip(L._corner_surf, False, True),  (margin, L._btn_bottom_y))
        screen.blit(pygame.transform.flip(L._corner_surf, True,  True),  (w - L._corner_w - margin, L._btn_bottom_y))
        screen.blit(L.scanlines, (0, 0))

        # Stacked two-colour pixel art title: MEGA (gold) + CHESS (teal)
        _title_sz = _fz(72, min(L._s, 1.1))   # cap title scale so it doesn't crowd buttons
        mega_surf  = _pixel_text('MEGA',  _title_sz, Colours.GOLD, bold=True)
        chess_surf = _pixel_text('CHESS', _title_sz, Colours.HIGH, bold=True)
        title_w  = max(mega_surf.get_width(), chess_surf.get_width())
        title_h  = mega_surf.get_height() + chess_surf.get_height() + 4
        frame_x  = w // 2 - title_w // 2 - 24
        pad = _fz(16, L._s)
        # Outer teal border + dark inner fill
        pygame.draw.rect(screen, Colours.HIGH,
                         (frame_x - 4, L.frame_y - 4, title_w + 56, title_h + pad * 2 + 8), 3)
        pygame.draw.rect(screen, (8, 8, 18),
                         (frame_x, L.frame_y, title_w + 48, title_h + pad * 2))
        # Bevel lines on title box
        bx, by, bw2, bh2 = frame_x, L.frame_y, title_w + 48, title_h + pad * 2
        pygame.draw.line(screen, (80, 215, 215), (bx, by), (bx + bw2, by), 1)
        pygame.draw.line(screen, (80, 215, 215), (bx, by), (bx, by + bh2), 1)
        pygame.draw.line(screen, (20, 40, 80), (bx, by + bh2), (bx + bw2, by + bh2), 1)
        pygame.draw.line(screen, (20, 40, 80), (bx + bw2, by), (bx + bw2, by + bh2), 1)
        for _dx, _dy in [(bx, by), (bx + bw2 - 4, by), (bx, by + bh2 - 4), (bx + bw2 - 4, by + bh2 - 4)]:
            pygame.draw.rect(screen, Colours.GOLD, (_dx, _dy, 4, 4))
        cx = bx + bw2 // 2
        screen.blit(mega_surf,  mega_surf.get_rect(centerx=cx,  top=L.frame_y + pad))
        screen.blit(chess_surf, chess_surf.get_rect(centerx=cx, top=L.frame_y + pad + mega_surf.get_height() + 4))

        # Blinking cursor prompt + keyboard shortcuts
        blink = (pygame.time.get_ticks() // 500) % 2
        hint_str = 'PRESS ENTER TO PLAY' + (' _' if blink else '  ')
        hint_s = _pixel_text(hint_str, _fz(16, L._s), (140, 130, 170), bold=True)
        screen.blit(hint_s, hint_s.get_rect(centerx=w // 2, top=L.frame_y + title_h + pad * 2 + L.gap))

        sub = _pixel_text('E = edit pieces   *   L = edit layout', _fz(14, L._s), (100, 90, 130), bold=True)
        screen.blit(sub, sub.get_rect(centerx=w // 2,
                                      top=L.frame_y + title_h + pad * 2 + L.gap + hint_s.get_height() + 4))

        BEVEL = 2
        _icon_map  = {'Play': 'play', 'Edit Pieces': 'pieces', 'Edit Layout': 'layout'}
        _label_map = {'Play': 'Play', 'Edit Pieces': 'Pieces', 'Edit Layout': 'Layout'}
        ICN = max(L.btns['Play'].height - 18, 14)
        tc = (220, 225, 235)
        for label, rect in L.btns.items():
            hov = rect.collidepoint(mx, my)
            base = L.btn_colors[label]
            bg = tuple(min(c + 35, 255) for c in base) if hov else base
            bhi = tuple(min(c + 55, 255) for c in base)
            blo = tuple(max(c - 20, 0) for c in base)
            pygame.draw.rect(screen, bg, rect, border_radius=0)
            pygame.draw.line(screen, bhi, rect.topleft,    rect.topright,    BEVEL)
            pygame.draw.line(screen, bhi, rect.topleft,    rect.bottomleft,  BEVEL)
            pygame.draw.line(screen, blo, rect.bottomleft, rect.bottomright, BEVEL)
            pygame.draw.line(screen, blo, rect.topright,   rect.bottomright, BEVEL)
            short = _label_map.get(label, label)
            _btn_text_sz = max(10, L.bh * 2 // 5)
            shadow_s = _pixel_text(short, _btn_text_sz, (0, 0, 0), bold=True)
            txt_s    = _pixel_text(short, _btn_text_sz, tc,         bold=True)
            total_w = ICN + 6 + txt_s.get_width()
            ix = rect.centerx - total_w // 2 + ICN // 2
            tx = rect.centerx - total_w // 2 + ICN + 6
            _draw_icon(screen, _icon_map.get(label, 'play'), ix, rect.centery, ICN, tc)
            screen.blit(shadow_s, shadow_s.get_rect(midleft=(tx + 1, rect.centery + 1)))
            screen.blit(txt_s,    txt_s.get_rect(midleft=(tx, rect.centery)))

        pygame.display.update()
        clock.tick(60)


def main():
    pygame.init()
    info = pygame.display.Info()
    _android = _on_android()
    if _android:
        w, h = info.current_w, info.current_h
    else:
        w = h = min(info.current_w, info.current_h)
    screen = pygame.display.set_mode((w, h), pygame.FULLSCREEN if _android else 0)
    w, h = screen.get_size()

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

        # Re-sync screen reference after any subsystem — editors and the game view each call
        # pygame.display.set_mode(), which may have changed dimensions (e.g. on rotation).
        # get_surface() always returns the current display surface without triggering a resize.
        _surf = pygame.display.get_surface()
        if _surf is not None:
            screen = _surf
            w, h = screen.get_size()


if __name__ == "__main__":
    main()
