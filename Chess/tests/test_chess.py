"""
Tests for PieceMoves, Board special moves (castling, en passant, promotion),
and legal_moves_safe check filtering.
"""
import os
import sys

# Headless pygame — must be set before any pygame import
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import pygame
pygame.init()

from board import Board, Piece
from common import Colours

W = Colours.WHITE
B = Colours.PIECE_BLACK


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clear_board(board):
    """Remove all pieces and reset special-move state."""
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
# PieceMoves via Board.legal_moves
# ---------------------------------------------------------------------------

class TestPieceMoves(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_rook_slides_empty_board(self):
        # From (3,3): right 4, left 3, up 3, down 4 = 14 squares
        place(self.board, 3, 3, W, 'rook')
        moves = self.board.legal_moves((3, 3))
        self.assertEqual(len(moves), 14)

    def test_rook_blocked_by_friendly(self):
        place(self.board, 3, 3, W, 'rook')
        place(self.board, 5, 3, W, 'pawn')   # blocks rightward ray after (4,3)
        moves = self.board.legal_moves((3, 3))
        self.assertIn((4, 3), moves)
        self.assertNotIn((5, 3), moves)
        self.assertNotIn((6, 3), moves)

    def test_rook_captures_enemy_and_stops(self):
        place(self.board, 3, 3, W, 'rook')
        place(self.board, 5, 3, B, 'pawn')
        moves = self.board.legal_moves((3, 3))
        self.assertIn((4, 3), moves)
        self.assertIn((5, 3), moves)    # can capture
        self.assertNotIn((6, 3), moves) # blocked after capture

    def test_pawn_single_step(self):
        place(self.board, 4, 4, W, 'pawn', has_moved=True)
        moves = self.board.legal_moves((4, 4))
        self.assertIn((4, 3), moves)
        self.assertNotIn((4, 2), moves)

    def test_pawn_double_push_from_start_row(self):
        place(self.board, 4, 6, W, 'pawn')   # y=6 is white start row
        moves = self.board.legal_moves((4, 6))
        self.assertIn((4, 5), moves)
        self.assertIn((4, 4), moves)

    def test_pawn_no_double_push_off_start_row(self):
        place(self.board, 4, 5, W, 'pawn', has_moved=True)
        moves = self.board.legal_moves((4, 5))
        self.assertIn((4, 4), moves)
        self.assertNotIn((4, 3), moves)

    def test_pawn_double_push_blocked_by_piece_on_first_square(self):
        place(self.board, 4, 6, W, 'pawn')
        place(self.board, 4, 5, B, 'pawn')   # blocks the first step
        moves = self.board.legal_moves((4, 6))
        self.assertNotIn((4, 5), moves)
        self.assertNotIn((4, 4), moves)

    def test_pawn_diagonal_capture(self):
        place(self.board, 4, 4, W, 'pawn', has_moved=True)
        place(self.board, 3, 3, B, 'pawn')
        place(self.board, 5, 3, B, 'pawn')
        moves = self.board.legal_moves((4, 4))
        self.assertIn((3, 3), moves)
        self.assertIn((5, 3), moves)

    def test_pawn_cannot_capture_forward(self):
        place(self.board, 4, 4, W, 'pawn', has_moved=True)
        place(self.board, 4, 3, B, 'pawn')
        moves = self.board.legal_moves((4, 4))
        self.assertNotIn((4, 3), moves)

    def test_black_pawn_moves_downward(self):
        place(self.board, 4, 1, B, 'pawn')   # y=1 is black start row
        moves = self.board.legal_moves((4, 1))
        self.assertIn((4, 2), moves)
        self.assertIn((4, 3), moves)   # double push

    def test_knight_all_eight_moves(self):
        place(self.board, 4, 4, W, 'knight')
        moves = self.board.legal_moves((4, 4))
        expected = [(6,5),(6,3),(2,5),(2,3),(5,6),(3,6),(5,2),(3,2)]
        for sq in expected:
            self.assertIn(sq, moves)
        self.assertEqual(len(moves), 8)

    def test_bishop_diagonal_slides(self):
        place(self.board, 4, 4, W, 'bishop')
        moves = self.board.legal_moves((4, 4))
        self.assertIn((7, 7), moves)
        self.assertIn((0, 0), moves)
        self.assertIn((7, 1), moves)
        self.assertIn((1, 7), moves)

    def test_queen_combines_rook_and_bishop(self):
        place(self.board, 4, 4, W, 'queen')
        moves = self.board.legal_moves((4, 4))
        self.assertIn((4, 0), moves)   # straight
        self.assertIn((7, 7), moves)   # diagonal
        self.assertIn((0, 4), moves)   # straight
        self.assertIn((0, 0), moves)   # diagonal

    def test_king_one_step_all_directions(self):
        place(self.board, 4, 4, W, 'king')
        # Give it has_moved=True so _castling_destinations returns nothing
        self.board.matrix[4][4].occupant.has_moved = True
        moves = self.board.legal_moves((4, 4))
        expected = [(3,3),(4,3),(5,3),(3,4),(5,4),(3,5),(4,5),(5,5)]
        for sq in expected:
            self.assertIn(sq, moves)
        self.assertEqual(len(moves), 8)


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
        self.board.en_passant_target = (4, 5)   # pretend it was set
        self.board.move_piece((4, 6), (4, 5))
        self.assertIsNone(self.board.en_passant_target)

    def test_ep_move_offered_to_adjacent_pawn(self):
        place(self.board, 4, 1, B, 'pawn')
        self.board.move_piece((4, 1), (4, 3))   # black double push → target (4,2)
        place(self.board, 3, 3, W, 'pawn', has_moved=True)
        moves = self.board.legal_moves((3, 3))
        self.assertIn((4, 2), moves)

    def test_ep_not_offered_to_non_adjacent_pawn(self):
        place(self.board, 4, 1, B, 'pawn')
        self.board.move_piece((4, 1), (4, 3))
        place(self.board, 1, 3, W, 'pawn', has_moved=True)   # two columns away
        moves = self.board.legal_moves((1, 3))
        self.assertNotIn((4, 2), moves)

    def test_ep_capture_removes_bypassed_pawn(self):
        place(self.board, 4, 1, B, 'pawn')
        self.board.move_piece((4, 1), (4, 3))
        place(self.board, 3, 3, W, 'pawn', has_moved=True)
        self.board.move_piece((3, 3), (4, 2))   # white captures en passant
        self.assertIsNone(self.board.matrix[4][3].occupant)   # black pawn gone
        self.assertIsNotNone(self.board.matrix[4][2].occupant) # white pawn arrived

    def test_ep_not_offered_after_intervening_move(self):
        place(self.board, 4, 1, B, 'pawn')
        self.board.move_piece((4, 1), (4, 3))   # double push
        # An intervening move clears the ep target
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
        """Standard castling setup: white king e1 (4,7), rooks a1/h1, black king e8."""
        place(self.board, 4, 7, W, 'king')
        place(self.board, 7, 7, W, 'rook')
        place(self.board, 0, 7, W, 'rook')
        place(self.board, 4, 0, B, 'king')

    def test_both_sides_available(self):
        self._setup_castling()
        dests = self.board._castling_destinations((4, 7))
        self.assertIn((6, 7), dests)   # kingside
        self.assertIn((2, 7), dests)   # queenside

    def test_blocked_king_has_moved(self):
        self._setup_castling()
        self.board.matrix[4][7].occupant.has_moved = True
        dests = self.board._castling_destinations((4, 7))
        self.assertEqual(dests, [])

    def test_blocked_kingside_rook_has_moved(self):
        self._setup_castling()
        self.board.matrix[7][7].occupant.has_moved = True
        dests = self.board._castling_destinations((4, 7))
        self.assertNotIn((6, 7), dests)
        self.assertIn((2, 7), dests)   # queenside still available

    def test_blocked_queenside_rook_has_moved(self):
        self._setup_castling()
        self.board.matrix[0][7].occupant.has_moved = True
        dests = self.board._castling_destinations((4, 7))
        self.assertIn((6, 7), dests)
        self.assertNotIn((2, 7), dests)

    def test_blocked_path_occupied(self):
        self._setup_castling()
        place(self.board, 5, 7, W, 'bishop')   # f1 blocks kingside
        dests = self.board._castling_destinations((4, 7))
        self.assertNotIn((6, 7), dests)
        self.assertIn((2, 7), dests)

    def test_blocked_when_in_check(self):
        self._setup_castling()
        place(self.board, 4, 3, B, 'rook')   # attacks e1 down column 4
        dests = self.board._castling_destinations((4, 7))
        self.assertEqual(dests, [])

    def test_blocked_transit_square_attacked(self):
        self._setup_castling()
        place(self.board, 5, 0, B, 'rook')   # attacks f1 (kingside transit)
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
        # Simulate game.py resolving the picker
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
        clear_board(self.board)
        place(self.board, 4, 7, W, 'king')
        rook = place(self.board, 7, 7, W, 'rook')
        place(self.board, 4, 0, B, 'king')
        self.board.move_piece((4, 7), (6, 7))   # kingside castle
        self.assertTrue(rook.has_moved)


# ---------------------------------------------------------------------------
# legal_moves_safe (check filtering)
# ---------------------------------------------------------------------------

class TestLegalMovesSafe(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_pinned_piece_cannot_leave_pin_ray(self):
        # White rook at (4,5) is pinned on column 4 by black rook at (4,0);
        # white king at (4,7). Any horizontal move would expose the king.
        place(self.board, 4, 7, W, 'king')
        place(self.board, 4, 5, W, 'rook')
        place(self.board, 4, 0, B, 'rook')
        safe = self.board.legal_moves_safe((4, 5))
        for sq in safe:
            self.assertEqual(sq[0], 4, f"Pinned rook moved off column 4 to {sq}")

    def test_king_cannot_move_into_check(self):
        # Black rook at (5,0) attacks all of column 5.
        # King at (4,7) must not be able to move to column 5.
        place(self.board, 4, 7, W, 'king')
        self.board.matrix[4][7].occupant.has_moved = True
        place(self.board, 5, 0, B, 'rook')
        safe = self.board.legal_moves_safe((4, 7))
        for sq in safe:
            self.assertNotEqual(sq[0], 5, f"King moved into check at {sq}")

    def test_ep_capture_safe_when_no_discovered_check(self):
        # Standard ep capture should appear in safe moves
        place(self.board, 4, 1, B, 'pawn')
        self.board.move_piece((4, 1), (4, 3))
        place(self.board, 3, 3, W, 'pawn', has_moved=True)
        place(self.board, 0, 7, W, 'king')
        place(self.board, 0, 0, B, 'king')
        safe = self.board.legal_moves_safe((3, 3))
        self.assertIn((4, 2), safe)

    def test_ep_capture_filtered_if_exposes_king(self):
        # Rare "discovered check through ep" position:
        # White king at (0,3), white pawn at (3,3), black pawn at (4,3) just doubled.
        # Black rook at (7,3) — if white takes ep, both (3,3) and (4,3) are vacated
        # leaving the king exposed on row 3.
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
