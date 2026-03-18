"""
Positions - a module used to determine the potential and legal positions a single piece can move
"""

class PieceMoves:
    """
    Computes legal moves for any piece by interpreting move_rules from pieces_defs.json.

    Supported rule properties:
      deltas              - list of [dx, dy] vectors or keywords "diagonal"/"straight"
      sliding             - if true, ray-cast in each direction until blocked
      directional         - if true, dy is relative to the piece's forward direction
                            (white moves toward lower y, black toward higher y)
      move_only           - squares occupied by any piece are not legal destinations
      capture_only        - can only move to squares occupied by an enemy
      jump_capture        - checkers-style: jump over one enemy to an empty square
      first_move_extra_steps        - extra steps allowed on the first move
      first_move_start_rows_from_back - how many rows from the back rank the start row is
    """

    DELTA_KEYWORDS = {
        "diagonal": [(1, 1), (1, -1), (-1, 1), (-1, -1)],
        "straight": [(1, 0), (-1, 0), (0, 1), (0, -1)],
    }

    def __init__(self, pos, piece_type, piece_color, board_matrix, piece_defs, white_color):
        self.pos = pos
        self.piece_type = piece_type
        self.piece_color = piece_color
        self.board = board_matrix
        self.defs = piece_defs
        self.is_white = (piece_color == white_color)
        self.legal = []
        self._compute()

    def _on_board(self, x, y):
        if not (0 <= x <= 7 and 0 <= y <= 7):
            return False
        return not self.board[x][y].is_hole

    def _occupant(self, x, y):
        return self.board[x][y].occupant

    def _is_enemy(self, x, y):
        occ = self._occupant(x, y)
        return occ is not None and occ.color != self.piece_color

    def _is_friendly(self, x, y):
        occ = self._occupant(x, y)
        return occ is not None and occ.color == self.piece_color

    def _expand_deltas(self, deltas):
        result = []
        for d in deltas:
            if isinstance(d, str):
                result.extend(self.DELTA_KEYWORDS.get(d, []))
            else:
                result.append(tuple(d))
        return result

    def _apply_direction(self, deltas):
        """Flip dy for pieces moving in the colour-relative forward direction."""
        sign = -1 if self.is_white else 1
        return [(dx, dy * sign) for dx, dy in deltas]

    def _compute(self):
        piece_def = self.defs.get(self.piece_type, {})
        for rule in piece_def.get('move_rules', []):
            self._apply_rule(rule)

    def _apply_rule(self, rule):
        x, y = self.pos
        deltas = self._expand_deltas(rule.get('deltas', []))
        if rule.get('directional'):
            deltas = self._apply_direction(deltas)

        sliding     = rule.get('sliding', False)
        move_only   = rule.get('move_only', False)
        capture_only = rule.get('capture_only', False)
        jump_capture = rule.get('jump_capture', False)

        max_steps = 1
        extra = rule.get('first_move_extra_steps', 0)
        if extra:
            rows_from_back = rule.get('first_move_start_rows_from_back', 0)
            direction = -1 if self.is_white else 1
            back_row  = 7 if self.is_white else 0
            start_row = back_row + direction * rows_from_back
            if y == start_row:
                max_steps += extra

        for dx, dy in deltas:
            if jump_capture:
                self._jump(x, y, dx, dy)
            elif sliding:
                self._slide(x, y, dx, dy, move_only, capture_only)
            else:
                self._step(x, y, dx, dy, max_steps, move_only, capture_only)

    def _step(self, x, y, dx, dy, max_steps, move_only, capture_only):
        steps = 0
        nx, ny = x + dx, y + dy
        while self._on_board(nx, ny):
            if steps >= max_steps:
                break
            if self._is_friendly(nx, ny):
                break
            is_capture = self._is_enemy(nx, ny)
            if is_capture and move_only:
                break
            if not is_capture and capture_only:
                break
            self.legal.append((nx, ny))
            if is_capture:
                break
            steps += 1
            nx += dx
            ny += dy

    def _slide(self, x, y, dx, dy, move_only, capture_only):
        nx, ny = x + dx, y + dy
        while self._on_board(nx, ny):
            if self._is_friendly(nx, ny):
                break
            is_capture = self._is_enemy(nx, ny)
            if is_capture and move_only:
                break
            if not is_capture and capture_only:
                nx += dx
                ny += dy
                continue
            self.legal.append((nx, ny))
            if is_capture:
                break
            nx += dx
            ny += dy

    def _jump(self, x, y, dx, dy):
        """Checkers-style jump: land on empty square after leaping over one enemy."""
        mx, my = x + dx, y + dy      # intermediate (enemy) square
        lx, ly = x + 2 * dx, y + 2 * dy  # landing square
        if self._on_board(lx, ly) and self._is_enemy(mx, my) and self._occupant(lx, ly) is None:
            self.legal.append((lx, ly))


