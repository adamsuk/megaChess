"""Tests for layout loading and LayoutMenu helpers."""
import json
import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import pygame
pygame.init()

from game import _load_layouts, _LAYOUTS_DIR, Game


class TestLoadLayouts(unittest.TestCase):

    def test_finds_at_least_two_bundled_layouts(self):
        layouts = _load_layouts()
        self.assertGreaterEqual(len(layouts), 2)

    def test_all_layouts_have_name(self):
        for layout in _load_layouts():
            self.assertIn('name', layout, f"Layout missing 'name': {layout}")

    def test_all_layouts_have_win_condition(self):
        for layout in _load_layouts():
            self.assertIn('win_condition', layout)
            self.assertIn(layout['win_condition'], ('chess', 'checkers'))

    def test_all_layouts_have_starting_position(self):
        for layout in _load_layouts():
            self.assertIn('starting_position', layout)
            self.assertIsInstance(layout['starting_position'], list)

    def test_standard_chess_layout_present(self):
        names = [l['name'] for l in _load_layouts()]
        self.assertIn('Standard Chess', names)

    def test_standard_checkers_layout_present(self):
        names = [l['name'] for l in _load_layouts()]
        self.assertIn('Standard Checkers', names)

    def test_all_layout_files_are_valid_json(self):
        import glob
        for path in glob.glob(os.path.join(_LAYOUTS_DIR, '*.json')):
            with open(path) as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as e:
                    self.fail(f'{path} is not valid JSON: {e}')

    def test_starting_position_entries_have_required_fields(self):
        for layout in _load_layouts():
            for entry in layout['starting_position']:
                for field in ('x', 'y', 'piece', 'color'):
                    self.assertIn(field, entry, f"Entry {entry} missing '{field}'")
                self.assertIn(entry['color'], ('white', 'black'))
                self.assertIsInstance(entry['x'], int)
                self.assertIsInstance(entry['y'], int)
                self.assertGreaterEqual(entry['x'], 0)
                self.assertLessEqual(entry['x'], 7)
                self.assertGreaterEqual(entry['y'], 0)
                self.assertLessEqual(entry['y'], 7)

    def test_returns_empty_list_if_no_layouts_dir(self, monkeypatch=None):
        import game as game_module
        orig = game_module._LAYOUTS_DIR
        game_module._LAYOUTS_DIR = '/tmp/megachess_nonexistent_layouts_dir_xyz'
        try:
            layouts = game_module._load_layouts()
            self.assertEqual(layouts, [])
        finally:
            game_module._LAYOUTS_DIR = orig


class TestGameWithLayout(unittest.TestCase):

    def _make_game(self, layout):
        game = object.__new__(Game)
        game.graphics = type('G', (), {
            'setup_window': lambda s: None,
            'load_piece_icons': lambda s, d: None,
            'piece_icons': {},
            'message': False,
        })()
        from board import Board
        game.board = Board()
        game.turn = None
        game.selected_piece = None
        game.selected_legal_moves = []
        game.click = False
        if layout is not None:
            game.board.load_layout(layout)
            from win_conditions import ChessWinCondition, CheckersWinCondition
            from game import _WIN_CONDITIONS
            wc_cls = _WIN_CONDITIONS.get(layout.get('win_condition', 'chess'), ChessWinCondition)
            game.win_condition = wc_cls()
        else:
            from win_conditions import ChessWinCondition
            game.win_condition = ChessWinCondition()
        from common import Colours
        game.turn = Colours.WHITE
        return game

    def test_chess_layout_sets_chess_win_condition(self):
        from win_conditions import ChessWinCondition
        layouts = _load_layouts()
        chess = next(l for l in layouts if l['name'] == 'Standard Chess')
        game = self._make_game(chess)
        self.assertIsInstance(game.win_condition, ChessWinCondition)

    def test_checkers_layout_sets_checkers_win_condition(self):
        from win_conditions import CheckersWinCondition
        layouts = _load_layouts()
        checkers = next(l for l in layouts if l['name'] == 'Standard Checkers')
        game = self._make_game(checkers)
        self.assertIsInstance(game.win_condition, CheckersWinCondition)

    def test_chess_layout_places_16_white_pieces(self):
        from common import Colours
        layouts = _load_layouts()
        chess = next(l for l in layouts if l['name'] == 'Standard Chess')
        game = self._make_game(chess)
        white_pieces = sum(
            1 for x in range(8) for y in range(8)
            if game.board.matrix[x][y].occupant
            and game.board.matrix[x][y].occupant.color == Colours.WHITE
        )
        self.assertEqual(white_pieces, 16)

    def test_checkers_layout_places_24_pieces(self):
        layouts = _load_layouts()
        checkers = next(l for l in layouts if l['name'] == 'Standard Checkers')
        game = self._make_game(checkers)
        total = sum(
            1 for x in range(8) for y in range(8)
            if game.board.matrix[x][y].occupant
        )
        self.assertEqual(total, 24)

    def test_no_layout_defaults_to_chess_win_condition(self):
        from win_conditions import ChessWinCondition
        game = self._make_game(None)
        self.assertIsInstance(game.win_condition, ChessWinCondition)


if __name__ == '__main__':
    unittest.main(verbosity=2)
