#!/usr/bin/env python
#
# This plugin handles a 128x64 SSD1306 LCD 

import web  # web.py framework
import gv  # Get access to ospi's settings
from urls import urls  # Get access to ospi's URLs
from ospi import template_render  #  Needed for working with web.py templates
from webpages import ProtectedPage  # Needed for security
import json  # for working with data file
# For helper functions
from helpers import *
# to write to the console
import sys
# sleep function
from time import sleep
# threads
from threading import Thread, Lock
# get open sprinkler signals
from blinker import signal
# to trace exceptions
import traceback
# to determine how much time as elapsed (for timeout purposes)
import time

# for i2c bus driver
import smbus

# TODO - if there are any settings I can think of in the future
# Add new URLs to access classes in this plugin.
#urls.extend([
#    '/ssd1306-sp', 'plugins.ssd1306.settings',
#    '/ssd1306-save', 'plugins.ssd1306.save_settings'
#    ])

# Add this plugin to the PLUGINS menu ['Menu Name', 'URL'], (Optional)
#gv.plugin_menu.append(['SSD1306 Plugin', '/ssd1306-sp'])

class Lcd:
    # Absolute min/max column and row
    MINIMUM_COLUMN = 0x00
    MAXIMUM_COLUMN = 0x7F
    MINIMUM_ROW = 0x00
    MAXIMUM_ROW = 0x07
    # LCD control and data byte values
    CONTROL_BYTE = 0x00
    DATA_BYTE = 0x40
    # Justification values
    JUSTIFY_LEFT = 0
    JUSTIFY_RIGHT = 1
    JUSTIFY_CENTER = 2
    # Offset of 0x20, up to 0x7F
    lcd_ascii = [
        [0x00, 0x00, 0x00, 0x00, 0x00],  # (space)
        [0x00, 0x00, 0x5F, 0x00, 0x00],  # !
        [0x00, 0x07, 0x00, 0x07, 0x00],  # "
        [0x14, 0x7F, 0x14, 0x7F, 0x14],  # #
        [0x24, 0x2A, 0x7F, 0x2A, 0x12],  # $
        [0x23, 0x13, 0x08, 0x64, 0x62],  # %
        [0x36, 0x49, 0x55, 0x22, 0x50],  # &
        [0x00, 0x05, 0x03, 0x00, 0x00],  # '
        [0x00, 0x1C, 0x22, 0x41, 0x00],  # (
        [0x00, 0x41, 0x22, 0x1C, 0x00],  # )
        [0x08, 0x2A, 0x1C, 0x2A, 0x08],  # *
        [0x08, 0x08, 0x3E, 0x08, 0x08],  # +
        [0x00, 0x50, 0x30, 0x00, 0x00],  # ,
        [0x08, 0x08, 0x08, 0x08, 0x08],  # -
        [0x00, 0x60, 0x60, 0x00, 0x00],  # .
        [0x20, 0x10, 0x08, 0x04, 0x02],  # /
        [0x3E, 0x51, 0x49, 0x45, 0x3E],  # 0
        [0x00, 0x42, 0x7F, 0x40, 0x00],  # 1
        [0x42, 0x61, 0x51, 0x49, 0x46],  # 2
        [0x21, 0x41, 0x45, 0x4B, 0x31],  # 3
        [0x18, 0x14, 0x12, 0x7F, 0x10],  # 4
        [0x27, 0x45, 0x45, 0x45, 0x39],  # 5
        [0x3C, 0x4A, 0x49, 0x49, 0x30],  # 6
        [0x01, 0x71, 0x09, 0x05, 0x03],  # 7
        [0x36, 0x49, 0x49, 0x49, 0x36],  # 8
        [0x06, 0x49, 0x49, 0x29, 0x1E],  # 9
        [0x00, 0x36, 0x36, 0x00, 0x00],  # :
        [0x00, 0x56, 0x36, 0x00, 0x00],  # ;
        [0x00, 0x08, 0x14, 0x22, 0x41],  # <
        [0x14, 0x14, 0x14, 0x14, 0x14],  # =
        [0x41, 0x22, 0x14, 0x08, 0x00],  # >
        [0x02, 0x01, 0x51, 0x09, 0x06],  # ?
        [0x32, 0x49, 0x79, 0x41, 0x3E],  # @
        [0x7E, 0x11, 0x11, 0x11, 0x7E],  # A
        [0x7F, 0x49, 0x49, 0x49, 0x36],  # B
        [0x3E, 0x41, 0x41, 0x41, 0x22],  # C
        [0x7F, 0x41, 0x41, 0x22, 0x1C],  # D
        [0x7F, 0x49, 0x49, 0x49, 0x41],  # E
        [0x7F, 0x09, 0x09, 0x01, 0x01],  # F
        [0x3E, 0x41, 0x41, 0x51, 0x32],  # G
        [0x7F, 0x08, 0x08, 0x08, 0x7F],  # H
        [0x00, 0x41, 0x7F, 0x41, 0x00],  # I
        [0x20, 0x40, 0x41, 0x3F, 0x01],  # J
        [0x7F, 0x08, 0x14, 0x22, 0x41],  # K
        [0x7F, 0x40, 0x40, 0x40, 0x40],  # L
        [0x7F, 0x02, 0x04, 0x02, 0x7F],  # M
        [0x7F, 0x04, 0x08, 0x10, 0x7F],  # N
        [0x3E, 0x41, 0x41, 0x41, 0x3E],  # O
        [0x7F, 0x09, 0x09, 0x09, 0x06],  # P
        [0x3E, 0x41, 0x51, 0x21, 0x5E],  # Q
        [0x7F, 0x09, 0x19, 0x29, 0x46],  # R
        [0x46, 0x49, 0x49, 0x49, 0x31],  # S
        [0x01, 0x01, 0x7F, 0x01, 0x01],  # T
        [0x3F, 0x40, 0x40, 0x40, 0x3F],  # U
        [0x1F, 0x20, 0x40, 0x20, 0x1F],  # V
        [0x7F, 0x20, 0x18, 0x20, 0x7F],  # W
        [0x63, 0x14, 0x08, 0x14, 0x63],  # X
        [0x03, 0x04, 0x78, 0x04, 0x03],  # Y
        [0x61, 0x51, 0x49, 0x45, 0x43],  # Z
        [0x00, 0x00, 0x7F, 0x41, 0x41],  # [
        [0x02, 0x04, 0x08, 0x10, 0x20],  # \
        [0x41, 0x41, 0x7F, 0x00, 0x00],  # ]
        [0x04, 0x02, 0x01, 0x02, 0x04],  # ^
        [0x40, 0x40, 0x40, 0x40, 0x40],  # _
        [0x00, 0x01, 0x02, 0x04, 0x00],  # `
        [0x20, 0x54, 0x54, 0x54, 0x78],  # a
        [0x7F, 0x48, 0x44, 0x44, 0x38],  # b
        [0x38, 0x44, 0x44, 0x44, 0x20],  # c
        [0x38, 0x44, 0x44, 0x48, 0x7F],  # d
        [0x38, 0x54, 0x54, 0x54, 0x18],  # e
        [0x08, 0x7E, 0x09, 0x01, 0x02],  # f
        [0x08, 0x14, 0x54, 0x54, 0x3C],  # g
        [0x7F, 0x08, 0x04, 0x04, 0x78],  # h
        [0x00, 0x44, 0x7D, 0x40, 0x00],  # i
        [0x20, 0x40, 0x44, 0x3D, 0x00],  # j
        [0x00, 0x7F, 0x10, 0x28, 0x44],  # k
        [0x00, 0x41, 0x7F, 0x40, 0x00],  # l
        [0x7C, 0x04, 0x18, 0x04, 0x78],  # m
        [0x7C, 0x08, 0x04, 0x04, 0x78],  # n
        [0x38, 0x44, 0x44, 0x44, 0x38],  # o
        [0x7C, 0x14, 0x14, 0x14, 0x08],  # p
        [0x08, 0x14, 0x14, 0x18, 0x7C],  # q
        [0x7C, 0x08, 0x04, 0x04, 0x08],  # r
        [0x48, 0x54, 0x54, 0x54, 0x20],  # s
        [0x04, 0x3F, 0x44, 0x40, 0x20],  # t
        [0x3C, 0x40, 0x40, 0x20, 0x7C],  # u
        [0x1C, 0x20, 0x40, 0x20, 0x1C],  # v
        [0x3C, 0x40, 0x30, 0x40, 0x3C],  # w
        [0x44, 0x28, 0x10, 0x28, 0x44],  # x
        [0x0C, 0x50, 0x50, 0x50, 0x3C],  # y
        [0x44, 0x64, 0x54, 0x4C, 0x44],  # z
        [0x00, 0x08, 0x36, 0x41, 0x00],  # {
        [0x00, 0x00, 0x7F, 0x00, 0x00],  # |
        [0x00, 0x41, 0x36, 0x08, 0x00],  # }
        [0x08, 0x08, 0x2A, 0x1C, 0x08],  # ->
        [0x08, 0x1C, 0x2A, 0x08, 0x08],  # <-
    ]
    # unknown character value
    char_other = [0x7F, 0x7F, 0x7F, 0x7F, 0x7F]

    def __init__(self, hwAddr = 0x3c, busAddr = 1):
        # hardware address of LCD
        self.hwAddr = hwAddr
        # i2c bus
        self.bus = smbus.SMBus(busAddr)
        # last selected view range
        self.gmin_col = Lcd.MINIMUM_COLUMN
        self.gmax_col = Lcd.MAXIMUM_COLUMN
        self.gmin_row = Lcd.MINIMUM_ROW
        self.gmax_row = Lcd.MAXIMUM_ROW
        # current column and row
        self.current_col = Lcd.MINIMUM_COLUMN
        self.current_row = Lcd.MINIMUM_ROW
        # write failure flag
        self.writeFailure = False
        return

    def lcd_increment_current(self, x):
        "Increments the current column/row values based on number of data values written"
        columns = (self.gmax_col - self.gmin_col + 1)
        rows = (self.gmax_row - self.gmin_row + 1)
        self.current_col += x
        self.current_row = (((self.current_col // columns) + self.current_row) % rows) + self.gmin_row
        self.current_col = (self.current_col % columns) + self.gmin_col
        return

    def lcd_control(self, byte):
        "Writes a single control byte"
        try:
            return self.bus.write_byte_data(self.hwAddr, Lcd.CONTROL_BYTE, byte)
        except:
            if not self.writeFailure:
                print "Failed to write control byte. Is the hardware connected?"
                self.writeFailure = True
            return -1

    def lcd_data(self, byte):
        "Writes a single data byte"
        self.lcd_increment_current(1)
        try:
            return self.bus.write_byte_data(self.hwAddr, Lcd.DATA_BYTE, byte)
        except:
            if not self.writeFailure:
                print "Failed to write data byte. Is the hardware connected?"
                self.writeFailure = True
            return -1

    def lcd_execute_sequence(self, cmd, sequence):
        "Executes a sequence 32 bytes at a time with a given command"
        ctrlarr = []
        try:
            # write_i2c_block_data() can execute a max of 32 bytes at a time
            for value in sequence:
                ctrlarr.append(value)
                if len(ctrlarr) == 32:
                    # execute!
                    self.bus.write_i2c_block_data(self.hwAddr, cmd, ctrlarr)
                    ctrlarr = []
            if len(ctrlarr) > 0:
                # execute the rest
                self.bus.write_i2c_block_data(self.hwAddr, cmd, ctrlarr)
        except:
            if not self.writeFailure:
                print "Failed to execute sequence. Is the hardware connected?"
                self.writeFailure = True
        if cmd == Lcd.DATA_BYTE:
            self.lcd_increment_current(len(sequence))
        return

    def lcd_execute_control_sequence(self, sequence):
        "Executes a control byte sequence"
        self.lcd_execute_sequence(Lcd.CONTROL_BYTE, sequence)
        return

    def lcd_execute_data_sequence(self, sequence):
        "Executes a data byte sequence"
        self.lcd_execute_sequence(Lcd.DATA_BYTE, sequence)
        return

    def initialize(self):
        "Initializes the LCD for this interface - call right after instantiation to initialize and clear display"
        print "LCD initialize..."
        # initialization sequence
        init_sequence = [
            0xae,  # turn off oled panel
            0x00,  # set low column address
            0x10,  # set high column address
            0x40,  # set start line address
            0x81,  # set contrast control register
            0xcf,
            0xa1,  # set segment re-map 95 to 0
            0xa6,  # set normal display
            0xa8,  # set multiplex ratio(1 to 64)
            0x3f,  # 1/64 duty
            0xd3,  # set display offset
            0x00,  # not offset
            0xd5,  # set display clock divide ratio/oscillator frequency
            0x80,  # set divide ratio
            0xd9,  # set pre-charge period
            0xf1,
            0xda,  # set com pins hardware configuration
            0x12,
            0xdb,  # set vcomh
            0x40,
            0x8d,  # set Charge Pump enable/disable
            0x14,  # set(0x10) disable
            0x20,  # horizontal addressing mode
            0x00,
            0xc8,  # Remapped mode. Scan from ComN-1 to Com0
        ]
        self.lcd_execute_control_sequence(init_sequence)
        # Clear out the buffer and synchronize with hardware
        self.clear()
        # Turn on OLED panel
        self.lcd_control( 0xaf )
        print "Done"
        return

    def lcd_set_print_area_max(self):
        "Sets the printable area to max screen"
        return self.lcd_set_print_area(Lcd.MINIMUM_COLUMN, Lcd.MAXIMUM_COLUMN, Lcd.MINIMUM_ROW, Lcd.MAXIMUM_ROW)

    def clear(self):
        # set print area to max in order to clear the entire screen
        self.lcd_set_print_area_max()
        #print "Clearing screen..."
        # set all pixels to 0
        dat = []
        for i in range(0,32):
            dat.append(0x00)
        for i in range(0,32):
            self.lcd_execute_data_sequence(dat)
        #print "Done"
        return

    def lcd_set_print_area(self, min_col, max_col, min_row, max_row):
        "Sets the print area of the screen with max of: (0x00, 0x7F, 0x00, 0x07)"
        if min_col < 0 or max_col > 0x7f or max_col < min_col:
            return 0
        elif min_row < 0 or max_row > 0x07 or max_row < min_row:
            return 0
        seq = []
        seq.append(0x21)
        seq.append(min_col)
        seq.append(max_col)
        seq.append(0x22)
        seq.append(min_row)
        seq.append(max_row)
        self.lcd_execute_control_sequence(seq)
        self.gmin_col = min_col
        self.gmax_col = max_col
        self.gmin_row = min_row
        self.gmax_row = max_row
        self.current_col = min_col
        self.current_row = min_row
        return 1

    @staticmethod
    def __bitShitftRightByteList(lst, num = 1):
        for i in range(num):
            addToNext = False
            for j in range(len(lst)):
                addToCurrent = addToNext
                addToNext = ( ( lst[j] & 0x01 ) > 0 )
                lst[j] = lst[j] >> 1
                if addToCurrent:
                    lst[j] = lst[j] | 0x80
        return lst
        
    def _generate_char_sequence(self, char, text_size_multiplier = 1):
        chv = ord(char)
        seq = []
        if chv >=0x20 and chv <= 0x7F:
            seq = list(self.lcd_ascii[chv - 0x20])
        else: # unknown
            seq = list(char_other)

        seq.append(0x00)

        mask = 0x80
        colMask = [0] * text_size_multiplier
        retSeq = []
        for i in range(text_size_multiplier):
            colMask[0] = colMask[0] >> 1
            colMask[0] = colMask[0] | 0x80
            retSeq.append( [0] * (len(seq) * text_size_multiplier) )
        for i in range(8):
            for j in range(len(seq)):
                v = seq[j]
                if( v & mask ):
                    for k in range(text_size_multiplier):
                        for l in range(text_size_multiplier):
                            retSeq[text_size_multiplier-k-1][(j * text_size_multiplier + l)] = retSeq[text_size_multiplier-k-1][(j * text_size_multiplier + l)] | colMask[k]
            colMask = Lcd.__bitShitftRightByteList(colMask, text_size_multiplier)
            mask = mask >> 1

        return retSeq
        
    def write_block(self, str, row_start, min_text_size, max_text_size, justification = 0):
        if( min_text_size > max_text_size or min_text_size <= 0 or max_text_size <= 0):
            return 0
        maxWidth = Lcd.MAXIMUM_COLUMN - Lcd.MINIMUM_COLUMN + 1
        words = str.split(" ")
        wordSizes = [0] * len(words)
        # I am assuming that each character is 5 pixel width with 1 pixel space 
        numberOfSpaces = len(words) - 1
        totalSize = numberOfSpaces * 6
        for i in range(len(words)):
            currentSize = 0
            for j in range(len(words[i])):
                currentSize += 6
            wordSizes[i] = currentSize
            totalSize += currentSize
        if( totalSize * max_text_size <= maxWidth or min_text_size == max_text_size or len(str) <= 0 ):
            # It can all fit in one line at max size min = max; we are done
            return self.write_line(str, row_start, max_text_size, justification)
        currentTextSize = max_text_size
        lines = []
        maxLines = 0
        while( currentTextSize > min_text_size ):
            currentTextSize -= 1
            maxLines = max_text_size / currentTextSize
            currentLine = 0
            lines = [ words[0] ]
            currentSize = wordSizes[0]
            lineTooLong = False
            for i in range(1, len(words)):
                nextSize = currentSize + wordSizes[i] + 6
                if( nextSize * currentTextSize > maxWidth ):
                    # Next line
                    lines.append(words[i])
                    currentLine += 1
                    currentSize = wordSizes[i]
                    # Flag if this word by itself is too long to fit
                    if( currentSize * currentTextSize > maxWidth ):
                        lineTooLong = True
                else:
                    lines[currentLine] += (" " + words[i])
                    currentSize += (wordSizes[i] + 6)
            if( len(lines) <= maxLines and not lineTooLong ):
                # we are done 
                break 
        while( len(lines) + 2 <= maxLines ):
            temp = ['']
            temp.extend(lines)
            lines = temp
            lines.append('')
        if( len(lines) > maxLines ):
            lines = lines[:maxLines]
        rowNum = row_start
        printedCount = 0
        for l in lines:
            printedCount += self.write_line(l, rowNum, currentTextSize, justification)
            rowNum += currentTextSize
        # Clear out the rest
        for i in range(rowNum, row_start + max_text_size):
            self.write_line('', i, 1, Lcd.JUSTIFY_LEFT)
        return printedCount

    def write_line(self, str, row_start, text_size_multiplier = 1, justification = 0):
        if row_start < Lcd.MINIMUM_ROW or row_start > Lcd.MAXIMUM_ROW:
            return 0
        if len(str) <= 0:
            str = ' '
        seq = []
        for c in str:
            seqChar = self._generate_char_sequence(c, text_size_multiplier)
            if len(seq) <= 0:
                seq = seqChar
            else:
                for i in range(len(seq)):
                    seq[i].extend(seqChar[i])

        row_end = row_start + text_size_multiplier - 1
        if row_end > Lcd.MAXIMUM_ROW:
            row_end = Lcd.MAXIMUM_ROW
        self.lcd_set_print_area(Lcd.MINIMUM_COLUMN, Lcd.MAXIMUM_COLUMN, row_start, row_end)

        maxNumRows = (self.gmax_row - self.gmin_row + 1)
        maxNumCols = (self.gmax_col - self.gmin_col + 1)
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
                    newSeq = ([0]*columnsToAdd)
                    newSeq.extend(seq[i])
                    seq[i] = newSeq
                elif justification == Lcd.JUSTIFY_CENTER:
                    columnsToAddLeft = columnsToAdd // 2
                    columnsToAddRight = columnsToAdd - columnsToAddLeft
                    newSeq = ([0]*columnsToAddLeft)
                    newSeq.extend(seq[i])
                    newSeq.extend([0]*columnsToAddRight)
                    seq[i] = newSeq
                else:
                    # Left justification by default
                    seq[i].extend([0]*columnsToAdd)
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
            self.lcd_execute_data_sequence(seq[i])
        return 1

class LcdPlugin(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.alarmSignaled = False
        self.alarmText = ''
        self.lastWrite = ''
        self.lastSubVal = ''
        self.lcd = Lcd()
        self.__set_default_settings()
        
    def initialize(self):
        self.lcd.initialize()
        self.lcd.clear()
        return True
        
    def __set_default_settings(self):
        # Nothing yet
        #self.sample_key = 0
        return
        
    def load_from_dict(self, settings):
        self.__set_default_settings()
        if settings is None:
            return
        #if settings.has_key("sample_key"):
        #    self.sample_key = settings["sample_key"]
        return
        
    def load_settings(self):
        # Get settings
        #try:
        #    with open('./data/ssd1306.json', 'r') as f:
        #        self.load_from_dict(json.load(f))
        #except:
        #    self.__set_default_settings()
        return
        
    def save_settings(self):
        #settings = {
        #    "sample_key": self.sample_key,
        #}
        #with open('./data/ssd1306.json', 'w') as f:
        #    json.dump(settings, f) # save to file
        return
        
    @staticmethod
    def __get_time_string():
        timeStr = ""
        nowt = gv.nowt
        timeHours = nowt.tm_hour
        timeMinutes = nowt.tm_min
        ampmString = ""
        if ( not gv.sd['tf'] ):
            isPm = False
            timeHours = gv.nowt.tm_hour
            if( timeHours == 0 ):
                timeHours = 12
            elif( timeHours == 12 ):
                isPm = True
            elif( timeHours > 12 ):
                timeHours -= 12
                isPm = True
            ampmString =  " PM" if isPm else " AM"
        hrString = str( timeHours )
        minString = str( timeMinutes / 10 >> 0 ) + str( timeMinutes % 10 >> 0 )
        timeStr = hrString + ":" + minString + ampmString
        return timeStr

    def __display_normal(self):
        if gv.pon is None:
            prg = 'Idle'
        elif gv.pon == 98:  # something is running
            prg = 'Run-once'
        elif gv.pon == 99:
            prg = 'Manual Mode'
        else:
            prg = "{}".format(gv.pon)

        s = ""
        if prg != "Idle":
            # Get Running Stations from gv.ps
            programRunning = False
            stationDuration = 0
            for i in range(len(gv.ps)):
                p, d = gv.ps[i]
                if p != 0:
                    programRunning = True
                if i + 1 != gv.sd['mas'] and gv.srvals[i]:
                    # not master and currently on
                    if len(s) == 0:
                        s = str(i + 1)
                    else:
                        s += (" " + str(i + 1))
                    if( d > stationDuration ):
                        stationDuration = d
            if( len(s) == 0 ):
                if programRunning:
                    if gv.pon == 98:
                        aboutToWrite = "RunningRun-onceProgram"
                        if( self.lastWrite != aboutToWrite ):
                            self.lcd.write_line("Running", 0, 2, Lcd.JUSTIFY_CENTER)
                            self.lcd.write_line("", 2, 1, Lcd.JUSTIFY_LEFT)
                            self.lcd.write_line("Run-once", 3, 2, Lcd.JUSTIFY_CENTER)
                            self.lcd.write_line("", 5, 1, Lcd.JUSTIFY_LEFT)
                            self.lcd.write_line("Program", 6, 2, Lcd.JUSTIFY_CENTER)
                            self.lastWrite = aboutToWrite
                    elif gv.pon == 99:
                        aboutToWrite = "ManualMode"
                        if( self.lastWrite != aboutToWrite ):
                            self.lcd.write_line("", 0, 1, Lcd.JUSTIFY_LEFT)
                            self.lcd.write_line("Manual", 1, 2, Lcd.JUSTIFY_CENTER)
                            self.lcd.write_line("", 3, 1, Lcd.JUSTIFY_LEFT)
                            self.lcd.write_line("Mode", 4, 2, Lcd.JUSTIFY_CENTER)
                            self.lcd.write_line("", 6, 2, Lcd.JUSTIFY_LEFT)
                            self.lastWrite = aboutToWrite
                    else:
                        aboutToWrite = "RunningProgram{}".format(prg)
                        if( self.lastWrite != aboutToWrite ):
                            self.lcd.write_line("Running", 0, 2, Lcd.JUSTIFY_CENTER)
                            self.lcd.write_line("", 2, 1, Lcd.JUSTIFY_LEFT)
                            self.lcd.write_line("Program", 3, 2, Lcd.JUSTIFY_CENTER)
                            self.lcd.write_line("", 5, 1, Lcd.JUSTIFY_LEFT)
                            self.lcd.write_line(prg, 6, 2, Lcd.JUSTIFY_CENTER)
                            self.lastWrite = aboutToWrite
                else:
                    # It was a lie!
                    prg = "Idle"
            else:
                if( self.lastWrite != s ):
                    self.lcd.write_block(s, 0, 1, 5, Lcd.JUSTIFY_CENTER)
                    self.lcd.write_line(' ', 5, 1, Lcd.JUSTIFY_CENTER)
                    self.lastWrite = s
                    self.lastSubVal = ''
                if gv.pon == 99 and stationDuration <= 0:
                    # Manual station on forever
                    aboutToWrite = 'ON'
                else:
                    stationSec = int(stationDuration) % 60
                    stationMin = int(stationDuration) / 60
                    stationHrs = stationMin / 60
                    stationMin = stationMin % 60
                    aboutToWrite = str(stationMin / 10) + str(stationMin % 10) + ":" + str(stationSec / 10) + str(stationSec % 10)
                    if( stationHrs > 0 ):
                        aboutToWrite = str(stationHrs / 10) + str(stationHrs % 10) + ":" + aboutToWrite
                if( self.lastSubVal != aboutToWrite ):
                    self.lcd.write_line(aboutToWrite, 6, 2, Lcd.JUSTIFY_CENTER)
                    self.lastSubVal = aboutToWrite
        # Check again because prg may have changed to Idle in the above if statement
        if prg == "Idle":
            if( not gv.sd['en'] ):
                if( self.lastWrite != "OFF" ):
                    self.lcd.write_line("OFF", 0, 3, Lcd.JUSTIFY_CENTER)
                    self.lcd.write_line("", 3, 5, Lcd.JUSTIFY_LEFT)
                    self.lastWrite = "OFF"
            elif( gv.sd['mm'] ):
                aboutToWrite = "IdleManualMode"
                if( self.lastWrite != aboutToWrite ):
                    self.lcd.write_line("Idle", 0, 3, Lcd.JUSTIFY_CENTER)
                    self.lcd.write_line("", 3, 1, Lcd.JUSTIFY_LEFT)
                    self.lcd.write_line("Manual", 4, 2, Lcd.JUSTIFY_CENTER)
                    self.lcd.write_line("Mode", 6, 2, Lcd.JUSTIFY_CENTER)
                    self.lastWrite = aboutToWrite
            elif( gv.sd['rd'] ):
                aboutToWrite = "RainDelay"
                if( self.lastWrite != aboutToWrite ):
                    self.lcd.write_line("Rain", 0, 2, Lcd.JUSTIFY_CENTER)
                    self.lcd.write_line("", 2, 1, Lcd.JUSTIFY_LEFT)
                    self.lcd.write_line("Delay", 3, 2, Lcd.JUSTIFY_CENTER)
                    self.lcd.write_line("", 5, 1, Lcd.JUSTIFY_LEFT)
                    self.lastWrite = aboutToWrite
                    self.lastSubVal = ''
                remainingHrs = (gv.sd['rdst'] - gv.now) / 60 / 60
                aboutToWrite = str(remainingHrs)
                if( self.lastSubVal != aboutToWrite ):
                    if( remainingHrs < 1 ):
                        self.lcd.write_line("<1 hr", 6, 2, Lcd.JUSTIFY_CENTER)
                    elif( remainingHrs == 1 ):
                        self.lcd.write_line("1 hr", 6, 2, Lcd.JUSTIFY_CENTER)
                    else:
                        self.lcd.write_line(str(remainingHrs) + " hrs", 6, 2, Lcd.JUSTIFY_CENTER)
                    self.lastSubVal = aboutToWrite
            elif( gv.sd['wl'] < 100 ):
                waterLevel = str(gv.sd['wl'])
                aboutToWrite = "IdleWaterLevel" + waterLevel
                if( self.lastWrite != aboutToWrite ):
                    self.lcd.write_line("Idle", 0, 3, Lcd.JUSTIFY_CENTER)
                    self.lcd.write_line(waterLevel + "%", 3, 2, Lcd.JUSTIFY_CENTER)
                    self.lcd.write_line("", 5, 1, Lcd.JUSTIFY_LEFT)
                    self.lastWrite = aboutToWrite
                    self.lastSubVal = ''
                aboutToWrite = LcdPlugin.__get_time_string()
                if( self.lastSubVal != aboutToWrite ):
                    self.lcd.write_line(aboutToWrite, 6, 2, Lcd.JUSTIFY_CENTER)
                    self.lastSubVal = aboutToWrite
            else:
                if( self.lastWrite != prg ):
                    self.lcd.write_line(prg, 0, 3, Lcd.JUSTIFY_CENTER)
                    self.lcd.write_line("", 3, 3, Lcd.JUSTIFY_LEFT)
                    self.lastWrite = prg
                    self.lastSubVal = ''
                aboutToWrite = LcdPlugin.__get_time_string()
                if( self.lastSubVal != aboutToWrite ):
                    self.lcd.write_line(aboutToWrite, 6, 2, Lcd.JUSTIFY_CENTER)
                    self.lastSubVal = aboutToWrite

    def __display_alarm(self):
        self.lcd.write_line("ALARM!", 0, 3, Lcd.JUSTIFY_CENTER)
        self.lcd.write_line("", 3, 1, Lcd.JUSTIFY_LEFT)
        self.lcd.write_line(self.alarmText, 4, 2, Lcd.JUSTIFY_CENTER)
        self.lcd.write_line("", 6, 2, Lcd.JUSTIFY_LEFT)
        self.lastWrite = ''

    def alarm(self, name,  **kw):
        self.alarmText = kw['txt']
        self.alarmSignaled = True

    def run(self):
        sleep(5)
        print "LCD plugin is active"
        while True:
            if self.alarmSignaled:
                self.__display_alarm()
                sleep(20)
                self.alarmText = ''
                self.alarmSignaled = False
            else:
                self.__display_normal()
            sleep(1)

# Start LCD
lcd_plugin = LcdPlugin()
if( lcd_plugin.initialize() ):
    lcd_plugin.start()
    alarm = signal('alarm_toggled')
    alarm.connect(lcd_plugin.alarm)



################################################################################
# Web pages:                                                                   #
################################################################################


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open('./data/ssd1306.json', 'r') as f:  # Read settings from json file if it exists
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
        qdict = web.input()  # Dictionary of values returned as query string from settings page.
        lcd_plugin.load_from_dict(qdict) # load settings from dictionary
        lcd_plugin.save_settings() # Save keypad settings
        raise web.seeother('/')  # Return user to home page.
