"""Tests for pieces.py — AllPieces load and save."""
import copy
import json
import os
import sys
import tempfile

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest

from pieces import AllPieces


class TestAllPiecesLoad(unittest.TestCase):

    def setUp(self):
        self.ap = AllPieces()

    def test_loads_standard_pieces(self):
        for piece in ('pawn', 'knight', 'bishop', 'rook', 'queen', 'king'):
            self.assertIn(piece, self.ap.pieces_defs)

    def test_each_piece_has_move_rules(self):
        for name, defn in self.ap.pieces_defs.items():
            self.assertIn('move_rules', defn, f'{name} missing move_rules')
            self.assertIsInstance(defn['move_rules'], list)
            self.assertGreater(len(defn['move_rules']), 0)

    def test_custom_path_loads_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom = {'test_piece': {'move_rules': [{'deltas': [[1, 0]]}]}}
            path = os.path.join(tmp, 'custom.json')
            with open(path, 'w') as f:
                json.dump(custom, f)
            ap = AllPieces(pieces_def_loc=tmp, pieces_def_filename='custom.json')
            self.assertIn('test_piece', ap.pieces_defs)


class TestAllPiecesSave(unittest.TestCase):

    def setUp(self):
        self.ap = AllPieces()

    def test_save_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'saved.json')
            self.ap.save(path)
            self.assertTrue(os.path.exists(path))

    def test_save_produces_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'saved.json')
            self.ap.save(path)
            with open(path) as f:
                data = json.load(f)
            self.assertIsInstance(data, dict)

    def test_roundtrip_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'saved.json')
            self.ap.save(path)
            with open(path) as f:
                reloaded = json.load(f)
            self.assertEqual(reloaded, self.ap.pieces_defs)

    def test_save_custom_piece(self):
        self.ap.pieces_defs['super_queen'] = {
            'move_rules': [{'deltas': ['diagonal', 'straight'], 'sliding': True}]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'saved.json')
            self.ap.save(path)
            with open(path) as f:
                data = json.load(f)
            self.assertIn('super_queen', data)

    def test_save_creates_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'subdir', 'nested.json')
            self.ap.save(path)
            self.assertTrue(os.path.exists(path))

    def test_save_modified_rule_persists(self):
        self.ap.pieces_defs['pawn']['move_rules'][0]['sliding'] = True
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'saved.json')
            self.ap.save(path)
            with open(path) as f:
                data = json.load(f)
            self.assertTrue(data['pawn']['move_rules'][0]['sliding'])


class TestPieceEditorLogic(unittest.TestCase):
    """Tests for PieceEditor non-rendering logic."""

    def setUp(self):
        self.ap = AllPieces()
        self.defs = copy.deepcopy(self.ap.pieces_defs)

    def test_clone_creates_new_entry(self):
        original = 'pawn'
        new_name = original + '_custom'
        self.assertNotIn(new_name, self.defs)
        self.defs[new_name] = copy.deepcopy(self.defs[original])
        self.assertIn(new_name, self.defs)

    def test_clone_is_deep_copy(self):
        self.defs['pawn_custom'] = copy.deepcopy(self.defs['pawn'])
        self.defs['pawn_custom']['move_rules'][0]['sliding'] = True
        self.assertFalse(self.defs['pawn']['move_rules'][0].get('sliding', False))

    def test_toggle_flag_on(self):
        self.defs['pawn']['move_rules'][0]['sliding'] = False
        self.defs['pawn']['move_rules'][0]['sliding'] = not self.defs['pawn']['move_rules'][0]['sliding']
        self.assertTrue(self.defs['pawn']['move_rules'][0]['sliding'])

    def test_toggle_flag_off(self):
        self.defs['rook']['move_rules'][0]['sliding'] = True
        self.defs['rook']['move_rules'][0]['sliding'] = not self.defs['rook']['move_rules'][0]['sliding']
        self.assertFalse(self.defs['rook']['move_rules'][0]['sliding'])

    def test_toggle_missing_flag_defaults_false_then_sets_true(self):
        rule = self.defs['pawn']['move_rules'][0]
        rule.pop('jump_capture', None)
        rule['jump_capture'] = not rule.get('jump_capture', False)
        self.assertTrue(rule['jump_capture'])

    def test_reset_restores_defaults(self):
        self.defs['pawn']['move_rules'][0]['sliding'] = True
        fresh = AllPieces().pieces_defs
        self.assertFalse(fresh['pawn']['move_rules'][0].get('sliding', False))

    def test_save_and_reload_custom_defs(self):
        self.defs['my_piece'] = {'move_rules': [{'deltas': [[0, 1]]}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'custom.json')
            ap = AllPieces()
            ap.pieces_defs = self.defs
            ap.save(path)
            with open(path) as f:
                reloaded = json.load(f)
            self.assertIn('my_piece', reloaded)


if __name__ == '__main__':
    unittest.main(verbosity=2)
