"""
Positions - a module used to determine the potential and legal positions a single piece can move
"""

class PosiblePositions:
    def __init__(self,
                 init_pos,
                 deltas,
                 board_size,
                 other_peices):
        self.init_pos = init_pos
        # posible positions
        self.current_x = init_pos[0]
        self.current_y = init_pos[1]
        self.deltas = deltas
        self.board_size = board_size
        self.other_peices = other_peices
        # define output variables
        self.pos_pos = []
        self.legal_pos = []
        # run methods here
        self._determine_delta_pos()
        self.pos_positions()
        self.legal_positions()

    def _determine_delta_pos(self):
        """
        Method for working out delta in positions
        """
        if not all([isinstance(delta, (list, tuple)) for delta in self.deltas]):
            print(self.deltas)

    def pos_positions(self):
        """
        Method to work out the possible positions based on current and peice deltas.
        """
        for delta in self.deltas:
            x_delta = delta[0]
            y_delta = delta[1]
            self.pos_pos.append([self.current_x + x_delta, self.current_y + y_delta])

    def legal_positions(self):
        """
        Determine if possible positions are legal
        """
        if not self.pos_pos:
            self.pos_positions()
        for pos_x, pos_y in self.pos_pos:
            # is possible position in the other_peices list
            if not [pos_x, pos_y] in self.other_peices:
                # is it in board boundary?
                if self._position_inside_board(pos_x, pos_y, self.board_size[0], self.board_size[1]):
                    self.legal_pos.append([pos_x, pos_y])

    @staticmethod
    def _position_inside_board(x, y, board_size_x, board_size_y):
        legal_pos = True
        # booleans for illegal moves
        if x < 0 or y < 0 or x > board_size_x or y > board_size_y:
            legal_pos = False
        return legal_pos

class ChessMoves:
    """
    Computes legal chess moves for a single piece given the full board state.
    Uses piece definitions loaded from pieces_defs.json.
    """
    def __init__(self, pos, piece_type, piece_color, board_matrix, piece_defs, white_color):
        self.pos = pos
        self.piece_type = piece_type
        self.piece_color = piece_color
        self.board = board_matrix
        self.defs = piece_defs
        self.white_color = white_color
        self.legal = []
        self._compute()

    def _on_board(self, x, y):
        return 0 <= x <= 7 and 0 <= y <= 7

    def _occupant(self, x, y):
        return self.board[x][y].occupant

    def _is_enemy(self, x, y):
        occ = self._occupant(x, y)
        return occ is not None and occ.color != self.piece_color

    def _is_friendly(self, x, y):
        occ = self._occupant(x, y)
        return occ is not None and occ.color == self.piece_color

    def _compute(self):
        if self.piece_type == 'pawn':
            self._pawn_moves()
        elif self.piece_type in ('bishop', 'rook', 'queen'):
            deltas = self.defs.get(self.piece_type, {}).get('deltas', [])
            self._sliding_moves(deltas)
        else:
            deltas = self.defs.get(self.piece_type, {}).get('deltas', [])
            self._fixed_moves(deltas)

    def _pawn_moves(self):
        x, y = self.pos
        direction = -1 if self.piece_color == self.white_color else 1
        start_row = 6 if self.piece_color == self.white_color else 1

        # Forward one square (no capture)
        ny = y + direction
        if self._on_board(x, ny) and self._occupant(x, ny) is None:
            self.legal.append((x, ny))
            # Forward two squares from starting row
            if y == start_row:
                ny2 = y + 2 * direction
                if self._on_board(x, ny2) and self._occupant(x, ny2) is None:
                    self.legal.append((x, ny2))

        # Diagonal captures
        for dx in (-1, 1):
            nx, ny = x + dx, y + direction
            if self._on_board(nx, ny) and self._is_enemy(nx, ny):
                self.legal.append((nx, ny))

    def _sliding_moves(self, deltas):
        x, y = self.pos
        directions = []
        for d in deltas:
            if d == "diagonal":
                directions += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
            elif d == "straight":
                directions += [(1, 0), (-1, 0), (0, 1), (0, -1)]
            else:
                directions.append(tuple(d))

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            while self._on_board(nx, ny):
                if self._is_friendly(nx, ny):
                    break
                self.legal.append((nx, ny))
                if self._is_enemy(nx, ny):
                    break
                nx += dx
                ny += dy

    def _fixed_moves(self, deltas):
        x, y = self.pos
        for d in deltas:
            nx, ny = x + d[0], y + d[1]
            if self._on_board(nx, ny) and not self._is_friendly(nx, ny):
                self.legal.append((nx, ny))


if __name__ == "__main__":
    # [x,y]
    init_pos = [4,3]
    deltas = [[2,1],[1,2],[-1,2],[-2,1],[-1,-2],[-2,-1],[1,-2],[2,-1]]
    board_size = [7,7]
    other_peices = []

    PosPos = PosiblePositions(init_pos=init_pos,
                              deltas=deltas,
                              board_size=board_size,
                              other_peices=other_peices)
    print(PosPos.legal_pos)
