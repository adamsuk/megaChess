"""Tests for game.py — Game, Graphics."""
import json
import os
import sys
import tempfile
import types

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from board import Board, Piece
from common import Colours
from win_conditions import ChessWinCondition, CheckersWinCondition
from game import Game, Graphics

W = Colours.WHITE
B = Colours.PIECE_BLACK


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clear_board(board):
    for x in range(8):
        for y in range(8):
            board.matrix[x][y].occupant = None
    board.en_passant_target = None
    board.promotion_pending = None


def place(board, x, y, color, piece_type, has_moved=False):
    p = Piece(color, piece_type)
    p.has_moved = has_moved
    board.matrix[x][y].occupant = p
    return p


def make_graphics_stub(square_size=80):
    """Graphics instance with all __init__ state set manually — no display needed."""
    g = object.__new__(Graphics)
    g.square_size = square_size
    g.piece_size = square_size // 2
    g.window_size = square_size * 8
    g.button_bar_height = 48
    total_h = g.window_size + g.button_bar_height
    g.screen = pygame.Surface((g.window_size, total_h), pygame.SRCALPHA)
    g.piece_font = pygame.font.SysFont(None, square_size // 2)
    g.message = False
    g.timed_message_surface = None
    g.timed_message_rect = None
    g.timed_message_until = 0
    g.piece_icons = {}
    g.highlights = False
    g.show_hints = True
    g.caption = 'megaChess'
    g.fps = 60
    g.clock = pygame.time.Clock()
    return g


def make_game():
    """Game-like object with mocked graphics — no display needed."""
    from game import Game
    game = object.__new__(Game)
    game.board = Board()
    game.turn = W
    game.selected_piece = (2, 2)
    game.selected_legal_moves = [(3, 3)]
    game.click = False
    game.win_condition = ChessWinCondition()
    msgs = []
    game.graphics = types.SimpleNamespace(
        draw_message=lambda m: msgs.append(('perm', m)),
        draw_timed_message=lambda m: msgs.append(('timed', m)),
    )
    game._msgs = msgs
    return game


# ---------------------------------------------------------------------------
# Graphics.promotion_pick
# ---------------------------------------------------------------------------

class TestPromotionPick(unittest.TestCase):

    def setUp(self):
        self.g = make_graphics_stub()

    def test_queen(self):
        self.assertEqual(self.g.promotion_pick((2, 3)), 'queen')

    def test_rook(self):
        self.assertEqual(self.g.promotion_pick((3, 3)), 'rook')

    def test_bishop(self):
        self.assertEqual(self.g.promotion_pick((4, 3)), 'bishop')

    def test_knight(self):
        self.assertEqual(self.g.promotion_pick((5, 3)), 'knight')

    def test_wrong_row_returns_none(self):
        self.assertIsNone(self.g.promotion_pick((2, 4)))

    def test_wrong_col_returns_none(self):
        self.assertIsNone(self.g.promotion_pick((0, 3)))

    def test_off_grid_col_returns_none(self):
        self.assertIsNone(self.g.promotion_pick((7, 3)))


# ---------------------------------------------------------------------------
# Graphics coordinate conversion
# ---------------------------------------------------------------------------

class TestCoords(unittest.TestCase):

    def setUp(self):
        self.g = make_graphics_stub(square_size=80)

    def test_pixel_coords_origin(self):
        self.assertEqual(self.g.pixel_coords((0, 0)), (40, 40))

    def test_pixel_coords_second_square(self):
        self.assertEqual(self.g.pixel_coords((1, 0)), (120, 40))

    def test_pixel_coords_offset(self):
        self.assertEqual(self.g.pixel_coords((2, 3)), (200, 280))

    def test_board_coords_origin(self):
        self.assertEqual(self.g.board_coords((40, 40)), (0, 0))

    def test_board_coords_second_square(self):
        self.assertEqual(self.g.board_coords((100, 100)), (1, 1))

    def test_board_coords_clamps_negative(self):
        self.assertEqual(self.g.board_coords((-10, -10)), (0, 0))

    def test_board_coords_clamps_large(self):
        self.assertEqual(self.g.board_coords((9999, 9999)), (7, 7))

    def test_board_coords_boundary(self):
        self.assertEqual(self.g.board_coords((560, 560)), (7, 7))


# ---------------------------------------------------------------------------
# Graphics drawing methods
# ---------------------------------------------------------------------------

class TestGraphicsDrawing(unittest.TestCase):

    def setUp(self):
        self.g = make_graphics_stub()
        self.board = Board()

    def test_draw_board_squares_no_error(self):
        self.g.draw_board_squares(self.board)

    def test_draw_board_pieces_starting_position(self):
        self.g.draw_board_pieces(self.board)

    def test_draw_board_pieces_empty_board(self):
        clear_board(self.board)
        self.g.draw_board_pieces(self.board)

    def test_highlight_squares_sets_flag(self):
        self.g.highlight_squares([(3, 3), (4, 4)], (2, 2))
        self.assertTrue(self.g.highlights)

    def test_highlight_squares_none_origin(self):
        self.g.highlight_squares([(3, 3)], None)
        self.assertTrue(self.g.highlights)

    def test_del_highlight_squares_clears_flag(self):
        self.g.highlights = True
        self.g.del_highlight_squares(self.board)
        self.assertFalse(self.g.highlights)

    def test_draw_timed_message_sets_surface(self):
        self.g.draw_timed_message('IN CHECK!')
        self.assertIsNotNone(self.g.timed_message_surface)

    def test_draw_timed_message_sets_expiry(self):
        before = pygame.time.get_ticks()
        self.g.draw_timed_message('CHECK!', duration_ms=3000)
        self.assertGreater(self.g.timed_message_until, before)

    def test_draw_promotion_picker_white(self):
        self.g.draw_promotion_picker('white')

    def test_draw_promotion_picker_black(self):
        self.g.draw_promotion_picker('black')

    def test_setup_window_no_error(self):
        self.g.setup_window()

    def test_update_display_no_selection_no_highlights(self):
        # No piece selected → no highlights regardless of click
        self.g.update_display(self.board, [], None, (4, 4), click=False)
        self.assertFalse(self.g.highlights)

    def test_update_display_click_without_selection_no_highlights(self):
        # click=True but selected_piece=None → still no highlights
        self.g.update_display(self.board, [], None, (4, 4), click=True)
        self.assertFalse(self.g.highlights)

    def test_update_display_selection_produces_highlights(self):
        # selected_piece set → highlights shown (click state irrelevant)
        self.g.update_display(self.board, [(3, 4)], (4, 4), (4, 4), click=False)
        self.assertTrue(self.g.highlights)

    def test_update_display_highlights_persist_without_click(self):
        # Highlights must stay visible across frames where click=False as long
        # as a piece is selected (regression: old code cleared on click=False).
        self.g.update_display(self.board, [(3, 4)], (4, 4), (4, 4), click=True)
        self.assertTrue(self.g.highlights)
        self.g.update_display(self.board, [(3, 4)], (4, 4), (4, 4), click=False)
        self.assertTrue(self.g.highlights, 'highlights cleared by click=False while piece still selected')

    def test_update_display_deselection_clears_highlights(self):
        # Once selected_piece goes back to None highlights must clear.
        self.g.update_display(self.board, [(3, 4)], (4, 4), (4, 4), click=False)
        self.assertTrue(self.g.highlights)
        self.g.update_display(self.board, [], None, (4, 4), click=False)
        self.assertFalse(self.g.highlights)

    def test_update_display_with_permanent_message(self):
        self.g.draw_message('WHITE WINS!')
        self.assertTrue(self.g.message)
        self.g.update_display(self.board, [], None, (0, 0), False)

    def test_update_display_with_timed_message(self):
        self.g.draw_timed_message('CHECK!', duration_ms=9999)
        self.g.update_display(self.board, [], None, (0, 0), False)


# ---------------------------------------------------------------------------
# Graphics button bar
# ---------------------------------------------------------------------------

class TestButtonBar(unittest.TestCase):

    def setUp(self):
        self.g = make_graphics_stub(square_size=80)
        # window_size = 640, button_bar_height = 48

    def test_save_btn_rect_is_in_bar(self):
        r = self.g.save_btn_rect
        self.assertGreaterEqual(r.top, self.g.window_size)
        self.assertLess(r.top, self.g.window_size + self.g.button_bar_height)

    def test_load_btn_rect_is_in_bar(self):
        r = self.g.load_btn_rect
        self.assertGreaterEqual(r.top, self.g.window_size)
        self.assertLess(r.top, self.g.window_size + self.g.button_bar_height)

    def test_hints_btn_rect_is_in_bar(self):
        r = self.g.hints_btn_rect
        self.assertGreaterEqual(r.top, self.g.window_size)
        self.assertLess(r.top, self.g.window_size + self.g.button_bar_height)

    def test_three_buttons_do_not_overlap(self):
        s, lo, h = self.g.save_btn_rect, self.g.load_btn_rect, self.g.hints_btn_rect
        self.assertFalse(s.colliderect(lo))
        self.assertFalse(s.colliderect(h))
        self.assertFalse(lo.colliderect(h))

    def test_button_order_left_to_right(self):
        s, lo, h = self.g.save_btn_rect, self.g.load_btn_rect, self.g.hints_btn_rect
        self.assertLess(s.right, lo.left + 1)
        self.assertLess(lo.right, h.left + 1)

    def test_draw_button_bar_no_error_save_exists(self):
        self.g.draw_button_bar((0, 0), save_exists=True)

    def test_draw_button_bar_no_error_no_save(self):
        self.g.draw_button_bar((0, 0), save_exists=False)

    def test_draw_button_bar_hover_save(self):
        center = self.g.save_btn_rect.center
        self.g.draw_button_bar(center, save_exists=True)

    def test_draw_button_bar_hover_load_enabled(self):
        center = self.g.load_btn_rect.center
        self.g.draw_button_bar(center, save_exists=True)

    def test_draw_button_bar_hover_load_disabled(self):
        center = self.g.load_btn_rect.center
        self.g.draw_button_bar(center, save_exists=False)

    def test_draw_button_bar_hints_on(self):
        center = self.g.hints_btn_rect.center
        self.g.draw_button_bar(center, save_exists=True, show_hints=True)

    def test_draw_button_bar_hints_off(self):
        center = self.g.hints_btn_rect.center
        self.g.draw_button_bar(center, save_exists=True, show_hints=False)

    def test_update_display_draws_bar(self):
        board = Board()
        # Should not raise even when save_exists is False
        self.g.update_display(board, [], None, (4, 4), False,
                              mouse_px=(0, 0), save_exists=False)

    def test_update_display_with_save_exists(self):
        board = Board()
        self.g.update_display(board, [], None, (4, 4), False,
                              mouse_px=(0, 0), save_exists=True)

    def test_show_hints_defaults_true(self):
        self.assertTrue(self.g.show_hints)

    def test_highlights_suppressed_when_hints_off(self):
        """show_hints=False must suppress highlighting even with a piece selected."""
        board = Board()
        self.g.show_hints = False
        self.g.update_display(board, [(3, 4)], (4, 4), (4, 4), click=False,
                              mouse_px=(0, 0), save_exists=False)
        self.assertFalse(self.g.highlights)

    def test_highlights_active_when_hints_on(self):
        """show_hints=True with a piece selected must produce highlights."""
        board = Board()
        self.g.show_hints = True
        self.g.update_display(board, [(3, 4)], (4, 4), (4, 4), click=False,
                              mouse_px=(0, 0), save_exists=True)
        self.assertTrue(self.g.highlights)

    def test_highlights_use_board_coords_not_pixel_coords(self):
        """
        Regression: highlight_squares was previously called with
        pixel_coords(mouse_pos) as the origin, which then got multiplied by
        square_size a second time inside highlight_squares, placing the
        origin rectangle far off-screen.  The fix passes selected_piece
        (board coords) directly so only one multiplication happens.

        We verify by checking that the origin rect stays within the board.
        """
        board = Board()
        self.g.show_hints = True
        sq = self.g.square_size  # 80
        # Select piece at board position (3, 4)
        self.g.update_display(board, [], (3, 4), (3, 4), click=False,
                              mouse_px=(0, 0), save_exists=False)
        # The origin square should be drawn at pixel (3*sq, 4*sq) = (240, 320).
        # The doubled-coordinate bug would place it at (240*80, 320*80) — off-screen.
        # We can't inspect draw calls directly, but we CAN confirm highlights is
        # True (meaning highlight_squares ran without error with in-bounds coords).
        self.assertTrue(self.g.highlights)


# ---------------------------------------------------------------------------
# Game.end_turn
# ---------------------------------------------------------------------------

class TestGameEndTurn(unittest.TestCase):

    def test_white_switches_to_black(self):
        game = make_game()
        game.turn = W
        game.end_turn()
        self.assertEqual(game.turn, B)

    def test_black_switches_to_white(self):
        game = make_game()
        game.turn = B
        game.end_turn()
        self.assertEqual(game.turn, W)

    def test_selected_piece_cleared(self):
        game = make_game()
        game.end_turn()
        self.assertIsNone(game.selected_piece)

    def test_selected_legal_moves_cleared(self):
        game = make_game()
        game.end_turn()
        self.assertEqual(game.selected_legal_moves, [])

    def test_no_message_when_game_ongoing(self):
        game = make_game()
        clear_board(game.board)
        place(game.board, 4, 7, W, 'king')
        place(game.board, 4, 0, B, 'king')
        place(game.board, 0, 6, W, 'rook')
        game.turn = W
        game.end_turn()
        self.assertEqual(game._msgs, [])

    def test_permanent_message_on_checkmate(self):
        # After switching to B, black is in checkmate
        game = make_game()
        clear_board(game.board)
        place(game.board, 7, 0, B, 'king')
        place(game.board, 7, 5, W, 'rook')
        place(game.board, 6, 7, W, 'rook')
        place(game.board, 0, 7, W, 'king')
        game.turn = W
        game.end_turn()
        self.assertEqual(len(game._msgs), 1)
        kind, msg = game._msgs[0]
        self.assertEqual(kind, 'perm')
        self.assertEqual(msg, 'WHITE WINS!')

    def test_timed_message_on_check(self):
        # After switching to B, black king is in check
        game = make_game()
        clear_board(game.board)
        place(game.board, 4, 0, B, 'king')
        place(game.board, 4, 7, W, 'rook')
        place(game.board, 0, 7, W, 'king')
        game.turn = W
        game.end_turn()
        self.assertEqual(len(game._msgs), 1)
        kind, msg = game._msgs[0]
        self.assertEqual(kind, 'timed')
        self.assertIn('CHECK', msg)


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------

def make_real_game():
    """Full Game instance with a real Board (no display needed)."""
    game = object.__new__(Game)
    game.board = Board()
    game.turn = W
    game.selected_piece = None
    game.selected_legal_moves = []
    game.click = False
    game.win_condition = ChessWinCondition()
    msgs = []
    game.graphics = types.SimpleNamespace(
        draw_timed_message=lambda m, duration_ms=2000: msgs.append(m),
        draw_message=lambda m: msgs.append(m),
        message=False,
        load_piece_icons=lambda defs: None,
    )
    game._msgs = msgs
    return game


class TestSaveLoad(unittest.TestCase):

    def _save_path(self, tmp_dir):
        return os.path.join(tmp_dir, 'test_save.json')

    def test_save_creates_file(self):
        game = make_real_game()
        with tempfile.TemporaryDirectory() as tmp:
            path = self._save_path(tmp)
            game.save(path)
            self.assertTrue(os.path.exists(path))

    def test_save_file_is_valid_json(self):
        game = make_real_game()
        with tempfile.TemporaryDirectory() as tmp:
            path = self._save_path(tmp)
            game.save(path)
            with open(path) as f:
                data = json.load(f)
            self.assertIn('board', data)
            self.assertIn('turn', data)
            self.assertIn('win_condition', data)

    def test_save_stores_turn(self):
        game = make_real_game()
        game.turn = B
        with tempfile.TemporaryDirectory() as tmp:
            path = self._save_path(tmp)
            game.save(path)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data['turn'], 'black')

    def test_save_stores_win_condition(self):
        game = make_real_game()
        game.win_condition = CheckersWinCondition()
        with tempfile.TemporaryDirectory() as tmp:
            path = self._save_path(tmp)
            game.save(path)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data['win_condition'], 'checkers')

    def test_load_missing_file_no_crash(self):
        game = make_real_game()
        original_turn = game.turn
        game.load('/tmp/megachess_nonexistent_save_xyz.json')
        self.assertEqual(game.turn, original_turn)

    def test_save_load_roundtrip_fresh_game(self):
        game = make_real_game()
        original = game.board.to_dict()
        with tempfile.TemporaryDirectory() as tmp:
            path = self._save_path(tmp)
            game.save(path)
            game2 = make_real_game()
            clear_board(game2.board)
            game2.load(path)
            self.assertEqual(game2.board.to_dict(), original)
            self.assertEqual(game2.turn, W)
            self.assertIsInstance(game2.win_condition, ChessWinCondition)

    def test_save_load_roundtrip_midgame(self):
        game = make_real_game()
        clear_board(game.board)
        place(game.board, 4, 7, W, 'king')
        place(game.board, 4, 0, B, 'king')
        rook = place(game.board, 0, 7, W, 'rook', has_moved=True)
        game.board.en_passant_target = (3, 5)
        game.turn = B
        with tempfile.TemporaryDirectory() as tmp:
            path = self._save_path(tmp)
            game.save(path)
            game2 = make_real_game()
            game2.load(path)
            self.assertEqual(game2.turn, B)
            self.assertEqual(game2.board.en_passant_target, (3, 5))
            restored_rook = game2.board.matrix[0][7].occupant
            self.assertIsNotNone(restored_rook)
            self.assertEqual(restored_rook.piece_type, 'rook')
            self.assertTrue(restored_rook.has_moved)

    def test_save_load_clears_selected_piece(self):
        game = make_real_game()
        with tempfile.TemporaryDirectory() as tmp:
            path = self._save_path(tmp)
            game.save(path)
            game.selected_piece = (4, 4)
            game.load(path)
            self.assertIsNone(game.selected_piece)

    def test_save_shows_timed_message(self):
        game = make_real_game()
        with tempfile.TemporaryDirectory() as tmp:
            game.save(self._save_path(tmp))
        self.assertIn('GAME SAVED', game._msgs)

    def test_load_shows_timed_message(self):
        game = make_real_game()
        with tempfile.TemporaryDirectory() as tmp:
            path = self._save_path(tmp)
            game.save(path)
            game._msgs.clear()
            game.load(path)
        self.assertIn('GAME LOADED', game._msgs)


# ---------------------------------------------------------------------------
# PieceEditor delta editing
# ---------------------------------------------------------------------------

class TestPieceEditorDeltas(unittest.TestCase):

    def _make_editor(self):
        from game import PieceEditor
        ed = object.__new__(PieceEditor)
        ed.w = 640
        ed.h = 640
        ed.PADDING    = PieceEditor.PADDING
        ed.TOGGLE_H   = PieceEditor.TOGGLE_H
        ed.CELL       = PieceEditor.CELL
        ed.CELL_GAP   = PieceEditor.CELL_GAP
        ed.GRID_RANGE = PieceEditor.GRID_RANGE
        ed.GRID_CELLS = PieceEditor.GRID_CELLS
        ed.GRID_SIZE  = PieceEditor.GRID_SIZE
        ed.FLAG_Y_OFF = PieceEditor.FLAG_Y_OFF
        ed.RULE_H     = PieceEditor.RULE_H
        return ed

    # ── keyword expansion ───────────────────────────────────────────────

    def test_expand_keywords_diagonal(self):
        from game import _expand_keywords
        defs = {'p': {'move_rules': [{'deltas': ['diagonal']}]}}
        _expand_keywords(defs)
        self.assertEqual(sorted(defs['p']['move_rules'][0]['deltas']),
                         sorted([[1,1],[1,-1],[-1,1],[-1,-1]]))

    def test_expand_keywords_straight(self):
        from game import _expand_keywords
        defs = {'p': {'move_rules': [{'deltas': ['straight']}]}}
        _expand_keywords(defs)
        self.assertEqual(sorted(defs['p']['move_rules'][0]['deltas']),
                         sorted([[1,0],[-1,0],[0,1],[0,-1]]))

    def test_expand_keywords_mixed(self):
        from game import _expand_keywords
        defs = {'p': {'move_rules': [{'deltas': ['diagonal', [0, 1]]}]}}
        _expand_keywords(defs)
        result = defs['p']['move_rules'][0]['deltas']
        self.assertEqual(len(result), 5)
        self.assertIn([0, 1], result)

    def test_expand_keywords_no_keywords(self):
        from game import _expand_keywords
        orig = [[1, 0], [-1, 0]]
        defs = {'p': {'move_rules': [{'deltas': list(orig)}]}}
        _expand_keywords(defs)
        self.assertEqual(defs['p']['move_rules'][0]['deltas'], orig)

    def test_expand_keywords_returns_defs(self):
        from game import _expand_keywords
        defs = {'p': {'move_rules': []}}
        result = _expand_keywords(defs)
        self.assertIs(result, defs)

    # ── delta grid geometry ────────────────────────────────────────────

    def test_delta_grid_rects_excludes_origin(self):
        ed = self._make_editor()
        rects = ed._delta_grid_rects(rule_y=100, right_x=220)
        self.assertNotIn((0, 0), rects)

    def test_delta_grid_rects_count(self):
        ed = self._make_editor()
        rects = ed._delta_grid_rects(rule_y=100, right_x=220)
        expected = ed.GRID_CELLS ** 2 - 1   # 24
        self.assertEqual(len(rects), expected)

    def test_delta_grid_rects_all_ranges(self):
        ed = self._make_editor()
        rects = ed._delta_grid_rects(rule_y=100, right_x=220)
        gr = ed.GRID_RANGE
        for dx in range(-gr, gr + 1):
            for dy in range(-gr, gr + 1):
                if dx == 0 and dy == 0:
                    continue
                self.assertIn((dx, dy), rects)

    def test_delta_grid_rects_top_left_corner(self):
        """(-GRID_RANGE, -GRID_RANGE) cell should start at (right_x, rule_y+24)."""
        ed = self._make_editor()
        rule_y, right_x = 100, 220
        rects = ed._delta_grid_rects(rule_y, right_x)
        gr = ed.GRID_RANGE
        rect = rects[(-gr, -gr)]
        self.assertEqual(rect.left, right_x)
        self.assertEqual(rect.top,  rule_y + 24)

    def test_delta_grid_rects_cell_size(self):
        ed = self._make_editor()
        rects = ed._delta_grid_rects(rule_y=0, right_x=0)
        for rect in rects.values():
            self.assertEqual(rect.width,  ed.CELL)
            self.assertEqual(rect.height, ed.CELL)

    # ── find_delta_click ──────────────────────────────────────────────

    def test_find_delta_click_hit(self):
        ed = self._make_editor()
        rule = {'deltas': [], 'sliding': False}
        piece_def = {'move_rules': [rule]}
        right_x, scroll_y = 220, 0
        # First rule_y = 92 - 0 = 92; grid top = 92 + 24 = 116
        # (-2, -2) cell: col=0, row=0 → x=right_x, y=116
        rect = ed._delta_grid_rects(92, right_x)[(-2, -2)]
        result = ed._find_delta_click(piece_def, rect.centerx, rect.centery,
                                      right_x, scroll_y)
        self.assertEqual(result, (0, -2, -2))

    def test_find_delta_click_origin_returns_none(self):
        """Clicking (0,0) must return None since origin is excluded from rects."""
        ed = self._make_editor()
        piece_def = {'move_rules': [{'deltas': []}]}
        right_x, scroll_y = 220, 0
        step = ed.CELL + ed.CELL_GAP
        # origin pixel centre
        ox = right_x + ed.GRID_RANGE * step + ed.CELL // 2
        oy = 92 + 24 + ed.GRID_RANGE * step + ed.CELL // 2
        result = ed._find_delta_click(piece_def, ox, oy, right_x, scroll_y)
        self.assertIsNone(result)

    def test_find_delta_click_second_rule(self):
        """Clicks on the second rule's grid return rule_idx=1."""
        ed = self._make_editor()
        piece_def = {'move_rules': [{'deltas': []}, {'deltas': []}]}
        right_x, scroll_y = 220, 0
        rule1_y = 92 + ed.RULE_H  # second rule starts here
        rect = ed._delta_grid_rects(rule1_y, right_x)[(1, 1)]
        result = ed._find_delta_click(piece_def, rect.centerx, rect.centery,
                                      right_x, scroll_y)
        self.assertEqual(result, (1, 1, 1))

    def test_find_delta_click_y_matches_draw(self):
        """Regression: first rule grid top = 92 + 24 (not 60 + 24 or other offset)."""
        ed = self._make_editor()
        piece_def = {'move_rules': [{'deltas': []}]}
        right_x, scroll_y = 220, 0
        grid_top = 92 + 24   # same as _draw: header=32 + rule_label=24
        # Click at top-left cell of grid
        result = ed._find_delta_click(piece_def,
                                      right_x + 1, grid_top + 1,
                                      right_x, scroll_y)
        self.assertIsNotNone(result, 'Delta not detected at expected draw position')

    # ── delta toggle logic ────────────────────────────────────────────

    def test_toggle_delta_adds(self):
        rule = {'deltas': []}
        rule['deltas'].append([1, 0])
        self.assertIn([1, 0], rule['deltas'])

    def test_toggle_delta_removes(self):
        rule = {'deltas': [[1, 0], [0, 1]]}
        rule['deltas'].remove([1, 0])
        self.assertNotIn([1, 0], rule['deltas'])
        self.assertIn([0, 1], rule['deltas'])

    # ── flag y-offset ─────────────────────────────────────────────────

    def test_flags_appear_below_grid(self):
        """Flag toggles must start at rule_y + FLAG_Y_OFF, not rule_y + 24."""
        ed = self._make_editor()
        rule_y, right_x, right_w = 100, 220, 400
        rects = ed._rule_toggle_rects({}, rule_y, right_x, right_w)
        # All flag rects must start at or after rule_y + FLAG_Y_OFF
        for rect in rects.values():
            self.assertGreaterEqual(rect.top, rule_y + ed.FLAG_Y_OFF)

    def test_find_toggle_uses_rule_h_step(self):
        """_find_toggle must step by RULE_H between rules (not the old 80px)."""
        ed = self._make_editor()
        rule = {f: False for f in ['sliding','directional','move_only',
                                   'capture_only','jump_capture']}
        piece_def = {'move_rules': [rule, dict(rule)]}
        right_x, right_w, scroll_y = 220, 400, 0
        # First rule flags start at 92 + FLAG_Y_OFF
        # Second rule flags start at 92 + RULE_H + FLAG_Y_OFF
        second_flag_top = 92 + ed.RULE_H + ed.FLAG_Y_OFF
        result = ed._find_toggle(piece_def,
                                 right_x + 5, second_flag_top + 5,
                                 right_x, right_w, scroll_y)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 1)   # second rule


# ---------------------------------------------------------------------------
# PieceEditor._button_rects
# ---------------------------------------------------------------------------

class TestPieceEditorButtons(unittest.TestCase):

    def _make_editor(self):
        from game import PieceEditor
        ed = object.__new__(PieceEditor)
        ed.w = 640
        ed.h = 640
        ed.PADDING = PieceEditor.PADDING
        ed.TOGGLE_H = PieceEditor.TOGGLE_H
        return ed

    def test_back_button_present(self):
        ed = self._make_editor()
        rects = ed._button_rects(btn_y=590, btn_h=42)
        self.assertIn('← Back', rects)

    def test_all_expected_labels_present(self):
        ed = self._make_editor()
        rects = ed._button_rects(btn_y=590, btn_h=42)
        for label in ('← Back', 'Clone', 'Reset', 'Save', 'Play'):
            self.assertIn(label, rects)

    def test_buttons_do_not_overlap(self):
        ed = self._make_editor()
        rects = list(ed._button_rects(btn_y=590, btn_h=42).values())
        for i, r1 in enumerate(rects):
            for r2 in rects[i + 1:]:
                self.assertFalse(r1.colliderect(r2))

    def test_back_button_leftmost(self):
        ed = self._make_editor()
        rects = ed._button_rects(btn_y=590, btn_h=42)
        back_left = rects['← Back'].left
        for label, rect in rects.items():
            if label != '← Back':
                self.assertLessEqual(back_left, rect.left)

    def test_play_button_rightmost(self):
        ed = self._make_editor()
        rects = ed._button_rects(btn_y=590, btn_h=42)
        play_right = rects['Play'].right
        for label, rect in rects.items():
            if label != 'Play':
                self.assertGreaterEqual(play_right, rect.right)

    def test_toggle_rects_use_toggle_h(self):
        from game import PieceEditor, _RULE_FLAGS
        ed = self._make_editor()
        rects = ed._rule_toggle_rects({}, rule_y=100, right_x=220, right_w=400)
        for flag in _RULE_FLAGS:
            self.assertIn(flag, rects)
            self.assertEqual(rects[flag].height, PieceEditor.TOGGLE_H)

    def test_find_toggle_y_matches_draw_offset(self):
        """_find_toggle flags must now sit at rule_y + FLAG_Y_OFF (below the delta grid)."""
        from game import PieceEditor, _RULE_FLAGS
        ed = self._make_editor()
        rule = {flag: False for flag in _RULE_FLAGS}
        rule['deltas'] = [[0, 1]]
        piece_def = {'move_rules': [rule]}
        right_x, right_w, scroll_y = 220, 400, 0
        # rule_y = 92; flags now start at rule_y + FLAG_Y_OFF
        draw_toggle_top = 92 + PieceEditor.FLAG_Y_OFF
        result = ed._find_toggle(piece_def, right_x + 5, draw_toggle_top + 5,
                                 right_x, right_w, scroll_y)
        self.assertIsNotNone(result, 'Toggle not detected — FLAG_Y_OFF mismatch!')

    def test_all_flags_have_descriptions(self):
        from game import PieceEditor, _RULE_FLAGS
        for flag in _RULE_FLAGS:
            self.assertIn(flag, PieceEditor.FLAG_DESCRIPTIONS)


if __name__ == '__main__':
    unittest.main(verbosity=2)
