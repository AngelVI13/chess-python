#!/usr/bin/env python
import os
import sys

if sys.version_info[0] > 2:
    print("This game runs on python 2 only")

from chesslib import board

# Load a save if it exists

if os.path.exists("state.fen"):
    with open("state.fen") as save:
        game = board.Board(save.read())
else:
    game = board.Board()

try:
    from chesslib.gui_tkinter import display
    display(game)
except ImportError:
    print "File 'gui_tkinter.py' is missing!"
    
