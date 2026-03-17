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


_CUSTOM_PIECES_PATH = os.path.join(os.path.dirname(__file__), 'defs', 'custom_pieces.json')
_DEFAULT_PIECES_PATH = os.path.join(os.path.dirname(__file__), 'defs', 'pieces_defs.json')

# Boolean flags that can be toggled per move_rule
_RULE_FLAGS = ['sliding', 'directional', 'move_only', 'capture_only', 'jump_capture']


class PieceEditor:
    """
    In-game piece rules editor.
    Left panel: list of piece types.
    Right panel: move_rules for the selected piece with toggleable flags.
    Bottom buttons: Clone / Reset / Save / Play.
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
        defs = copy.deepcopy(all_pieces.pieces_defs)
        # Load any previously saved custom defs
        if os.path.exists(_CUSTOM_PIECES_PATH):
            try:
                with open(_CUSTOM_PIECES_PATH) as f:
                    defs = json.load(f)
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

                    # Right panel — toggle rule flags
                    elif mx >= right_x and my < btn_y:
                        if selected in defs:
                            toggle = self._find_toggle(defs[selected], mx, my,
                                                       right_x, right_w, scroll_y)
                            if toggle is not None:
                                rule_idx, flag = toggle
                                rules = defs[selected]['move_rules']
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
                                defs = copy.deepcopy(AllPieces().pieces_defs)
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
                    scroll_y = max(0, scroll_y - event.y * 20)

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
        tw = 110
        for flag in _RULE_FLAGS:
            rect = pygame.Rect(x, rule_y + 24, tw - 4, 20)
            rects[flag] = rect
            x += tw
            if x + tw > right_x + right_w:
                x = right_x
                rule_y += 26
        return rects

    def _find_toggle(self, piece_def, mx, my, right_x, right_w, scroll_y):
        """Return (rule_idx, flag) if the click lands on a toggle, else None."""
        y = 60 - scroll_y
        for i, rule in enumerate(piece_def.get('move_rules', [])):
            toggle_rects = self._rule_toggle_rects(rule, y, right_x, right_w)
            for flag, rect in toggle_rects.items():
                if rect.collidepoint(mx, my):
                    return (i, flag)
            y += 80
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

        if selected and selected in defs:
            piece_def = defs[selected]
            y = 60 - scroll_y
            hdr = self.label_font.render(f'{selected}  —  move rules', True, self.TEXT)
            self.screen.blit(hdr, (right_x, y))
            y += 32

            for i, rule in enumerate(piece_def.get('move_rules', [])):
                rule_label = self.small_font.render(f'Rule {i + 1}  deltas: {rule.get("deltas", [])}',
                                                    True, self.DIM_TEXT)
                self.screen.blit(rule_label, (right_x, y))

                toggle_rects = self._rule_toggle_rects(rule, y, right_x, right_w)
                for flag, rect in toggle_rects.items():
                    val = rule.get(flag, False)
                    bg  = self.ON_COLOR if val else self.OFF_COLOR
                    pygame.draw.rect(self.screen, bg, rect, border_radius=4)
                    ft = self.tiny_font.render(flag, True, (10, 10, 10) if val else (160, 165, 175))
                    self.screen.blit(ft, ft.get_rect(center=rect.center))
                y += 80

        self.screen.set_clip(None)

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
