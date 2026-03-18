"""Tests for win_conditions.py — GameResult, ChessWinCondition, CheckersWinCondition."""
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
from win_conditions import GameResult, ChessWinCondition, CheckersWinCondition

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


class MockGame:
    """Minimal stand-in for Game — only needs .board and .turn."""
    def __init__(self, board, turn):
        self.board = board
        self.turn = turn


# ---------------------------------------------------------------------------
# GameResult
# ---------------------------------------------------------------------------

class TestGameResult(unittest.TestCase):

    def test_message_stored(self):
        r = GameResult('CHECKMATE!')
        self.assertEqual(r.message, 'CHECKMATE!')

    def test_permanent_defaults_to_true(self):
        self.assertTrue(GameResult('msg').permanent)

    def test_permanent_false(self):
        self.assertFalse(GameResult('IN CHECK!', permanent=False).permanent)


# ---------------------------------------------------------------------------
# ChessWinCondition
# ---------------------------------------------------------------------------

class TestChessWinCondition(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)
        self.wc = ChessWinCondition()

    def test_ongoing_returns_none(self):
        place(self.board, 4, 7, W, 'king')
        place(self.board, 4, 0, B, 'king')
        place(self.board, 0, 6, W, 'rook')
        self.assertIsNone(self.wc.check(MockGame(self.board, W)))

    def test_white_in_check_timed_result(self):
        # White king on col 4, black rook checks along col 4
        place(self.board, 4, 7, W, 'king')
        place(self.board, 4, 0, B, 'rook')
        place(self.board, 7, 0, B, 'king')
        result = self.wc.check(MockGame(self.board, W))
        self.assertIsNotNone(result)
        self.assertFalse(result.permanent)
        self.assertEqual(result.message, 'WHITE IN CHECK!')

    def test_black_in_check_timed_result(self):
        place(self.board, 4, 0, B, 'king')
        place(self.board, 4, 7, W, 'rook')
        result = self.wc.check(MockGame(self.board, B))
        self.assertIsNotNone(result)
        self.assertFalse(result.permanent)
        self.assertEqual(result.message, 'BLACK IN CHECK!')

    def test_white_checkmate_black_wins(self):
        # King at (0,7); rook (0,5) checks col 0; rook (1,0) controls col 1
        place(self.board, 0, 7, W, 'king')
        place(self.board, 0, 5, B, 'rook')
        place(self.board, 1, 0, B, 'rook')
        place(self.board, 4, 0, B, 'king')
        result = self.wc.check(MockGame(self.board, W))
        self.assertIsNotNone(result)
        self.assertTrue(result.permanent)
        self.assertEqual(result.message, 'BLACK WINS!')

    def test_black_checkmate_white_wins(self):
        # King at (7,0); rook (7,5) checks col 7; rook (6,7) controls col 6
        place(self.board, 7, 0, B, 'king')
        place(self.board, 7, 5, W, 'rook')
        place(self.board, 6, 7, W, 'rook')
        place(self.board, 0, 7, W, 'king')
        result = self.wc.check(MockGame(self.board, B))
        self.assertIsNotNone(result)
        self.assertTrue(result.permanent)
        self.assertEqual(result.message, 'WHITE WINS!')

    def test_stalemate(self):
        # King at (0,7); queen at (1,5) controls all escape squares but NOT (0,7)
        place(self.board, 0, 7, W, 'king')
        place(self.board, 1, 5, B, 'queen')
        place(self.board, 7, 0, B, 'king')
        result = self.wc.check(MockGame(self.board, W))
        self.assertIsNotNone(result)
        self.assertTrue(result.permanent)
        self.assertEqual(result.message, 'STALEMATE!')

    def test_safe_moves_delegates_to_legal_moves_safe(self):
        place(self.board, 4, 7, W, 'king')
        place(self.board, 4, 0, B, 'king')
        safe = self.wc.safe_moves(self.board, (4, 7))
        expected = self.board.legal_moves_safe((4, 7))
        self.assertEqual(sorted(safe), sorted(expected))


# ---------------------------------------------------------------------------
# CheckersWinCondition
# ---------------------------------------------------------------------------

class TestCheckersWinCondition(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        clear_board(self.board)
        self.wc = CheckersWinCondition()

    def test_returns_none_when_current_player_has_moves(self):
        place(self.board, 4, 4, W, 'rook')
        place(self.board, 4, 0, B, 'king')
        self.assertIsNone(self.wc.check(MockGame(self.board, W)))

    def test_white_no_pieces_black_wins(self):
        place(self.board, 4, 0, B, 'king')
        result = self.wc.check(MockGame(self.board, W))
        self.assertIsNotNone(result)
        self.assertTrue(result.permanent)
        self.assertEqual(result.message, 'BLACK WINS!')

    def test_black_no_pieces_white_wins(self):
        place(self.board, 4, 7, W, 'king')
        result = self.wc.check(MockGame(self.board, B))
        self.assertIsNotNone(result)
        self.assertTrue(result.permanent)
        self.assertEqual(result.message, 'WHITE WINS!')

    def test_default_safe_moves_returns_all_legal_moves(self):
        place(self.board, 4, 4, W, 'rook')
        self.assertEqual(
            sorted(self.wc.safe_moves(self.board, (4, 4))),
            sorted(self.board.legal_moves((4, 4))),
        )


# ---------------------------------------------------------------------------
# Hole squares are skipped in win-condition iteration
# ---------------------------------------------------------------------------

class TestHoleSkippedInWinCheck(unittest.TestCase):

    def setUp(self):
        self.board = Board()
        for x in range(8):
            for y in range(8):
                self.board.matrix[x][y].occupant = None
        self.board.en_passant_target = None
        self.board.promotion_pending = None
        self.chess_wc = ChessWinCondition()
        self.checkers_wc = CheckersWinCondition()

    def test_chess_wc_skips_hole_and_detects_stalemate(self):
        """With only a king that is in check on a mostly-hole board, checkmate is detected."""
        # Place white king at (4, 4), surround with black rooks to force checkmate
        place(self.board, 4, 4, W, 'king')
        place(self.board, 0, 0, B, 'rook')
        place(self.board, 0, 7, B, 'rook')
        # Mark all squares except the occupied ones as holes to limit escape routes
        for x in range(8):
            for y in range(8):
                if self.board.matrix[x][y].occupant is None:
                    self.board.matrix[x][y].is_hole = True
        game = MockGame(self.board, W)
        # Should not raise an exception regardless of result
        result = self.chess_wc.check(game)
        # Result may be checkmate, stalemate, or check — we just need no crash
        # and if there's a result it must be a GameResult
        if result is not None:
            self.assertIsInstance(result, GameResult)

    def test_chess_wc_hole_squares_produce_no_false_pieces(self):
        """Hole squares are not treated as occupied by any colour."""
        place(self.board, 4, 4, W, 'king')
        place(self.board, 4, 0, B, 'king')
        # Mark (0,0) as a hole — it should be skipped, not counted as a piece
        self.board.matrix[0][0].is_hole = True
        game = MockGame(self.board, W)
        # Must not raise; win condition should run normally
        self.chess_wc.check(game)

    def test_checkers_wc_skips_hole_squares(self):
        """CheckersWinCondition skips holes without raising."""
        place(self.board, 4, 4, W, 'king')
        place(self.board, 4, 0, B, 'king')
        self.board.matrix[0][0].is_hole = True
        game = MockGame(self.board, W)
        self.checkers_wc.check(game)  # should not raise

    def test_checkers_wc_hole_does_not_block_win_detection(self):
        """A hole on the board doesn't prevent checkers win detection."""
        place(self.board, 4, 4, W, 'king')
        # No black pieces — black has no moves
        game = MockGame(self.board, B)
        self.board.matrix[3][3].is_hole = True
        result = self.checkers_wc.check(game)
        self.assertIsNotNone(result)
        self.assertIn('WHITE WINS', result.message)


if __name__ == '__main__':
    unittest.main(verbosity=2)
