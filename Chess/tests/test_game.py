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
    g.screen = pygame.display.get_surface() or pygame.Surface((640, 640))
    g.square_size = square_size
    g.piece_size = square_size // 2
    g.window_size = square_size * 8
    g.piece_font = pygame.font.SysFont(None, square_size // 2)
    g.message = False
    g.timed_message_surface = None
    g.timed_message_rect = None
    g.timed_message_until = 0
    g.piece_icons = {}
    g.highlights = False
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

    def test_update_display_no_click(self):
        self.g.update_display(self.board, [], None, (4, 4), False)

    def test_update_display_with_click_and_moves(self):
        self.g.update_display(self.board, [(3, 4)], (4, 4), (4, 4), True)

    def test_update_display_with_permanent_message(self):
        self.g.draw_message('WHITE WINS!')
        self.assertTrue(self.g.message)
        self.g.update_display(self.board, [], None, (0, 0), False)

    def test_update_display_with_timed_message(self):
        self.g.draw_timed_message('CHECK!', duration_ms=9999)
        self.g.update_display(self.board, [], None, (0, 0), False)


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


if __name__ == '__main__':
    unittest.main(verbosity=2)
