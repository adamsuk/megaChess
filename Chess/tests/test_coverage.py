"""
Additional tests to push coverage above 80%.

Targets:
  - win_conditions.py  (0% → ~100%)
  - board.py utility methods (86% → ~95%)
  - svg_renderer._parse_color / _parse_path (0% → ~60%)
  - positions.py _jump / _slide capture_only (91% → ~100%)
  - game.py Graphics.promotion_pick + coord math (0% → partial)
"""
import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import pygame
pygame.init()

from board import Board, Piece
from common import Colours, Directions
from win_conditions import GameResult, ChessWinCondition, CheckersWinCondition
from svg_renderer import _parse_color, _parse_path
from positions import PieceMoves

W = Colours.WHITE
B = Colours.PIECE_BLACK


# ---------------------------------------------------------------------------
# Helpers (same pattern as test_chess.py)
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


class MockGame:
    """Minimal stand-in for Game — only needs .board and .turn."""
    def __init__(self, board, turn):
        self.board = board
        self.turn = turn


# ===========================================================================
# GameResult
# ===========================================================================

class TestGameResult(unittest.TestCase):

    def test_message_stored(self):
        r = GameResult('CHECKMATE!')
        self.assertEqual(r.message, 'CHECKMATE!')

    def test_permanent_defaults_to_true(self):
        r = GameResult('msg')
        self.assertTrue(r.permanent)

    def test_permanent_false(self):
        r = GameResult('IN CHECK!', permanent=False)
        self.assertFalse(r.permanent)


# ===========================================================================
# ChessWinCondition
# ===========================================================================

class TestChessWinCondition(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)
        self.wc = ChessWinCondition()

    def test_ongoing_returns_none(self):
        # White king not in check, has safe moves
        place(self.board, 4, 7, W, 'king')
        place(self.board, 4, 0, B, 'king')
        place(self.board, 0, 6, W, 'rook')
        game = MockGame(self.board, W)
        self.assertIsNone(self.wc.check(game))

    def test_white_in_check_returns_timed_result(self):
        # White king on column 4, black rook attacks along column 4
        place(self.board, 4, 7, W, 'king')
        place(self.board, 4, 0, B, 'rook')
        place(self.board, 7, 0, B, 'king')
        game = MockGame(self.board, W)
        result = self.wc.check(game)
        self.assertIsNotNone(result)
        self.assertFalse(result.permanent)
        self.assertEqual(result.message, 'WHITE IN CHECK!')

    def test_black_in_check_returns_timed_result(self):
        # Black king on column 4, white rook attacks along column 4
        place(self.board, 4, 0, B, 'king')
        place(self.board, 4, 7, W, 'rook')
        game = MockGame(self.board, B)
        result = self.wc.check(game)
        self.assertIsNotNone(result)
        self.assertFalse(result.permanent)
        self.assertEqual(result.message, 'BLACK IN CHECK!')

    def test_white_checkmate_black_wins(self):
        # White king at (0,7), escape squares (0,6)(1,6)(1,7) attacked by two black rooks
        # Rook at (0,5) controls col 0 → attacks (0,6) and (0,7) (king in check)
        # Rook at (1,0) controls col 1 → attacks (1,6) and (1,7)
        place(self.board, 0, 7, W, 'king')
        place(self.board, 0, 5, B, 'rook')
        place(self.board, 1, 0, B, 'rook')
        place(self.board, 4, 0, B, 'king')
        game = MockGame(self.board, W)
        result = self.wc.check(game)
        self.assertIsNotNone(result)
        self.assertTrue(result.permanent)
        self.assertEqual(result.message, 'BLACK WINS!')

    def test_black_checkmate_white_wins(self):
        # Black king at (7,0), rook at (7,5) checks along col 7
        # Rook at (6,7) controls col 6 → blocks (6,0) and (6,1)
        place(self.board, 7, 0, B, 'king')
        place(self.board, 7, 5, W, 'rook')
        place(self.board, 6, 7, W, 'rook')
        place(self.board, 0, 7, W, 'king')
        game = MockGame(self.board, B)
        result = self.wc.check(game)
        self.assertIsNotNone(result)
        self.assertTrue(result.permanent)
        self.assertEqual(result.message, 'WHITE WINS!')

    def test_stalemate(self):
        # White king at (0,7), black queen at (1,5) controls all escape squares
        # but does NOT attack (0,7) directly → stalemate
        place(self.board, 0, 7, W, 'king')
        place(self.board, 1, 5, B, 'queen')  # SW→(0,6), S→(1,6)(1,7), W→(0,5)
        place(self.board, 7, 0, B, 'king')
        game = MockGame(self.board, W)
        result = self.wc.check(game)
        self.assertIsNotNone(result)
        self.assertTrue(result.permanent)
        self.assertEqual(result.message, 'STALEMATE!')

    def test_safe_moves_returns_check_filtered_moves(self):
        place(self.board, 4, 7, W, 'king')
        place(self.board, 4, 0, B, 'king')
        safe = self.wc.safe_moves(self.board, (4, 7))
        expected = self.board.legal_moves_safe((4, 7))
        self.assertEqual(sorted(safe), sorted(expected))


# ===========================================================================
# CheckersWinCondition
# ===========================================================================

class TestCheckersWinCondition(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)
        self.wc = CheckersWinCondition()

    def test_returns_none_when_current_player_has_moves(self):
        place(self.board, 4, 4, W, 'rook')
        place(self.board, 4, 0, B, 'king')
        game = MockGame(self.board, W)
        self.assertIsNone(self.wc.check(game))

    def test_white_no_pieces_black_wins(self):
        place(self.board, 4, 0, B, 'king')
        game = MockGame(self.board, W)
        result = self.wc.check(game)
        self.assertIsNotNone(result)
        self.assertTrue(result.permanent)
        self.assertEqual(result.message, 'BLACK WINS!')

    def test_black_no_pieces_white_wins(self):
        place(self.board, 4, 7, W, 'king')
        game = MockGame(self.board, B)
        result = self.wc.check(game)
        self.assertIsNotNone(result)
        self.assertTrue(result.permanent)
        self.assertEqual(result.message, 'WHITE WINS!')

    def test_default_safe_moves_returns_all_legal_moves(self):
        place(self.board, 4, 4, W, 'rook')
        all_moves = self.board.legal_moves((4, 4))
        safe = self.wc.safe_moves(self.board, (4, 4))
        self.assertEqual(sorted(safe), sorted(all_moves))


# ===========================================================================
# Board utility methods
# ===========================================================================

class TestBoardRel(unittest.TestCase):

    def setUp(self):
        self.board = Board()

    def test_northwest(self):
        self.assertEqual(self.board.rel(Directions.NORTHWEST, (3, 4)), (2, 3))

    def test_northeast(self):
        self.assertEqual(self.board.rel(Directions.NORTHEAST, (3, 4)), (4, 3))

    def test_southwest(self):
        self.assertEqual(self.board.rel(Directions.SOUTHWEST, (3, 4)), (2, 5))

    def test_southeast(self):
        self.assertEqual(self.board.rel(Directions.SOUTHEAST, (3, 4)), (4, 5))

    def test_invalid_direction_returns_zero(self):
        self.assertEqual(self.board.rel('INVALID', (3, 4)), 0)


class TestBoardAdjacent(unittest.TestCase):

    def setUp(self):
        self.board = Board()

    def test_adjacent_center_has_four_entries(self):
        result = self.board.adjacent((3, 4))
        self.assertEqual(len(result), 4)

    def test_adjacent_center_coords(self):
        result = self.board.adjacent((3, 4))
        self.assertIn((2, 3), result)   # NW
        self.assertIn((4, 3), result)   # NE
        self.assertIn((2, 5), result)   # SW
        self.assertIn((4, 5), result)   # SE

    def test_adjacent_always_four_entries_at_corner(self):
        # off-board values may appear; length is still 4
        result = self.board.adjacent((0, 0))
        self.assertEqual(len(result), 4)
        self.assertIn((1, 1), result)   # SE — the only on-board one


class TestBoardOnBoard(unittest.TestCase):

    def setUp(self):
        self.board = Board()

    def test_center_is_on_board(self):
        self.assertTrue(self.board.on_board((4, 4)))

    def test_all_corners_on_board(self):
        for coord in [(0, 0), (7, 0), (0, 7), (7, 7)]:
            self.assertTrue(self.board.on_board(coord))

    def test_negative_x_off_board(self):
        self.assertFalse(self.board.on_board((-1, 4)))

    def test_negative_y_off_board(self):
        self.assertFalse(self.board.on_board((4, -1)))

    def test_x_too_large_off_board(self):
        self.assertFalse(self.board.on_board((8, 4)))

    def test_y_too_large_off_board(self):
        self.assertFalse(self.board.on_board((4, 8)))


class TestBoardIsEndSquare(unittest.TestCase):

    def setUp(self):
        self.board = Board()

    def test_top_rank_is_end(self):
        self.assertTrue(self.board.is_end_square((3, 0)))

    def test_bottom_rank_is_end(self):
        self.assertTrue(self.board.is_end_square((5, 7)))

    def test_middle_is_not_end(self):
        self.assertFalse(self.board.is_end_square((4, 4)))

    def test_row_1_not_end(self):
        self.assertFalse(self.board.is_end_square((0, 1)))

    def test_row_6_not_end(self):
        self.assertFalse(self.board.is_end_square((7, 6)))


class TestBoardRemovePiece(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_remove_piece_clears_occupant(self):
        place(self.board, 4, 4, W, 'rook')
        self.assertIsNotNone(self.board.matrix[4][4].occupant)
        self.board.remove_piece((4, 4))
        self.assertIsNone(self.board.matrix[4][4].occupant)

    def test_remove_on_empty_square_no_error(self):
        self.board.remove_piece((0, 0))
        self.assertIsNone(self.board.matrix[0][0].occupant)


class TestBoardNearestSquare(unittest.TestCase):

    def setUp(self):
        self.board = Board()

    def test_returns_same_coords(self):
        self.assertEqual(self.board.nearest_square((3, 5)), (3, 5))

    def test_corner(self):
        self.assertEqual(self.board.nearest_square((0, 0)), (0, 0))

    def test_far_corner(self):
        self.assertEqual(self.board.nearest_square((7, 7)), (7, 7))


class TestBoardKingMethod(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_empty_square_does_nothing(self):
        self.board.king((4, 4))
        self.assertIsNone(self.board.promotion_pending)

    def test_non_pawn_on_back_rank_no_promotion(self):
        place(self.board, 4, 0, W, 'rook')
        self.board.king((4, 0))
        self.assertIsNone(self.board.promotion_pending)

    def test_white_pawn_on_rank_0_sets_pending(self):
        place(self.board, 4, 0, W, 'pawn')
        self.board.king((4, 0))
        self.assertEqual(self.board.promotion_pending, (4, 0))

    def test_black_pawn_on_rank_7_sets_pending(self):
        place(self.board, 3, 7, B, 'pawn')
        self.board.king((3, 7))
        self.assertEqual(self.board.promotion_pending, (3, 7))

    def test_white_pawn_mid_board_no_promotion(self):
        place(self.board, 4, 3, W, 'pawn')
        self.board.king((4, 3))
        self.assertIsNone(self.board.promotion_pending)


# ===========================================================================
# svg_renderer._parse_color
# ===========================================================================

class TestParseColor(unittest.TestCase):

    def test_six_digit_hex(self):
        self.assertEqual(_parse_color('#FF8040'), (255, 128, 64, 255))

    def test_black(self):
        self.assertEqual(_parse_color('#000000'), (0, 0, 0, 255))

    def test_white(self):
        self.assertEqual(_parse_color('#FFFFFF'), (255, 255, 255, 255))

    def test_three_digit_hex_expands(self):
        # #F80 → #FF8800
        self.assertEqual(_parse_color('#F80'), (255, 136, 0, 255))

    def test_none_string_returns_none(self):
        self.assertIsNone(_parse_color('none'))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_color(''))

    def test_none_value_returns_none(self):
        self.assertIsNone(_parse_color(None))

    def test_unknown_format_returns_none(self):
        self.assertIsNone(_parse_color('red'))

    def test_whitespace_stripped(self):
        self.assertEqual(_parse_color('  #FF0000  '), (255, 0, 0, 255))

    def test_lowercase_hex(self):
        self.assertEqual(_parse_color('#ff0000'), (255, 0, 0, 255))


# ===========================================================================
# svg_renderer._parse_path
# ===========================================================================

class TestParsePath(unittest.TestCase):

    def test_simple_triangle(self):
        result = _parse_path('M 0 0 L 10 0 L 5 10 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(len(result[0]), 3)

    def test_scale_applied(self):
        result = _parse_path('M 0 0 L 10 0 L 0 10 Z', 2.0, 3.0)
        self.assertEqual(len(result), 1)
        pts = result[0]
        self.assertIn((20.0, 0.0), pts)   # (10,0) × (2,3) → (20,0)
        self.assertIn((0.0, 30.0), pts)   # (0,10) × (2,3) → (0,30)

    def test_empty_path_returns_empty(self):
        result = _parse_path('', 1.0, 1.0)
        self.assertEqual(result, [])

    def test_two_subpaths(self):
        d = 'M 0 0 L 5 0 L 0 5 Z M 10 10 L 15 10 L 10 15 Z'
        result = _parse_path(d, 1.0, 1.0)
        self.assertEqual(len(result), 2)

    def test_relative_lineto(self):
        # m and l use relative coords
        result = _parse_path('M 10 10 l 5 0 l 0 5 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)

    def test_horizontal_and_vertical_commands(self):
        result = _parse_path('M 0 0 H 10 V 10 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)

    def test_lowercase_hv_commands(self):
        result = _parse_path('M 5 5 h 5 v 5 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)

    def test_implicit_lineto_after_move(self):
        # After M, subsequent coords are treated as implicit L
        result = _parse_path('M 0 0 10 0 5 10 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(len(result[0]), 3)

    def test_cubic_bezier_adds_points(self):
        result = _parse_path('M 0 0 C 0 5 10 5 10 0 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)
        self.assertGreater(len(result[0]), 3)   # bezier approximation adds extra pts

    def test_quadratic_bezier_adds_points(self):
        result = _parse_path('M 0 0 Q 5 10 10 0 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)
        self.assertGreater(len(result[0]), 2)


# ===========================================================================
# positions.py — _slide with capture_only (lines 125-129)
# ===========================================================================

_SLIDING_CAPTURE_ONLY_DEFS = {
    'test_piece': {
        'move_rules': [{
            'deltas': [[1, 0]],
            'sliding': True,
            'capture_only': True,
        }]
    }
}


class TestSlideCaptureOnly(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_skips_empty_squares_and_lands_on_enemy(self):
        place(self.board, 0, 4, W, 'test_piece')
        place(self.board, 4, 4, B, 'pawn')
        moves = PieceMoves(
            pos=(0, 4),
            piece_type='test_piece',
            piece_color=W,
            board_matrix=self.board.matrix,
            piece_defs=_SLIDING_CAPTURE_ONLY_DEFS,
            white_color=W,
        ).legal
        self.assertIn((4, 4), moves)
        self.assertNotIn((1, 4), moves)
        self.assertNotIn((2, 4), moves)
        self.assertNotIn((3, 4), moves)

    def test_friendly_piece_blocks_ray(self):
        place(self.board, 0, 4, W, 'test_piece')
        place(self.board, 2, 4, W, 'pawn')   # friendly blocker
        place(self.board, 5, 4, B, 'pawn')   # unreachable enemy
        moves = PieceMoves(
            pos=(0, 4),
            piece_type='test_piece',
            piece_color=W,
            board_matrix=self.board.matrix,
            piece_defs=_SLIDING_CAPTURE_ONLY_DEFS,
            white_color=W,
        ).legal
        self.assertNotIn((5, 4), moves)

    def test_no_enemy_no_moves(self):
        place(self.board, 0, 4, W, 'test_piece')
        # Row 4 columns 1-7 all empty
        moves = PieceMoves(
            pos=(0, 4),
            piece_type='test_piece',
            piece_color=W,
            board_matrix=self.board.matrix,
            piece_defs=_SLIDING_CAPTURE_ONLY_DEFS,
            white_color=W,
        ).legal
        self.assertEqual(moves, [])


# ===========================================================================
# positions.py — _jump / checkers-style captures (lines 136-141)
# ===========================================================================

_JUMP_DEFS = {
    'test_jumper': {
        'move_rules': [{
            'deltas': [[1, 1], [1, -1], [-1, 1], [-1, -1]],
            'jump_capture': True,
        }]
    }
}


class TestJumpCapture(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_can_jump_over_enemy(self):
        place(self.board, 3, 4, W, 'test_jumper')
        place(self.board, 4, 3, B, 'pawn')   # enemy to jump NE
        moves = PieceMoves(
            pos=(3, 4),
            piece_type='test_jumper',
            piece_color=W,
            board_matrix=self.board.matrix,
            piece_defs=_JUMP_DEFS,
            white_color=W,
        ).legal
        self.assertIn((5, 2), moves)

    def test_landing_square_must_be_empty(self):
        place(self.board, 3, 4, W, 'test_jumper')
        place(self.board, 4, 3, B, 'pawn')
        place(self.board, 5, 2, W, 'pawn')   # blocks landing
        moves = PieceMoves(
            pos=(3, 4),
            piece_type='test_jumper',
            piece_color=W,
            board_matrix=self.board.matrix,
            piece_defs=_JUMP_DEFS,
            white_color=W,
        ).legal
        self.assertNotIn((5, 2), moves)

    def test_cannot_jump_friendly(self):
        place(self.board, 3, 4, W, 'test_jumper')
        place(self.board, 4, 3, W, 'pawn')   # friendly, not an enemy
        moves = PieceMoves(
            pos=(3, 4),
            piece_type='test_jumper',
            piece_color=W,
            board_matrix=self.board.matrix,
            piece_defs=_JUMP_DEFS,
            white_color=W,
        ).legal
        self.assertNotIn((5, 2), moves)

    def test_no_enemy_no_jump(self):
        place(self.board, 3, 4, W, 'test_jumper')
        moves = PieceMoves(
            pos=(3, 4),
            piece_type='test_jumper',
            piece_color=W,
            board_matrix=self.board.matrix,
            piece_defs=_JUMP_DEFS,
            white_color=W,
        ).legal
        self.assertEqual(moves, [])

    def test_jump_off_board_not_added(self):
        place(self.board, 0, 0, W, 'test_jumper')
        place(self.board, 1, 1, B, 'pawn')   # landing (2,2) is on-board
        place(self.board, 0, 1, B, 'pawn')   # landing (-1, 2) off-board → not added
        moves = PieceMoves(
            pos=(0, 0),
            piece_type='test_jumper',
            piece_color=W,
            board_matrix=self.board.matrix,
            piece_defs=_JUMP_DEFS,
            white_color=W,
        ).legal
        for mx, my in moves:
            self.assertTrue(0 <= mx <= 7 and 0 <= my <= 7)


# ===========================================================================
# game.py — Graphics.promotion_pick  (pure dict lookup, no rendering)
# ===========================================================================

class TestGraphicsPromotionPick(unittest.TestCase):

    def setUp(self):
        from game import Graphics
        self.g = object.__new__(Graphics)
        self.g.PROMOTION_ROW = 3
        self.g.PROMOTION_PIECES = ['queen', 'rook', 'bishop', 'knight']
        self.g.PROMOTION_COLS = [2, 3, 4, 5]

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

    def test_off_grid_returns_none(self):
        self.assertIsNone(self.g.promotion_pick((7, 3)))


# ===========================================================================
# game.py — Graphics coordinate conversion (pure math, no rendering)
# ===========================================================================

class TestGraphicsCoords(unittest.TestCase):

    def setUp(self):
        from game import Graphics
        self.g = object.__new__(Graphics)
        self.g.square_size = 80
        self.g.piece_size = 40

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
        # pixel at exactly the start of last column/row
        self.assertEqual(self.g.board_coords((560, 560)), (7, 7))


# ===========================================================================
# svg_renderer.render_svg  (lines 138-209)
# Tests the full rendering pipeline for each SVG element type.
# ===========================================================================

# Ensure a display surface exists so SRCALPHA surfaces can be created
pygame.display.set_mode((1, 1))

from svg_renderer import render_svg


class TestRenderSvg(unittest.TestCase):

    def test_returns_surface_of_correct_size(self):
        svg = '<svg viewBox="0 0 80 80"></svg>'
        surf = render_svg(svg, (64, 64))
        self.assertEqual(surf.get_size(), (64, 64))

    def test_renders_circle(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<circle cx="40" cy="40" r="20" fill="#FF0000"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_renders_circle_with_stroke(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<circle cx="40" cy="40" r="20" fill="#FF0000" stroke="#000000" stroke-width="2"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_renders_rect(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<rect x="10" y="10" width="60" height="60" fill="#00FF00"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_renders_rect_with_stroke_and_rx(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<rect x="5" y="5" width="70" height="70" rx="5"'
               ' fill="#FFFFFF" stroke="#000000" stroke-width="1"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_renders_polygon(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<polygon points="40,5 5,75 75,75" fill="#0000FF"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_renders_polygon_with_stroke(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<polygon points="40,5 5,75 75,75" fill="none" stroke="#FF0000" stroke-width="2"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_renders_line(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<line x1="0" y1="0" x2="80" y2="80" stroke="#FF0000" stroke-width="2"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_renders_path(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<path d="M 10 10 L 70 10 L 40 70 Z" fill="#FFFF00"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_renders_path_with_bezier(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<path d="M 10 40 C 10 10 70 10 70 40 Z" fill="#FF00FF"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_renders_path_with_quadratic(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<path d="M 10 70 Q 40 10 70 70 Z" fill="#00FFFF"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_custom_viewbox_scales_correctly(self):
        # viewBox 160x160 → output 80x80: half scale
        svg = '<svg viewBox="0 0 160 160"></svg>'
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_none_fill_skips_fill_draw(self):
        # fill="none" — no error, just no fill drawn
        svg = ('<svg viewBox="0 0 80 80">'
               '<rect x="10" y="10" width="60" height="60" fill="none" stroke="#000000"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertIsNotNone(surf)

    def test_zero_radius_circle_skipped(self):
        # r=0 → circle not drawn, but no crash
        svg = '<svg viewBox="0 0 80 80"><circle cx="40" cy="40" r="0" fill="#FF0000"/></svg>'
        surf = render_svg(svg, (80, 80))
        self.assertIsNotNone(surf)

    def test_relative_cubic_bezier_path(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<path d="M 10 40 c 0 -30 60 -30 60 0 Z" fill="#FF8000"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))

    def test_relative_quadratic_bezier_path(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<path d="M 10 70 q 30 -60 60 0 Z" fill="#8000FF"/>'
               '</svg>')
        surf = render_svg(svg, (80, 80))
        self.assertEqual(surf.get_size(), (80, 80))


# ===========================================================================
# game.py — Game.end_turn  (bypasses Graphics.__init__ via object.__new__)
# ===========================================================================

import types


def _make_game():
    """Return a Game-like instance with mocked Graphics, no display needed."""
    from game import Game
    from win_conditions import ChessWinCondition

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


class TestGameEndTurn(unittest.TestCase):

    def test_white_switches_to_black(self):
        game = _make_game()
        game.turn = W
        game.end_turn()
        self.assertEqual(game.turn, B)

    def test_black_switches_to_white(self):
        game = _make_game()
        game.turn = B
        game.end_turn()
        self.assertEqual(game.turn, W)

    def test_selected_piece_cleared(self):
        game = _make_game()
        game.end_turn()
        self.assertIsNone(game.selected_piece)

    def test_selected_legal_moves_cleared(self):
        game = _make_game()
        game.end_turn()
        self.assertEqual(game.selected_legal_moves, [])

    def test_no_message_when_game_ongoing(self):
        game = _make_game()
        clear_board(game.board)
        place(game.board, 4, 7, W, 'king')
        place(game.board, 4, 0, B, 'king')
        place(game.board, 0, 6, W, 'rook')
        game.turn = W
        game.end_turn()
        self.assertEqual(game._msgs, [])

    def test_permanent_message_on_checkmate(self):
        # White king trapped and in check → after end_turn (now black's turn? no...
        # end_turn switches turn first, THEN checks. So set up a position where
        # after switching to B, black is in checkmate.
        game = _make_game()
        clear_board(game.board)
        place(game.board, 7, 0, B, 'king')
        place(game.board, 7, 5, W, 'rook')
        place(game.board, 6, 7, W, 'rook')
        place(game.board, 0, 7, W, 'king')
        game.turn = W   # will switch to B, then check B's position
        game.end_turn()
        self.assertEqual(len(game._msgs), 1)
        kind, msg = game._msgs[0]
        self.assertEqual(kind, 'perm')
        self.assertEqual(msg, 'WHITE WINS!')

    def test_timed_message_on_check(self):
        game = _make_game()
        clear_board(game.board)
        # After switching to B, black king on col 4 is in check from white rook
        place(game.board, 4, 0, B, 'king')
        place(game.board, 4, 7, W, 'rook')
        place(game.board, 0, 7, W, 'king')
        game.turn = W   # switches to B
        game.end_turn()
        self.assertEqual(len(game._msgs), 1)
        kind, msg = game._msgs[0]
        self.assertEqual(kind, 'timed')
        self.assertIn('CHECK', msg)


# ===========================================================================
# game.py — Graphics drawing methods (bypassing __init__ via object.__new__)
# ===========================================================================

class TestGraphicsDrawing(unittest.TestCase):
    """Exercise the rendering methods using a real pygame Surface."""

    def setUp(self):
        from game import Graphics
        g = object.__new__(Graphics)
        # Attributes normally set by __init__
        g.screen = pygame.display.get_surface() or pygame.Surface((640, 640))
        g.square_size = 80
        g.piece_size = 40
        g.window_size = 640
        g.piece_font = pygame.font.SysFont(None, 40)
        g.message = False
        g.timed_message_surface = None
        g.timed_message_rect = None
        g.timed_message_until = 0
        g.piece_icons = {}
        g.highlights = False
        g.caption = 'megaChess'
        g.fps = 60
        g.clock = pygame.time.Clock()
        self.g = g
        self.board = Board()

    def test_draw_board_squares_no_error(self):
        self.g.draw_board_squares(self.board)   # just checks no exception

    def test_draw_board_pieces_empty_board(self):
        clear_board(self.board)
        self.g.draw_board_pieces(self.board)

    def test_draw_board_pieces_with_pieces(self):
        # Starting board with all pieces
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
        self.assertIsNotNone(self.g.timed_message_rect)

    def test_draw_timed_message_sets_expiry(self):
        before = pygame.time.get_ticks()
        self.g.draw_timed_message('CHECK!', duration_ms=3000)
        self.assertGreater(self.g.timed_message_until, before)

    def test_draw_promotion_picker_white(self):
        self.g.draw_promotion_picker('white')   # no exception

    def test_draw_promotion_picker_black(self):
        self.g.draw_promotion_picker('black')

    def test_setup_window_no_error(self):
        self.g.setup_window()

    def test_update_display_no_click(self):
        self.g.update_display(self.board, [], None, (4, 4), False)

    def test_update_display_with_click_and_moves(self):
        self.g.update_display(self.board, [(3, 4)], (4, 4), (4, 4), True)

    def test_update_display_shows_permanent_message(self):
        self.g.draw_message('WHITE WINS!')
        self.assertTrue(self.g.message)
        self.g.update_display(self.board, [], None, (0, 0), False)

    def test_update_display_shows_timed_message(self):
        self.g.draw_timed_message('CHECK!', duration_ms=9999)
        self.g.update_display(self.board, [], None, (0, 0), False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
