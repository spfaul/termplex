"""
Terminal Emulator UI - each TerminalWindow object spins up a single process
"""

import re
import curses
import select
from dataclasses import dataclass
from core.esc_code import EscCodeHandler
from core.termproc import TerminalProcess
from core.char_display import CharDisplay, CharCell
from .boxed import Boxed


class TerminalWindow(Boxed):
    def __init__(self, logs, win):
        super().__init__(win)
        self.logs = logs
        max_y, max_x = self._win.getmaxyx()
        self.term = TerminalProcess()
        self.char_disp = CharDisplay(logs, (max_x, max_y))
        self.esc_handler = EscCodeHandler(self.logs, self.char_disp)
        self.setup_esc()
        self.__line = ""
        
    def refresh_curs(self):
        self._win.move(self.char_disp.curs.y, self.char_disp.curs.x)

    def setup_esc(self):
        self.esc_handler.on("A", self.move_curs_up)
        self.esc_handler.on("B", self.move_curs_down)
        self.esc_handler.on("C", self.move_curs_right)
        self.esc_handler.on("D", self.move_curs_left)
        self.esc_handler.on("H", self.move_curs_home)
        self.esc_handler.on("J", self.erase_disp)
        self.esc_handler.on("K", self.erase_inline)
        self.esc_handler.on("P", self.del_char)

    def move_curs_home(self, disp, lines=0, cols=0):
        disp.curs.set_pos(int(cols), int(lines))

    def del_char(self, disp, code):
        line = disp.buffer[disp.curs.y]
        cols = int(code)
        if not cols:
            cols = 1
        if cols + disp.curs.x > disp.size[0] - 1:
            return
        disp.buffer[disp.curs.y] = line[:disp.curs.x] + line[disp.curs.x+cols:] + [CharCell() for _ in range(cols)]
        self.draw()

    def erase_disp(self, disp, code):
        if code == "0":
            disp.erase_all_to_curs()
        elif code == "1":
            disp.erase_all_from_curs()
        elif code == "2":
            disp.erase_all()

    def erase_inline(self, disp, code):
        if code == "0":
            disp.erase_inline_from_curs()

    def move_curs_up(self, disp, lines):
        if lines == "0":
            lines = 1
        disp.curs.y = max(0, disp.curs.y-int(lines))
    
    def move_curs_down(self, disp, lines):
        if lines == "0":
            lines = 1
        disp.curs.y = min(disp.size[1]-1, disp.curs.y+int(lines))

    def move_curs_right(self, disp, cols):
        if cols == "0":
            cols = 1
        disp.curs.x = min(disp.size[0]-1, disp.curs.x+int(cols))

    def move_curs_left(self, disp, cols):
        if cols == "0":            
            cols = 1
        disp.curs.x = max(0, disp.curs.x-int(cols))
        self.refresh_curs()

    def draw(self):
        self._win.erase()
        for y, row in enumerate(self.char_disp.buffer):
            for x, cell in enumerate(row):
                if cell.data:
                    self._win.addch(y, x, cell.data)
        self.refresh_curs()
        self._win.refresh()

    __line = ""
    def _parse(self, chunk):
        while chunk:
            c = chunk[0]
            if c == "\n":
                self.char_disp.write(self.__line)
                self.char_disp.newline()
                self.__line = ""
            elif c == "\x1b":
                new_chunk = self.esc_handler.handle_head(chunk)
                if new_chunk is None:
                    self.char_disp.write(self.__line)
                    self.__line = c
                    return
                chunk = new_chunk
                continue
            elif c == "\r":
                self.char_disp.write(self.__line)
                self.char_disp.curs.x = 0
                self.__line = ""
            elif c == "\b":
                self.char_disp.write(self.__line)
                self.move_curs_left(self.char_disp, 1)
                self.__line = ""
            else:
                self.__line += c
            chunk = chunk[1:]

        self.char_disp.write(self.__line)
        self.__line = ""

    def update(self):
        for buff in [self.term.stdout, self.term.stderr]:
            chunk = self.term.read(buff, 4096)
            if chunk:
                self.logs.info(repr(chunk))
                self._parse(chunk)
            self.draw()
    