import json
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
		self.en_passant_target = None   # square a pawn just skipped over (ep capture destination)
		self.promotion_pending = None   # (x, y) of pawn awaiting promotion choice
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

		self.en_passant_target = None
		self.promotion_pending = None

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

	def legal_moves(self, coord_tuple):
		"""
		Returns a list of legal move locations for the piece at (x,y).
		Uses PieceMoves to compute per-piece-type chess movement from pieces_defs.json,
		then appends castling and en passant moves.
		"""
		x, y = coord_tuple
		piece = self.matrix[int(x)][int(y)].occupant
		if piece is None:
			return []
		moves = PieceMoves(
			pos=(x, y),
			piece_type=piece.piece_type,
			piece_color=piece.color,
			board_matrix=self.matrix,
			piece_defs=self.pieces_defs,
			white_color=Colours.WHITE
		).legal
		moves += self._castling_destinations(coord_tuple)
		moves += self._en_passant_moves(coord_tuple)
		return moves

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
		Handles special moves: en passant capture, castling rook, en passant target tracking.
		"""
		start_x, start_y = start_coord_tuple
		end_x, end_y = end_coord_tuple
		piece = self.matrix[start_x][start_y].occupant

		# En passant: pawn moves diagonally to the empty en-passant target square.
		# Guard: only fire when the destination IS the recorded en_passant_target,
		# otherwise any custom diagonal pawn move to an empty square would wrongly
		# remove the piece at (end_x, start_y).
		if (piece and piece.piece_type == 'pawn'
				and start_x != end_x
				and self.matrix[end_x][end_y].occupant is None
				and self.en_passant_target == (end_x, end_y)):
			# Remove the bypassed pawn (same column as destination, same row as source)
			self.matrix[end_x][start_y].occupant = None

		# Castling: king moves 2 squares — also slide the rook
		if piece and piece.piece_type == 'king' and abs(end_x - start_x) == 2:
			if end_x > start_x:   # kingside
				rook_x, rook_dest_x = 7, end_x - 1
			else:                  # queenside
				rook_x, rook_dest_x = 0, end_x + 1
			rook = self.matrix[rook_x][start_y].occupant
			self.matrix[rook_dest_x][start_y].occupant = rook
			self.matrix[rook_x][start_y].occupant = None
			if rook:
				rook.has_moved = True

		# Perform the move
		self.matrix[end_x][end_y].occupant = piece
		self.matrix[start_x][start_y].occupant = None

		# Update en passant target: set only on a straight double-push (dx == 0, |dy| == 2).
		# A diagonal move with |dy| == 2 (custom rule) must NOT create an en-passant target.
		if (piece and piece.piece_type == 'pawn'
				and start_x == end_x
				and abs(end_y - start_y) == 2):
			self.en_passant_target = (end_x, (start_y + end_y) // 2)
		else:
			self.en_passant_target = None

		# Mark piece as moved (used for castling eligibility)
		if piece:
			piece.has_moved = True

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
		Called after a piece lands on coord_tuple.
		If a pawn has reached the opponent's back rank, sets self.promotion_pending
		so the game loop can prompt the player to choose a promotion piece.
		"""
		x, y = coord_tuple
		piece = self.matrix[x][y].occupant
		if piece is None:
			return
		if piece.piece_type == 'pawn':
			back_rank = 0 if piece.color == Colours.WHITE else 7
			if y == back_rank:
				self.promotion_pending = (x, y)

	# ------------------------------------------------------------------
	# Special move generators
	# ------------------------------------------------------------------

	def _castling_destinations(self, coord_tuple):
		"""
		Returns castling destination squares for the king at coord_tuple.
		Checks: king hasn't moved, rook hasn't moved, path clear,
		king not currently in check, king doesn't cross a checked square.
		The destination square itself is checked by legal_moves_safe().
		"""
		x, y = coord_tuple
		piece = self.matrix[x][y].occupant
		if piece is None or piece.piece_type != 'king' or piece.has_moved:
			return []
		if self.is_in_check(piece.color):
			return []

		destinations = []
		# (rook_col, king_destination_col, transit_col)
		for rook_x, king_dest_x, transit_x in [(7, x + 2, x + 1), (0, x - 2, x - 1)]:
			if not (0 <= king_dest_x <= 7):
				continue
			# King cannot castle to a hole square
			if self.matrix[king_dest_x][y].is_hole:
				continue
			rook = self.matrix[rook_x][y].occupant
			if rook is None or rook.piece_type != 'rook' or rook.has_moved:
				continue
			# All squares between king and rook must be empty and not holes
			lo, hi = min(x, rook_x) + 1, max(x, rook_x)
			if any(self.matrix[bx][y].occupant is not None or self.matrix[bx][y].is_hole
				   for bx in xrange(lo, hi)):
				continue
			# King must not pass through a square that is under attack
			captured = self._simulate_move((x, y), (transit_x, y))
			in_check = self.is_in_check(piece.color)
			self._undo_move((x, y), (transit_x, y), captured)
			if in_check:
				continue
			destinations.append((king_dest_x, y))
		return destinations

	def _en_passant_moves(self, coord_tuple):
		"""
		Returns the en passant capture square for the pawn at coord_tuple, if any.
		self.en_passant_target is the square the capturing pawn would land on.
		"""
		if self.en_passant_target is None:
			return []
		x, y = coord_tuple
		piece = self.matrix[x][y].occupant
		if piece is None or piece.piece_type != 'pawn':
			return []
		ep_x, ep_y = self.en_passant_target
		# Pawn must be one column away and on the correct rank
		direction = -1 if piece.color == Colours.WHITE else 1
		if abs(x - ep_x) == 1 and ep_y == y + direction:
			return [(ep_x, ep_y)]
		return []

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
		Handles en passant simulation (removes the bypassed pawn temporarily).
		"""
		piece = self.location(coord_tuple).occupant
		if piece is None:
			return []
		safe = []
		for dest in self.legal_moves(coord_tuple):
			# For en passant, temporarily remove the captured pawn from its real square
			ep_pos = None
			ep_piece = None
			if (piece.piece_type == 'pawn'
					and dest == self.en_passant_target
					and self.matrix[dest[0]][dest[1]].occupant is None):
				ep_pos = (dest[0], coord_tuple[1])
				ep_piece = self.matrix[ep_pos[0]][ep_pos[1]].occupant
				self.matrix[ep_pos[0]][ep_pos[1]].occupant = None

			captured = self._simulate_move(coord_tuple, dest)
			in_check = self.is_in_check(piece.color)
			self._undo_move(coord_tuple, dest, captured)

			if ep_pos:
				self.matrix[ep_pos[0]][ep_pos[1]].occupant = ep_piece

			if not in_check:
				safe.append(dest)
		return safe

	# ------------------------------------------------------------------
	# Serialisation
	# ------------------------------------------------------------------

	_COLOR_TO_STR = None   # populated lazily after Colours is imported

	@classmethod
	def _color_to_str(cls, color):
		return 'white' if color == Colours.WHITE else 'black'

	@classmethod
	def _str_to_color(cls, s):
		return Colours.WHITE if s == 'white' else Colours.PIECE_BLACK

	def to_dict(self):
		"""Serialise the full board state to a JSON-compatible dict."""
		matrix_data = []
		for x in xrange(8):
			col = []
			for y in xrange(8):
				sq = self.matrix[x][y]
				if sq.is_hole:
					col.append('hole')
				elif sq.occupant is None:
					col.append(None)
				else:
					col.append({
						'piece_type': sq.occupant.piece_type,
						'color': self._color_to_str(sq.occupant.color),
						'has_moved': sq.occupant.has_moved,
					})
			matrix_data.append(col)
		return {
			'matrix': matrix_data,
			'en_passant_target': list(self.en_passant_target) if self.en_passant_target else None,
			'promotion_pending': list(self.promotion_pending) if self.promotion_pending else None,
		}

	def from_dict(self, d):
		"""Restore board state from a dict produced by to_dict()."""
		self.draw_board_squares()
		self.en_passant_target = tuple(d['en_passant_target']) if d.get('en_passant_target') else None
		self.promotion_pending = tuple(d['promotion_pending']) if d.get('promotion_pending') else None
		for x, col in enumerate(d['matrix']):
			for y, cell in enumerate(col):
				if cell == 'hole':
					self.matrix[x][y].is_hole = True
					self.matrix[x][y].color = Colours.HOLE
				elif cell is not None:
					p = Piece(self._str_to_color(cell['color']), cell['piece_type'])
					p.has_moved = cell['has_moved']
					self.matrix[x][y].occupant = p


class Piece:
	def __init__(self, color, piece_type, king=False):
		self.color = color
		self.piece_type = piece_type
		self.king = king
		self.has_moved = False   # used for castling eligibility

class Square:
	def __init__(self, color, coords, occupant=None, is_hole=False):
		self.color = color # color is either BLACK or WHITE
		self.occupant = occupant # occupant is a Square object
		self.coords = coords
		self.is_hole = is_hole   # True → disabled square (pieces cannot enter)
