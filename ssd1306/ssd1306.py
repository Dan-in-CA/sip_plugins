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

# For helper functions
from helpers import *

# to write to the console
import sys

# sleep function
from time import sleep

# threads
from threading import Thread, Lock, RLock, Condition

# get open sprinkler signals
from blinker import signal

# to trace exceptions
import traceback

# to determine how much time as elapsed (for timeout purposes)
import time

# for i2c bus driver
import smbus

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
    # Justification values
    JUSTIFY_LEFT = 0
    JUSTIFY_RIGHT = 1
    JUSTIFY_CENTER = 2
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
        # last selected view range
        self._gmin_col = self._min_col_addr
        self._gmax_col = self._max_col_addr
        self._gmin_row = self._min_row_addr
        self._gmax_row = self._max_row_addr
        # current column and row
        self._current_col = self._min_col_addr
        self._current_row = self._min_row_addr
        # A copy of what is currently displayed
        self._screen = [bytearray(screen_pixel_width) for _ in range(num_rows)]
        # write failure flag
        self._write_failure = False
        # The current power state (True for on; False for off)
        self._power_state = False
        # Allow external interface to disable me
        self._enabled = True
        return

    def disable(self):
        """
        Disables any further writing to hardware and powers off display
        """
        if self._enabled:
            self._enabled = False
            self._force_power_off()

    def _set_screen_bytes(self, b):
        """
        Sets internal screen array and increments the current column/row values based on number
        of data values written
        Inputs: b - A list of bytes to write at current position
        """
        # Compute current selection size
        columns = self._gmax_col - self._gmin_col + 1
        rows = self._gmax_row - self._gmin_row + 1
        #
        def lcd_add_to_current(x):
            """
            Increments the current column/row values based on number of data values written
            Inputs: x - Number of columns to increment (to the right then down)
            """
            new_col = self._current_col + x
            new_row = (
                ((new_col // columns) + self._current_row) % rows
            ) + self._gmin_row
            new_col = (new_col % columns) + self._gmin_col
            return (new_row, new_col)
        # Handle case where length of b is more than current selection size
        if len(b) > (columns * rows):
            extra = (columns * rows) - len(b)
            b = b[extra:]
            (self._current_row, self._current_col) = lcd_add_to_current(extra)
        # Write the screen
        (new_row, new_col) = lcd_add_to_current(len(b))
        if new_row == self._current_row and new_col > self._current_col:
            # All changes confined to a single row (easy)
            self._screen[self._current_row][self._current_col:new_col] = b
        else:
            # Changes to be written to more than one row
            next_idx = 0
            row = self._current_row
            col = self._current_col
            while next_idx < len(b):
                cur_idx = next_idx
                next_idx += columns
                if next_idx > len(b):
                    next_idx = len(b)
                cnt = next_idx - cur_idx
                self._screen[row][col:col + cnt] = b[cur_idx:next_idx]
                row += 1
                if row >= self._gmax_row:
                    row = self._gmin_row
                col = self._gmin_col
        # Set new screen position
        self._current_row = new_row
        self._current_col = new_col

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
            0x20,  # horizontal addressing mode
            0x00,
            0xC8,  # Remapped mode. Scan from ComN-1 to Com0
        ]
        self._write_control_sequence(init_sequence)
        # Clear out the buffer and synchronize with hardware
        self.clear()
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

    def clear(self):
        """
        Clear all contents of the display
        Returns: True if successfully written; False if an exception occurred
        """
        status = True
        # set print area to max in order to clear the entire screen
        self._lcd_set_print_area_max()
        # set all pixels to 0
        for _ in range(0, 32):
            if not self._write_data_sequence([0] * 32):
                status = False
        return status

    def _lcd_set_print_area_max(self):
        """
        Sets the printable area to max screen
        Returns: True if successfully set; False if an exception occurred
        """
        return self._lcd_set_print_area(
            self._min_col_addr, self._max_col_addr, self._min_row_addr, self._max_row_addr
        )

    def _lcd_set_print_area(self, min_col, max_col, min_row, max_row):
        """
        Sets the print area of the screen with max of: (0x00, 0x7F, 0x00, 0x07)
        Inputs: min_col - minimum column (pixel)
                max_col - maximum column (pixel)
                min_row - minimum row (set of 8 pixels)
                max_row - maximum row (set of 8 pixels)
        Returns: True if successfully set; False if an exception occurred
        """
        if min_col < 0 or max_col > self._max_col_addr or max_col < min_col:
            return False
        elif min_row < 0 or max_row > self._max_row_addr or max_row < min_row:
            return False
        seq = [0x21, min_col, max_col, 0x22, min_row, max_row]
        status = self._write_control_sequence(seq)
        self._gmin_col = min_col
        self._gmax_col = max_col
        self._gmin_row = min_row
        self._gmax_row = max_row
        self._current_col = min_col
        self._current_row = min_row
        return status

    @staticmethod
    def _bit_shift_right_byte_list(lst, num):
        """
        Bit shifts right all bytes in the given list
        Inputs: lst - List of bytes
                num - Number of bits to shift right
        Returns: The transformed list
        """
        original_length = len(lst)
        if sys.version_info.major >= 3: # Python3 version of this
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

    def _generate_char_sequence(self, char, size):
        """
        Resizes a single character into the rows needed to print
        Inputs: char - The ascii character to print
                n - integer size multiplier [1,N]
        Returns: A list of lists, defining what bits to write to each row
        """
        chv = ord(char)
        seq = []
        if chv >= Lcd.LCD_ASCII_BEGIN and chv <= Lcd.LCD_ASCII_MAX:
            seq = bytearray(Lcd.LCD_ASCII[chv - Lcd.LCD_ASCII_BEGIN])
        else:  # unknown
            seq = bytearray(Lcd.char_other)
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
            col_mask = Lcd._bit_shift_right_byte_list(col_mask, size)
        return ret_seq

    def write_block(self, str, row_start, min_text_size, max_text_size, justification=0):
        """
        Writes text to the LCD, autoformatting within the space specified
        Inputs: str - The string to write
                row_start - The starting row to print this
                min_text_size - The minimum size (scale) for this text (int)
                max_text_size - The maximum size (scale) for this text (int)
                justification - One of the Lcd.JUSTIFY_* values (LEFT, RIGHT, or CENTER)
        """
        if min_text_size > max_text_size or min_text_size <= 0 or max_text_size <= 0:
            return 0
        maxWidth = self._max_col_addr - self._min_col_addr + 1
        words = str.split(" ")
        wordSizes = [0] * len(words)
        # I am assuming that each character is 5 pixel width with 1 pixel space
        numberOfSpaces = len(words) - 1
        totalSize = numberOfSpaces * 6
        for i in range(len(words)):
            currentSize = 0
            for _ in range(len(words[i])):
                currentSize += 6
            wordSizes[i] = currentSize
            totalSize += currentSize
        if (
            totalSize * max_text_size <= maxWidth
            or min_text_size == max_text_size
            or len(str) <= 0
        ):
            # It can all fit in one line at max size min = max; we are done
            return self.write_line(str, row_start, max_text_size, justification)
        currentTextSize = max_text_size
        lines = []
        maxLines = 0
        while currentTextSize > min_text_size:
            currentTextSize -= 1
            maxLines = max_text_size // currentTextSize
            currentLine = 0
            lines = [words[0]]
            currentSize = wordSizes[0]
            lineTooLong = False
            for i in range(1, len(words)):
                nextSize = currentSize + wordSizes[i] + 6
                if nextSize * currentTextSize > maxWidth:
                    # Next line
                    lines.append(words[i])
                    currentLine += 1
                    currentSize = wordSizes[i]
                    # Flag if this word by itself is too long to fit
                    if currentSize * currentTextSize > maxWidth:
                        lineTooLong = True
                else:
                    lines[currentLine] += " " + words[i]
                    currentSize += wordSizes[i] + 6
            if len(lines) <= maxLines and not lineTooLong:
                # we are done
                break
        while len(lines) + 2 <= maxLines:
            temp = [u""]
            temp.extend(lines)
            lines = temp
            lines.append("")
        if len(lines) > maxLines:
            lines = lines[:maxLines]
        rowNum = row_start
        printedCount = 0
        for l in lines:
            printedCount += self.write_line(l, rowNum, currentTextSize, justification)
            rowNum += currentTextSize
        # Clear out the rest
        for i in range(rowNum, row_start + max_text_size):
            self.write_line("", i, 1, Lcd.JUSTIFY_LEFT)
        return printedCount

    def write_line(self, str, row_start, text_size_multiplier=1, justification=0):
        """
        Writes a horizontal line of text to the LCD.
        Inputs: str - The ASCII string to print
                row_start - The vertical position to write to (0-based, from top)
                text_size_multiplier - Scaling for text (how many rows to occupy)
                justification - One of the Lcd.JUSTIFY_* values (LEFT, RIGHT, or CENTER)
        Returns 1 if successful, 0 if invalid arguments given
        """
        if row_start < self._min_row_addr or row_start > self._max_row_addr:
            return 0
        if len(str) <= 0:
            str = " "
        seq = []
        for c in str:
            seqChar = self._generate_char_sequence(c, text_size_multiplier)
            if len(seq) <= 0:
                seq = seqChar
            else:
                for i in range(len(seq)):
                    seq[i].extend(seqChar[i])

        row_end = row_start + text_size_multiplier - 1
        if row_end > self._max_row_addr:
            row_end = self._max_row_addr
        self._lcd_set_print_area(self._min_col_addr, self._max_col_addr, row_start, row_end)

        maxNumRows = self._gmax_row - self._gmin_row + 1
        maxNumCols = self._gmax_col - self._gmin_col + 1
        # Add rows until we get the number of rows in range
        for i in range(len(seq), maxNumRows):
            seq.append([0] * len(seq[0]))
        # Remove rows until we get the number of rows in range
        del seq[maxNumRows:]
        # Add columns until we get the number of columns in range
        columnsToAdd = maxNumCols - len(seq[0])
        if columnsToAdd > 0:
            for i in range(len(seq)):
                if justification == Lcd.JUSTIFY_RIGHT:
                    newSeq = [0] * columnsToAdd
                    newSeq.extend(seq[i])
                    seq[i] = newSeq
                elif justification == Lcd.JUSTIFY_CENTER:
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
                if justification == Lcd.JUSTIFY_RIGHT:
                    del seq[i][0:columnsToRemove]
                elif justification == Lcd.JUSTIFY_CENTER:
                    columnsToRemoveLeft = columnsToRemove // 2
                    columnsToRemoveRight = columnsToRemove - columnsToRemoveLeft
                    del seq[i][0:columnsToRemoveLeft]
                    del seq[i][-columnsToRemoveRight:]
                else:
                    # Left justification by default
                    del seq[i][-columnsToRemove:]
        for i in range(len(seq)):
            self._write_data_sequence(seq[i])
        #screen_copy = list(self._screen)
        #for i in range(len(self._screen)):
        #    screen_copy[i] = bytearray(self._screen[i])
        #sleep(0.25)
        #self.clear()
        #self._lcd_set_print_area_max()
        #for row in screen_copy:
        #    self._write_data_sequence(row)
        return 1


class LcdPlugin(Thread):
    """
    LCD Plugin which integrates into SIP
    """
    def __init__(self):
        Thread.__init__(self)
        self._daemon = True
        self._reset_lcd_state()
        self._lcd = None
        self._running = True
        self._display_condition = Condition()
        self._display_notify_thread = Thread(target=self._notify_display_condition)
        # All of the idle values need to be read and set as one
        self._idle_lock = RLock()
        self._custom_display_lock = RLock()
        self._custom_display_queue = []
        self._displaying_custom = False
        self._custom_display_canceled = False
        self._set_default_settings()

    def _reset_lcd_state(self):
        self._last_write = u""
        self._last_sub_val = u""
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
            self._lcd.set_power(on=False)
            self.initialize(load_settings=False)
            self._reset_lcd_state()

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
        nowt = gv.nowt
        timeHours = nowt.tm_hour
        timeMinutes = nowt.tm_min
        ampmString = u""
        if not gv.sd[u"tf"]:
            isPm = False
            timeHours = gv.nowt.tm_hour
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
        finally:
            self._idle_lock.release()

    def _display_idled(self):
        self._idle_lock.acquire()
        try:
            self._idled = True
            self._lcd.set_power(on=False)
        finally:
            self._idle_lock.release()

    def _display_normal(self):
        """
        Refreshes the display for "normal" operation which displays some of the current state
        """

        ########################################################################
        # All of this logic is a gigantic mess! I plan on eventually cleaning
        # this up. For now, please don't judge :)
        ########################################################################

        # If previously displayed custom, refresh state
        if self._displaying_custom:
            self._reset_lcd_state()
            self._displaying_custom = False
            self._custom_display_canceled = False
            self._wake_display()
        if gv.pon is None:
            prg = u"Idle"
        elif gv.pon == 98:  # something is running
            prg = u"Run-once"
        elif gv.pon == 99:
            prg = u"Manual Mode"
        else:
            prg = u"{}".format(gv.pon)

        s = ""
        if prg != u"Idle":
            # If previously idle, reset flag and make sure display is on
            self._wake_display()
            # Get Running Stations from gv.ps
            programRunning = False
            stationDuration = 0
            for i in range(len(gv.ps)):
                p, d = gv.ps[i]
                if p != 0:
                    programRunning = True
                if i + 1 != gv.sd[u"mas"] and gv.srvals[i]:
                    # not master and currently on
                    if len(s) == 0:
                        s = str(i + 1)
                    else:
                        s += " " + str(i + 1)
                    if d > stationDuration:
                        stationDuration = d
            if len(s) == 0:
                if programRunning:
                    if gv.pon == 98:
                        aboutToWrite = u"RunningRun-onceProgram"
                        if self._last_write != aboutToWrite:
                            self._lcd.write_line(u"Running", 0, 2, Lcd.JUSTIFY_CENTER)
                            self._lcd.write_line("", 2, 1, Lcd.JUSTIFY_LEFT)
                            self._lcd.write_line(u"Run-once", 3, 2, Lcd.JUSTIFY_CENTER)
                            self._lcd.write_line("", 5, 1, Lcd.JUSTIFY_LEFT)
                            self._lcd.write_line(u"Program", 6, 2, Lcd.JUSTIFY_CENTER)
                            self._last_write = aboutToWrite
                    elif gv.pon == 99:
                        aboutToWrite = u"ManualMode"
                        if self._last_write != aboutToWrite:
                            self._lcd.write_line(u"", 0, 1, Lcd.JUSTIFY_LEFT)
                            self._lcd.write_line(u"Manual", 1, 2, Lcd.JUSTIFY_CENTER)
                            self._lcd.write_line(u"", 3, 1, Lcd.JUSTIFY_LEFT)
                            self._lcd.write_line(u"Mode", 4, 2, Lcd.JUSTIFY_CENTER)
                            self._lcd.write_line(u"", 6, 2, Lcd.JUSTIFY_LEFT)
                            self._last_write = aboutToWrite
                    else:
                        aboutToWrite = u"RunningProgram{}".format(prg)
                        if self._last_write != aboutToWrite:
                            self._lcd.write_line(u"Running", 0, 2, Lcd.JUSTIFY_CENTER)
                            self._lcd.write_line("", 2, 1, Lcd.JUSTIFY_LEFT)
                            self._lcd.write_line(u"Program", 3, 2, Lcd.JUSTIFY_CENTER)
                            self._lcd.write_line(u"", 5, 1, Lcd.JUSTIFY_LEFT)
                            self._lcd.write_line(prg, 6, 2, Lcd.JUSTIFY_CENTER)
                            self._last_write = aboutToWrite
                else:
                    # It was a lie!
                    prg = u"Idle"
            else:
                if self._last_write != s:
                    self._lcd.write_block(s, 0, 1, 5, Lcd.JUSTIFY_CENTER)
                    self._lcd.write_line(" ", 5, 1, Lcd.JUSTIFY_CENTER)
                    self._last_write = s
                    self._last_sub_val = ""
                if gv.pon == 99 and stationDuration <= 0:
                    # Manual station on forever
                    aboutToWrite = u"ON"
                else:
                    stationSec = int(stationDuration) % 60
                    stationMin = int(stationDuration) // 60
                    stationHrs = stationMin // 60
                    stationMin = stationMin % 60
                    aboutToWrite = (
                        str(stationMin // 10)
                        + str(stationMin % 10)
                        + ":"
                        + str(stationSec // 10)
                        + str(stationSec % 10)
                    )
                    if stationHrs > 0:
                        aboutToWrite = (
                            str(stationHrs // 10)
                            + str(stationHrs % 10)
                            + ":"
                            + aboutToWrite
                        )
                if self._last_sub_val != aboutToWrite:
                    self._lcd.write_line(aboutToWrite, 6, 2, Lcd.JUSTIFY_CENTER)
                    self._last_sub_val = aboutToWrite
        # Check again because prg may have changed to Idle in the above if statement
        if prg == u"Idle":
            if not gv.sd[u"en"]:
                if self._last_write != u"OFF":
                    self._wake_display()
                    self._lcd.write_line(u"OFF", 0, 3, Lcd.JUSTIFY_CENTER)
                    self._lcd.write_line(u"", 3, 5, Lcd.JUSTIFY_LEFT)
                    self._last_write = u"OFF"
            elif gv.sd[u"mm"]:
                aboutToWrite = u"IdleManualMode"
                if self._last_write != aboutToWrite:
                    self._wake_display()
                    self._lcd.write_line(u"Idle", 0, 3, Lcd.JUSTIFY_CENTER)
                    self._lcd.write_line(u"", 3, 1, Lcd.JUSTIFY_LEFT)
                    self._lcd.write_line(u"Manual", 4, 2, Lcd.JUSTIFY_CENTER)
                    self._lcd.write_line(u"Mode", 6, 2, Lcd.JUSTIFY_CENTER)
                    self._last_write = aboutToWrite
            elif gv.sd[u"rd"]:
                aboutToWrite = u"RainDelay"
                if self._last_write != aboutToWrite:
                    self._wake_display()
                    self._lcd.write_line(u"Rain", 0, 2, Lcd.JUSTIFY_CENTER)
                    self._lcd.write_line(u"", 2, 1, Lcd.JUSTIFY_LEFT)
                    self._lcd.write_line(u"Delay", 3, 2, Lcd.JUSTIFY_CENTER)
                    self._lcd.write_line(u"", 5, 1, Lcd.JUSTIFY_LEFT)
                    self._last_write = aboutToWrite
                    self._last_sub_val = u""
                remainingHrs = (gv.sd[u"rdst"] - gv.now) // 60 // 60
                aboutToWrite = str(remainingHrs)
                if self._last_sub_val != aboutToWrite:
                    if remainingHrs < 1:
                        self._lcd.write_line(u"<1 hr", 6, 2, Lcd.JUSTIFY_CENTER)
                    elif remainingHrs == 1:
                        self._lcd.write_line(u"1 hr", 6, 2, Lcd.JUSTIFY_CENTER)
                    else:
                        self._lcd.write_line(
                            str(remainingHrs) + u" hrs", 6, 2, Lcd.JUSTIFY_CENTER
                        )
                    self._last_sub_val = aboutToWrite
            elif gv.sd[u"wl"] < 100:
                waterLevel = str(gv.sd[u"wl"])
                aboutToWrite = u"IdleWaterLevel" + waterLevel
                if self._last_write != aboutToWrite:
                    self._wake_display()
                    self._lcd.write_line(u"Idle", 0, 3, Lcd.JUSTIFY_CENTER)
                    self._lcd.write_line(waterLevel + u"%", 3, 2, Lcd.JUSTIFY_CENTER)
                    self._lcd.write_line(u"", 5, 1, Lcd.JUSTIFY_LEFT)
                    self._last_write = aboutToWrite
                    self._last_sub_val = u""
                aboutToWrite = LcdPlugin._get_time_string()
                if self._last_sub_val != aboutToWrite:
                    self._lcd.write_line(aboutToWrite, 6, 2, Lcd.JUSTIFY_CENTER)
                    self._last_sub_val = aboutToWrite
            else:
                if self._last_write != prg:
                    self._wake_display()
                    self._lcd.write_line(prg, 0, 3, Lcd.JUSTIFY_CENTER)
                    self._lcd.write_line(u"", 3, 3, Lcd.JUSTIFY_LEFT)
                    self._last_write = prg
                    self._last_sub_val = u""
                aboutToWrite = LcdPlugin._get_time_string()
                if self._last_sub_val != aboutToWrite:
                    self._lcd.write_line(aboutToWrite, 6, 2, Lcd.JUSTIFY_CENTER)
                    self._last_sub_val = aboutToWrite

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

    def _display_custom(self):
        """
        Displays a custom message
        """
        while self._custom_display_queue:
            self._custom_display_lock.acquire()
            try:
                queue_item = self._custom_display_queue.pop()
            finally:
                self._custom_display_lock.release()
            # Activator name needed for future use
            # activator_name = queue_item.get(u"activator", None)
            cancel = queue_item.get(u"cancel", False)
            if not cancel:
                text = queue_item.get(u"txt", u"")
                row_start = queue_item.get(u"row_start", 0)
                min_text_size = queue_item.get(u"min_text_size", 1)
                max_text_size = queue_item.get(u"max_text_size", 1)
                justification_string = queue_item.get(u"justification", u"LEFT").upper()
                justification_lookup = {u"LEFT": Lcd.JUSTIFY_LEFT,
                                        u"RIGHT": Lcd.JUSTIFY_RIGHT,
                                        u"CENTER": Lcd.JUSTIFY_CENTER}
                justification = justification_lookup.get(justification_string, Lcd.JUSTIFY_LEFT)
                append = queue_item.get(u"append", False)
                # Force append to false if we are not already displaying custom
                if not self._displaying_custom or self._custom_display_canceled:
                    append = False
                delay = queue_item.get(u"delay", 1)
                # Do the thing
                if not append:
                    self._lcd.clear()
                self._lcd.write_block(text, row_start, min_text_size, max_text_size, justification)
                self._displaying_custom = True
                self._wake_display()
                self._custom_display_canceled = False
                # print(u"SSD1306 plugin: displayed: {}".format(queue_item))
            else: # canceled
                # print(u"SSD1306 plugin: custom display canceled")
                # To force a refresh if there is another thing in the queue after this
                self._custom_display_canceled = True
                # Delay of 0 will force the run thread right into the next cycle
                delay = 0
        return delay

    def _notify_display_condition(self):
        self._display_condition.acquire()
        self._display_condition.notify_all()
        self._display_condition.release()

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

    def run(self):
        """
        Main execution method which is executed when the super class (Thread) is started
        """
        sleep(5)
        print(u"SSD1306 plugin: active")
        self._display_condition.acquire()
        try:
            while self._running:
                wait_time = 1
                if self._custom_display_queue:
                    wait_time = self._display_custom()
                else:
                    self._display_normal()
                    wait_time = 1 # Refresh time
                # Only wait if we are still running by this point
                if self._running:
                    self._display_condition.wait(wait_time)
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
        # Note about this signal: It shouldn't be used by multiple external modules at once. Nothing
        # handles such concurrent calls internally. See how _display_custom dissects the message.
        display_signal = signal(u"ssd1306_display")
        display_signal.connect(lcd_plugin.display_signal)
        wake_signal = signal(u"ssd1306_wake")
        wake_signal.connect(lcd_plugin.wake_signal)
        # Attach to restart signal
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
