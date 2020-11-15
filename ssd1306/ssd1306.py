#!/usr/bin/env python
#
# This plugin handles a 128x64 SSD1306 LCD

from __future__ import print_function
import traceback
import web  # web.py framework
import gv  # Get access to sip's settings
from urls import urls  # Get access to sip's URLs
from sip import template_render  #  Needed for working with web.py templates
from webpages import ProtectedPage  # Needed for security
import json  # for working with data file
from collections import OrderedDict

# to write to the console
import sys

# sleep function
from time import sleep

# threads
from threading import Thread, Lock, RLock, Condition, BoundedSemaphore

# get open sprinkler signals
from blinker import signal

# to trace exceptions
import traceback

# to determine how much time as elapsed (for timeout purposes)
import time

# for i2c bus driver
import smbus

# Justification values
JUSTIFY_LEFT = 0
JUSTIFY_RIGHT = 1
JUSTIFY_CENTER = 2

def inc_matrix_ptr(row, col, min_row, max_row, min_col, max_col, inc):
    """
    Increments a pointer a number of values in a 2D matrix.
    returns (new_row, new_col)
    """
    width = max_col - min_col + 1
    height = max_row - min_row + 1
    row -= min_row
    col -= min_col
    col += inc
    row = (
        ((col // width) + row) % height
    ) + min_row
    col = (col % width) + min_col
    return (row, col)

def is_python_3_or_better():
    return sys.version_info.major >= 3

class SipGlobals:
    """
    Provides a "namespace" where global values are accessed.
    """
    @staticmethod
    def get_now_time():
        return gv.nowt
    @staticmethod
    def get_now():
        return gv.now
    @staticmethod
    def is_24hr_time_format():
        return bool(gv.sd[u"tf"])
    @staticmethod
    def is_idle():
        return (gv.pon is None)
    @staticmethod
    def get_running_program():
        return gv.pon
    @staticmethod
    def is_enabled():
        return bool(gv.sd[u"en"])
    @staticmethod
    def is_manual_mode_enabled():
        return bool(gv.sd[u"mm"])
    @staticmethod
    def is_rain_delay_set():
        return bool(gv.sd[u"rd"])
    @staticmethod
    def get_rain_delay_end_time():
        return gv.sd[u"rdst"]
    @staticmethod
    def get_water_level():
        return gv.sd[u"wl"]
    @staticmethod
    def get_running_stations():
        running_stations = []
        station_duration = 0
        program_running = False
        for i in range(len(gv.ps)):
            p, d = gv.ps[i]
            if p != 0:
                program_running = True
            if i + 1 != gv.sd[u"mas"] and gv.srvals[i]:
                # not master and currently on
                running_stations.append(i + 1)
                if d > station_duration:
                    station_duration = d
        return (program_running, station_duration, running_stations)
    @staticmethod
    def is_runonce_program_running():
        return (gv.pon == 98)
    @staticmethod
    def is_manual_mode_program_running():
        return (gv.pon == 99)

class Screen:
    """
    Virtual SSD1306 screen. This screen has internal data setup to conform to the way Lcd sets data
    on the SSD1306. This class only supports static textual data. Scrolling text is not supported.
    """
    # Offset of 0x20, up to 0x7F
    LCD_ASCII_BEGIN = 0x20
    LCD_ASCII_MAX = 0x7F
    LCD_ASCII = [
        bytearray([0x00, 0x00, 0x00, 0x00, 0x00]),  # (space)
        bytearray([0x00, 0x00, 0x5F, 0x00, 0x00]),  # !
        bytearray([0x00, 0x07, 0x00, 0x07, 0x00]),  # "
        bytearray([0x14, 0x7F, 0x14, 0x7F, 0x14]),  # #
        bytearray([0x24, 0x2A, 0x7F, 0x2A, 0x12]),  # $
        bytearray([0x23, 0x13, 0x08, 0x64, 0x62]),  # %
        bytearray([0x36, 0x49, 0x55, 0x22, 0x50]),  # &
        bytearray([0x00, 0x05, 0x03, 0x00, 0x00]),  # '
        bytearray([0x00, 0x1C, 0x22, 0x41, 0x00]),  # (
        bytearray([0x00, 0x41, 0x22, 0x1C, 0x00]),  # )
        bytearray([0x08, 0x2A, 0x1C, 0x2A, 0x08]),  # *
        bytearray([0x08, 0x08, 0x3E, 0x08, 0x08]),  # +
        bytearray([0x00, 0x50, 0x30, 0x00, 0x00]),  # ,
        bytearray([0x08, 0x08, 0x08, 0x08, 0x08]),  # -
        bytearray([0x00, 0x60, 0x60, 0x00, 0x00]),  # .
        bytearray([0x20, 0x10, 0x08, 0x04, 0x02]),  # /
        bytearray([0x3E, 0x51, 0x49, 0x45, 0x3E]),  # 0
        bytearray([0x00, 0x42, 0x7F, 0x40, 0x00]),  # 1
        bytearray([0x42, 0x61, 0x51, 0x49, 0x46]),  # 2
        bytearray([0x21, 0x41, 0x45, 0x4B, 0x31]),  # 3
        bytearray([0x18, 0x14, 0x12, 0x7F, 0x10]),  # 4
        bytearray([0x27, 0x45, 0x45, 0x45, 0x39]),  # 5
        bytearray([0x3C, 0x4A, 0x49, 0x49, 0x30]),  # 6
        bytearray([0x01, 0x71, 0x09, 0x05, 0x03]),  # 7
        bytearray([0x36, 0x49, 0x49, 0x49, 0x36]),  # 8
        bytearray([0x06, 0x49, 0x49, 0x29, 0x1E]),  # 9
        bytearray([0x00, 0x36, 0x36, 0x00, 0x00]),  # :
        bytearray([0x00, 0x56, 0x36, 0x00, 0x00]),  # ;
        bytearray([0x00, 0x08, 0x14, 0x22, 0x41]),  # <
        bytearray([0x14, 0x14, 0x14, 0x14, 0x14]),  # =
        bytearray([0x41, 0x22, 0x14, 0x08, 0x00]),  # >
        bytearray([0x02, 0x01, 0x51, 0x09, 0x06]),  # ?
        bytearray([0x32, 0x49, 0x79, 0x41, 0x3E]),  # @
        bytearray([0x7E, 0x11, 0x11, 0x11, 0x7E]),  # A
        bytearray([0x7F, 0x49, 0x49, 0x49, 0x36]),  # B
        bytearray([0x3E, 0x41, 0x41, 0x41, 0x22]),  # C
        bytearray([0x7F, 0x41, 0x41, 0x22, 0x1C]),  # D
        bytearray([0x7F, 0x49, 0x49, 0x49, 0x41]),  # E
        bytearray([0x7F, 0x09, 0x09, 0x01, 0x01]),  # F
        bytearray([0x3E, 0x41, 0x41, 0x51, 0x32]),  # G
        bytearray([0x7F, 0x08, 0x08, 0x08, 0x7F]),  # H
        bytearray([0x00, 0x41, 0x7F, 0x41, 0x00]),  # I
        bytearray([0x20, 0x40, 0x41, 0x3F, 0x01]),  # J
        bytearray([0x7F, 0x08, 0x14, 0x22, 0x41]),  # K
        bytearray([0x7F, 0x40, 0x40, 0x40, 0x40]),  # L
        bytearray([0x7F, 0x02, 0x04, 0x02, 0x7F]),  # M
        bytearray([0x7F, 0x04, 0x08, 0x10, 0x7F]),  # N
        bytearray([0x3E, 0x41, 0x41, 0x41, 0x3E]),  # O
        bytearray([0x7F, 0x09, 0x09, 0x09, 0x06]),  # P
        bytearray([0x3E, 0x41, 0x51, 0x21, 0x5E]),  # Q
        bytearray([0x7F, 0x09, 0x19, 0x29, 0x46]),  # R
        bytearray([0x46, 0x49, 0x49, 0x49, 0x31]),  # S
        bytearray([0x01, 0x01, 0x7F, 0x01, 0x01]),  # T
        bytearray([0x3F, 0x40, 0x40, 0x40, 0x3F]),  # U
        bytearray([0x1F, 0x20, 0x40, 0x20, 0x1F]),  # V
        bytearray([0x7F, 0x20, 0x18, 0x20, 0x7F]),  # W
        bytearray([0x63, 0x14, 0x08, 0x14, 0x63]),  # X
        bytearray([0x03, 0x04, 0x78, 0x04, 0x03]),  # Y
        bytearray([0x61, 0x51, 0x49, 0x45, 0x43]),  # Z
        bytearray([0x00, 0x00, 0x7F, 0x41, 0x41]),  # [
        bytearray([0x02, 0x04, 0x08, 0x10, 0x20]),  # \
        bytearray([0x41, 0x41, 0x7F, 0x00, 0x00]),  # ]
        bytearray([0x04, 0x02, 0x01, 0x02, 0x04]),  # ^
        bytearray([0x40, 0x40, 0x40, 0x40, 0x40]),  # _
        bytearray([0x00, 0x01, 0x02, 0x04, 0x00]),  # `
        bytearray([0x20, 0x54, 0x54, 0x54, 0x78]),  # a
        bytearray([0x7F, 0x48, 0x44, 0x44, 0x38]),  # b
        bytearray([0x38, 0x44, 0x44, 0x44, 0x20]),  # c
        bytearray([0x38, 0x44, 0x44, 0x48, 0x7F]),  # d
        bytearray([0x38, 0x54, 0x54, 0x54, 0x18]),  # e
        bytearray([0x08, 0x7E, 0x09, 0x01, 0x02]),  # f
        bytearray([0x08, 0x14, 0x54, 0x54, 0x3C]),  # g
        bytearray([0x7F, 0x08, 0x04, 0x04, 0x78]),  # h
        bytearray([0x00, 0x44, 0x7D, 0x40, 0x00]),  # i
        bytearray([0x20, 0x40, 0x44, 0x3D, 0x00]),  # j
        bytearray([0x00, 0x7F, 0x10, 0x28, 0x44]),  # k
        bytearray([0x00, 0x41, 0x7F, 0x40, 0x00]),  # l
        bytearray([0x7C, 0x04, 0x18, 0x04, 0x78]),  # m
        bytearray([0x7C, 0x08, 0x04, 0x04, 0x78]),  # n
        bytearray([0x38, 0x44, 0x44, 0x44, 0x38]),  # o
        bytearray([0x7C, 0x14, 0x14, 0x14, 0x08]),  # p
        bytearray([0x08, 0x14, 0x14, 0x18, 0x7C]),  # q
        bytearray([0x7C, 0x08, 0x04, 0x04, 0x08]),  # r
        bytearray([0x48, 0x54, 0x54, 0x54, 0x20]),  # s
        bytearray([0x04, 0x3F, 0x44, 0x40, 0x20]),  # t
        bytearray([0x3C, 0x40, 0x40, 0x20, 0x7C]),  # u
        bytearray([0x1C, 0x20, 0x40, 0x20, 0x1C]),  # v
        bytearray([0x3C, 0x40, 0x30, 0x40, 0x3C]),  # w
        bytearray([0x44, 0x28, 0x10, 0x28, 0x44]),  # x
        bytearray([0x0C, 0x50, 0x50, 0x50, 0x3C]),  # y
        bytearray([0x44, 0x64, 0x54, 0x4C, 0x44]),  # z
        bytearray([0x00, 0x08, 0x36, 0x41, 0x00]),  # {
        bytearray([0x00, 0x00, 0x7F, 0x00, 0x00]),  # |
        bytearray([0x00, 0x41, 0x36, 0x08, 0x00]),  # }
        bytearray([0x08, 0x08, 0x2A, 0x1C, 0x08]),  # ->
        bytearray([0x08, 0x1C, 0x2A, 0x08, 0x08]),  # <-
    ]
    # unknown character value
    char_other = bytearray([0x7F, 0x7F, 0x7F, 0x7F, 0x7F])

    def __init__(self,
                 screen_pixel_width=128,
                 screen_pixel_height=64):
        # defined maximum LCD addresses
        self._max_col_addr = screen_pixel_width - 1
        # note: ssd1306 addresses rows by 8 vertical pixels at a time, so the screen height had
        #       better be divisible by 8 (rounding up to the nearest 8 here to be sure)
        num_rows = (screen_pixel_height + 7) // 8
        self._max_row_addr = num_rows - 1
        # The screen data
        self._screen_bytes = [bytearray(screen_pixel_width) for _ in range(num_rows)]

    def copy(self):
        pixel_width = self._max_col_addr + 1
        pixel_height = (self._max_row_addr + 1) * 8
        screen_copy = Screen(screen_pixel_width=pixel_width,
                             screen_pixel_height=pixel_height)
        for (from_row, to_row) in zip(self._screen_bytes, screen_copy._screen_bytes):
            # This forces a copy of bytes into the target row object
            to_row[0:pixel_width] = from_row
        return screen_copy

    @property
    def row_start(self):
        return 0

    @property
    def row_end(self):
        return self._max_row_addr

    @property
    def col_start(self):
        return 0

    @property
    def col_end(self):
        return self._max_col_addr

    @property
    def bytes(self):
        """
        Returns a reference to the screen bytes as a 2D list of bytearrays.
        """
        return self._screen_bytes

    @staticmethod
    def bytes_to_string(screen_bytes):
        screen_width = len(screen_bytes[0])
        out_string = '-' * (screen_width + 2) + '\n'
        for row in screen_bytes:
            for mask in [0x01 << i for i in range(8)]:
                out_string += ''.join(['|'] +
                                      ['X' if mask & int(col) != 0 else ' ' for col in row] +
                                      ['|\n'])
        out_string += '-' * (screen_width + 2) + '\n'
        return out_string

    def __str__(self):
        return Screen.bytes_to_string(self.bytes)

    def set_bytes(self,
                  b,
                  cur_row,
                  cur_col):
        """
        Sets internal screen array and increments the current column/row values based on number
        of data values written
        Inputs: b - A 1D list of bytes to write at current position
        Returns: (new_row, new_col)
        """
        return self.get_screen_block(row_start=self.row_start,
                                     row_end=self.row_end,
                                     col_start=self.col_start,
                                     col_end=self.col_end)\
            .set_bytes(b, cur_row=cur_row, cur_col=cur_col)

    def write_block(self,
                    string,
                    row_start=0,
                    row_end=None,
                    col_start=0,
                    col_end=None,
                    min_text_size=1,
                    max_text_size=1,
                    justification=0):
        """
        Writes text to the LCD, autoformatting within the space specified.
        Inputs: str - The string to write
                row_start - The starting row to print this
                row_end - The ending row to print this (inclusive)
                col_start - The starting column to print this
                col_end - The ending column to print this (inclusive)
                min_text_size - The minimum size (scale) for this text (int)
                max_text_size - The maximum size (scale) for this text (int)
                justification - One of the JUSTIFY_* values (LEFT, RIGHT, or CENTER)
        """
        if row_end is None:
            # Compute the end row based on the text size and number of lines in string
            num_lines = len(string.split(u"\n"))
            row_end = min(self.row_end, row_start + (num_lines * max_text_size - 1))
        if col_end is None:
            col_end = self.col_end
        return self.get_screen_block(row_start=row_start,
                                     row_end=row_end,
                                     col_start=col_start,
                                     col_end=col_end)\
            .write_block(string=string,
                         min_text_size=min_text_size,
                         max_text_size=max_text_size,
                         justification=justification)

    def write_line(self, string, row_start, text_size_multiplier=1, justification=0):
        """
        Writes a horizontal line of text to the screen.
        Inputs: str - The ASCII string to print
                row_start - The vertical position to write to (0-based, from top)
                text_size_multiplier - Scaling for text (how many rows to occupy)
                justification - One of the JUSTIFY_* values (LEFT, RIGHT, or CENTER)
        Returns 1 if successful, 0 if invalid arguments given
        """
        return self.get_screen_block(row_start=row_start,
                                     row_end=self.row_end,
                                     col_start=self.col_start,
                                     col_end=self.col_end)\
            .write_line(string=string,
                        text_size_multiplier=text_size_multiplier,
                        justification=justification)

    def clear(self):
        self._screen_bytes = \
            [bytearray(len(self._screen_bytes[0])) for _ in range(len(self._screen_bytes))]

    def serialize(self):
        """
        Returns: All bytes in my screen data as a serializes stream of bytes.
        """
        return bytearray([item for sublist in self._screen_bytes for item in sublist])

    def get_screen_block(self, row_start, row_end, col_start=0, col_end=None):
        """
        Returns a ScreenBlock object.
        """
        if col_end is None:
            col_end = self._max_col_addr
        return ScreenBlock(self, row_start, row_end, col_start, col_end)

    def serialize_block(self, row_start, row_end, col_start=0, col_end=None):
        """
        Returns bytes for a specific rectangular section of the screen.
        """
        return self.get_screen_block(row_start, row_end, col_start, col_end).serialize()

    def bytes_block(self, row_start, row_end, col_start=0, col_end=None):
        """
        Returns bytes for a specific rectangular section of the screen.
        """
        return self.get_screen_block(row_start, row_end, col_start, col_end).bytes

class ScreenBlock:
    """
    This class contains an instance of Screen with a rectangular boundary where data my be written
    to and accessed from.
    """
    def __init__(self, screen, row_start, row_end, col_start, col_end):
        self._screen = screen
        if row_start < screen.row_start:
            raise ValueError(u"row_start [{}] < screen.row_start [{}]".format(row_start, screen.row_start))
        if row_end > screen.row_end:
            raise ValueError(u"row_end [{}] > screen.row_end [{}]".format(row_end, screen.row_end))
        if row_end < row_start:
            raise ValueError(u"row_end [{}] < row_start [{}]".format(row_end, row_start))
        if col_start < screen.col_start:
            raise ValueError(u"col_start [{}] < screen.col_start [{}]".format(col_start, screen.col_start))
        if col_end > screen.col_end:
            raise ValueError(u"col_end [{}] > screen.col_end [{}]".format(col_end, screen.col_end))
        if col_end < col_start:
            raise ValueError(u"col_end [{}] < col_start [{}]".format(col_end, col_start))
        self._row_start = row_start
        self._row_end = row_end
        self._col_start = col_start
        self._col_end = col_end

    @property
    def row_start(self):
        return self._row_start

    @property
    def row_end(self):
        return self._row_end

    @property
    def col_start(self):
        return self._col_start

    @property
    def col_end(self):
        return self._col_end

    @property
    def bytes(self):
        """
        Returns a copy of the bytes in a 2D array as a list of bytearrays, confined to this screen
        block.
        """
        return [self._screen.bytes[i][self.col_start:self.col_end + 1]
                for i in range(self.row_start, self.row_end + 1)]

    def __str__(self):
        return Screen.bytes_to_string(self.bytes)

    def set_bytes(self, b, cur_row, cur_col):
        """
        Sets internal screen array and increments the current column/row values based on number
        of data values written
        Inputs: b - A 1D list of bytes to write at current position
        Returns: (new_row, new_col)
        """
        # Compute current selection size
        columns = self.col_end - self.col_start + 1
        rows = self.row_end - self.row_start + 1
        #
        def lcd_add_to_current(x):
            """
            Increments the current column/row values based on number of data values written
            Inputs: x - Number of columns to increment (to the right then down)
            """
            return inc_matrix_ptr(row=cur_row,
                                  col=cur_col,
                                  min_row=self.row_start,
                                  max_row=self.row_end,
                                  min_col=self.col_start,
                                  max_col=self.col_end,
                                  inc=x)
        # Handle case where length of b is more than current selection size
        if len(b) > (columns * rows):
            extra = len(b) - (columns * rows)
            b = b[extra:]
            (cur_row, cur_col) = lcd_add_to_current(extra)
        # Write the screen
        (new_row, new_col) = lcd_add_to_current(len(b))
        if new_row == cur_row and new_col > cur_col:
            # All changes confined to a single row (easy)
            # Note: The following is taking advantage of bytes returning a reference to the list
            self._screen.bytes[cur_row][cur_col:new_col] = b
        else:
            # Changes to be written to more than one row
            next_idx = 0
            row = cur_row
            col = cur_col
            while next_idx < len(b):
                cur_idx = next_idx
                next_idx += (self.col_end - col + 1)
                if next_idx > len(b):
                    next_idx = len(b)
                cnt = next_idx - cur_idx
                # Note: The following is taking advantage of bytes returning a reference to the list
                self._screen.bytes[row][col:col + cnt] = b[cur_idx:next_idx]
                row += 1
                if row > self.row_end:
                    row = self.row_start
                col = self.col_start
        # Return new screen position
        return (new_row, new_col)

    def serialize(self):
        return bytearray(
            [
                item
                for sublist in self._screen.bytes[self._row_start:self._row_end + 1]
                    for item in sublist[self._col_start:self._col_end + 1]
            ]
        )

    def clear(self):
        for row in self._screen.bytes[self.row_start:self.row_end + 1]:
            row[self.col_start:self.col_end + 1] = bytearray(self.col_end - self.col_start + 1)

    @staticmethod
    def _bit_shift_right_byte_list(lst, num):
        """
        Bit shifts right all bytes in the given list
        Inputs: lst - List of bytes
                num - Number of bits to shift right
        Returns: The transformed list
        """
        original_length = len(lst)
        if is_python_3_or_better(): # Python3 version of this
            # Convert the list to integer in big-endian order
            list_value = int.from_bytes(bytes(lst), byteorder='big')
            # Do the bit shifting
            list_value >>= num
            # Convert the integer back to a list
            lst = list(int(list_value).to_bytes(length=original_length, byteorder='big'))
        else: # Python2 version of this; this will take about 5 times longer to process
            # Convert the list to integer in big-endian order
            list_value = int(''.join(format(val, '02x') for val in lst), 16)
            # Do the bit shifting
            list_value >>= num
            # Convert the integer back to a list
            list_string = format(list_value, '0' + str(original_length * 2) + 'x')
            lst = [int(list_string[x:x+2], 16) for x in range(0, original_length * 2, 2)]
        return lst

    @staticmethod
    def _generate_char_sequence(char, size):
        """
        Resizes a single character into the rows needed to print
        Inputs: char - The ascii character to print
                n - integer size multiplier [1,N]
        Returns: A list of lists, defining what bits to write to each row
        """
        chv = ord(char)
        seq = []
        if chv >= Screen.LCD_ASCII_BEGIN and chv <= Screen.LCD_ASCII_MAX:
            seq = bytearray(Screen.LCD_ASCII[chv - Screen.LCD_ASCII_BEGIN])
        else:  # unknown
            seq = bytearray(Screen.char_other)
        # 1 vertical line of space before next char
        seq.append(0x00)
        # Make a 0-initialized 2-dimensional return array, n tall by n wide
        ret_seq = [[0] * (len(seq) * size) for _ in range(size)]
        # col_mask holds what vertical bits must be set in each row for the current bit
        # (left to right) when the current bit is HIGH
        col_mask = [0] * size
        for i, mul in zip(range(size + 7 // 8), range(0, size, 8)):
            mul = min(8, size - mul)
            col_mask[i] = (2**mul - 1) << (8 - mul)
        # For each bit in a byte (from left to right)...
        for bit_mask in [0x80 >> i for i in range(8)]:
            # For each byte in the sequence (from left to right)...
            for j, v in zip(range(len(seq)), seq):
                # If this bit is set in the current sequence byte...
                if v & bit_mask:
                    # This bit will need to be duplicated n**2 times
                    for k in range(size): # For each row
                        for l in range(size): # For each column
                            # Each vertical line is printed from the bottom to top
                            # This therefore indexes from n-1 to 0
                            row_idx = size - 1 - k
                            # From column (j*n) to (j*n + n-1)
                            col_idx = j * size + l
                            # Set the bit sequence
                            ret_seq[row_idx][col_idx] |= col_mask[k]
            # Shift the column mask to the right to prepare for next bit
            col_mask = ScreenBlock._bit_shift_right_byte_list(col_mask, size)
        return ret_seq

    def write_block(self, string, min_text_size, max_text_size, justification=0):
        """
        Writes text to the LCD, autoformatting within the space specified
        Inputs: str - The string to write
                min_text_size - The minimum size (scale) for this text (int)
                max_text_size - The maximum size (scale) for this text (int)
                justification - One of the JUSTIFY_* values (LEFT, RIGHT, or CENTER)
        """
        if (
            min_text_size > max_text_size or
            min_text_size <= 0 or
            max_text_size > (self.row_end - self.row_start + 1)
        ):
            raise ValueError(u"Invalid min [{}] or max [{}] text size"\
                .format(min_text_size, max_text_size))
        # Compute sizes relative to number of characters
        char_len = len(Screen.char_other) + 1
        lines = string.split(u"\n")
        num_lines = len(lines)
        widest_line = max([len(line) for line in lines])
        max_width = (self.col_end - self.col_start + 1) // char_len
        max_height = self.row_end - self.row_start + 1
        # Compute the largest text size the string may have for the space provided
        if widest_line <= 0:
            largest_width_size = max_text_size
        else:
            largest_width_size = max_width // widest_line
        largest_height_size = max_height // num_lines
        largest_size = min(largest_width_size, largest_height_size)
        # Get size within range
        selected_size = max(min(max_text_size, largest_size), min_text_size)
        # Clear this screen block so that only new text is shown
        self.clear()
        # Write the lines!
        cnt = 0
        for (line, i) in zip(lines, range(min(self.row_end - self.row_start + 1, len(lines)))):
            cnt += self.write_line(string=line,
                                   row_offset=0 + (i * selected_size),
                                   text_size_multiplier=selected_size,
                                   justification=justification)
        return cnt

    def write_line(self, string, row_offset=0, text_size_multiplier=1, justification=0):
        """
        Writes a horizontal line of text to the screen.
        Inputs: str - The ASCII string to print
                text_size_multiplier - Scaling for text (how many rows to occupy)
                justification - One of the JUSTIFY_* values (LEFT, RIGHT, or CENTER)
        Returns 1 if successful, 0 if invalid arguments given
        """
        if len(string) <= 0:
            string = " "
        seq = []
        for c in string:
            seqChar = self._generate_char_sequence(c, text_size_multiplier)
            if len(seq) <= 0:
                seq = seqChar
            else:
                for i in range(len(seq)):
                    seq[i].extend(seqChar[i])

        maxNumRows = text_size_multiplier
        maxNumCols = self.col_end - self.col_start + 1
        # Remove rows until we get the number of rows in range
        del seq[maxNumRows:]
        # Add columns until we get the number of columns in range
        columnsToAdd = maxNumCols - len(seq[0])
        if columnsToAdd > 0:
            for i in range(len(seq)):
                if justification == JUSTIFY_RIGHT:
                    newSeq = [0] * columnsToAdd
                    newSeq.extend(seq[i])
                    seq[i] = newSeq
                elif justification == JUSTIFY_CENTER:
                    columnsToAddLeft = columnsToAdd // 2
                    columnsToAddRight = columnsToAdd - columnsToAddLeft
                    newSeq = [0] * columnsToAddLeft
                    newSeq.extend(seq[i])
                    newSeq.extend([0] * columnsToAddRight)
                    seq[i] = newSeq
                else:
                    # Left justification by default
                    seq[i].extend([0] * columnsToAdd)
        # Remove columns until we get the number of columns in range
        columnsToRemove = len(seq[0]) - maxNumCols
        if columnsToRemove > 0:
            for i in range(len(seq)):
                if justification == JUSTIFY_RIGHT:
                    del seq[i][0:columnsToRemove]
                elif justification == JUSTIFY_CENTER:
                    columnsToRemoveLeft = columnsToRemove // 2
                    columnsToRemoveRight = columnsToRemove - columnsToRemoveLeft
                    del seq[i][0:columnsToRemoveLeft]
                    del seq[i][-columnsToRemoveRight:]
                else:
                    # Left justification by default
                    del seq[i][-columnsToRemove:]
        self.set_bytes([item for sublist in seq for item in sublist],
                       cur_row=(self.row_start + row_offset),
                       cur_col=self.col_start)
        return 1

class Lcd:
    """
    LCD control class for SSD1306 I2C LCD
    """
    # LCD control and data byte values
    CONTROL_BYTE = 0x00
    DATA_BYTE = 0x40
    # Select LCD control bytes
    LCD_CONTROL_PWR_OFF = 0xAE
    LCD_CONTROL_PWR_ON = 0xAF

    def __init__(self,
                 i2c_hw_addr=0x78,
                 i2c_bus_number=1,
                 screen_pixel_width=128,
                 screen_pixel_height=64):
        """
        Initializes an Lcd object
        Inputs: i2c_hw_addr - The hardware address of this Lcd (excluding leading R/W bit)
                              Note: All I2C operations in this class will be write (0) ex: an
                                    address value of 0x78 given as the address here will show as
                                    0x3c in i2cdetect.
                i2c_bus_number - The I2C bus number passed to SMBus
                screen_pixel_width - The number of horizontal pixels for this Lcd
                screen_pixel_height - The number of vertical pixels for this Lcd
                                      (must be divisible by 8)
        """
        # hardware address of LCD (bit shift address 1 to the right to make write operation)
        self._hw_write_addr = i2c_hw_addr >> 1
        # i2c bus
        self._bus = smbus.SMBus(i2c_bus_number)
        # Lock needed for any write operations
        self._write_lock = Lock()
        # defined minimum and maximum LCD addresses
        self._min_col_addr = 0
        self._max_col_addr = screen_pixel_width - 1
        self._min_row_addr = 0
        # note: ssd1306 addresses rows by 8 vertical pixels at a time, so the screen height had
        #       better be divisible by 8 (rounding up to the nearest 8 here to be sure)
        num_rows = (screen_pixel_height + 7) // 8
        self._max_row_addr = num_rows - 1
        # current column and row
        self._current_col = self._min_col_addr
        self._current_row = self._min_row_addr
        # A copy of what is currently displayed
        self._screen = Screen(screen_pixel_width=screen_pixel_width,
                              screen_pixel_height=screen_pixel_height)
        # write failure flag
        self._write_failure = False
        # The current power state (True for on; False for off)
        self._power_state = False
        # Allow external interface to disable me
        self._enabled = True

    def disable(self):
        """
        Disables any further writing to hardware and powers off display
        """
        if self._enabled:
            self._enabled = False
            self._force_power_off()

    def _set_screen_bytes(self, b):
        (self._current_row, self._current_col) = \
            self._screen.set_bytes(b,
                                   cur_row=self._current_row,
                                   cur_col=self._current_col)

    def _write_control_byte(self, byte, force=False):
        """
        Writes a single control byte to the SSD1306 display
        Inputs: byte - The control byte to write
                force - Set to true to ignore my disabled flag
        Returns: True if successfully written; False if an exception occurred
        """
        status = False
        self._write_lock.acquire()
        try:
            if self._enabled or force:
                try:
                    self._bus.write_byte_data(self._hw_write_addr, Lcd.CONTROL_BYTE, byte)
                    status = True
                except Exception as e:
                    if not self._write_failure:
                        print(u"SSD1306 plugin: Failed to write control byte. " +
                                u"Is the hardware connected and the right address selected?" + \
                                u":\n{}".format(e))
                        self._write_failure = True
        finally:
            self._write_lock.release()
        return status

    def _write_data_byte(self, byte):
        """
        Writes a single data byte to the SSD1306 display
        Inputs: byte - The data byte to write
        Returns: True if successfully written; False if an exception occurred
        """
        status = False
        self._write_lock.acquire()
        try:
            if self._enabled:
                try:
                    self._bus.write_byte_data(self._hw_write_addr, Lcd.DATA_BYTE, byte)
                    self._set_screen_bytes([byte])
                    status = True
                except Exception as e:
                    if not self._write_failure:
                        print(u"SSD1306 plugin: Failed to write data byte. " +
                                u"Is the hardware connected and the right address selected?" + \
                                u":\n{}".format(e))
                        self._write_failure = True
        finally:
            self._write_lock.release()
        return status

    def _write_sequence(self, cmd, sequence):
        """
        Writes a given sequence to the SSD1306 display. Sequence is written 32 bytes at a time.
        Inputs: cmd - Command byte
                sequence - List of bytes to write
        Returns: True if successfully written; False if an exception occurred
        """
        # write_i2c_block_data() only accepts list of integers, so convert bytearray to list
        if isinstance(sequence, bytearray):
            sequence = list(sequence)
        status = False
        self._write_lock.acquire()
        try:
            if self._enabled:
                # write_i2c_block_data() can execute a max of 32 bytes at a time
                n = 32
                for chunk in [sequence[i:i + n] for i in range(0, len(sequence), n)]:
                    try:
                        # execute this chunk
                        self._bus.write_i2c_block_data(self._hw_write_addr, cmd, chunk)
                    except Exception as e:
                        if not self._write_failure:
                            print(u"SSD1306 plugin: Failed to execute sequence. " +
                                u"Is the hardware connected and the right address selected?" + \
                                u":\n{}".format(e))
                            self._write_failure = True
                            status = False
                            break
                    else:
                        # If this was a data byte, then we need to update the display pointers by
                        # the number of bytes given because they would have been incremented by the
                        # SSD1306
                        if cmd == Lcd.DATA_BYTE:
                            self._set_screen_bytes(chunk)
                        status = True

        finally:
            self._write_lock.release()
        return status

    def _write_control_sequence(self, sequence):
        """
        Executes a control byte sequence
        Inputs: sequence - List of control bytes to write
        Returns: True if successfully written; False if an exception occurred
        """
        return self._write_sequence(Lcd.CONTROL_BYTE, sequence)

    def _write_data_sequence(self, sequence):
        """
        Executes a data byte sequence
        Inputs: sequence - List of data bytes to write
        Returns: True if successfully written; False if an exception occurred
        """
        return self._write_sequence(Lcd.DATA_BYTE, sequence)

    def write_initialization_sequence(self):
        """
        Initializes the LCD for this interface - call right after instantiation to initialize and
        clear display
        """
        print(u"SSD1306 plugin: LCD initialize...")
        # initialization sequence
        init_sequence = [
            Lcd.LCD_CONTROL_PWR_OFF,  # turn off oled panel
            0x00,  # set low column address
            0x10,  # set high column address
            0x40,  # set start line address
            0x81,  # set contrast control register
            0xCF,
            0xA1,  # set segment re-map 95 to 0
            0xA6,  # set normal display
            0xA8,  # set multiplex ratio(1 to 64)
            0x3F,  # 1/64 duty
            0xD3,  # set display offset
            0x00,  # not offset
            0xD5,  # set display clock divide ratio/oscillator frequency
            0x80,  # set divide ratio
            0xD9,  # set pre-charge period
            0xF1,
            0xDA,  # set com pins hardware configuration
            0x12,
            0xDB,  # set vcomh
            0x40,
            0x8D,  # set Charge Pump enable/disable
            0x14,  # set(0x10) disable
            0x20,  # page addressing mode
            0x02,  #    this means row pointer will never increase unless manually set
            0xC8,  # Remapped mode. Scan from ComN-1 to Com0
        ]
        self._write_control_sequence(init_sequence)
        # Clear out the buffer and synchronize with hardware
        self.clear(force=True)
        # Turn on OLED panel
        self.set_power(on=True)
        print(u"SSD1306 plugin: Done (LCD initialize)")

    def is_powered(self):
        """
        Returns the current power state
        """
        return self._power_state

    def set_power(self, on):
        """
        Turns the display on or off
        Inputs: on - True to turn on; False to turn off
        Returns: True if successfully written; False if an exception occurred
        """
        status = self._write_control_byte(Lcd.LCD_CONTROL_PWR_ON if on else Lcd.LCD_CONTROL_PWR_OFF)
        if status:
            self._power_state = on
        return status

    def _force_power_off(self):
        """
        Force the power off, even if disabled
        """
        status = self._write_control_byte(Lcd.LCD_CONTROL_PWR_OFF, force=True)
        if status:
            self._power_state = False
        return status

    def write_screen(self, screen, force=False):
        """
        Writes the given screen based on what is currently displayed and given screen.
        Inputs: screen - Either a Screen or ScreenBlock object
        """
        current_bytes = self._screen.bytes_block(row_start=screen.row_start,
                                                 row_end=screen.row_end,
                                                 col_start=screen.col_start,
                                                 col_end=screen.col_end)
        new_bytes = screen.bytes
        status = True
        if force or current_bytes != new_bytes:
            # Write row by row to cut down on write time
            for (cur_row, new_row, idx) in zip(current_bytes, new_bytes, range(len(new_bytes))):
                if force or cur_row != new_row:
                    if self._lcd_set_pointer(row=screen.row_start + idx,
                                             col=screen.col_start):
                        if not self._write_data_sequence(new_row):
                            status = False
                            break
                    else:
                        status = False
                        break
        return status

    def clear(self, force=False):
        """
        Clear all contents of the display
        Returns: True if successfully written; False if an exception occurred
        """
        screen_copy = self._screen.copy()
        screen_copy.clear()
        return self.write_screen(screen_copy, force)

    def _lcd_set_pointer(self, row=None, col=None):
        seq = []
        if row is not None:
            seq.append(row & 0x0F | 0xB0)
            self._current_row = row
        if col is not None:
            seq.extend([(col >> 4) & 0x0F | 0x10, col & 0x0F])
            self._current_col = col
        status = False
        if seq:
            status = self._write_control_sequence(seq)
        return status

class LcdPlugin(Thread):
    """
    LCD Plugin which integrates into SIP
    """
    def __init__(self):
        Thread.__init__(self)
        self._daemon = True
        self._state_screen = Screen()
        self._reset_lcd_state()
        # Key is screen name, value is a Screen object
        self._custom_screens = {}
        # Key is screen name, value is number of seconds left for it to display
        self._custom_screens_stack = OrderedDict()
        self._lcd = None
        self._running = True
        self._display_condition = Condition()
        self._notify_display_sem = BoundedSemaphore(1)
        self._notify_display_sem.acquire()
        self._notify_display_thread = Thread(target=self._notify_display_task)
        # All of the idle values need to be read and set as one
        self._idle_lock = RLock()
        self._custom_display_lock = RLock()
        self._custom_display_queue = [] # Not using real queue to limit number of libraries needed
        self._set_default_settings()

    def _reset_lcd_state(self):
        self._state_screen.clear()
        self._last_idle_state = u""
        self._idle_entry_time = None
        self._idled = False

    def initialize(self, load_settings):
        """
        Initializes this plugin
        """
        if load_settings:
            self._load_settings()
        self._lcd = Lcd(i2c_hw_addr=self._lcd_hw_address, i2c_bus_number=1)
        self._lcd.write_initialization_sequence()
        return True

    def _set_default_settings(self):
        """
        Sets the json settings to their defaults
        """
        self._idle_timeout_seconds = 0
        self._lcd_hw_address = 0x78

    def load_from_dict(self, settings, allow_reinit):
        """
        Loads settings from a given dictionary
        """
        if settings is None:
            return
        if u"idle_timeout" in settings:
            self._idle_timeout_seconds = int(settings[u"idle_timeout"])
        reinit_required = False
        if u"i2c_hw_address" in settings:
            old_addr = self._lcd_hw_address
            self._lcd_hw_address = int(settings[u"i2c_hw_address"], 16)
            if old_addr != self._lcd_hw_address:
                reinit_required = True
        if reinit_required and allow_reinit:
            self._lcd.set_power(on=False) # Power off current LCD
            self.initialize(load_settings=False) # Initialize new LCD
            self._reset_lcd_state() # Make sure state is refreshed on next loop

    def _load_settings(self):
        """
        Loads settings from the settings json file for this plugin
        """
        # Get settings
        try:
            with open('./data/ssd1306.json', 'r') as f:
                self.load_from_dict(json.load(f), allow_reinit=False)
        except:
            self._set_default_settings()

    def save_settings(self):
        """
        Saves these settings to the json file for this plugin
        """
        settings = {
           u"idle_timeout": self._idle_timeout_seconds,
           u"i2c_hw_address": str(format(self._lcd_hw_address, '02x'))
        }
        with open('./data/ssd1306.json', 'w') as f:
            json.dump(settings, f) # save to file

    @staticmethod
    def _get_time_string():
        """
        Returns the current time as a string
        """
        timeStr = u""
        nowt = SipGlobals.get_now_time()
        timeHours = nowt.tm_hour
        timeMinutes = nowt.tm_min
        ampmString = u""
        if not SipGlobals.is_24hr_time_format():
            isPm = False
            timeHours = nowt.tm_hour
            if timeHours == 0:
                timeHours = 12
            elif timeHours == 12:
                isPm = True
            elif timeHours > 12:
                timeHours -= 12
                isPm = True
            ampmString = u" PM" if isPm else u" AM"
        hrString = str(timeHours)
        minString = str(timeMinutes // 10 >> 0) + str(timeMinutes % 10 >> 0)
        timeStr = hrString + ":" + minString + ampmString
        return timeStr

    def _wake_display(self):
        """
        Resets idle entry time and wakes the display if we had previously idled
        """
        self._idle_lock.acquire()
        try:
            self._idle_entry_time = time.time()
            if self._idled:
                self._lcd.set_power(on=True)
                self._idled = False
                self._last_idle_state = u""
        finally:
            self._idle_lock.release()

    def _set_idle_state(self, idle_state):
        if self._last_idle_state != idle_state:
            self._wake_display()
            self._last_idle_state = idle_state

    def _display_idled(self):
        self._idle_lock.acquire()
        try:
            self._idled = True
            self._lcd.set_power(on=False)
        finally:
            self._idle_lock.release()

    def _display_idle(self):
        if not SipGlobals.is_enabled():
            idle_state = u"OFF"
            self._state_screen.write_line(u"OFF", 0, 3, JUSTIFY_CENTER)
            self._state_screen.write_line(u"", 3, 5, JUSTIFY_LEFT)
        elif SipGlobals.is_manual_mode_enabled():
            idle_state = u"Idle_mm"
            self._state_screen.write_line(u"Idle", 0, 3, JUSTIFY_CENTER)
            self._state_screen.write_line(u"", 3, 1, JUSTIFY_LEFT)
            self._state_screen.write_line(u"Manual", 4, 2, JUSTIFY_CENTER)
            self._state_screen.write_line(u"Mode", 6, 2, JUSTIFY_CENTER)
        elif SipGlobals.is_rain_delay_set():
            idle_state = u"Rain"
            self._state_screen.write_line(u"Rain", 0, 2, JUSTIFY_CENTER)
            self._state_screen.write_line(u"", 2, 1, JUSTIFY_LEFT)
            self._state_screen.write_line(u"Delay", 3, 2, JUSTIFY_CENTER)
            self._state_screen.write_line(u"", 5, 1, JUSTIFY_LEFT)
            remainingHrs = (SipGlobals.get_rain_delay_end_time() - SipGlobals.get_now()) // 60 // 60
            if remainingHrs < 1:
                self._state_screen.write_line(u"<1 hr", 6, 2, JUSTIFY_CENTER)
            elif remainingHrs == 1:
                self._state_screen.write_line(u"1 hr", 6, 2, JUSTIFY_CENTER)
            else:
                self._state_screen.write_line(
                    str(remainingHrs) + u" hrs", 6, 2, JUSTIFY_CENTER
                )
        elif SipGlobals.get_water_level() < 100:
            idle_state = u"Idle_wl"
            waterLevel = str(SipGlobals.get_water_level())
            self._state_screen.write_line(u"Idle", 0, 3, JUSTIFY_CENTER)
            self._state_screen.write_line(waterLevel + u"%", 3, 2, JUSTIFY_CENTER)
            self._state_screen.write_line(u"", 5, 1, JUSTIFY_LEFT)
            self._state_screen.write_line(LcdPlugin._get_time_string(), 6, 2, JUSTIFY_CENTER)
        else:
            idle_state = u"Idle"
            self._state_screen.write_line(u"Idle", 0, 3, JUSTIFY_CENTER)
            self._state_screen.write_line(u"", 3, 3, JUSTIFY_LEFT)
            self._state_screen.write_line(LcdPlugin._get_time_string(), 6, 2, JUSTIFY_CENTER)
        self._lcd.write_screen(self._state_screen)
        self._set_idle_state(idle_state)

        self._idle_lock.acquire()
        try:
            # Save the idle timeout value just in case it gets written to as we are checking
            # (self._idle_timeout_seconds is not protected by the lock)
            idle_timeout_seconds = self._idle_timeout_seconds
            if (
                not self._idled
                and self._idle_entry_time is not None
                and idle_timeout_seconds > 0
                and (time.time() - self._idle_entry_time) > idle_timeout_seconds
            ):
                self._display_idled()
        finally:
            self._idle_lock.release()

    @staticmethod
    def _time_to_string(t):
        seconds = int(t) % 60
        minutes = int(t) // 60
        hours = minutes // 60
        minutes = minutes % 60
        string = (
            str(minutes // 10)
            + str(minutes % 10)
            + ":"
            + str(seconds // 10)
            + str(seconds % 10)
        )
        if hours > 0:
            string = (
                str(hours // 10)
                + str(hours % 10)
                + ":"
                + string
            )
        return string

    def _display_normal(self):
        """
        Refreshes the display for "normal" operation which displays some of the current state
        """
        is_idle = SipGlobals.is_idle()

        if not is_idle:
            # Get Running Stations from gv.ps
            (program_running, station_duration, running_stations) = \
                SipGlobals.get_running_stations()
            if not running_stations:
                if program_running:
                    if SipGlobals.is_runonce_program_running():
                        self._state_screen.write_line(u"Running", 0, 2, JUSTIFY_CENTER)
                        self._state_screen.write_line("", 2, 1, JUSTIFY_LEFT)
                        self._state_screen.write_line(u"Run-once", 3, 2, JUSTIFY_CENTER)
                        self._state_screen.write_line("", 5, 1, JUSTIFY_LEFT)
                        self._state_screen.write_line(u"Program", 6, 2, JUSTIFY_CENTER)
                        self._lcd.write_screen(self._state_screen)
                    elif SipGlobals.is_manual_mode_program_running():
                        self._state_screen.write_line(u"", 0, 1, JUSTIFY_LEFT)
                        self._state_screen.write_line(u"Manual", 1, 2, JUSTIFY_CENTER)
                        self._state_screen.write_line(u"", 3, 1, JUSTIFY_LEFT)
                        self._state_screen.write_line(u"Mode", 4, 2, JUSTIFY_CENTER)
                        self._state_screen.write_line(u"", 6, 2, JUSTIFY_LEFT)
                        self._lcd.write_screen(self._state_screen)
                    else:
                        self._state_screen.write_line(u"Running", 0, 2, JUSTIFY_CENTER)
                        self._state_screen.write_line("", 2, 1, JUSTIFY_LEFT)
                        self._state_screen.write_line(u"Program", 3, 2, JUSTIFY_CENTER)
                        self._state_screen.write_line(u"", 5, 1, JUSTIFY_LEFT)
                        prg = str(SipGlobals.get_running_program())
                        self._state_screen.write_line(prg, 6, 2, JUSTIFY_CENTER)
                        self._lcd.write_screen(self._state_screen)
                else:
                    # It was a lie!
                    is_idle = True
            else:
                s = u" ".join([str(item) for item in running_stations])
                self._state_screen.write_block(string=s,
                                               row_start=0,
                                               min_text_size=1,
                                               max_text_size=5,
                                               justification=JUSTIFY_CENTER)
                self._state_screen.write_line(" ", 5, 1, JUSTIFY_CENTER)
                if SipGlobals.is_manual_mode_program_running() and station_duration <= 0:
                    # Manual station on forever
                    time_string = u"ON"
                else:
                    time_string = self._time_to_string(station_duration)
                self._state_screen.write_line(time_string, 6, 2, JUSTIFY_CENTER)
                self._lcd.write_screen(self._state_screen)
        # Check again because is_idle may have changed in the above "if" statement
        if is_idle:
            self._display_idle()
        else:
            # If previously idle, reset flag and make sure display is on
            self._wake_display()

    def _decrement_custom_display_stack(self, last_wait_time):
        """
        Decrements the delays of all items in the display stack and removes any displays which have
        delays close to 0.
        """
        if self._custom_screens_stack:
            key_list = list(self._custom_screens_stack.keys())
            # Decrement delays and remove items from stack
            if last_wait_time > 0:
                for key in key_list:
                    if self._custom_screens_stack[key][u"delay"] is not None:
                        self._custom_screens_stack[key][u"delay"] -= last_wait_time
                        if self._custom_screens_stack[key][u"delay"] <= 0.25:
                            # Close enough to 0 that this item should be removed
                            del self._custom_screens_stack[key]

    def _show_top_custom_display(self):
        delay = 0 # by default, immediately go to normal display
        if self._custom_screens_stack:
            top_key = list(self._custom_screens_stack.keys())[-1]
            top_value = self._custom_screens_stack[top_key]
            delay = top_value[u"delay"]
            wake = top_value[u"wake"]
            self._lcd.write_screen(self._custom_screens[top_key])
            if wake:
                self._wake_display()
        return delay

    def _display_custom(self, last_wait_time):
        """
        Displays a custom message
        """
        # If there are items in the stack, first decrement pop whatever is necessary
        self._decrement_custom_display_stack(last_wait_time)
        while self._custom_display_queue:
            self._custom_display_lock.acquire()
            try:
                queue_item = self._custom_display_queue.pop()
            finally:
                self._custom_display_lock.release()
            # The activator name and screen ID addresses a unique custom screen
            activator_name = queue_item.get(u"activator", "default")
            screen_id = queue_item.get(u"screen_id", "default")
            screen_name = "{}/{}".format(activator_name, screen_id)
            if screen_name not in self._custom_screens:
                self._custom_screens[screen_name] = Screen()
            screen = self._custom_screens[screen_name]
            # If cancel is set, all other data will be ignored and screen will be popped
            cancel = queue_item.get(u"cancel", False)
            delay = 0
            wake = False
            if not cancel:
                text = queue_item.get(u"txt", u"")
                row_start = queue_item.get(u"row_start", 0)
                row_end = queue_item.get(u"row_end", None)
                col_start = queue_item.get(u"col_start", 0)
                col_end = queue_item.get(u"col_end", None)
                min_text_size = queue_item.get(u"min_text_size", 1)
                max_text_size = queue_item.get(u"max_text_size", 1)
                text_size = queue_item.get(u"text_size", None)
                if text_size is not None:
                    min_text_size = text_size
                    max_text_size = text_size
                justification_string = queue_item.get(u"justification", u"LEFT").upper()
                justification_lookup = {u"LEFT": JUSTIFY_LEFT,
                                        u"RIGHT": JUSTIFY_RIGHT,
                                        u"CENTER": JUSTIFY_CENTER}
                justification = justification_lookup.get(justification_string, JUSTIFY_LEFT)
                append = queue_item.get(u"append", False)
                # None is allowed for delay to display until cancelled
                # Delay <= 0 has the same result as cancel=True
                delay = queue_item.get(u"delay", 1)
                wake = queue_item.get(u"wake", True)
                # If this data is not to be appended, first clear screen
                if not append:
                    screen.clear()
                # Set the text
                try:
                    screen.write_block(string=text,
                                    row_start=row_start,
                                    row_end=row_end,
                                    col_start=col_start,
                                    col_end=col_end,
                                    min_text_size=min_text_size,
                                    max_text_size=max_text_size,
                                    justification=justification)
                except Exception as ex:
                    print(u"SSD1306 plugin: Exception occurred while trying to display " +
                          u"custom screen: {}".format(ex))
                    print(u"SSD1306 plugin: Custom display data: {}".format(queue_item))
            # Make sure it is on the top of the stack or completely removed if delay is 0
            if screen_name in self._custom_screens_stack.keys():
                del self._custom_screens_stack[screen_name]
            if delay is None or delay > 0:
                self._custom_screens_stack[screen_name] = {u"delay": delay, u"wake": wake}
        # Display whatever is at the top of the stack and get its delay
        delay = self._show_top_custom_display()
        return delay

    def _notify_display_task(self):
        # It may seem silly to notify a condition through a semaphore, but acquiring the condition
        # lock may block for a while if the LCD is busy writing to I2C. Python semaphores don't have
        # a timed wait method. I'd otherwise just use a semaphore instead of the condition variable.
        while self._running:
            self._notify_display_sem.acquire()
            self._display_condition.acquire()
            self._display_condition.notify_all()
            self._display_condition.release()

    def _notify_display_condition(self):
        try:
            self._notify_display_sem.release()
        except ValueError:
            # This is fine; something else already released it
            pass

    def display_signal(self, name, **kw):
        """
        Display signal handler
        """
        self._custom_display_lock.acquire()
        try:
            self._custom_display_queue.insert(0, kw)
        finally:
            self._custom_display_lock.release()
        # Notify the run thread that there is new data here
        self._notify_display_condition()

    def wake_signal(self, *args, **kw):
        """
        Wakes the display
        """
        self._wake_display()

    def sleep_signal(self, *args, **kw):
        """
        Forced the display to be idled
        """
        self._display_idled()

    def run(self):
        """
        Main execution method which is executed when the super class (Thread) is started
        """
        self._notify_display_thread.start()
        sleep(5)
        print(u"SSD1306 plugin: active")
        self._display_condition.acquire()
        try:
            last_waited_time = 0
            while self._running:
                # This will return a wait time of 0 if we need to drop into normal display.
                wait_time = self._display_custom(last_waited_time)
                if wait_time == 0:
                    self._display_normal()
                    wait_time = 1 # Refresh time
                # Only wait if we are still running by this point
                if self._running:
                    start_time = time.time()
                    # This is the only reason the condition variable is needed - to be able to wait
                    # with a specified timeout.
                    self._display_condition.wait(wait_time)
                    last_waited_time = time.time() - start_time
        finally:
            self._display_condition.release()

    def stop(self):
        """
        Stops my running process
        """
        self._running = False
        self._lcd.disable()
        self._notify_display_condition()

    ### Restart ###
    # Restart signal needs to be handled in 1 second or less
    def notify_restart(self, name, **kw):
        """
        Restart handler
        """
        print(u"SSD1306 plugin: received restart signal; turning off LCD...")
        try:
            self.stop()
        except Exception as ex:
            print(u"SSD1306 plugin: Exception caught while trying to stop")
            traceback.print_exc()
            print(ex)
        else:
            print(u"SSD1306 plugin: LCD has been shut off")


lcd_plugin = LcdPlugin()
try:
    # Start LCD
    if lcd_plugin.initialize(load_settings=True):
        lcd_plugin.start()
        display_signal = signal(u"ssd1306_display")
        display_signal.connect(lcd_plugin.display_signal)
        wake_signal = signal(u"ssd1306_wake")
        wake_signal.connect(lcd_plugin.wake_signal)
        sleep_signal = signal(u"ssd1306_sleep")
        sleep_signal.connect(lcd_plugin.sleep_signal)
        restart = signal(u"restart")
        restart.connect(lcd_plugin.notify_restart)
except Exception as ex:
    print(u"SSD1306 plugin: Exception occurred during initialization")
    traceback.print_exc()
    raise ex # SIP will catch this exception and print it

################################################################################
# Web pages:                                                                   #
################################################################################

# Add new URLs to access classes in this plugin.
urls.extend([
   '/ssd1306-sp', 'plugins.ssd1306.settings',
   '/ssd1306-save', 'plugins.ssd1306.save_settings'
   ])

# Add this plugin to the PLUGINS menu ['Menu Name', 'URL'], (Optional)
gv.plugin_menu.append(['SSD1306 Plugin', '/ssd1306-sp'])

class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open(
                u"./data/ssd1306.json", u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = {}  # Default settings. can be list, dictionary, etc.
        return template_render.ssd1306(settings)  # open settings page

class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):
        qdict = (
            web.input()
        )  # Dictionary of values returned as query string from settings page.
        lcd_plugin.load_from_dict(qdict, allow_reinit=True)  # load settings from dictionary
        lcd_plugin.save_settings()  # Save keypad settings
        raise web.seeother(u"/")  # Return user to home page.
