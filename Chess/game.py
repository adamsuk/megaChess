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

        self.square_size = self.window_size // 8
        self.piece_size = self.square_size // 2
        self.piece_font = pygame.font.SysFont(None, self.piece_size)

        self.message = False

        self.timed_message_surface = None
        self.timed_message_rect = None
        self.timed_message_until = 0  # pygame.time.get_ticks() expiry

        self.piece_icons = {}  # (piece_type, 'white'|'black') -> scaled Surface

        self.highlights = False
        self.show_hints = True   # toggle: show piece selection + legal-move highlighting

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
        """Draw the Save / Load / Hints button strip below the board."""
        bar_rect = pygame.Rect(0, self.window_size, self.window_size, self.button_bar_height)
        pygame.draw.rect(self.screen, (30, 32, 42), bar_rect)

        font = pygame.font.Font('freesansbold.ttf', 18)

        for label, rect, enabled, toggled in [
            ('Save  [S]',  self.save_btn_rect,  True,       True),
            ('Load  [L]',  self.load_btn_rect,  save_exists, True),
            ('Hints  [H]', self.hints_btn_rect, True,       show_hints),
        ]:
            hovered = rect.collidepoint(*mouse_px) and enabled
            if not enabled:
                bg = (45, 48, 58)
                tc = (80, 85, 95)
            elif not toggled:
                # Hints-off state: muted red-tinted background
                bg = (100, 75, 75) if hovered else (70, 52, 52)
                tc = (200, 175, 175)
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


_CUSTOM_PIECES_PATH = os.path.join(os.path.dirname(__file__), 'defs', 'custom_pieces.json')
_DEFAULT_PIECES_PATH = os.path.join(os.path.dirname(__file__), 'defs', 'pieces_defs.json')

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

    BG          = (25, 28, 38)
    PANEL_BG    = (38, 42, 56)
    SEL_BG      = Colours.HIGH
    SEL_TEXT    = (20, 20, 20)
    TEXT        = (210, 215, 225)
    DIM_TEXT    = (120, 130, 145)
    BTN_BG      = (55, 62, 80)
    BTN_HOV     = (80, 90, 110)
    BTN_SAVE    = (60, 130, 80)
    BTN_PLAY    = (60, 100, 160)
    BTN_RESET   = (140, 70, 60)
    TITLE_COLOR = Colours.GOLD
    ON_COLOR    = (80, 190, 100)
    OFF_COLOR   = (80, 80, 90)
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


def _start_menu(screen, w, h):
    """
    Simple title screen: 'Play' or 'Edit Pieces'. Returns 'play' or 'edit'.
    """
    pygame.display.set_caption('megaChess')
    title_font = pygame.font.Font('freesansbold.ttf', 52)
    sub_font   = pygame.font.Font('freesansbold.ttf', 20)
    btn_font   = pygame.font.Font('freesansbold.ttf', 28)
    clock = pygame.time.Clock()
    bw, bh = 240, 56
    btns = {
        'Play':       pygame.Rect(w // 2 - bw - 16, h * 2 // 3, bw, bh),
        'Edit Pieces': pygame.Rect(w // 2 + 16,      h * 2 // 3, bw, bh),
    }
    btn_colors = {'Play': (60, 110, 170), 'Edit Pieces': (60, 100, 80)}

    while True:
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == locals.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == locals.MOUSEBUTTONDOWN:
                for label, rect in btns.items():
                    if rect.collidepoint(mx, my):
                        return 'play' if label == 'Play' else 'edit'
            if event.type == locals.KEYDOWN:
                if event.key == locals.K_RETURN:
                    return 'play'
                if event.key == locals.K_e:
                    return 'edit'

        screen.fill((25, 28, 38))
        title = title_font.render('megaChess', True, Colours.GOLD)
        sub   = sub_font.render('Press Enter to play  •  E to edit pieces', True, (160, 165, 175))
        screen.blit(title, title.get_rect(centerx=w // 2, y=h // 4))
        screen.blit(sub,   sub.get_rect(centerx=w // 2,   y=h // 4 + 70))

        for label, rect in btns.items():
            hov = rect.collidepoint(mx, my)
            base = btn_colors[label]
            bg = tuple(min(c + 30, 255) for c in base) if hov else base
            pygame.draw.rect(screen, bg, rect, border_radius=10)
            txt = btn_font.render(label, True, (220, 225, 235))
            screen.blit(txt, txt.get_rect(center=rect.center))

        pygame.display.update()
        clock.tick(60)


def main():
    pygame.init()
    info = pygame.display.Info()
    w = h = min(info.current_w, info.current_h)
    screen = pygame.display.set_mode((w, h))

    custom_defs = None
    while True:
        choice = _start_menu(screen, w, h)
        if choice == 'edit':
            defs, saved_path = PieceEditor().run()
            if saved_path:
                custom_defs = defs
        else:
            game = Game()
            if custom_defs is not None:
                game.board.pieces_defs = custom_defs
            game.main()


if __name__ == "__main__":
    main()
