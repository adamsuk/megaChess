"""Tests for board.py — Board, Square, Piece."""
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


# ---------------------------------------------------------------------------
# Coordinate utilities
# ---------------------------------------------------------------------------

class TestRel(unittest.TestCase):

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


class TestAdjacent(unittest.TestCase):

    def setUp(self):
        self.board = Board()

    def test_returns_four_entries(self):
        self.assertEqual(len(self.board.adjacent((3, 4))), 4)

    def test_center_coords(self):
        result = self.board.adjacent((3, 4))
        self.assertIn((2, 3), result)   # NW
        self.assertIn((4, 3), result)   # NE
        self.assertIn((2, 5), result)   # SW
        self.assertIn((4, 5), result)   # SE

    def test_corner_still_four_entries(self):
        # off-board values may appear; length is always 4
        result = self.board.adjacent((0, 0))
        self.assertEqual(len(result), 4)
        self.assertIn((1, 1), result)


class TestOnBoard(unittest.TestCase):

    def setUp(self):
        self.board = Board()

    def test_center(self):
        self.assertTrue(self.board.on_board((4, 4)))

    def test_all_corners(self):
        for coord in [(0, 0), (7, 0), (0, 7), (7, 7)]:
            self.assertTrue(self.board.on_board(coord))

    def test_negative_x(self):
        self.assertFalse(self.board.on_board((-1, 4)))

    def test_negative_y(self):
        self.assertFalse(self.board.on_board((4, -1)))

    def test_x_too_large(self):
        self.assertFalse(self.board.on_board((8, 4)))

    def test_y_too_large(self):
        self.assertFalse(self.board.on_board((4, 8)))


class TestIsEndSquare(unittest.TestCase):

    def setUp(self):
        self.board = Board()

    def test_rank_0_is_end(self):
        self.assertTrue(self.board.is_end_square((3, 0)))

    def test_rank_7_is_end(self):
        self.assertTrue(self.board.is_end_square((5, 7)))

    def test_middle_not_end(self):
        self.assertFalse(self.board.is_end_square((4, 4)))

    def test_rank_1_not_end(self):
        self.assertFalse(self.board.is_end_square((0, 1)))

    def test_rank_6_not_end(self):
        self.assertFalse(self.board.is_end_square((7, 6)))


class TestRemovePiece(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_removes_occupant(self):
        place(self.board, 4, 4, W, 'rook')
        self.assertIsNotNone(self.board.matrix[4][4].occupant)
        self.board.remove_piece((4, 4))
        self.assertIsNone(self.board.matrix[4][4].occupant)

    def test_empty_square_no_error(self):
        self.board.remove_piece((0, 0))
        self.assertIsNone(self.board.matrix[0][0].occupant)


class TestNearestSquare(unittest.TestCase):

    def setUp(self):
        self.board = Board()

    def test_identity(self):
        self.assertEqual(self.board.nearest_square((3, 5)), (3, 5))

    def test_origin(self):
        self.assertEqual(self.board.nearest_square((0, 0)), (0, 0))

    def test_far_corner(self):
        self.assertEqual(self.board.nearest_square((7, 7)), (7, 7))


# ---------------------------------------------------------------------------
# king() / promotion detection
# ---------------------------------------------------------------------------

class TestKingMethod(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_empty_square_no_promotion(self):
        self.board.king((4, 4))
        self.assertIsNone(self.board.promotion_pending)

    def test_non_pawn_on_back_rank_no_promotion(self):
        place(self.board, 4, 0, W, 'rook')
        self.board.king((4, 0))
        self.assertIsNone(self.board.promotion_pending)

    def test_white_pawn_rank_0_sets_pending(self):
        place(self.board, 4, 0, W, 'pawn')
        self.board.king((4, 0))
        self.assertEqual(self.board.promotion_pending, (4, 0))

    def test_black_pawn_rank_7_sets_pending(self):
        place(self.board, 3, 7, B, 'pawn')
        self.board.king((3, 7))
        self.assertEqual(self.board.promotion_pending, (3, 7))

    def test_pawn_mid_board_no_promotion(self):
        place(self.board, 4, 3, W, 'pawn')
        self.board.king((4, 3))
        self.assertIsNone(self.board.promotion_pending)


# ---------------------------------------------------------------------------
# En passant
# ---------------------------------------------------------------------------

class TestEnPassant(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_target_set_after_white_double_push(self):
        place(self.board, 4, 6, W, 'pawn')
        self.board.move_piece((4, 6), (4, 4))
        self.assertEqual(self.board.en_passant_target, (4, 5))

    def test_target_set_after_black_double_push(self):
        place(self.board, 3, 1, B, 'pawn')
        self.board.move_piece((3, 1), (3, 3))
        self.assertEqual(self.board.en_passant_target, (3, 2))

    def test_target_cleared_after_single_push(self):
        place(self.board, 4, 6, W, 'pawn')
        self.board.en_passant_target = (4, 5)
        self.board.move_piece((4, 6), (4, 5))
        self.assertIsNone(self.board.en_passant_target)

    def test_ep_move_offered_to_adjacent_pawn(self):
        place(self.board, 4, 1, B, 'pawn')
        self.board.move_piece((4, 1), (4, 3))
        place(self.board, 3, 3, W, 'pawn', has_moved=True)
        moves = self.board.legal_moves((3, 3))
        self.assertIn((4, 2), moves)

    def test_ep_not_offered_to_non_adjacent_pawn(self):
        place(self.board, 4, 1, B, 'pawn')
        self.board.move_piece((4, 1), (4, 3))
        place(self.board, 1, 3, W, 'pawn', has_moved=True)
        moves = self.board.legal_moves((1, 3))
        self.assertNotIn((4, 2), moves)

    def test_ep_capture_removes_bypassed_pawn(self):
        place(self.board, 4, 1, B, 'pawn')
        self.board.move_piece((4, 1), (4, 3))
        place(self.board, 3, 3, W, 'pawn', has_moved=True)
        self.board.move_piece((3, 3), (4, 2))
        self.assertIsNone(self.board.matrix[4][3].occupant)
        self.assertIsNotNone(self.board.matrix[4][2].occupant)

    def test_ep_not_offered_after_intervening_move(self):
        place(self.board, 4, 1, B, 'pawn')
        self.board.move_piece((4, 1), (4, 3))
        place(self.board, 0, 6, W, 'pawn')
        self.board.move_piece((0, 6), (0, 5))
        place(self.board, 3, 3, W, 'pawn', has_moved=True)
        moves = self.board.legal_moves((3, 3))
        self.assertNotIn((4, 2), moves)


# ---------------------------------------------------------------------------
# Castling
# ---------------------------------------------------------------------------

class TestCastling(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def _setup_castling(self):
        place(self.board, 4, 7, W, 'king')
        place(self.board, 7, 7, W, 'rook')
        place(self.board, 0, 7, W, 'rook')
        place(self.board, 4, 0, B, 'king')

    def test_both_sides_available(self):
        self._setup_castling()
        dests = self.board._castling_destinations((4, 7))
        self.assertIn((6, 7), dests)
        self.assertIn((2, 7), dests)

    def test_blocked_king_has_moved(self):
        self._setup_castling()
        self.board.matrix[4][7].occupant.has_moved = True
        self.assertEqual(self.board._castling_destinations((4, 7)), [])

    def test_blocked_kingside_rook_has_moved(self):
        self._setup_castling()
        self.board.matrix[7][7].occupant.has_moved = True
        dests = self.board._castling_destinations((4, 7))
        self.assertNotIn((6, 7), dests)
        self.assertIn((2, 7), dests)

    def test_blocked_queenside_rook_has_moved(self):
        self._setup_castling()
        self.board.matrix[0][7].occupant.has_moved = True
        dests = self.board._castling_destinations((4, 7))
        self.assertIn((6, 7), dests)
        self.assertNotIn((2, 7), dests)

    def test_blocked_path_occupied(self):
        self._setup_castling()
        place(self.board, 5, 7, W, 'bishop')
        dests = self.board._castling_destinations((4, 7))
        self.assertNotIn((6, 7), dests)
        self.assertIn((2, 7), dests)

    def test_blocked_when_in_check(self):
        self._setup_castling()
        place(self.board, 4, 3, B, 'rook')
        self.assertEqual(self.board._castling_destinations((4, 7)), [])

    def test_blocked_transit_square_attacked(self):
        self._setup_castling()
        place(self.board, 5, 0, B, 'rook')
        dests = self.board._castling_destinations((4, 7))
        self.assertNotIn((6, 7), dests)
        self.assertIn((2, 7), dests)

    def test_kingside_castle_moves_rook_to_f1(self):
        self._setup_castling()
        self.board.move_piece((4, 7), (6, 7))
        self.assertEqual(self.board.matrix[6][7].occupant.piece_type, 'king')
        self.assertEqual(self.board.matrix[5][7].occupant.piece_type, 'rook')
        self.assertIsNone(self.board.matrix[7][7].occupant)

    def test_queenside_castle_moves_rook_to_d1(self):
        self._setup_castling()
        self.board.move_piece((4, 7), (2, 7))
        self.assertEqual(self.board.matrix[2][7].occupant.piece_type, 'king')
        self.assertEqual(self.board.matrix[3][7].occupant.piece_type, 'rook')
        self.assertIsNone(self.board.matrix[0][7].occupant)

    def test_castling_appears_in_legal_moves(self):
        self._setup_castling()
        moves = self.board.legal_moves((4, 7))
        self.assertIn((6, 7), moves)
        self.assertIn((2, 7), moves)


# ---------------------------------------------------------------------------
# Pawn promotion
# ---------------------------------------------------------------------------

class TestPromotion(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_white_pawn_on_back_rank_sets_pending(self):
        place(self.board, 4, 1, W, 'pawn', has_moved=True)
        self.board.move_piece((4, 1), (4, 0))
        self.assertEqual(self.board.promotion_pending, (4, 0))

    def test_black_pawn_on_back_rank_sets_pending(self):
        place(self.board, 4, 6, B, 'pawn', has_moved=True)
        self.board.move_piece((4, 6), (4, 7))
        self.assertEqual(self.board.promotion_pending, (4, 7))

    def test_no_promotion_mid_board(self):
        place(self.board, 4, 4, W, 'pawn', has_moved=True)
        self.board.move_piece((4, 4), (4, 3))
        self.assertIsNone(self.board.promotion_pending)

    def test_piece_type_changes_on_promotion(self):
        place(self.board, 4, 1, W, 'pawn', has_moved=True)
        self.board.move_piece((4, 1), (4, 0))
        self.board.matrix[4][0].occupant.piece_type = 'queen'
        self.board.promotion_pending = None
        self.assertEqual(self.board.matrix[4][0].occupant.piece_type, 'queen')
        self.assertIsNone(self.board.promotion_pending)


# ---------------------------------------------------------------------------
# has_moved flag
# ---------------------------------------------------------------------------

class TestHasMoved(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_piece_starts_unmoved(self):
        p = place(self.board, 4, 4, W, 'rook')
        self.assertFalse(p.has_moved)

    def test_has_moved_set_after_move(self):
        p = place(self.board, 4, 4, W, 'rook')
        self.board.move_piece((4, 4), (4, 3))
        self.assertTrue(p.has_moved)

    def test_castling_sets_rook_has_moved(self):
        place(self.board, 4, 7, W, 'king')
        rook = place(self.board, 7, 7, W, 'rook')
        place(self.board, 4, 0, B, 'king')
        self.board.move_piece((4, 7), (6, 7))
        self.assertTrue(rook.has_moved)


# ---------------------------------------------------------------------------
# legal_moves_safe (check filtering)
# ---------------------------------------------------------------------------

class TestLegalMovesSafe(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_pinned_piece_cannot_leave_pin_ray(self):
        place(self.board, 4, 7, W, 'king')
        place(self.board, 4, 5, W, 'rook')
        place(self.board, 4, 0, B, 'rook')
        safe = self.board.legal_moves_safe((4, 5))
        for sq in safe:
            self.assertEqual(sq[0], 4, f"Pinned rook moved off column 4 to {sq}")

    def test_king_cannot_move_into_check(self):
        place(self.board, 4, 7, W, 'king')
        self.board.matrix[4][7].occupant.has_moved = True
        place(self.board, 5, 0, B, 'rook')
        safe = self.board.legal_moves_safe((4, 7))
        for sq in safe:
            self.assertNotEqual(sq[0], 5, f"King moved into check at {sq}")

    def test_ep_capture_safe_when_no_discovered_check(self):
        place(self.board, 4, 1, B, 'pawn')
        self.board.move_piece((4, 1), (4, 3))
        place(self.board, 3, 3, W, 'pawn', has_moved=True)
        place(self.board, 0, 7, W, 'king')
        place(self.board, 0, 0, B, 'king')
        safe = self.board.legal_moves_safe((3, 3))
        self.assertIn((4, 2), safe)

    def test_ep_capture_filtered_if_exposes_king(self):
        place(self.board, 0, 3, W, 'king')
        place(self.board, 3, 3, W, 'pawn', has_moved=True)
        place(self.board, 4, 1, B, 'pawn')
        self.board.move_piece((4, 1), (4, 3))
        place(self.board, 7, 3, B, 'rook')
        place(self.board, 0, 0, B, 'king')
        safe = self.board.legal_moves_safe((3, 3))
        self.assertNotIn((4, 2), safe)


if __name__ == '__main__':
    unittest.main(verbosity=2)
