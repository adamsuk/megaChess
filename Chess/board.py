import pygame
import sys
from pygame import locals

from common import Colours, Directions
from pieces import AllPieces
from positions import PieceMoves

try:
    # Python 2
    xrange
except NameError:
    # Python 3, xrange is now named range
    xrange = range

pygame.font.init()

class Board:
	def __init__(self):
		self.pieces_defs = AllPieces().pieces_defs
		self.new_board()

	def draw_board_squares(self):
		for x in xrange(8):
			for y in xrange(8):
				color = Colours.CREAM if (x + y) % 2 == 0 else Colours.BROWN
				self.matrix[int(y)][int(x)] = Square(color, (x, y))

	def new_board(self):
		"""
		Create a new board matrix.
		"""

		# initialize squares and place them in matrix

		self.matrix = [[None] * 8 for i in xrange(8)]

		# initialize the board squares
		self.draw_board_squares()

		# initialize chess pieces in starting positions
		back_rank = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook']
		for x in xrange(8):
			self.matrix[x][0].occupant = Piece(Colours.PIECE_BLACK, back_rank[x])
			self.matrix[x][1].occupant = Piece(Colours.PIECE_BLACK, 'pawn')
			self.matrix[x][6].occupant = Piece(Colours.WHITE, 'pawn')
			self.matrix[x][7].occupant = Piece(Colours.WHITE, back_rank[x])


	def rel(self, dir, coord_tuple):
		"""
		Returns the coordinates one square in a different direction to (x,y).

		===DOCTESTS===

		>>> board = Board()

		>>> board.rel(Directions.NORTHWEST, (1,2))
		(0,1)

		>>> board.rel(Directions.SOUTHEAST, (3,4))
		(4,5)

		>>> board.rel(Directions.NORTHEAST, (3,6))
		(4,5)

		>>> board.rel(Directions.SOUTHWEST, (2,5))
		(1,6)
		"""
		x, y = coord_tuple
		if dir == Directions.NORTHWEST:
			return (x - 1, y - 1)
		elif dir == Directions.NORTHEAST:
			return (x + 1, y - 1)
		elif dir == Directions.SOUTHWEST:
			return (x - 1, y + 1)
		elif dir == Directions.SOUTHEAST:
			return (x + 1, y + 1)
		else:
			return 0

	def adjacent(self, coord_tuple):
		"""
		Returns a list of squares locations that are adjacent (on a diagonal) to (x,y).
		"""
		x, y = coord_tuple
		return [self.rel(Directions.NORTHWEST, (x,y)), self.rel(Directions.NORTHEAST, (x,y)),self.rel(Directions.SOUTHWEST, (x,y)),self.rel(Directions.SOUTHEAST, (x,y))]

	def location(self, coord_tuple):
		"""
		Takes a set of coordinates as arguments and returns self.matrix[int(x)][int(y)]
		This can be faster than writing something like self.matrix[coords[0]][coords[1]]
		"""
		x, y = coord_tuple
		return self.matrix[int(x)][int(y)]

	def legal_moves(self, coord_tuple, hop=False):
		"""
		Returns a list of legal move locations for the piece at (x,y).
		Uses ChessMoves to compute per-piece-type chess movement from pieces_defs.json.
		"""
		x, y = coord_tuple
		piece = self.matrix[int(x)][int(y)].occupant
		if piece is None:
			return []
		return PieceMoves(
			pos=(x, y),
			piece_type=piece.piece_type,
			piece_color=piece.color,
			board_matrix=self.matrix,
			piece_defs=self.pieces_defs,
			white_color=Colours.WHITE
		).legal

	def nearest_square(self, mouse_pos):
		return self.matrix[int(mouse_pos[1])][int(mouse_pos[0])].coords

	def remove_piece(self, coord_tuple):
		"""
		Removes a piece from the board at position (x,y). 
		"""
		x, y = coord_tuple
		self.matrix[int(x)][int(y)].occupant = None

	def move_piece(self, start_coord_tuple, end_coord_tuple):
		"""
		Move a piece from (start_x, start_y) to (end_x, end_y).
		"""
		start_x, start_y = start_coord_tuple
		end_x, end_y = end_coord_tuple
		self.matrix[end_x][end_y].occupant = self.matrix[start_x][start_y].occupant
		self.remove_piece((start_x, start_y))

		self.king((end_x, end_y))

	def is_end_square(self, coords):
		"""
		Is passed a coordinate tuple (x,y), and returns true or 
		false depending on if that square on the board is an end square.

		===DOCTESTS===

		>>> board = Board()

		>>> board.is_end_square((2,7))
		True

		>>> board.is_end_square((5,0))
		True

		>>>board.is_end_square((0,5))
		False
		"""

		if coords[1] == 0 or coords[1] == 7:
			return True
		else:
			return False

	def on_board(self, coord_tuple):
		"""
		Checks to see if the given square (x,y) lies on the board.
		If it does, then on_board() return True. Otherwise it returns false.

		===DOCTESTS===
		>>> board = Board()

		>>> board.on_board((5,0)):
		True

		>>> board.on_board(-2, 0):
		False

		>>> board.on_board(3, 9):
		False
		"""
		x, y = coord_tuple
		if x < 0 or y < 0 or x > 7 or y > 7:
			return False
		else:
			return True


	def king(self, coord_tuple):
		"""
		Takes in (x,y), the coordinates of square to be considered for kinging.
		If it meets the criteria, then king() kings the piece in that square and kings it.
		"""
		x, y = coord_tuple
		pass

	# ------------------------------------------------------------------
	# Check / checkmate helpers
	# ------------------------------------------------------------------

	def find_king(self, color):
		"""Returns (x, y) of the king belonging to `color`, or None."""
		for x in xrange(8):
			for y in xrange(8):
				piece = self.matrix[x][y].occupant
				if piece and piece.color == color and piece.piece_type == 'king':
					return (x, y)
		return None

	def is_in_check(self, color):
		"""Returns True if the king of `color` is currently under attack."""
		king_pos = self.find_king(color)
		if king_pos is None:
			return False
		for x in xrange(8):
			for y in xrange(8):
				piece = self.matrix[x][y].occupant
				if piece and piece.color != color:
					if king_pos in PieceMoves(
						pos=(x, y),
						piece_type=piece.piece_type,
						piece_color=piece.color,
						board_matrix=self.matrix,
						piece_defs=self.pieces_defs,
						white_color=Colours.WHITE
					).legal:
						return True
		return False

	def _simulate_move(self, start, end):
		"""Temporarily applies a move. Returns the piece that was on `end` (may be None)."""
		sx, sy = start
		ex, ey = end
		captured = self.matrix[ex][ey].occupant
		self.matrix[ex][ey].occupant = self.matrix[sx][sy].occupant
		self.matrix[sx][sy].occupant = None
		return captured

	def _undo_move(self, start, end, captured):
		"""Reverses a simulated move."""
		sx, sy = start
		ex, ey = end
		self.matrix[sx][sy].occupant = self.matrix[ex][ey].occupant
		self.matrix[ex][ey].occupant = captured

	def legal_moves_safe(self, coord_tuple):
		"""
		Like legal_moves(), but filters out moves that would leave the
		moving player's own king in check.
		"""
		piece = self.location(coord_tuple).occupant
		if piece is None:
			return []
		safe = []
		for dest in self.legal_moves(coord_tuple):
			captured = self._simulate_move(coord_tuple, dest)
			if not self.is_in_check(piece.color):
				safe.append(dest)
			self._undo_move(coord_tuple, dest, captured)
		return safe

class Piece:
	def __init__(self, color, piece_type, king=False):
		self.color = color
		self.piece_type = piece_type
		self.king = king

class Square:
	def __init__(self, color, coords, occupant=None):
		self.color = color # color is either BLACK or WHITE
		self.occupant = occupant # occupant is a Square object
		self.coords = coords
