"""
Win / endgame condition strategies.

Each class exposes two methods:

  check(game)  -> str | None
      Called after every move.  Returns a display message (e.g. "WHITE WINS!",
      "STALEMATE!") when the game is over, or None while it is still ongoing.

  safe_moves(board, coord) -> list
      Returns the moves that should be offered to the player at `coord`.
      Chess filters out moves that leave the king in check; checkers does not.

Swap ``game.win_condition`` at any time to change how the game is won.
"""

from common import Colours


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
      - Checkmate  : current player's king is in check and they have no safe moves.
      - Stalemate  : current player is NOT in check but has no safe moves.
    """

    def check(self, game):
        current = game.turn

        has_safe = False
        for x in range(8):
            for y in range(8):
                sq = game.board.location((x, y))
                if sq.occupant and sq.occupant.color == current:
                    if game.board.legal_moves_safe((x, y)):
                        has_safe = True
                        break
            if has_safe:
                break

        if not has_safe:
            if game.board.is_in_check(current):
                # Checkmate — the side that just moved wins
                return 'BLACK WINS!' if current == Colours.WHITE else 'WHITE WINS!'
            return 'STALEMATE!'

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
        for x in range(8):
            for y in range(8):
                sq = game.board.location((x, y))
                if sq.occupant and sq.occupant.color == current:
                    if game.board.legal_moves((x, y)):
                        has_move = True
                        break
            if has_move:
                break

        if not has_move:
            return 'BLACK WINS!' if current == Colours.WHITE else 'WHITE WINS!'

        return None
