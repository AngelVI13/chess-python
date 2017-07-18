from itertools import groupby
from copy import deepcopy

import pieces
import re

##########
# import time
from multiprocessing import Pool
import pathos.pools as pp
###########


class ChessError(Exception):
    pass


class InvalidCoord(ChessError):
    pass


class InvalidColor(ChessError):
    pass


class InvalidMove(ChessError):
    pass


class Check(ChessError):
    pass


class CheckMate(ChessError):
    pass


class Draw(ChessError):
    pass


class NotYourTurn(ChessError):
    pass

FEN_STARTING = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
RANK_REGEX = re.compile(r"^[A-Z][1-8]$")


class Board(dict):
    """
       Board

       A simple chessboard class

       TODO:

        * PGN export
        * En passant
        * Castling
        * Promoting pawns
        * Fifty-move rule
    """

    axis_y = ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H')
    axis_x = tuple(range(1, 9))  # (1,2,3,...8)

    captured_pieces = {'white': [], 'black': []}
    player_turn = None
    castling = '-'
    en_passant = '-'
    halfmove_clock = 0
    fullmove_number = 1
    history = []

    in_check = ("", False)
    in_mate = ("", False)

    def __init__(self, fen=None):
        if fen is None:
            self.load(FEN_STARTING)
        else:
            self.load(fen)

    def __getitem__(self, coord):
        if isinstance(coord, str):
            coord = coord.upper()
            if not re.match(RANK_REGEX, coord.upper()):
                raise KeyError
        elif isinstance(coord, tuple):
            coord = self.letter_notation(coord)
        try:
            return super(Board, self).__getitem__(coord)
        except KeyError:
            return None

    def save_to_file(self): pass

    def is_in_check_after_move(self, p1, p2):
        # Create a temporary board
        tmp = deepcopy(self)
        tmp._do_move(p1, p2)
        return tmp.is_in_check(self[p1].color)

    def move(self, p1, p2):
        p1, p2 = p1.upper(), p2.upper()
        piece = self[p1]
        dest = self[p2]

        if self.player_turn != piece.color:
            raise NotYourTurn("Not " + piece.color + "'s turn!")

        enemy = self.get_enemy(piece.color)
        legal_moves = self.all_legal_piece_moves(p1)
        # 0. Check if p2 is in the possible moves
        if p2 not in legal_moves:
            raise InvalidMove

        self._do_move(p1, p2)
        self._finish_move(piece, dest, p2)
        if self.is_in_check(enemy):
            self.in_check = (enemy, True)
        else:
            self.in_check = ("", False)  # resets the in_check drawing flag

    @staticmethod
    def get_enemy(color):
        if color == "white":
            return "black"
        else:
            return "white"

    def _do_move(self, p1, p2):
        """
            Move a piece without validation
        """
        piece = self[p1]
        del self[p1]
        self[p2] = piece

    def _finish_move(self, piece, dest, p2):
        """
            Set next player turn, count moves, log moves, etc.
        """
        enemy = self.get_enemy(piece.color)
        if piece.color == 'black':
            self.fullmove_number += 1
        self.halfmove_clock += 1
        self.player_turn = enemy
        abbr = piece.abbreviation
        if abbr == 'P':
            # Pawn has no letter
            abbr = ''
            # Pawn resets halfmove_clock
            self.halfmove_clock = 0
        if dest is None:
            # No capturing
            movetext = abbr + p2.lower()
        else:
            # Capturing
            movetext = abbr + 'x' + p2.lower()
            # Capturing resets halfmove_clock
            self.halfmove_clock = 0

        self.history.append(movetext)

    def all_possible_moves(self, color):
        """
            Return a list of `color`'s possible moves.
            Does not check for check.
        """
        # start = time.time()
        if color not in ("black", "white"):
            raise InvalidColor
        result = []
        for coord in self.keys():
            if (self[coord] is not None) and self[coord].color == color:
                moves = self[coord].possible_moves(coord)
                if moves:
                    result += moves
        # print "all_possible_moves took ", time.time() - start, 's'
        return result

    def all_legal_piece_moves(self, piece):
        """
            Return a list of a piece's legal moves
        """
        def add_move(move):
            if self.is_in_check_after_move(piece, move) is False:
                return move

        possible_piece_moves = self[piece].possible_moves(piece)

        pool = pp.ProcessPool()  # starts process workers
        result = pool.map(add_move, possible_piece_moves)
        return result

    def all_legal_side_moves(self, color):
        """
            Return a dict of `color`'s legal moves
            In the format of PIECE: ALL LEGAL MOVES
        """
        def add_move():
            if (self[coord] is not None) and self[coord].color == color:
                legal_moves = self.all_legal_piece_moves(coord)
                if legal_moves:
                    result[coord] = legal_moves

        if color not in ("black", "white"):
            raise InvalidColor
        result = {}
        pool = Pool()  # start worker processes
        # run this statement for all coord in self.keys()
        [pool.apply_async(add_move, ()) for coord in self.keys()]
        return result

    def occupied(self, color):
        """
            Return a list of coordinates occupied by `color`
        """
        result = []
        if color not in ("black", "white"):
            raise InvalidColor

        for coord in self:
            if self[coord].color == color:
                result.append(coord)
        return result

    @staticmethod
    def is_king(piece):
        return isinstance(piece, pieces.King)

    def get_king_position(self, color):
        for pos in self.keys():
            if self.is_king(self[pos]) and self[pos].color == color:
                return pos

    def get_king(self, color):
        if color not in ("black", "white"):
            raise InvalidColor
        return self[self.get_king_position(color)]

    def is_in_check(self, color):
        if color not in ("black", "white"):
            raise InvalidColor
        king = self.get_king(color)
        enemy = self.get_enemy(color)
        return king in map(self.__getitem__, self.all_possible_moves(enemy))

    def evaluate_board(self):
        """
            Evaluates the board after each move
            in order to catch a checkmate scenario
        """
        board_status = ""
        # If a side is in check
        if self.in_check[1]:
            side_in_check = self.in_check[0]
            self.in_mate = (side_in_check, True)
            # checks if the side in check has any possible moves that can escape the check
            side_legal_moves = self.all_legal_side_moves(side_in_check)
            if not side_legal_moves:
                self.in_mate = ("", False)
                return board_status  # if even 1 move is found in which the side in check escapes the check then return
            
            # If the side in check has no possible moves or cannot escape check then declare mate
            if self.in_mate[1]:
                board_status = side_in_check + " is in checkmate!"
                return board_status
        else:
            pass  # check if the enemy side has any legal moves left -if not => draw
            # need a function to tell me which side's turn it is

    def letter_notation(self, coord):
        if not self.is_in_bounds(coord):
            return
        try:
            return self.axis_y[coord[1]] + str(self.axis_x[coord[0]])
        except IndexError:
            raise InvalidCoord

    def number_notation(self, coord):
        if coord is not None:
            return int(coord[1])-1, self.axis_y.index(coord[0])

    @staticmethod
    def is_in_bounds(coord):
        if coord[1] < 0 or coord[1] > 7 or\
           coord[0] < 0 or coord[0] > 7:
            return False
        else:
            return True

    def load(self, fen):
        """
            Import state from FEN notation
        """
        self.clear()
        # Split data
        fen = fen.split(' ')

        # Expand blanks
        def expand(match): return ' ' * int(match.group(0))

        fen[0] = re.compile(r'\d').sub(expand, fen[0])

        for x, row in enumerate(fen[0].split('/')):
            for y, letter in enumerate(row):
                if letter == ' ':
                    continue
                coord = self.letter_notation((7-x, y))
                self[coord] = pieces.piece(letter)
                self[coord].place(self)

        if fen[1] == 'w':
            self.player_turn = 'white'
        else:
            self.player_turn = 'black'

        self.castling = fen[2]
        self.en_passant = fen[3]
        self.halfmove_clock = int(fen[4])
        self.fullmove_number = int(fen[5])

    def export(self):
        """
            Export state to FEN notation
        """
        def join(k, g):
            if k == ' ':
                return str(len(g))
            else:
                return "".join(g)

        def replace_spaces(row):
            # replace spaces with their count
            _result = [join(k, list(g)) for k, g in groupby(row)]
            return "".join(_result)

        result = ''
        for number in self.axis_x[::-1]:
            for letter in self.axis_y:
                piece = self[letter+str(number)]
                if piece is not None:
                    result += piece.abbreviation
                else:
                    result += ' '
            result += '/'

        result = result[:-1]  # remove trailing "/"
        result = replace_spaces(result)
        result += " " + (" ".join([self.player_turn[0],
                         self.castling,
                         self.en_passant,
                         str(self.halfmove_clock),
                         str(self.fullmove_number)]))
        return result
