"""Tests for positions.py — PieceMoves movement logic."""
import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import pygame
pygame.init()

from board import Board, Piece
from common import Colours
from positions import PieceMoves

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
# Standard chess pieces (via Board.legal_moves)
# ---------------------------------------------------------------------------

class TestPieceMoves(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)

    def test_rook_slides_empty_board(self):
        place(self.board, 3, 3, W, 'rook')
        moves = self.board.legal_moves((3, 3))
        self.assertEqual(len(moves), 14)

    def test_rook_blocked_by_friendly(self):
        place(self.board, 3, 3, W, 'rook')
        place(self.board, 5, 3, W, 'pawn')
        moves = self.board.legal_moves((3, 3))
        self.assertIn((4, 3), moves)
        self.assertNotIn((5, 3), moves)
        self.assertNotIn((6, 3), moves)

    def test_rook_captures_enemy_and_stops(self):
        place(self.board, 3, 3, W, 'rook')
        place(self.board, 5, 3, B, 'pawn')
        moves = self.board.legal_moves((3, 3))
        self.assertIn((4, 3), moves)
        self.assertIn((5, 3), moves)
        self.assertNotIn((6, 3), moves)

    def test_pawn_single_step(self):
        place(self.board, 4, 4, W, 'pawn', has_moved=True)
        moves = self.board.legal_moves((4, 4))
        self.assertIn((4, 3), moves)
        self.assertNotIn((4, 2), moves)

    def test_pawn_double_push_from_start_row(self):
        place(self.board, 4, 6, W, 'pawn')
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
        place(self.board, 4, 5, B, 'pawn')
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
        place(self.board, 4, 1, B, 'pawn')
        moves = self.board.legal_moves((4, 1))
        self.assertIn((4, 2), moves)
        self.assertIn((4, 3), moves)

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
        self.assertIn((4, 0), moves)
        self.assertIn((7, 7), moves)
        self.assertIn((0, 4), moves)
        self.assertIn((0, 0), moves)

    def test_king_one_step_all_directions(self):
        place(self.board, 4, 4, W, 'king')
        self.board.matrix[4][4].occupant.has_moved = True
        moves = self.board.legal_moves((4, 4))
        expected = [(3,3),(4,3),(5,3),(3,4),(5,4),(3,5),(4,5),(5,5)]
        for sq in expected:
            self.assertIn(sq, moves)
        self.assertEqual(len(moves), 8)

    def test_empty_square_returns_empty(self):
        moves = self.board.legal_moves((4, 4))
        self.assertEqual(moves, [])


# ---------------------------------------------------------------------------
# _slide with capture_only (exercises lines 125-129 in positions.py)
# ---------------------------------------------------------------------------

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

    def _moves(self):
        return PieceMoves(
            pos=(0, 4),
            piece_type='test_piece',
            piece_color=W,
            board_matrix=self.board.matrix,
            piece_defs=_SLIDING_CAPTURE_ONLY_DEFS,
            white_color=W,
        ).legal

    def test_skips_empty_squares_and_lands_on_enemy(self):
        place(self.board, 0, 4, W, 'test_piece')
        place(self.board, 4, 4, B, 'pawn')
        moves = self._moves()
        self.assertIn((4, 4), moves)
        self.assertNotIn((1, 4), moves)
        self.assertNotIn((2, 4), moves)
        self.assertNotIn((3, 4), moves)

    def test_friendly_blocks_ray(self):
        place(self.board, 0, 4, W, 'test_piece')
        place(self.board, 2, 4, W, 'pawn')
        place(self.board, 5, 4, B, 'pawn')
        moves = self._moves()
        self.assertNotIn((5, 4), moves)

    def test_no_enemy_no_moves(self):
        place(self.board, 0, 4, W, 'test_piece')
        moves = self._moves()
        self.assertEqual(moves, [])


# ---------------------------------------------------------------------------
# _jump — checkers-style captures (exercises lines 136-141 in positions.py)
# ---------------------------------------------------------------------------

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

    def _moves(self, pos):
        return PieceMoves(
            pos=pos,
            piece_type='test_jumper',
            piece_color=W,
            board_matrix=self.board.matrix,
            piece_defs=_JUMP_DEFS,
            white_color=W,
        ).legal

    def test_can_jump_over_enemy(self):
        place(self.board, 3, 4, W, 'test_jumper')
        place(self.board, 4, 3, B, 'pawn')
        self.assertIn((5, 2), self._moves((3, 4)))

    def test_landing_square_must_be_empty(self):
        place(self.board, 3, 4, W, 'test_jumper')
        place(self.board, 4, 3, B, 'pawn')
        place(self.board, 5, 2, W, 'pawn')
        self.assertNotIn((5, 2), self._moves((3, 4)))

    def test_cannot_jump_friendly(self):
        place(self.board, 3, 4, W, 'test_jumper')
        place(self.board, 4, 3, W, 'pawn')
        self.assertNotIn((5, 2), self._moves((3, 4)))

    def test_no_enemy_no_jump(self):
        place(self.board, 3, 4, W, 'test_jumper')
        self.assertEqual(self._moves((3, 4)), [])

    def test_off_board_landing_not_added(self):
        place(self.board, 0, 0, W, 'test_jumper')
        place(self.board, 1, 1, B, 'pawn')
        place(self.board, 0, 1, B, 'pawn')
        for mx, my in self._moves((0, 0)):
            self.assertTrue(0 <= mx <= 7 and 0 <= my <= 7)


if __name__ == '__main__':
    unittest.main(verbosity=2)
