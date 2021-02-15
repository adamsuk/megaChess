import pygame
import sys
from pygame import locals

from common import Colours, Directions

try:
    # Python 2
    xrange
except NameError:
    # Python 3, xrange is now named range
    xrange = range

pygame.font.init()

class Board:
	def __init__(self):
		self.new_board()

	def draw_board_squares(self):
		# The following code block has been adapted from
		# http://itgirl.dreamhosters.com/itgirlgames/games/Program%20Leaders/ClareR/Checkers/checkers.py
		for x in xrange(8):
			for y in xrange(8):
				if (x % 2 != 0) and (y % 2 == 0):
					self.matrix[int(y)][int(x)] = Square(Colours.WHITE, (x,y))
				elif (x % 2 != 0) and (y % 2 != 0):
					self.matrix[int(y)][int(x)] = Square(Colours.BLACK, (x,y))
				elif (x % 2 == 0) and (y % 2 != 0):
					self.matrix[int(y)][int(x)] = Square(Colours.WHITE, (x,y))
				elif (x % 2 == 0) and (y % 2 == 0): 
					self.matrix[int(y)][int(x)] = Square(Colours.BLACK, (x,y))

	def new_board(self):
		"""
		Create a new board matrix.
		"""

		# initialize squares and place them in matrix

		self.matrix = [[None] * 8 for i in xrange(8)]

		# initialize the board squares
		self.draw_board_squares()

		# initialize the pieces and put them in the appropriate squares

		for x in xrange(8):
			for y in xrange(3):
				if self.matrix[int(x)][int(y)].color == Colours.BLACK:
					self.matrix[int(x)][int(y)].occupant = Piece(Colours.RED)
			for y in xrange(5, 8):
				if self.matrix[int(x)][int(y)].color == Colours.BLACK:
					self.matrix[int(x)][int(y)].occupant = Piece(Colours.BLUE)


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

	def blind_legal_moves(self, coord_tuple):
		"""
		Returns a list of blind legal move locations from a set of coordinates (x,y) on the board. 
		If that location is empty, then blind_legal_moves() return an empty list.
		"""
		x, y = coord_tuple
		if self.matrix[int(x)][int(y)].occupant != None:
			
			if self.matrix[int(x)][int(y)].occupant.king == False and self.matrix[int(x)][int(y)].occupant.color == Colours.BLUE:
				blind_legal_moves = [self.rel(Directions.NORTHWEST, (x,y)), self.rel(Directions.NORTHEAST, (x,y))]
				
			elif self.matrix[int(x)][int(y)].occupant.king == False and self.matrix[int(x)][int(y)].occupant.color == Colours.RED:
				blind_legal_moves = [self.rel(Directions.SOUTHWEST, (x,y)), self.rel(Directions.SOUTHEAST, (x,y))]

			else:
				blind_legal_moves = [self.rel(Directions.NORTHWEST, (x,y)), self.rel(Directions.NORTHEAST, (x,y)), self.rel(Directions.SOUTHWEST, (x,y)), self.rel(Directions.SOUTHEAST, (x,y))]

		else:
			blind_legal_moves = []

		return blind_legal_moves

	def legal_moves(self, coord_tuple, hop = False):
		"""
		Returns a list of legal move locations from a given set of coordinates (x,y) on the board.
		If that location is empty, then legal_moves() returns an empty list.
		"""
		x, y = coord_tuple
		# TODO some logic that ensures the legal positions are piece centered (currently passing in cursor centered but
		#  this should also include logic to piece center coordinates.
		blind_legal_moves = self.blind_legal_moves((x,y)) 
		legal_moves = []

		if hop == False:
			for move in blind_legal_moves:
				if hop == False:
					if self.on_board(move):
						if self.location(move).occupant == None:
							legal_moves.append(move)

						elif self.location(move).occupant.color != self.location((x,y)).occupant.color and self.on_board((move[0] + (move[0] - x), move[1] + (move[1] - y))) and self.location((move[0] + (move[0] - x), move[1] + (move[1] - y))).occupant == None: # is this location filled by an enemy piece?
							legal_moves.append((move[0] + (move[0] - x), move[1] + (move[1] - y)))

		else: # hop == True
			for move in blind_legal_moves:
				if self.on_board(move) and self.location(move).occupant != None:
					if self.location(move).occupant.color != self.location((x,y)).occupant.color and self.on_board((move[0] + (move[0] - x), move[1] + (move[1] - y))) and self.location((move[0] + (move[0] - x), move[1] + (move[1] - y))).occupant == None: # is this location filled by an enemy piece?
						legal_moves.append((move[0] + (move[0] - x), move[1] + (move[1] - y)))

		return legal_moves

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
		if self.location((x,y)).occupant != None:
			if (self.location((x,y)).occupant.color == Colours.BLUE and y == 0) or (self.location((x,y)).occupant.color == Colours.RED and y == 7):
				self.location((x,y)).occupant.king = True 

class Piece:
	def __init__(self, color, king=False):
		self.color = color
		self.king = king

class Square:
	def __init__(self, color, coords, occupant=None):
		self.color = color # color is either BLACK or WHITE
		self.occupant = occupant # occupant is a Square object
		self.coords = coords
