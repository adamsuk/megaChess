"""
Win / endgame condition strategies.

Each class exposes two methods:

  check(game)  -> GameResult | None
      Called after every move.  Returns a GameResult when something
      noteworthy happened (check, checkmate, stalemate, win), or None
      while the game is ongoing and no check is present.

  safe_moves(board, coord) -> list
      Returns the moves that should be offered to the player at `coord`.
      Chess filters out moves that leave the king in check; checkers does not.

Swap ``game.win_condition`` at any time to change how the game is won.
"""

from common import Colours


class GameResult:
    """
    Returned by WinCondition.check().

    Attributes:
      message   (str)  - text to display
      permanent (bool) - True  → show until the game is restarted (win/stalemate)
                         False → show for a short time then fade (e.g. "CHECK!")
    """
    def __init__(self, message, permanent=True):
        self.message = message
        self.permanent = permanent


class WinCondition:
    """Abstract base. Subclass and override check() and optionally safe_moves()."""

    def check(self, game):
        raise NotImplementedError

    def safe_moves(self, board, coord):
        """Default: every pseudo-legal move is allowed."""
        return board.legal_moves(coord)


class ChessWinCondition(WinCondition):
    """
    Standard chess endgame:
      - Check      : current player's king is in check but they still have safe moves.
                     Returns a timed GameResult so "CHECK!" fades after a few seconds.
      - Checkmate  : current player's king is in check and they have no safe moves.
      - Stalemate  : current player is NOT in check but has no safe moves.
    """

    def check(self, game):
        current = game.turn

        has_safe = False
        N = game.board.board_size
        for x in range(N):
            for y in range(N):
                if game.board.matrix[x][y].is_hole:
                    continue
                sq = game.board.location((x, y))
                if sq.occupant and sq.occupant.color == current:
                    if game.board.legal_moves_safe((x, y)):
                        has_safe = True
                        break
            if has_safe:
                break

        in_check = game.board.is_in_check(current)

        if not has_safe:
            if in_check:
                # Checkmate — the side that just moved wins
                msg = 'BLACK WINS!' if current == Colours.WHITE else 'WHITE WINS!'
                return GameResult(msg, permanent=True)
            return GameResult('STALEMATE!', permanent=True)

        if in_check:
            # Still has moves, but king is under attack — temporary alert
            msg = 'WHITE IN CHECK!' if current == Colours.WHITE else 'BLACK IN CHECK!'
            return GameResult(msg, permanent=False)

        return None

    def safe_moves(self, board, coord):
        """Only show moves that don't leave the player's king in check."""
        return board.legal_moves_safe(coord)


class CheckersWinCondition(WinCondition):
    """
    Checkers endgame: a player wins when their opponent has no legal moves
    (all pieces captured or all blocked).
    """

    def check(self, game):
        current = game.turn

        has_move = False
        N = game.board.board_size
        for x in range(N):
            for y in range(N):
                if game.board.matrix[x][y].is_hole:
                    continue
                sq = game.board.location((x, y))
                if sq.occupant and sq.occupant.color == current:
                    if game.board.legal_moves((x, y)):
                        has_move = True
                        break
            if has_move:
                break

        if not has_move:
            msg = 'BLACK WINS!' if current == Colours.WHITE else 'WHITE WINS!'
            return GameResult(msg, permanent=True)

        return None
