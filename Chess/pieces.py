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
    
    def _load_pieces_defs(self):
        self.pieces_defs = json.load(self.pieces_def_loc)

if __name__ == "__main__":
    allPieces = AllPieces()
    print(allPieces.pieces_defs)
