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


if __name__ == '__main__':
    unittest.main(verbosity=2)
