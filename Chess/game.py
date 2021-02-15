"""
The main game control.
"""
import pygame
import sys
from pygame import locals

from board import Board
from common import Colours, Directions

try:
    # Python 2
    xrange
except NameError:
    # Python 3, xrange is now named range
    xrange = range

class Game:

    def __init__(self):
        """
        The main game control.
        """
        self.graphics = Graphics()
        self.board = Board()

        self.turn = Colours.BLUE
        self.selected_piece = None  # a board location.
        self.hop = False
        self.selected_legal_moves = []
        self.click = False

    def setup(self):
        """Draws the window and board at the beginning of the game"""
        self.graphics.setup_window()

    def event_loop(self):
        """
        The event loop. This is where events are triggered
        (like a mouse click) and then effect the game state.
        """
        self.mouse_pos = self.graphics.board_coords(pygame.mouse.get_pos())  # what square is the mouse in?
        if self.selected_piece != None:
            self.selected_legal_moves = self.board.legal_moves(self.selected_piece, self.hop)

        for event in pygame.event.get():

            if event.type == locals.QUIT:
                self.terminate_game()

            self.click = event.type == locals.MOUSEBUTTONDOWN

            if self.click:
                print('mouse_pos: {}'.format(self.mouse_pos))
                selected_square = self.board.nearest_square(self.mouse_pos)
                print('selected_square: {}'.format(selected_square))
                selected_pixels = self.graphics.pixel_coords(selected_square)
                print('selected_pixels: {}'.format(selected_pixels))

                if self.hop == False:
                    if self.board.location(self.mouse_pos).occupant != None and self.board.location(
                            self.mouse_pos).occupant.color == self.turn:
                        # TODO: this centers on the cursor not the piece - ie a self.board method
                        self.selected_piece = selected_square

                    elif self.selected_piece != None and self.mouse_pos in self.board.legal_moves(self.selected_piece):

                        self.board.move_piece(self.selected_piece, selected_square)

                        if self.mouse_pos not in self.board.adjacent(self.selected_piece):
                            self.board.remove_piece((self.selected_piece[0] + (
                                        self.mouse_pos[0] - self.selected_piece[0]) / 2, self.selected_piece[1] + (
                                                                 self.mouse_pos[1] - self.selected_piece[1]) / 2))

                            self.hop = True
                            self.selected_piece = selected_square

                        else:
                            self.end_turn()

                if self.hop == True:
                    if self.selected_piece != None and self.mouse_pos in self.board.legal_moves(self.selected_piece,
                                                                                                self.hop):
                        self.board.move_piece(self.selected_piece, selected_square)
                        self.board.remove_piece((self.selected_piece[0] + (
                                    self.mouse_pos[0] - self.selected_piece[0]) / 2, self.selected_piece[1] + (
                                                             self.mouse_pos[1] - self.selected_piece[1]) / 2))

                    if self.board.legal_moves(self.mouse_pos, self.hop) == []:
                        self.end_turn()

                    else:
                        self.selected_piece = selected_square

    def update(self):
        """Calls on the graphics class to update the game display."""
        self.graphics.update_display(self.board,
                                     self.selected_legal_moves,
                                     self.selected_piece,
                                     self.mouse_pos,
                                     self.click)

    def terminate_game(self):
        """Quits the program and ends the game."""
        pygame.quit()
        sys.exit

    def main(self):
        """"This executes the game and controls its flow."""
        self.setup()

        while True:  # main game loop
            self.event_loop()
            self.update()

    def end_turn(self):
        """
        End the turn. Switches the current player.
        end_turn() also checks for and game and resets a lot of class attributes.
        """
        if self.turn == Colours.BLUE:
            self.turn = Colours.RED
        else:
            self.turn = Colours.BLUE

        self.selected_piece = None
        self.selected_legal_moves = []
        self.hop = False

        if self.check_for_endgame():
            if self.turn == Colours.BLUE:
                self.graphics.draw_message("RED WINS!")
            else:
                self.graphics.draw_message("BLUE WINS!")

    def check_for_endgame(self):
        """
        Checks to see if a player has run out of moves or pieces. If so, then return True. Else return False.
        """
        for x in xrange(8):
            for y in xrange(8):
                if self.board.location((x, y)).color == Colours.BLACK and self.board.location(
                        (x, y)).occupant != None and self.board.location((x, y)).occupant.color == self.turn:
                    if self.board.legal_moves((x, y)) != []:
                        return False

        return True


class Graphics:
    def __init__(self):
        self.caption = "megaChess"

        self.fps = 60
        self.clock = pygame.time.Clock()

        self.window_size = 600
        self.screen = pygame.display.set_mode((self.window_size, self.window_size))
        # self.background = pygame.image.load('resources/board.png')
        
        self.square_size = self.window_size / 8
        self.piece_size = self.square_size / 2

        self.message = False

        self.highlights = False

    def setup_window(self):
        """
        This initializes the window and sets the caption at the top.
        """
        pygame.init()
        pygame.display.set_caption(self.caption)

    def update_display(self, board, legal_moves, selected_piece, mouse_pos, click):
        """
        This updates the current display.
        """
        # self.screen.blit(self.background, (0,0))
        print('click: {}'.format(click))
        print('self.highlights: {}'.format(self.highlights))
        if click:
            self.highlight_squares(legal_moves, self.pixel_coords(mouse_pos))
        #elif not click and self.highlights:
        #    self.del_highlight_squares(board)

        self.draw_board_pieces(board)

        if self.message:
            self.screen.blit(self.text_surface_obj, self.text_rect_obj)

        pygame.display.update()
        self.clock.tick(self.fps)

    def draw_board_squares(self, board):
        """
        Takes a board object and draws all of its squares to the display
        """
        for x in xrange(8):
            for y in xrange(8):
                pygame.draw.rect(self.screen, board[int(x)][int(y)].color,
                                 (x * self.square_size, y * self.square_size, self.square_size, self.square_size), )

    def draw_board_pieces(self, board):
        """
        Takes a board object and draws all of its pieces to the display
        """
        for x in xrange(8):
            for y in xrange(8):
                if board.matrix[int(x)][int(y)].occupant != None:
                    #print(self.screen, board.matrix[int(x)][int(y)].occupant.color, self.pixel_coords((x, y)),
                    #      self.piece_size)
                    pygame.draw.circle(self.screen, board.matrix[int(x)][int(y)].occupant.color,
                                       self.pixel_coords((x, y)), self.piece_size)

                    if board.location((x, y)).occupant.king == True:
                        pygame.draw.circle(self.screen, GOLD, self.pixel_coords((x, y)), int(self.piece_size / 1.7),
                                           self.piece_size / 4)

    def pixel_coords(self, board_coords):
        """
        Takes in a tuple of board coordinates (x,y)
        and returns the pixel coordinates of the center of the square at that location.
        """
        return ((board_coords[0] * self.square_size) + self.piece_size, (board_coords[1] * self.square_size) + self.piece_size)

    def board_coords(self, pixel_coords_tuple):
        """
        Does the reverse of pixel_coords(). Takes in a tuple of of pixel coordinates and returns what square they are in.
        """
        pixel_x, pixel_y = pixel_coords_tuple
        #print(pixel_x / self.square_size, pixel_y / self.square_size)
        return (pixel_x / self.square_size, pixel_y / self.square_size)

    def highlight_squares(self, squares, origin):
        """
        Squares is a list of board coordinates.
        highlight_squares highlights them.
        """
        self.highlighted_squares = squares
        for square in squares:
            pygame.draw.rect(self.screen, Colours.HIGH, (
                square[0] * self.square_size, square[1] * self.square_size, 
                self.square_size, self.square_size))

        if origin != None:
            pygame.draw.rect(self.screen, Colours.HIGH, (
                origin[0] * self.square_size, origin[1] * self.square_size, 
                self.square_size, self.square_size))
        
        self.highlights = True

    def del_highlight_squares(self, board):
        # redraw board squares
        board.draw_board_squares()
        self.highlights = False

    def draw_message(self, message):
        """
        Draws message to the screen.
        """
        self.message = True
        self.font_obj = pygame.font.Font('freesansbold.ttf', 44)
        self.text_surface_obj = self.font_obj.render(message, True, Colours.HIGH, Colours.BLACK)
        self.text_rect_obj = self.text_surface_obj.get_rect()
        self.text_rect_obj.center = (self.window_size / 2, self.window_size / 2)


def main():
	game = Game()
	game.main()

if __name__ == "__main__":
	main()
