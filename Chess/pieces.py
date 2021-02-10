"""
Pieces - a module intended to obtain piece definitions
"""
# all definitions will be in json format
import json
import os


class Piece:
    def __init__(self, name):
        self.name = name


class AllPieces:
    def __init__(self,
                 pieces_def_loc=None,
                 pieces_def_filename="pieces_defs.json"):
        if not pieces_def_loc:
            script_loc = os.path.dirname(os.path.abspath(__file__))
            pieces_def_loc = os.path.join(script_loc, "defs")
        self.pieces_def_loc = os.path.join(pieces_def_loc, pieces_def_filename)
        # load up the definitions
        self._load_pieces_defs()
        # figure out potential move deltas
        self._turn_moves_to_deltas()

    def _load_pieces_defs(self):
        with open(self.pieces_def_loc) as f:
            self.pieces_defs = json.load(f)
    
    def _turn_moves_to_deltas(self):
        for piece, defs in self.pieces_defs.items():
            if all([isinstance(move, (list, tuple)) for move in defs["moves"]):
                self.pieces_defs[piece]["deltas"] = defs["moves"]
        print(self.pieces_defs)

if __name__ == "__main__":
    allPieces = AllPieces()
    print(allPieces.pieces_defs)
