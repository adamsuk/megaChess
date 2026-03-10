"""
The main game control.
"""
import pygame
import sys
from pygame import locals

from board import Board
from common import Colours, Directions
from win_conditions import ChessWinCondition

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

        self.turn = Colours.WHITE
        self.selected_piece = None  # a board location.
        self.selected_legal_moves = []
        self.click = False

        # Swap this to change how the game is won (e.g. CheckersWinCondition()).
        self.win_condition = ChessWinCondition()

    def setup(self):
        """Draws the window and board at the beginning of the game"""
        self.graphics.setup_window()
        self.graphics.load_piece_icons(self.board.pieces_defs)

    def event_loop(self):
        """
        The event loop. This is where events are triggered
        (like a mouse click) and then effect the game state.
        """
        self.mouse_pos = self.graphics.board_coords(pygame.mouse.get_pos())  # what square is the mouse in?
        if self.selected_piece != None:
            self.selected_legal_moves = self.win_condition.safe_moves(self.board, self.selected_piece)

        for event in pygame.event.get():

            if event.type == locals.QUIT:
                self.terminate_game()

            self.click = event.type == locals.MOUSEBUTTONDOWN

            if self.click:
                if self.board.location(self.mouse_pos).occupant != None and self.board.location(
                        self.mouse_pos).occupant.color == self.turn:
                    self.selected_piece = self.mouse_pos

                elif self.selected_piece != None and self.mouse_pos in self.win_condition.safe_moves(self.board, self.selected_piece):
                    self.board.move_piece(self.selected_piece, self.mouse_pos)
                    self.end_turn()

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
        End the turn. Switches the current player, then asks the active
        win condition whether the game is over.
        """
        if self.turn == Colours.WHITE:
            self.turn = Colours.PIECE_BLACK
        else:
            self.turn = Colours.WHITE

        self.selected_piece = None
        self.selected_legal_moves = []

        result = self.win_condition.check(self)
        if result:
            if result.permanent:
                self.graphics.draw_message(result.message)
            else:
                self.graphics.draw_timed_message(result.message)


class Graphics:
    def __init__(self):
        self.caption = "megaChess"

        self.fps = 60
        self.clock = pygame.time.Clock()

        pygame.init()
        info = pygame.display.Info()
        self.window_size = min(info.current_w, info.current_h)
        self.screen = pygame.display.set_mode((self.window_size, self.window_size))
        # self.background = pygame.image.load('resources/board.png')
        
        self.square_size = self.window_size // 8
        self.piece_size = self.square_size // 2
        self.piece_font = pygame.font.SysFont(None, self.piece_size)

        self.message = False

        self.timed_message_surface = None
        self.timed_message_rect = None
        self.timed_message_until = 0  # pygame.time.get_ticks() expiry

        self.piece_icons = {}  # (piece_type, 'white'|'black') -> scaled Surface

        self.highlights = False

    def load_piece_icons(self, pieces_defs):
        """
        Load and scale piece icon images whose paths are defined in pieces_defs.
        Missing files are silently skipped; draw_board_pieces falls back to
        circle+letter rendering for any piece that has no icon loaded.
        """
        self.piece_icons = {}
        icon_size = (self.square_size - 8, self.square_size - 8)
        for piece_type, defn in pieces_defs.items():
            for color_name, path in defn.get('icons', {}).items():
                try:
                    img = pygame.image.load(path).convert_alpha()
                    self.piece_icons[(piece_type, color_name)] = (
                        pygame.transform.smoothscale(img, icon_size)
                    )
                except (pygame.error, FileNotFoundError, OSError):
                    pass  # graceful fallback to circle+letter

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
        self.draw_board_squares(board)
        if click:
            self.highlight_squares(legal_moves, self.pixel_coords(mouse_pos))
        elif not click and self.highlights:
            self.highlights = False

        self.draw_board_pieces(board)

        if self.message:
            self.screen.blit(self.text_surface_obj, self.text_rect_obj)

        if self.timed_message_surface and pygame.time.get_ticks() < self.timed_message_until:
            self.screen.blit(self.timed_message_surface, self.timed_message_rect)

        pygame.display.update()
        self.clock.tick(self.fps)

    def draw_board_squares(self, board):
        """
        Takes a board object and draws all of its squares to the display
        """
        for x in xrange(8):
            for y in xrange(8):
                pygame.draw.rect(self.screen, board.matrix[int(x)][int(y)].color,
                                 (x * self.square_size, y * self.square_size, self.square_size, self.square_size), )

    def draw_board_pieces(self, board):
        """
        Takes a board object and draws all of its pieces to the display.
        Uses icon images when available, falls back to circle+letter otherwise.
        """
        piece_labels = {'pawn': 'P', 'rook': 'R', 'knight': 'N', 'bishop': 'B', 'queen': 'Q', 'king': 'K'}
        for x in xrange(8):
            for y in xrange(8):
                piece = board.matrix[int(x)][int(y)].occupant
                if piece is not None:
                    center = self.pixel_coords((x, y))
                    color_key = 'white' if piece.color == Colours.WHITE else 'black'
                    icon = self.piece_icons.get((piece.piece_type, color_key))
                    if icon:
                        self.screen.blit(icon, icon.get_rect(center=center))
                    else:
                        pygame.draw.circle(self.screen, piece.color, center, self.piece_size)
                        outline = Colours.BLACK if piece.color == Colours.WHITE else Colours.WHITE
                        pygame.draw.circle(self.screen, outline, center, self.piece_size, 2)
                        label = piece_labels.get(piece.piece_type, '?')
                        text_color = Colours.BLACK if piece.color == Colours.WHITE else Colours.WHITE
                        text_surf = self.piece_font.render(label, True, text_color)
                        self.screen.blit(text_surf, text_surf.get_rect(center=center))

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
        x = min(max(pixel_x // self.square_size, 0), 7)
        y = min(max(pixel_y // self.square_size, 0), 7)
        return (x, y)

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
        self.draw_board_squares(board)
        self.highlights = False

    def draw_message(self, message):
        """Draws a permanent centred message (win / stalemate)."""
        self.message = True
        self.font_obj = pygame.font.Font('freesansbold.ttf', 44)
        self.text_surface_obj = self.font_obj.render(message, True, Colours.HIGH, Colours.BLACK)
        self.text_rect_obj = self.text_surface_obj.get_rect()
        self.text_rect_obj.center = (self.window_size / 2, self.window_size / 2)

    def draw_timed_message(self, message, duration_ms=3000):
        """Draws a temporary message near the top of the board that expires after duration_ms."""
        font = pygame.font.Font('freesansbold.ttf', 36)
        self.timed_message_surface = font.render(message, True, Colours.BLACK, Colours.HIGH)
        self.timed_message_rect = self.timed_message_surface.get_rect()
        self.timed_message_rect.center = (self.window_size // 2, self.square_size // 2)
        self.timed_message_until = pygame.time.get_ticks() + duration_ms


def main():
	game = Game()
	game.main()

if __name__ == "__main__":
	main()
