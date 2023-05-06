from __future__ import print_function

# !/usr/bin/env python

# Written by James M Smith 6/14/2015
# This plugin uses a 4x4 scanning keypad and optionally a buzzer
# Keypad should have the following layout
#      (C1) (C2) (C3) (C4)
# (R1)  1    2    3    A
# (R2)  4    5    6    B
# (R3)  7    8    9    C
# (R4)  *    0    #    D
#
# To enter a value under the default function, enter number followed by pound (#)
#     Example: 1-3-# to enter 13
#
# If manual station is selected, the station will run under "Run Once" for 5 minutes by default.
# The manual station time may be changed under the settings.
# Running a station or program will stop the current program in progress, if any.
# Entering 0# will stop all programs in progress, leaving the system idle.
# Press the asterisk key (*) at any time to cancel out entered value.
# Timeout for entering a value after first keypress is 5 seconds by default.
#

import web  # web.py framework
import gv  # Get access to ospi's settings
from urls import urls  # Get access to ospi's URLs
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
from threading import Thread

# get open sprinkler signals
from blinker import signal

# to trace exceptions
import traceback

# to determine how much time as elapsed (for timeout purposes)
import time

# Load the Raspberry Pi GPIO (General Purpose Input Output) library
try:
    if gv.use_pigpio:
        import pigpio
        pi = pigpio.pi()
    else:
        import RPi.GPIO as GPIO
except IOError:
    pass

# KEYPAD VARIABLES
# Keypad column pins
KEYPAD_PIN_COLUMNS = [29, 31, 33, 35]  # C1  # C2  # C3  # C4
# Keypad row pins
KEYPAD_PIN_ROWS = [37, 40, 38, 36]  # R1  # R2  # R3  # R4
# Maps keypad key to index
KEYPAD_INDICES = [
    #    C1  C2  C3  C4
    [1, 2, 3, 10],  # R1
    [4, 5, 6, 11],  # R2
    [7, 8, 9, 12],  # R3
    [14, 0, 15, 13],  # R4
]
# Maps keypad index to character
KEYPAD_KEY_LIST = [
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "A",
    "B",
    "C",
    "D",
    "*",
    "#",
]

# Add new URLs to access classes in this plugin.
urls.extend(
    [
        "/keypad-sp",
        "plugins.keypad.settings",
        "/keypad-save",
        "plugins.keypad.save_settings",
    ]
)

# Add this plugin to the PLUGINS menu ['Menu Name', 'URL'], (Optional)
gv.plugin_menu.append([_("Keypad Plugin"), "/keypad-sp"])

class ScanningKeypad:
    """ This class handles the keypad hardware """
    def __init__(self, pin_columns, pin_rows, indices, char_list):
        """
        Initializes a ScanningKeypad object
        Inputs: pin_columns - List of pin numbers for the keypad columns
                pin_rows - List of pin numbers for the keypad rows
                indices - A 2-dimensional table of the resulting index for each key when a column
                          meets with a row
                char_list - List of characters where the key is a value within indices
        """
        self._pin_columns = pin_columns
        self._pin_rows = pin_rows
        self._indices = indices
        self._char_list = char_list
        # Current energized column
        self._keypad_current_column = -1
        # set to true after keypad pins are first initialized; set to false on exception
        self._pins_initialized = False
        # Boolean to help force blocking calls to exit once this transitions to False
        self._running = True

    def set_running(self, is_running):
        """
        Sets the running flag (forces some blocking calls to unblock when set to False)
        """
        self._running = is_running

    def isReady(self):
        """
        Returns True if the hardware is ready; False otherwise
        """
        return self._pins_initialized

    @staticmethod
    def _set_floating_input(pin):
        """
        Set the hardware input as floating (not pulled up or down by a resistor)
        """
        if gv.use_pigpio:
            pi.set_mode(gv.pin_map[pin], pigpio.INPUT)
            pi.set_pull_up_down(gv.pin_map[pin], pigpio.PUD_OFF)
        else:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)

    def _set_column(self, col):
        """
        Output LOW to the previous column and output HIGH to the given column
        Inputs: col - The column index to set
        Returns: True if operation succeeded; False otherwise
        """
        if self._pins_initialized:
            try:
                if self._keypad_current_column >= 0:
                    # Set old value as floating input so it won't affect anyone else
                    ScanningKeypad._set_floating_input(self._keypad_current_column)
                # set current pin and make output HIGH
                self._keypad_current_column = col
                if gv.use_pigpio:
                    pi.set_mode(gv.pin_map[self._keypad_current_column], pigpio.OUTPUT)
                    pi.write(gv.pin_map[self._keypad_current_column], 1)
                else:
                    GPIO.setup(self._keypad_current_column, GPIO.OUT)
                    GPIO.output(self._keypad_current_column, GPIO.HIGH)
            except Exception as err:
                print(u"Keypad plugin: except:\n{}".format(err))
                print(traceback.format_exc())
                self._pins_initialized = False
        return self._pins_initialized

    def _init_pins(self):
        """
        Initializes the pins used by this ScanningKeypad
        Returns: True if operation succeeded; False otherwise
        """
        try:
            if not gv.use_pigpio:
                GPIO.setmode(GPIO.BOARD)
            # set column pins as floating to start with
            for v in self._pin_columns:
                ScanningKeypad._set_floating_input(v)
            self._keypad_current_column = -1
            # row pins will be used as input with pull down resistors
            for v in self._pin_rows:
                if gv.use_pigpio:
                    pi.set_mode(gv.pin_map[v], pigpio.INPUT)
                    pi.set_pull_up_down(gv.pin_map[v], pigpio.PUD_DOWN)
                else:
                    GPIO.setup(v, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            self._pins_initialized = True
        except Exception as err:
            print(u"Keypad plugin: except:\n{}".format(err))
            print(traceback.format_exc())
            self._pins_initialized = False
        return self._pins_initialized

    def _sample(self):
        """
        Samples all rows and returns the depressed keys for the current column
        """
        keys = [False] * len(self._char_list)
        for col, col_v in enumerate(self._pin_columns):
            if self._set_column(col_v):
                sleep(0.001)  # just to make sure the output is fully charged
                try:
                    for row, row_v in enumerate(self._pin_rows):
                        if gv.use_pigpio:
                            keys[self._indices[row][col]] = pi.read(gv.pin_map[row_v])
                        else:
                            keys[self._indices[row][col]] = GPIO.input(row_v)
                except Exception as err:
                    print(u"Keypad plugin: except:\n{}".format(err))
                    print(traceback.format_exc())
                    self._pins_initialized = False
            else:
                keys = [False] * len(self._char_list)
                break
        return keys

    def wait_for_any_key(self):
        """
        Waits for any key to be pressed
        """
        c = self._sample()
        while True not in c:
            sleep(0.01)
            c = self._sample()

    def getc(self, down_keys=None, timeout_s=-1):
        """
        Gets next key press
        Inputs: down_keys - Updated to the currently depressed keys on return
                timeout_s - The amount of time in seconds to block before giving up
        """
        # Get starting time
        start_time = time.time()
        # Get initial sample
        last = keys = self._sample()
        c = []
        while self._running and self._pins_initialized:
            # Check for error
            if keys is None:
                return None  # There was a fatal error
            # Add any new keys to c
            for i, v in enumerate(self._char_list):
                if last[i] != keys[i] and keys[i]:
                    c.append(v)
            # If any new keys have been added, we are done
            if len(c) > 0:
                break
            # Check for timeout
            current_time = time.time()
            if timeout_s > 0 and (current_time - start_time) >= timeout_s:
                break  # Timeout occurred
            # Check for change every 25 ms so we don't bog anything down.
            # This also serves as a debounce.
            sleep(0.025)
            # Next sample
            last = keys
            keys = self._sample()
        # Copy keys to down_keys
        if (
            down_keys is not None
            and len(down_keys) >= len(self._char_list)
            and keys is not None
        ):
            for i in range(0, len(self._char_list)):
                down_keys[i] = keys[i]
        return c

    def wait_for_key_index_up(self, key_index, timeout_s=-1, running=True):
        if key_index >= 0 and key_index < len(self._char_list):
            timeout_reached = False
            # Get starting time
            start_time = time.time()
            while running and self._pins_initialized and not timeout_reached:
                keys = self._sample()
                current_time = time.time()
                # Check to see if the selected key is up
                if not keys[key_index]:
                    return current_time - start_time
                # Check for timeout
                elif timeout_s > 0 and (current_time - start_time) >= timeout_s:
                    return current_time - start_time  # Timeout occurred
                sleep(0.025)  # sleep for a moment before trying again
            return -1  # we are not running or pins aren't initialized
        else:
            return -1  # invalid index

    def wait_for_key_char_up(self, key_char, timeout_s=-1, running=True):
        key_index = -1
        for i, c in enumerate(self._char_list):
            if c == key_char:
                key_index = i
                break
        return self.wait_for_key_index_up(key_index, timeout_s, running)


def float_to_field_str(value):
    return format(value, '0.2f').rstrip('0').rstrip('.')

# This class contains the functionality for this plugin
class KeypadPlugin:
    # Constants
    #
    # Value functions
    FN_NONE = -1
    FN_MANUAL_STATION = 0
    FN_MANUAL_PROGRAM = 1
    FN_WATER_LEVEL = 2
    FN_MANUAL_STATION_TIME = 3
    FN_RAIN_DELAY_TIME = 4
    FN_START_RAIN_DELAY = 5
    # Function text must be 9 chars or less
    FUNCTION_TEXT = {FN_MANUAL_STATION:      u"Station",
                     FN_MANUAL_PROGRAM:      u"Program",
                     FN_WATER_LEVEL:         u"Water Lvl",
                     FN_MANUAL_STATION_TIME: u"Sta Time",
                     FN_RAIN_DELAY_TIME:     u"RDly Time",
                     FN_START_RAIN_DELAY:    u"Rain Dly"}
    # Instantaneous functions
    HLDFN_NONE = -1
    HLDFN_STOP_ALL = 16
    HLDFN_ACTIVATE_RAIN_DELAY = 17
    HLDFN_DEACTIVATE_RAIN_DELAY = 18
    HLDFN_SYSTEM_ON = 19
    HLDFN_SYSTEM_OFF = 20
    HLDFN_RESTART_SYSTEM = 21
    HLDFN_REBOOT_OS = 22
    HLDFN_RESET_WATER_LEVEL = 23
    HLDFN_TOGGLE_RAIN_DELAY = 24
    HLDFN_TOGGLE_SYSTEM_EN = 25
    # Function text must be 10 chars or less
    HOLD_FUNCTION_TEXT = {HLDFN_STOP_ALL:              u"Stop All",
                          HLDFN_ACTIVATE_RAIN_DELAY:   u"RDelay On",
                          HLDFN_DEACTIVATE_RAIN_DELAY: u"RDelay Off",
                          HLDFN_SYSTEM_ON:             u"System On",
                          HLDFN_SYSTEM_OFF:            u"System Off",
                          HLDFN_RESTART_SYSTEM:        u"Restarting",
                          HLDFN_REBOOT_OS:             u"Rebooting",
                          HLDFN_RESET_WATER_LEVEL:     u"WLvl=100%",
                          HLDFN_TOGGLE_RAIN_DELAY:     u"Tgl RDelay",
                          HLDFN_TOGGLE_SYSTEM_EN:      u"Tgl Sys En"}
    # Execution enumeration
    EXECUTE_FAILED = 0
    EXECUTE_COMPLETE = 1
    EXECUTE_TOGGLE_ON = 2
    EXECUTE_TOGGLE_OFF = 3

    # Types of keys
    FUNCTION_KEYS = ["A", "B", "C", "D"]
    NUMBER_KEYS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
    ENTER_KEY = "#"
    CANCEL_KEY = "*"

    # Allow up to 9999 station/program
    MAX_NUMBER_ENTRY = 4

    def __init__(self):
        # Keypad object to get key presses
        self._keypad = ScanningKeypad(
            KEYPAD_PIN_COLUMNS, KEYPAD_PIN_ROWS, KEYPAD_INDICES, KEYPAD_KEY_LIST
        )
        # Buzzer signal for feedback
        self._buzzer_signal = signal(u"buzzer_beep")
        # Wake signalling for SSD1306 display
        self._ssd1306_wake_signal = signal(u"ssd1306_wake")
        # Signalling for displaying currently pressed keys
        self._ssd1306_display_signal = signal(u"ssd1306_display")

        # Set all default settings
        self._set_default_settings()
        # Currently selected function
        self._reset_selected_function()

        # Set to True when running and False to exit task
        self._set_running(False)
        # Handle to the running thread for this plugin
        self._running_thread = None

        # Set to True when function is selected by user
        self._function_selected = False
        return

    def _set_running(self, is_running):
        """
        Sets the running flag (forces some blocking calls to unblock when set to False)
        """
        self._running = is_running
        self._keypad.set_running(is_running)

    def _set_default_settings(self):
        """
        Sets the json settings to their defaults
        """
        # settings
        self.keypad_press_timeout_s = 5
        self.keypad_manual_station_time_s = 300
        self.rain_delay_hrs = 24
        self.key_hold_time_s = 1
        self.selectable_functions = {
            "A": KeypadPlugin.FN_MANUAL_STATION,
            "B": KeypadPlugin.FN_START_RAIN_DELAY,
            "C": KeypadPlugin.FN_WATER_LEVEL,
            "D": KeypadPlugin.FN_MANUAL_STATION_TIME,
        }
        self.hold_functions = {
            "A": KeypadPlugin.HLDFN_NONE,
            "B": KeypadPlugin.HLDFN_NONE,
            "C": KeypadPlugin.HLDFN_NONE,
            "D": KeypadPlugin.HLDFN_NONE,
        }
        # Default function
        self.default_function = KeypadPlugin.FN_MANUAL_STATION

        # Beeps
        self.acknowledge_command_beep = 0.100
        self.cancel_beep = [0.050, 0.050, 0.100]
        self.error_beep = [0.100, 0.100, 0.500]
        self.hold_function_executed_beep = [0.100, 0.050, 0.100]
        self.hold_function_toggle_on_beep = [0.050, 0.050, 0.200]
        self.hold_function_toggle_off_beep = [0.200, 0.050, 0.050]
        self.button_pressed_beep = 0.025

    def init_pins(self):
        """
        Initializes hardware pins
        """
        return self._keypad._init_pins()

    # This function is based on change_runonce class in webpages.py
    @staticmethod
    def _set_runonce_station(stationID, seconds=300):
        """
        Runs a single station for a given number of seconds. This will override any running program.
        """
        found = False
        newrovals = []
        for i in range(gv.sd["nst"]):
            if i == (stationID - 1):
                found = True
                newrovals.append(seconds)
            else:
                newrovals.append(0)
        run_schedule = False
        if found:
            print(u"Keypad plugin: Running station %d for %d seconds." % (stationID, seconds))
            run_schedule = True
        elif stationID == 0:
            print(u"Keypad plugin: Stopping all stations.")
            run_schedule = True
        else:
            print(u"Keypad plugin: Station %d not found. Ignoring entry." % stationID)
            run_schedule = False
        if run_schedule:
            gv.rovals = newrovals
            stations = [0] * gv.sd["nbrd"]
            gv.ps = []  # program schedule (for display)
            gv.rs = []  # run schedule
            for i in range(gv.sd["nst"]):
                gv.ps.append([0, 0])
                gv.rs.append([0, 0, 0, 0])
            for i, v in enumerate(gv.rovals):
                if v:  # if this element has a value
                    gv.rs[i][0] = gv.now + 3
                    gv.rs[i][2] = v
                    gv.rs[i][3] = 98
                    gv.ps[i][0] = 98
                    gv.ps[i][1] = v
                    stations[i // 8] += 2 ** (i % 8)

            schedule_stations(stations)
        return run_schedule

    # This function is based on run_now class in webpages.py
    @staticmethod
    def _set_runonce_program(programID):
        """
        Run a scheduled program now. This will override any running programs.
        """
        if programID == 0:
            print(u"Keypad plugin: Stopping all stations.")
            stop_stations()
            return True
        pid = programID - 1
        if len(gv.pd) <= pid:
            print(u"Keypad plugin: Invalid program: %d" % programID)
            return False
        else:
            print(u"Keypad plugin: Program entry doesn't currently work")
            return False
            # TODO: Fix this! The internal structure has changed
            p = gv.pd[int(pid)]  # program data
            stop_stations()
            extra_adjustment = plugin_adjustment()
            sid = -1
            for b in range(gv.sd["nbrd"]):  # check each station
                for s in range(8):
                    sid += 1  # station index
                    if sid + 1 == gv.sd["mas"]:  # skip if this is master valve
                        continue
                    if (
                        p[7 + b] & 1 << s
                    ):  # if this station is scheduled in this program
                        if gv.sd["idd"]:
                            duration = p[-1][sid]
                        else:
                            duration = p[6]
                        if not gv.sd["iw"][b] & 1 << s:
                            duration = duration * gv.sd["wl"] / 100 * extra_adjustment
                        gv.rs[sid][2] = duration
                        gv.rs[sid][3] = pid + 1  # store program number in schedule
                        gv.ps[sid][0] = pid + 1  # store program number for display
                        gv.ps[sid][1] = duration  # duration
            print(u"Keypad plugin: Running program #%d" % programID)
            schedule_stations(p[7 : 7 + gv.sd["nbrd"]])
            return True

    @staticmethod
    def _set_water_level(level):
        print(u"Keypad plugin: Set water level for %d%%" % level)
        if level >= 0:
            gv.sd["wl"] = level
            return True
        return False

    def _set_manual_station_time(self, time):
        print(u"Keypad plugin: Set manual station time for %d seconds" % time)
        self.keypad_manual_station_time_s = time
        self.save_keypad_settings()
        return True

    def _set_rain_delay_time(self, time):
        print(u"Keypad plugin: Set rain delay for %d hours" % time)
        self.rain_delay_hrs = time
        self.save_keypad_settings()
        return True

    def _wait_for_ready(self):
        """
        Waits for hardware to be ready
        Returns: True if hardware is ready; False if timeout occurred
        """
        if not self._running:
            return False
        MAX_INIT_RETRY = 3
        retry = 0
        # Wait for keypad to be ready
        while self._running and (not self._keypad.isReady()) and retry < MAX_INIT_RETRY:
            if retry == 0:
                print(u"Keypad plugin: keypad or button not ready")
            # sleep for a moment and try to reinit
            sleep(5)
            print(u"Keypad plugin: Attempting to reinitialize keypad plugin...")
            if self.init_pins():
                print(u"Keypad plugin: Done")
            else:
                print(u"Keypad plugin: Failed")
            retry += 1
        if retry >= MAX_INIT_RETRY:
            print(u"Keypad plugin: Keypad failure")
            self._set_running(False)
        return self._running

    def _getc(self, down_keys=None, timeout_s=-1):
        """
        Gets next key press from my Keypad
        Inputs: down_keys - Updated to the currently depressed keys on return
                timeout_s - The amount of time in seconds to block before giving up
        """
        c = self._keypad.getc(down_keys=down_keys, timeout_s=timeout_s)
        if len(c) > 0:
            self._ssd1306_wake_signal.send() # Wake the display
        return c

    def _display_function_text(self, append):
        self._ssd1306_display_signal.send(
            activator=u"keypad",
            txt=u"{}:".format(
                KeypadPlugin.FUNCTION_TEXT.get(self.selected_function, u"")
            ),
            row_start=0,
            min_text_size=2,
            max_text_size=2,
            justification=u"CENTER",
            append=append,
            delay=self.keypad_press_timeout_s
        )

    def _display_entry_text(self, command_value, append):
        self._display_function_text(append=append)
        value = "".join(command_value)
        self._ssd1306_display_signal.send(
            activator=u"keypad",
            txt=u"{}".format(value),
            row_start=4,
            min_text_size=4,
            max_text_size=4,
            justification=u"CENTER",
            append=True, # This must be appended since write handled in _display_function_text
            delay=self.keypad_press_timeout_s
        )

    def _display_hold_function(self, hold_function):
        if hold_function in KeypadPlugin.HOLD_FUNCTION_TEXT:
            self._ssd1306_display_signal.send(
                activator=u"keypad",
                txt=u"Hold Fn:",
                row_start=0,
                min_text_size=2,
                max_text_size=2,
                justification=u"CENTER",
                append=False,
                delay=2
            )
            self._ssd1306_display_signal.send(
                activator=u"keypad",
                txt=u"{}".format(
                    KeypadPlugin.HOLD_FUNCTION_TEXT.get(hold_function, u"")
                ),
                row_start=4,
                min_text_size=2,
                max_text_size=2,
                justification=u"CENTER",
                append=True,
                delay=2
            )

    def _display_cancel(self):
        self._ssd1306_display_signal.send(activator=u"keypad", cancel=True)

    def _set_value_function(self, function_key):
        """
        Set the selected (momentary press) function
        """
        if (
            function_key in self.selectable_functions
            and self.selectable_functions[function_key] != KeypadPlugin.FN_NONE
        ):
            self.selected_function = self.selectable_functions[function_key]
            self._function_selected = True
            # Display null entry so far
            self._display_entry_text([], append=False)
            return True
        return False

    def _execute_hold_function(self, function_key):
        """
        Executes a hold function (when a function key is held down)
        """
        hold_function = KeypadPlugin.HLDFN_NONE
        if function_key in self.hold_functions:
            hold_function = self.hold_functions[function_key]
        self._display_hold_function(hold_function)
        if hold_function == KeypadPlugin.HLDFN_STOP_ALL:
            # Stop all stations
            print(u"Keypad plugin: Stop all stations")
            stop_stations()
            return KeypadPlugin.EXECUTE_COMPLETE
        elif hold_function == KeypadPlugin.HLDFN_ACTIVATE_RAIN_DELAY:
            # Activate rain delay
            print(u"Keypad plugin: Activating rain delay for %d hours" % self.rain_delay_hrs)
            gv.sd["rd"] = self.rain_delay_hrs
            gv.sd["rdst"] = int(gv.now + gv.sd["rd"] * 3600)
            stop_onrain()
            return KeypadPlugin.EXECUTE_COMPLETE
        elif hold_function == KeypadPlugin.HLDFN_DEACTIVATE_RAIN_DELAY:
            # Deactivate rain delay
            print(u"Keypad plugin: Deactivating rain delay")
            gv.sd["rd"] = 0
            gv.sd["rdst"] = 0
            jsave(gv.sd, "sd")
            return KeypadPlugin.EXECUTE_COMPLETE
        elif hold_function == KeypadPlugin.HLDFN_SYSTEM_ON:
            # Enable system
            print(u"Keypad plugin: Enabling system")
            gv.sd["en"] = 1
            return KeypadPlugin.EXECUTE_COMPLETE
        elif hold_function == KeypadPlugin.HLDFN_SYSTEM_OFF:
            # Disable system
            print(u"Keypad plugin: Disabling system")
            gv.sd["en"] = 0
            return KeypadPlugin.EXECUTE_COMPLETE
        elif hold_function == KeypadPlugin.HLDFN_RESTART_SYSTEM:
            # Restart system
            print(u"Keypad plugin: Restarting system")
            # Beep now because we won't get a chance to later
            self._buzzer_signal.send(self.hold_function_executed_beep)
            restart()
            return KeypadPlugin.EXECUTE_COMPLETE
        elif hold_function == KeypadPlugin.HLDFN_REBOOT_OS:
            # Reboot operating system
            print(u"Keypad plugin: Rebooting system")
            # Beep now because we won't get a chance to later
            self._buzzer_signal.send(self.hold_function_executed_beep)
            reboot()
            return KeypadPlugin.EXECUTE_COMPLETE
        elif hold_function == KeypadPlugin.HLDFN_RESET_WATER_LEVEL:
            # Reset water level to 100%
            print(u"Keypad plugin: Resetting water level to 100%")
            KeypadPlugin._set_water_level(100)
            return KeypadPlugin.EXECUTE_COMPLETE
        elif hold_function == KeypadPlugin.HLDFN_TOGGLE_RAIN_DELAY:
            if gv.sd["rd"] > 0:
                # Deactivate rain delay
                print(u"Keypad plugin: Deactivating rain delay")
                gv.sd["rd"] = 0
                gv.sd["rdst"] = 0
                jsave(gv.sd, "sd")
                return KeypadPlugin.EXECUTE_TOGGLE_OFF
            else:
                # Activate rain delay
                print(u"Keypad plugin: Activating rain delay for %d hours" % self.rain_delay_hrs)
                gv.sd["rd"] = self.rain_delay_hrs
                gv.sd["rdst"] = int(gv.now + gv.sd["rd"] * 3600)
                stop_onrain()
                return KeypadPlugin.EXECUTE_TOGGLE_ON
        elif hold_function == KeypadPlugin.HLDFN_TOGGLE_SYSTEM_EN:
            if gv.sd["en"]:
                # Disable system
                print(u"Keypad plugin: Disabling system")
                gv.sd["en"] = 0
                return KeypadPlugin.EXECUTE_TOGGLE_OFF
            else:
                # Enable system
                print(u"Keypad plugin: Enabling system")
                gv.sd["en"] = 1
                return KeypadPlugin.EXECUTE_TOGGLE_ON
        else:
            print(u"Keypad plugin: Hold function not implemented")
            return KeypadPlugin.EXECUTE_FAILED

    def _execute_value_function(self, command_value):
        """
        Executes the value function for the given value
        """
        value = -1
        # Parse value
        try:
            value = int("".join(command_value))
        except ValueError:
            value = -1
        # If function set to manual station or none, run manual station
        if (
            self.selected_function == KeypadPlugin.FN_MANUAL_STATION
            or self.selected_function == KeypadPlugin.FN_NONE
        ):
            if gv.sd["rd"] > 0:
                print(u"Keypad plugin: Deactivating rain delay")
                gv.sd["rd"] = 0
                gv.sd["rdst"] = 0
                jsave(gv.sd, "sd")
            stationID = value
            # Start station and provide feedback
            return stationID >= 0 and KeypadPlugin._set_runonce_station(
                stationID, self.keypad_manual_station_time_s
            )
        elif self.selected_function == KeypadPlugin.FN_MANUAL_PROGRAM:
            programID = value
            # Execute program and provide feedback
            return programID >= 0 and KeypadPlugin._set_runonce_program(programID)
        elif self.selected_function == KeypadPlugin.FN_WATER_LEVEL:
            water_level = value
            return water_level >= 0 and KeypadPlugin._set_water_level(water_level)
        elif self.selected_function == KeypadPlugin.FN_MANUAL_STATION_TIME:
            manual_station_time = value * 60
            return manual_station_time > 0 and self._set_manual_station_time(
                manual_station_time
            )
        elif self.selected_function == KeypadPlugin.FN_RAIN_DELAY_TIME:
            rain_delay_time = value
            return rain_delay_time > 0 and self._set_rain_delay_time(rain_delay_time)
        elif self.selected_function == KeypadPlugin.FN_START_RAIN_DELAY:
            # Actvate rain delay
            print(u"Keypad plugin: Activating rain delay for %d hours" % value)
            gv.sd["rd"] = value
            if gv.sd["rd"] > 0:
                gv.sd["rdst"] = int(gv.now + gv.sd["rd"] * 3600)
            else:
                gv.sd["rdst"] = 0
            stop_onrain()
            return True
        else:
            print(u"Keypad plugin: Keypad function not implemented")
            return False

    def _function_key_down(self, function_key):
        if (
            function_key in self.hold_functions
            and self.hold_functions[function_key] != KeypadPlugin.HLDFN_NONE
        ) or (
            function_key in self.selectable_functions
            and self.selectable_functions[function_key] != KeypadPlugin.FN_NONE
        ):
            # This key has either a value function or a hold function!
            self._buzzer_signal.send(self.button_pressed_beep)  # Acknowledge press
            use_hold_fn = False
            if (
                function_key in self.hold_functions
                and self.hold_functions[function_key] != KeypadPlugin.HLDFN_NONE
            ):
                # There is a hold function assigned to this key; wait for up before deciding what to do
                if (
                    self._keypad.wait_for_key_char_up(
                        function_key, self.key_hold_time_s, self._running
                    )
                    >= self.key_hold_time_s
                ):
                    # Key was held at least hold time; select the hold function
                    use_hold_fn = True
            if use_hold_fn:
                # execute hold function
                executionValue = self._execute_hold_function(function_key)
                if executionValue == KeypadPlugin.EXECUTE_COMPLETE:
                    # Executed
                    self._buzzer_signal.send(self.hold_function_executed_beep)
                elif executionValue == KeypadPlugin.EXECUTE_TOGGLE_ON:
                    # Toggle On
                    self._buzzer_signal.send(self.hold_function_toggle_on_beep)
                elif executionValue == KeypadPlugin.EXECUTE_TOGGLE_OFF:
                    # Toggle Off
                    self._buzzer_signal.send(self.hold_function_toggle_off_beep)
                else:
                    # Something else
                    self._buzzer_signal.send(self.error_beep)
            else:
                # Set value function
                if not self._set_value_function(function_key):
                    self._buzzer_signal.send(self.error_beep)
        else:
            print(u"Keypad plugin: Nothing assigned to this key")
            self._buzzer_signal.send(self.error_beep)

    def _handle_value(self, first_key_down, down_keys):
        # copy first button(s) pressed
        function_value = []
        if first_key_down is not None:
            function_value = list(first_key_down)
        # Only append this first value (not clear) if a function key was selected (not default)
        self._display_entry_text(function_value, append=self._function_selected)
        if len(function_value) > 0:
            self._buzzer_signal.send(self.button_pressed_beep)  # Acknowledge first press
        while self._running:
            # wait for up to timeout value for next key
            c = self._getc(down_keys, self.keypad_press_timeout_s)
            if c is None:
                # There was an error; go to top of loop to wait for ready
                return False
            elif len(c) == 0:
                # Timeout occurred with no command
                self._buzzer_signal.send(self.error_beep)  # Nack for timeout
                function_value = []
                self._display_cancel()
                break
            elif KeypadPlugin.ENTER_KEY in c:
                # Execute command
                if self._execute_value_function(function_value):
                    self._buzzer_signal.send(
                        self.acknowledge_command_beep
                    )  # Acknowledge execution
                else:
                    self._buzzer_signal.send(
                        self.error_beep
                    )  # Nack for invalid station or exception
                function_value = []
                self._display_cancel()
                # reset selected function to default
                self._reset_selected_function()
                break
            elif KeypadPlugin.CANCEL_KEY in c:
                # Canceled
                self._buzzer_signal.send(self.cancel_beep)  # Nack for canceled
                function_value = []
                self._display_cancel()
                break
            elif len(function_value) + len(c) > KeypadPlugin.MAX_NUMBER_ENTRY:
                # Too many numbers entered
                print(u"Keypad plugin: Entered value is too large! Canceling...")
                self._buzzer_signal.send(self.error_beep)  # Error
                function_value = []
                self._display_cancel()
                break
            else:
                valid_key = True
                for v in c:
                    if (
                        v not in KeypadPlugin.NUMBER_KEYS
                    ):  # Only number keys are valid here
                        # invlaid key!
                        valid_key = False
                        break
                if valid_key:
                    # Only save number and sound buzzer if function selected
                    if self.selected_function != KeypadPlugin.FN_NONE:
                        self._buzzer_signal.send(
                            self.button_pressed_beep
                        )  # Acknowledge press
                        # append pressed key(s)
                        for v in c:
                            function_value.append(v)
                        self._display_entry_text(function_value, append=True)
                else:
                    # Invalid key
                    print(u"Keypad plugin: Invalid key! Canceling...")
                    self._buzzer_signal.send(self.error_beep)
                    function_value = []
                    self._display_cancel()
                    break
        return True

    def _get_first_function_key(self, c):
        function_key = None
        for v in c:
            if v in KeypadPlugin.FUNCTION_KEYS:
                function_key = v
                break
        return function_key

    def _reset_selected_function(self):
        self.selected_function = self.default_function
        self._function_selected = False

    def _keypad_plugin_task(self):
        # Load settings from file
        keypad_plugin.load_keypad_settings()
        # set selected function to default
        self._reset_selected_function()
        while self._running:
            # Wait for hardware
            if not self._wait_for_ready():
                break
            #
            down_keys = []
            # First button press
            if self._function_selected:
                # User has selected a function; wait up until timeout for next key
                c = self._getc(down_keys, self.keypad_press_timeout_s)
                if len(c) == 0:
                    # Timeout with nothing entered
                    self._reset_selected_function()
                    self._buzzer_signal.send(self.error_beep)
                    self._display_cancel()
                    continue
            else:
                # Wait indefinitely for key
                c = self._getc(down_keys, -1)
            if c is None or len(c) == 0:
                # There was an error; go to top of loop to wait for ready
                continue
            elif KeypadPlugin.CANCEL_KEY in c:
                # Cancel received
                # buzz for cancel, reset, and go to next iteration
                self._buzzer_signal.send(self.cancel_beep)
                self._reset_selected_function()
                self._display_cancel()
            elif KeypadPlugin.ENTER_KEY in c:
                # No function or value with enter key pressed
                # Just give press acknowledgement
                self._buzzer_signal.send(self.button_pressed_beep)
            else:
                # Check if function key was pressed
                function_key = self._get_first_function_key(c)
                if function_key is not None:
                    self._function_key_down(function_key)
                else:
                    # Check if number key is pressed
                    hasNumberKey = False
                    for v in c:
                        if v in KeypadPlugin.NUMBER_KEYS:
                            hasNumberKey = True
                            break
                    # handle value if not number or selected function is not none
                    if (not hasNumberKey) or (
                        self.selected_function != KeypadPlugin.FN_NONE
                    ):
                        self._handle_value(c, down_keys)
                    self._reset_selected_function()
        print(u"Keypad plugin: Exiting keypad task")
        return

    def run(self):
        """
        Starts the Keypad thread
        """
        if self._running and self._running_thread is not None:
            print(u"Keypad plugin: Run called when already running")
        elif not self.init_pins():
            print(u"Keypad plugin: Could not start keypad plugin: GPIO pins init failed")
        else:
            self._set_running(True)
            self._running_thread = Thread(target=keypad_plugin._keypad_plugin_task)
            self._running_thread.start()
        return self._running

    def stop(self):
        """
        Stops the keypad thread
        Returns True if successfully stopped; False otherwise
        """
        if self._running_thread is not None:
            self._set_running(False)
            self._running_thread.join(0.5)
            if not self._running_thread.is_alive():
                self._running_thread = None
        return (self._running_thread is None)

    @staticmethod
    def __button_list_to_string(l):
        return ", ".join(str(e) for e in [int(x * 1000) for x in l])

    @staticmethod
    def __string_to_button_list(s):
        strlist = s.split(",")
        flist = []
        total_time = 0
        for x in strlist:
            try:
                value = int(x) / 1000.0
                # single value cannot be more than 1 second
                if value > 1:
                    value = 1
                # total time cannot be more than 3 seconds
                total_time += value
                if total_time > 3:
                    break
                flist.append(value)
            except ValueError:
                # do nothing
                pass
        return flist

    def load_from_dict(self, settings):
        self._set_default_settings()
        if settings is None:
            return
        if "mstationtime" in settings:
            self.keypad_manual_station_time_s = float(settings["mstationtime"]) * 60
        if "keytimeout" in settings:
            self.keypad_press_timeout_s = float(settings["keytimeout"])
        if "hrraindelay" in settings:
            self.rain_delay_hrs = float(settings["hrraindelay"])
        if "keyholdtime" in settings:
            self.key_hold_time_s = float(settings["keyholdtime"])
        if (
            "akeyfn" in settings
            and "bkeyfn" in settings
            and "ckeyfn" in settings
            and "dkeyfn" in settings
        ):
            self.selectable_functions = {
                "A": int(settings["akeyfn"]),
                "B": int(settings["bkeyfn"]),
                "C": int(settings["ckeyfn"]),
                "D": int(settings["dkeyfn"]),
            }
        if (
            "aholdfn" in settings
            and "bholdfn" in settings
            and "choldfn" in settings
            and "dholdfn" in settings
        ):
            self.hold_functions = {
                "A": int(settings["aholdfn"]),
                "B": int(settings["bholdfn"]),
                "C": int(settings["choldfn"]),
                "D": int(settings["dholdfn"]),
            }
        if "defaultfn" in settings:
            self.default_function = int(settings["defaultfn"])
            self._reset_selected_function()
        if "acknowledge_command_beep" in settings:
            self.acknowledge_command_beep = KeypadPlugin.__string_to_button_list(
                settings["acknowledge_command_beep"]
            )
        if "cancel_beep" in settings:
            self.cancel_beep = KeypadPlugin.__string_to_button_list(
                settings["cancel_beep"]
            )
        if "error_beep" in settings:
            self.error_beep = KeypadPlugin.__string_to_button_list(
                settings["error_beep"]
            )
        if "hold_function_executed_beep" in settings:
            self.hold_function_executed_beep = KeypadPlugin.__string_to_button_list(
                settings["hold_function_executed_beep"]
            )
        if "hold_function_toggle_on_beep" in settings:
            self.hold_function_toggle_on_beep = KeypadPlugin.__string_to_button_list(
                settings["hold_function_toggle_on_beep"]
            )
        if "hold_function_toggle_off_beep" in settings:
            self.hold_function_toggle_off_beep = KeypadPlugin.__string_to_button_list(
                settings["hold_function_toggle_off_beep"]
            )
        return

    def load_keypad_settings(self):
        # Get settings
        try:
            with open("./data/keypad.json", "r") as f:
                self.load_from_dict(json.load(f))
        except:
            self._set_default_settings()
        return

    def save_keypad_settings(self):
        settings = {
            "mstationtime": float_to_field_str(self.keypad_manual_station_time_s / 60),
            "keytimeout": float_to_field_str(self.keypad_press_timeout_s),
            "hrraindelay": float_to_field_str(self.rain_delay_hrs),
            "keyholdtime": float_to_field_str(self.key_hold_time_s),
            "akeyfn": str(self.selectable_functions["A"]),
            "bkeyfn": str(self.selectable_functions["B"]),
            "ckeyfn": str(self.selectable_functions["C"]),
            "dkeyfn": str(self.selectable_functions["D"]),
            "aholdfn": str(self.hold_functions["A"]),
            "bholdfn": str(self.hold_functions["B"]),
            "choldfn": str(self.hold_functions["C"]),
            "dholdfn": str(self.hold_functions["D"]),
            "defaultfn": str(self.default_function),
            "acknowledge_command_beep": KeypadPlugin.__button_list_to_string(
                self.acknowledge_command_beep
            ),
            "cancel_beep": KeypadPlugin.__button_list_to_string(self.cancel_beep),
            "error_beep": KeypadPlugin.__button_list_to_string(self.error_beep),
            "hold_function_executed_beep": KeypadPlugin.__button_list_to_string(
                self.hold_function_executed_beep
            ),
            "hold_function_toggle_on_beep": KeypadPlugin.__button_list_to_string(
                self.hold_function_toggle_on_beep
            ),
            "hold_function_toggle_off_beep": KeypadPlugin.__button_list_to_string(
                self.hold_function_toggle_off_beep
            ),
        }
        with open("./data/keypad.json", "w") as f:
            json.dump(settings, f)  # save to file
        return

    ### Restart ###
    # Restart signal needs to be handled in 1 second or less
    def notify_restart(self, name, **kw):
        print(u"Keypad plugin: Received restart signal; stopping keypad task...")
        if self.stop():
            print(u"Keypad plugin: Keypad task stopped")
        else:
            print(u"Keypad plugin: Could not stop keypad task")


# Keypad plugin object
keypad_plugin = KeypadPlugin()


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open(
                "./data/keypad.json", "r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = {}  # Default settings. can be list, dictionary, etc.
        return template_render.keypad(settings)  # open settings page


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
        keypad_plugin.load_from_dict(qdict)  # load settings from dictionary
        keypad_plugin.save_keypad_settings()  # Save keypad settings
        raise web.seeother("/")  # Return user to home page.


# Attach to restart signal
restart_signal = signal("restart")
restart_signal.connect(keypad_plugin.notify_restart)

#  Run when plugin is loaded
keypad_plugin.run()
