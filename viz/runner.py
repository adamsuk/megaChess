"""Run megaChess rules without copying them or opening the PyGame window.

board.py imports pygame at module level. This runner stubs that module,
then imports Chess/board.py, positions.py, pieces.py and win_conditions.py.
"""

import sys
import types
from pathlib import Path
from types import SimpleNamespace

try:
    ROOT = Path(__file__).resolve().parents[1]
except NameError:
    ROOT = Path("/chess")
CHESS = ROOT / "Chess"
FLAGS = ("sliding", "directional", "move_only", "capture_only", "jump_capture")


def _stub_pygame():
    pygame = types.ModuleType("pygame")
    pygame.font = types.SimpleNamespace(init=lambda: None, Font=lambda *a, **k: None, SysFont=lambda *a, **k: None)
    pygame.locals = types.ModuleType("pygame.locals")
    pygame.display = types.SimpleNamespace(set_mode=lambda *a, **k: None, set_caption=lambda *a: None, get_surface=lambda: None, update=lambda: None, flip=lambda: None)
    pygame.draw = types.SimpleNamespace(rect=lambda *a, **k: None, line=lambda *a, **k: None, circle=lambda *a, **k: None)
    pygame.Surface = lambda *a, **k: types.SimpleNamespace(fill=lambda *a: None, blit=lambda *a: None)
    pygame.SRCALPHA = 0
    pygame.time = types.SimpleNamespace(Clock=lambda: None, get_ticks=lambda: 0)
    pygame.Rect = lambda *a: types.SimpleNamespace(collidepoint=lambda *a: False)
    pygame.image = types.SimpleNamespace(load=lambda *a: None)
    pygame.transform = types.SimpleNamespace(scale=lambda *a: None)
    sys.modules["pygame"] = pygame
    sys.modules["pygame.locals"] = pygame.locals


def _load(chess_dir=None):
    _stub_pygame()
    chess = str(Path(chess_dir) if chess_dir else CHESS)
    if chess not in sys.path:
        sys.path.insert(0, chess)
    for name in ("common", "pieces", "positions", "board", "win_conditions", "svg_renderer", "game"):
        sys.modules.pop(name, None)
    import board
    import win_conditions
    import game
    return board, win_conditions, game


def _condition(win, mode):
    if mode == "checkers":
        return win.CheckersWinCondition()
    return win.ChessWinCondition()


def _session(state, chess_dir):
    board_mod, win, _game = _load(chess_dir)
    board = board_mod.Board()
    rules = (state or {}).get("rules")
    if rules:
        board.pieces_defs = rules
    if state and state.get("board"):
        board.from_dict(state["board"])
        if rules:
            board.pieces_defs = rules
    return board_mod, board, win


def _layout_checkers(board_mod, board):
    from common import Colours
    board.new_board()
    for x in range(board.board_size):
        for y in range(board.board_size):
            board.matrix[x][y].occupant = None
    for y in range(3):
        for x in range(board.board_size):
            if (x + y) % 2:
                board.matrix[x][y].occupant = board_mod.Piece(Colours.PIECE_BLACK, "checkers_man")
    for y in range(board.board_size - 3, board.board_size):
        for x in range(board.board_size):
            if (x + y) % 2:
                board.matrix[x][y].occupant = board_mod.Piece(Colours.WHITE, "checkers_man")


def _state(board, turn, mode):
    from common import Colours
    color = Colours.WHITE if turn == "white" else Colours.PIECE_BLACK
    _, win, _game = _load()
    result = _condition(win, mode).check(SimpleNamespace(turn=color, board=board))
    return {
        "board": board.to_dict(),
        "turn": turn,
        "mode": mode,
        "rules": board.pieces_defs,
        "flags": list(FLAGS),
        "result": result.message if result else None,
    }


def new_game(chess_dir=None, mode="chess"):
    board_mod, board, _win = _session(None, chess_dir)
    if mode == "checkers":
        _layout_checkers(board_mod, board)
    return _state(board, "white", mode)


def legal(state, square, chess_dir=None):
    _board_mod, board, win = _session(state, chess_dir)
    moves = _condition(win, state.get("mode", "chess")).safe_moves(board, tuple(square))
    return [list(move) for move in moves]


def move(state, start, end, chess_dir=None):
    _board_mod, board, win = _session(state, chess_dir)
    mode = state.get("mode", "chess")
    start, end = tuple(start), tuple(end)
    allowed = [tuple(item) for item in _condition(win, mode).safe_moves(board, start)]
    if end not in allowed:
        raise ValueError("illegal move")
    board.move_piece(start, end)
    if board.promotion_pending:
        x, y = board.promotion_pending
        board.matrix[x][y].occupant.piece_type = "queen"
        board.promotion_pending = None
    turn = "black" if state.get("turn") == "white" else "white"
    return _state(board, turn, mode)


def set_rule(state, piece_type, rule_index, flag, value, chess_dir=None):
    _board_mod, board, _win = _session(state, chess_dir)
    rule = board.pieces_defs[piece_type]["move_rules"][int(rule_index)]
    rule[flag] = bool(value)
    return _state(board, state.get("turn", "white"), state.get("mode", "chess"))


def clone_piece(state, piece_type, chess_dir=None):
    _board_mod, board, _win = _session(state, chess_dir)
    name = piece_type if piece_type.endswith("_custom") else piece_type + "_custom"
    board.pieces_defs[name] = json_copy(board.pieces_defs[piece_type])
    return _state(board, state.get("turn", "white"), state.get("mode", "chess"))


def json_copy(value):
    import json
    return json.loads(json.dumps(value))


def presets(chess_dir=None):
    _board, _win, game = _load(chess_dir)
    return {
        "standard": game._preset_standard(),
        "diamond": game._preset_diamond(),
        "hexagon": game._preset_hexagon(),
    }


def expand_rules(rules, chess_dir=None):
    _board, _win, game = _load(chess_dir)
    return game._expand_keywords(json_copy(rules))


def start(chess_dir=None, mode="chess", rules=None, layout=None):
    board_mod, board, _win, = _session({"rules": rules, "board": layout} if layout else {"rules": rules}, chess_dir)
    if layout:
        board.from_dict(layout)
        if rules:
            board.pieces_defs = rules
    elif mode == "checkers":
        _layout_checkers(board_mod, board)
    return _state(board, "white", mode)
