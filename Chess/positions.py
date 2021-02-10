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
        pass

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
