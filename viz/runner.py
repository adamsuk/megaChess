"""Run megaChess rules without copying them or opening the PyGame window.

board.py imports pygame at module level. This runner stubs that module,
then imports Chess/board.py, positions.py and pieces.py from the repo.
"""

import json
import sys
import types
from pathlib import Path

try:
    ROOT = Path(__file__).resolve().parents[1]
except NameError:
    ROOT = Path("/chess")
CHESS = ROOT / "Chess"


def _stub_pygame():
    pygame = types.ModuleType("pygame")
    pygame.font = types.SimpleNamespace(init=lambda: None)
    pygame.locals = types.ModuleType("pygame.locals")
    sys.modules["pygame"] = pygame
    sys.modules["pygame.locals"] = pygame.locals


def _load(chess_dir=None):
    _stub_pygame()
    chess = str(Path(chess_dir) if chess_dir else CHESS)
    if chess not in sys.path:
        sys.path.insert(0, chess)
    for name in ("common", "pieces", "positions", "board"):
        sys.modules.pop(name, None)
    import board
    return board


def _state(board, turn):
    from common import Colours
    color = Colours.WHITE if turn == "white" else Colours.PIECE_BLACK
    return {
        "board": board.to_dict(),
        "turn": turn,
        "check": board.is_in_check(color),
    }


def new_game(chess_dir=None):
    board = _load(chess_dir).Board()
    return _state(board, "white")


def legal(state, square, chess_dir=None):
    module = _load(chess_dir)
    board = module.Board()
    board.from_dict(state["board"])
    moves = board.legal_moves_safe(tuple(square))
    return [list(move) for move in moves]


def move(state, start, end, chess_dir=None):
    module = _load(chess_dir)
    board = module.Board()
    board.from_dict(state["board"])
    start, end = tuple(start), tuple(end)
    allowed = [tuple(item) for item in board.legal_moves_safe(start)]
    if end not in allowed:
        raise ValueError("illegal move")
    board.move_piece(start, end)
    if board.promotion_pending:
        x, y = board.promotion_pending
        board.matrix[x][y].occupant.piece_type = "queen"
        board.promotion_pending = None
    turn = "black" if state.get("turn") == "white" else "white"
    return _state(board, turn)


def set_rule(state, piece_type, rule_index, flag, value):
    module = _load()
    board = module.Board()
    board.from_dict(state["board"])
    rule = board.pieces_defs[piece_type]["move_rules"][int(rule_index)]
    rule[flag] = bool(value)
    fresh = module.Board()
    fresh.pieces_defs = board.pieces_defs
    fresh.from_dict(state["board"])
    fresh.pieces_defs = board.pieces_defs
    return {**_state(fresh, state.get("turn", "white")), "rules": board.pieces_defs}
