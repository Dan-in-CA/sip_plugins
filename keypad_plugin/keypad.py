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
        pi = 0
except IOError:
    pass

# KEYPAD VARIABLES
# Keypad column pins
KEYPAD_PIN_COLUMNS = [
    29, # C1
    31, # C2
    33, # C3
    35, # C4
]
# Keypad row pins
KEYPAD_PIN_ROWS = [
    37, # R1
    40, # R2
    38, # R3
    36, # R4
]
# Maps keypad key to index
KEYPAD_INDICIES = [    
#    C1  C2  C3  C4
    [ 1,  2,  3, 10], # R1
    [ 4,  5,  6, 11], # R2
    [ 7,  8,  9, 12], # R3
    [14,  0, 15, 13]  # R4
]
# Maps keypad index to character
KEYPAD_KEY_LIST = [
    '0',
    '1',
    '2',
    '3',
    '4',
    '5',
    '6',
    '7',
    '8',
    '9',
    'A',
    'B',
    'C',
    'D',
    '*',
    '#'
]

# Add new URLs to access classes in this plugin.
urls.extend([
    '/keypad-sp', 'plugins.keypad.settings',
    '/keypad-save', 'plugins.keypad.save_settings'
    ])

# Add this plugin to the PLUGINS menu ['Menu Name', 'URL'], (Optional)
gv.plugin_menu.append(['Keypad Plugin', '/keypad-sp'])

# This class handles the keypad hardware
class ScanningKeypad:    
    def __init__(self, pin_columns, pin_rows, indicies, char_list):
        self.pin_columns = pin_columns
        self.pin_rows = pin_rows
        self.indicies = indicies
        self.char_list = char_list
        # Current energized column
        self.keypad_current_column = -1
        # set to true after keypad pins are first initialized; set to false on exception
        self.pins_initialized = False
        return
        
    def isReady(self):
        return self.pins_initialized

    @staticmethod
    def __set_floating_input(pin):
        if gv.use_pigpio:
            pi.set_mode(gv.pin_map[pin], pigpio.INPUT)
            pi.set_pull_up_down(gv.pin_map[pin], pigpio.PUD_OFF)
        else:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
        
    def __set_column(self, col):
        if (not self.pins_initialized):
            return False
        try:
            if (self.keypad_current_column >= 0):
                # Set old value as floating input so it won't affect anyone else
                ScanningKeypad.__set_floating_input(self.keypad_current_column)
            # set current pin and make output HIGH
            self.keypad_current_column = col
            if gv.use_pigpio:
                pi.set_mode(gv.pin_map[self.keypad_current_column], pigpio.OUTPUT)
                pi.write(gv.pin_map[self.keypad_current_column], 1)
            else:
                GPIO.setup(self.keypad_current_column, GPIO.OUT)
                GPIO.output(self.keypad_current_column, GPIO.HIGH)
        except Exception, err:
            print "keypad plugin except"
            print(traceback.format_exc())
            self.pins_initialized = False
        return self.pins_initialized
    
    def init_pins(self):
        try:
            if not gv.use_pigpio:
                GPIO.setmode(GPIO.BOARD)
            # set column pins as floating to start with
            for v in self.pin_columns:
                ScanningKeypad.__set_floating_input(v)
            self.keypad_current_column = -1
            # row pins will be used as input with pull down resistors
            for v in self.pin_rows:
                if gv.use_pigpio:
                    pi.set_mode(gv.pin_map[v], pigpio.INPUT)
                    pi.set_pull_up_down(gv.pin_map[v], pigpio.PUD_DOWN)
                else:
                    GPIO.setup(v, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            self.pins_initialized = True
        except Exception, err:
            print "keypad plugin except"
            print(traceback.format_exc())
            self.pins_initialized = False
        return self.pins_initialized
    
    def sample(self):
        keys = [False] * len(self.char_list)
        for col, col_v in enumerate(self.pin_columns):
            if self.__set_column(col_v):
                sleep(0.001) # just to make sure the output is fully charged
                try:
                    for row, row_v in enumerate(self.pin_rows):
                        if gv.use_pigpio:
                            keys[self.indicies[row][col]] = (pi.read(gv.pin_map[row_v]))
                        else:
                            keys[self.indicies[row][col]] = (GPIO.input(row_v))
                except Exception, err:
                    print "keypad plugin except"
                    print(traceback.format_exc())
                    self.pins_initialized = False
            else:
                keys = [False] * len(self.char_list)
                break
        return keys
    
    def wait_for_any_key(self):
        c = self.sample()
        while (True not in c):
            sleep(0.01)
            c = self.sample()
        return
    
    def getc(self, down_keys = None, timeout_s = -1, running = True):
        "Gets next key press"
        # Get starting time
        start_time = time.time()
        # Get initial sample
        last = keys = self.sample()
        c = []
        while (running and self.pins_initialized):
            # Check for error
            if (keys is None):
                return None     # There was a fatal error
            # Add any new keys to c
            for i, v in enumerate(self.char_list):
                if (last[i] != keys[i] and keys[i]):
                    c.append(v)
            # If any new keys have been added, we are done
            if (len(c) > 0):
                break
            # Check for timeout
            current_time = time.time()
            if (timeout_s > 0 and (current_time - start_time) >= timeout_s):
                break   # Timeout occurred
            sleep(0.025) # Check for change every 25 ms so we don't bog anything down. This also serves as a debounce
            # Next sample
            last = keys
            keys = self.sample()
        # Copy keys to down_keys
        if (down_keys is not None and len(down_keys) >= len(self.char_list) and keys is not None):
            for i in range(0,len(self.char_list)):
                down_keys[i] = keys[i]
        return c
        
    def wait_for_key_index_up(self, key_index, timeout_s = -1, running = True):
        if (key_index >= 0 and key_index < len(self.char_list)):
            timeout_reached = False
            # Get starting time
            start_time = time.time()
            while (running and self.pins_initialized and not timeout_reached):
                keys = self.sample()
                current_time = time.time()
                # Check to see if the selected key is up
                if (not keys[key_index]):
                    return current_time - start_time
                # Check for timeout
                elif (timeout_s > 0 and (current_time - start_time) >= timeout_s):
                    return current_time - start_time   # Timeout occurred
                sleep(0.025) # sleep for a moment before trying again
            return -1 # we are not running or pins aren't initialized
        else:
            return -1 # invalid index
    
    def wait_for_key_char_up(self, key_char, timeout_s = -1, running = True):
        key_index = -1
        for i, c in enumerate(self.char_list):
            if (c == key_char):
                key_index = i
                break
        return self.wait_for_key_index_up(key_index, timeout_s, running)
        
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
    # Execution enumeration
    EXECUTE_FAILED = 0
    EXECUTE_COMPLETE = 1
    EXECUTE_TOGGLE_ON = 2
    EXECUTE_TOGGLE_OFF = 3
    
    # Types of keys
    FUNCTION_KEYS = ['A', 'B', 'C', 'D']
    NUMBER_KEYS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
    ENTER_KEY = '#'
    CANCEL_KEY = '*'
    
    # Allow up to 9999 station/program
    MAX_NUMBER_ENTRY = 4
    
    def __init__(self):
        # Keypad object to get key presses
        self.keypad = ScanningKeypad(KEYPAD_PIN_COLUMNS, KEYPAD_PIN_ROWS, KEYPAD_INDICIES, KEYPAD_KEY_LIST)
        # Buzzer signal for feedback
        self.buzzerSignal = signal('buzzer_beep')
        
        # Set all default settings
        self.__set_default_settings()
        # Currently selected function
        self.__reset_selected_function()
        
        # Set to True when running and False to exit task
        self.running = False
        # Handle to the running thread for this plugin
        self.running_thread = None
        
        # Set to True when function is selected by user
        self.function_selected = False
        return
    
    def __set_default_settings(self):
        # settings
        self.keypad_press_timeout_s = 5
        self.keypad_manual_station_time_s = 300
        self.rain_delay_hrs = 24
        self.key_hold_time_s = 1
        self.selectable_functions = {
            'A': KeypadPlugin.FN_MANUAL_STATION, 
            'B': KeypadPlugin.FN_MANUAL_PROGRAM,
            'C': KeypadPlugin.FN_WATER_LEVEL,
            'D': KeypadPlugin.FN_MANUAL_STATION_TIME,
        }
        self.hold_functions = {
            'A': KeypadPlugin.HLDFN_NONE,
            'B': KeypadPlugin.HLDFN_NONE,
            'C': KeypadPlugin.HLDFN_NONE,
            'D': KeypadPlugin.HLDFN_NONE,
        }
        # Default function 
        self.default_function = KeypadPlugin.FN_MANUAL_STATION
        
        # Beeps
        self.acknowledge_command_beep = 0.100
        self.cancel_beep = [0.100, 0.100, 0.500] 
        self.hold_function_executed_beep = [0.100, 0.050, 0.100]
        self.hold_function_toggle_on_beep = [0.050, 0.050, 0.200]
        self.hold_function_toggle_off_beep = [0.200, 0.050, 0.050]
        self.button_pressed_beep = 0.025
    
    def init_pins(self):
        return (self.keypad.init_pins())

    # This function is based on change_runonce class in webpages.py
    @staticmethod
    def __set_runonce_station(stationID, seconds = 300):
        """Runs a single station for a given number of seconds. This will override any running program."""
        found = False
        stop_all_first = False
        newrovals = []
        for i in range(gv.sd['nst']):
            if i == (stationID - 1):
                found = True
                newrovals.append(seconds)
            else:
                newrovals.append(0)
        run_schedule = False
        if found:
            print "Running station %d for %d seconds." % (stationID, seconds)
            run_schedule = True
        elif stationID == 0:
            print "Stopping all stations."
            run_schedule = True
        else:
            print "Station %d not found. Ignoring entry." % stationID
            run_schedule = False
        if run_schedule:
            gv.rovals = newrovals
            stations = [0] * gv.sd['nbrd']
            gv.ps = []  # program schedule (for display)
            gv.rs = []  # run schedule
            for i in range(gv.sd['nst']):
                gv.ps.append([0, 0])
                gv.rs.append([0, 0, 0, 0])
            for i, v in enumerate(gv.rovals):
                if v: # if this element has a value
                    gv.rs[i][0] = gv.now + 3
                    gv.rs[i][2] = v
                    gv.rs[i][3] = 98
                    gv.ps[i][0] = 98
                    gv.ps[i][1] = v
                    stations[i / 8] += 2 ** (i % 8)

            schedule_stations(stations)
        return run_schedule
        
    # This function is based on run_now class in webpages.py
    @staticmethod
    def __set_runonce_program(programID):
        """Run a scheduled program now. This will override any running programs."""
        
        if (programID == 0):
            print "Stopping all stations."
            stop_stations()
            return True
        pid = programID - 1
        if len(gv.pd) <= pid:
            print "Invalid program: %d" % programID
            return False
        else:
            p = gv.pd[int(pid)]  # program data
            stop_stations()
            extra_adjustment = plugin_adjustment()
            sid = -1
            for b in range(gv.sd['nbrd']):  # check each station
                for s in range(8):
                    sid += 1  # station index
                    if sid + 1 == gv.sd['mas']:  # skip if this is master valve
                        continue
                    if p[7 + b] & 1 << s:  # if this station is scheduled in this program
                        if gv.sd['idd']:
                            duration = p[-1][sid]
                        else:
                            duration = p[6]
                        if not gv.sd['iw'][b] & 1 << s:
                            duration = duration * gv.sd['wl'] / 100 * extra_adjustment
                        gv.rs[sid][2] = duration
                        gv.rs[sid][3] = pid + 1  # store program number in schedule
                        gv.ps[sid][0] = pid + 1  # store program number for display
                        gv.ps[sid][1] = duration  # duration
            print "Running program #%d" % programID
            schedule_stations(p[7:7 + gv.sd['nbrd']])
            return True
    
    @staticmethod
    def __set_water_level(level):
        print "Set water level for %d%%" % level
        if level >= 0:
            gv.sd['wl'] = level
            return True
        return False
        
    def __set_manual_station_time(self, time):
        print "Set manual station time for %d seconds" % time
        self.keypad_manual_station_time_s = time
        self.save_keypad_settings()
        return True
        
    def __set_rain_delay_time(self, time):
        print "Set rain delay for %d hours" % time
        self.rain_delay_hrs = time
        self.save_keypad_settings()
        return True
        
    def __wait_for_ready(self):
        if (not self.running):
            return False
        MAX_INIT_RETRY = 3
        retry = 0
        # Wait for keypad to be ready
        while (self.running and (not self.keypad.isReady()) and retry < MAX_INIT_RETRY):
            if (retry == 0):
                print "keypad or button not ready"
            #sleep for a moment and try to reinit
            sleep(5)
            print "Attempting to reinitialize keypad plugin..."
            if (self.init_pins()):
                print "Done"
            else:
                print "Failed"
            retry+=1
        if (retry >= MAX_INIT_RETRY):
            print "Keypad failure"
            self.running = False
        return self.running
        
    def __set_value_function(self, function_key):
        if (self.selectable_functions.has_key(function_key) and self.selectable_functions[function_key] != KeypadPlugin.FN_NONE):
            self.selected_function = self.selectable_functions[function_key]
            self.function_selected = True
            return True
        return False
        
    def __execute_hold_function(self, function_key):
        hold_function = KeypadPlugin.HLDFN_NONE
        if (self.hold_functions.has_key(function_key)):
            hold_function = self.hold_functions[function_key]
        if (hold_function == KeypadPlugin.HLDFN_STOP_ALL):
            # Stop all stations
            print "Stop all stations"
            stop_stations()
            return KeypadPlugin.EXECUTE_COMPLETE
        elif (hold_function == KeypadPlugin.HLDFN_ACTIVATE_RAIN_DELAY):
            # Activate rain delay
            print "Activating rain delay for %d hours" % self.rain_delay_hrs
            gv.sd['rd'] = self.rain_delay_hrs
            gv.sd['rdst'] = int(gv.now + gv.sd['rd'] * 3600) 
            stop_onrain()
            return KeypadPlugin.EXECUTE_COMPLETE
        elif (hold_function == KeypadPlugin.HLDFN_DEACTIVATE_RAIN_DELAY):
            # Deactivate rain delay
            print "Deactivating rain delay"
            gv.sd['rd'] = 0
            gv.sd['rdst'] = 0
            jsave(gv.sd, 'sd')
            return KeypadPlugin.EXECUTE_COMPLETE
        elif (hold_function == KeypadPlugin.HLDFN_SYSTEM_ON):
            # Enable system
            print "Enabling system"
            gv.sd['en'] = 1
            return KeypadPlugin.EXECUTE_COMPLETE
        elif (hold_function == KeypadPlugin.HLDFN_SYSTEM_OFF):
            # Disable system
            print "Disabling system"
            gv.sd['en'] = 0
            return KeypadPlugin.EXECUTE_COMPLETE
        elif (hold_function == KeypadPlugin.HLDFN_RESTART_SYSTEM):
            # Restart system
            print "Restarting system"
            # Beep now because we won't get a chance to later
            self.buzzerSignal.send(self.hold_function_executed_beep)
            restart()
            return KeypadPlugin.EXECUTE_COMPLETE
        elif (hold_function == KeypadPlugin.HLDFN_REBOOT_OS):
            # Reboot operating system
            print "Rebooting system"
            # Beep now because we won't get a chance to later
            self.buzzerSignal.send(self.hold_function_executed_beep)
            reboot()
            return KeypadPlugin.EXECUTE_COMPLETE
        elif (hold_function == KeypadPlugin.HLDFN_RESET_WATER_LEVEL):
            # Reset water level to 100%
            print "Resetting water level to 100%"
            KeypadPlugin.__set_water_level(100)
            return KeypadPlugin.EXECUTE_COMPLETE
        elif (hold_function == KeypadPlugin.HLDFN_TOGGLE_RAIN_DELAY):
            if( gv.sd['rd'] > 0 ):
                # Deactivate rain delay
                print "Deactivating rain delay"
                gv.sd['rd'] = 0
                gv.sd['rdst'] = 0
                jsave(gv.sd, 'sd')
                return KeypadPlugin.EXECUTE_TOGGLE_OFF
            else:
                # Activate rain delay
                print "Activating rain delay for %d hours" % self.rain_delay_hrs
                gv.sd['rd'] = self.rain_delay_hrs
                gv.sd['rdst'] = int(gv.now + gv.sd['rd'] * 3600) 
                stop_onrain()
                return KeypadPlugin.EXECUTE_TOGGLE_ON
        elif (hold_function == KeypadPlugin.HLDFN_TOGGLE_SYSTEM_EN):
            if( gv.sd['en'] ):
                # Disable system
                print "Disabling system"
                gv.sd['en'] = 0
                return KeypadPlugin.EXECUTE_TOGGLE_OFF
            else:
                # Enable system
                print "Enabling system"
                gv.sd['en'] = 1
                return KeypadPlugin.EXECUTE_TOGGLE_ON
        else:
            print "Hold function not implemented"
            return KeypadPlugin.EXECUTE_FAILED
        
    def __execute_value_function(self, command_value):
        value = -1
        # Parse value
        try:
            value = int("".join(command_value))
        except ValueError:
            value = -1
        # If function set to manual station or none, run manual station
        if (self.selected_function == KeypadPlugin.FN_MANUAL_STATION or self.selected_function == KeypadPlugin.FN_NONE):
            if( gv.sd['rd'] > 0 ):
                print "Deactivating rain delay"
                gv.sd['rd'] = 0
                gv.sd['rdst'] = 0
                jsave(gv.sd, 'sd')
            stationID = value
            # Start station and provide feedback
            return stationID >= 0 and KeypadPlugin.__set_runonce_station(stationID, self.keypad_manual_station_time_s)
        elif (self.selected_function == KeypadPlugin.FN_MANUAL_PROGRAM):
            programID = value
            # Execute program and provide feedback
            return programID >= 0 and KeypadPlugin.__set_runonce_program(programID)
        elif (self.selected_function == KeypadPlugin.FN_WATER_LEVEL):
            water_level = value
            return water_level >= 0 and KeypadPlugin.__set_water_level(water_level)
        elif (self.selected_function == KeypadPlugin.FN_MANUAL_STATION_TIME):
            manual_station_time = value * 60
            return manual_station_time > 0 and self.__set_manual_station_time(manual_station_time)
        elif (self.selected_function == KeypadPlugin.FN_RAIN_DELAY_TIME):
            rain_delay_time = value
            return rain_delay_time > 0 and self.__set_rain_delay_time(rain_delay_time)
        elif( self.selected_function == KeypadPlugin.FN_START_RAIN_DELAY ):
            # Actvate rain delay
            print "Activating rain delay for %d hours" % value
            gv.sd['rd'] = value
            if gv.sd['rd'] > 0:
                gv.sd['rdst'] = int(gv.now + gv.sd['rd'] * 3600) 
            else:
                gv.sd['rdst'] = 0
            stop_onrain()
            return True 
        else:
            print "Keypad function not implemented"
            return False
            
    def __function_key_down(self, function_key):
        if (self.hold_functions.has_key(function_key) and self.hold_functions[function_key] != KeypadPlugin.HLDFN_NONE) or \
                (self.selectable_functions.has_key(function_key) and self.selectable_functions[function_key] != KeypadPlugin.FN_NONE):
            # This key has either a value function or a hold function!
            self.buzzerSignal.send(self.button_pressed_beep) # Acknowledge press
            use_hold_fn = False
            if self.hold_functions.has_key(function_key) and self.hold_functions[function_key] != KeypadPlugin.HLDFN_NONE:
                # There is a hold function assinged to this key; wait for up before deciding what to do
                if self.keypad.wait_for_key_char_up(function_key, self.key_hold_time_s, self.running) >= self.key_hold_time_s:
                    # Key was held at least hold time; select the hold function
                    use_hold_fn = True
            if use_hold_fn:
                # execute hold function
                executionValue = self.__execute_hold_function(function_key)
                if executionValue == KeypadPlugin.EXECUTE_COMPLETE:
                    # Executed
                    self.buzzerSignal.send(self.hold_function_executed_beep)
                elif executionValue == KeypadPlugin.EXECUTE_TOGGLE_ON:
                    # Toggle On
                    self.buzzerSignal.send(self.hold_function_toggle_on_beep)
                elif executionValue == KeypadPlugin.EXECUTE_TOGGLE_OFF:
                    # Toggle Off
                    self.buzzerSignal.send(self.hold_function_toggle_off_beep)
                else:
                    self.buzzerSignal.send(self.cancel_beep)
            else:
                # Set value function
                if not self.__set_value_function(function_key):
                    self.buzzerSignal.send(self.cancel_beep)
        else:
            print "Nothing assigned to this key"
            self.buzzerSignal.send(self.cancel_beep)
            
    def __handle_value(self, first_key_down, down_keys):
        # copy first button(s) pressed
        function_value = []
        if first_key_down is not None:
            function_value = list(first_key_down)
        if (len(function_value) > 0):
            self.buzzerSignal.send(self.button_pressed_beep) # Acknowledge first press
        while (self.running):
            # wait for up to timeout value for next key
            c = self.keypad.getc(down_keys, self.keypad_press_timeout_s, self.running) 
            if (c is None):
                # There was an error; go to top of loop to wait for ready
                return False
            elif (len(c) == 0):
                # Timeout occurred with no command
                self.buzzerSignal.send(self.cancel_beep) # Nack for timeout
                function_value = []
                break
            elif (KeypadPlugin.ENTER_KEY in c):
                # Execute command
                if self.__execute_value_function(function_value):
                    self.buzzerSignal.send(self.acknowledge_command_beep) # Acknowledge execution
                else:
                    self.buzzerSignal.send(self.cancel_beep) # Nack for invalid station or exception
                function_value = []
                # reset selected function to default
                self.__reset_selected_function()
                break
            elif (KeypadPlugin.CANCEL_KEY in c):
                # Canceled
                self.buzzerSignal.send(self.cancel_beep) # Nack for canceled
                function_value = []
                break;
            elif (len(function_value) + len(c) > KeypadPlugin.MAX_NUMBER_ENTRY):
                # Too many numbers entered
                print "Entered value is too large! Canceling..."
                self.buzzerSignal.send(self.cancel_beep) # Error
                function_value = []
                break
            else:
                valid_key = True
                for v in c:
                    if v not in KeypadPlugin.NUMBER_KEYS: # Only number keys are valid here
                        # invlaid key!
                        valid_key = False
                        break
                if valid_key:
                    # Only save number and sound buzzer if function selected
                    if self.selected_function != KeypadPlugin.FN_NONE:
                        self.buzzerSignal.send(self.button_pressed_beep) # Acknowledge press
                        # append pressed key(s)
                        for v in c:
                            function_value.append(v)
                else:
                    # Invalid key
                    print "Invalid key! Canceling..."
                    self.buzzerSignal.send(self.cancel_beep)
                    function_value = []
                    break
        return True
        
    def __get_first_function_key(self, c):
        function_key = None
        for v in c:
            if v in KeypadPlugin.FUNCTION_KEYS:
                function_key = v
                break
        return function_key
        
    def __reset_selected_function(self):
        self.selected_function = self.default_function
        self.function_selected = False
    
    def __keypad_plugin_task(self):
        # Load settings from file
        keypad_plugin.load_keypad_settings()
        # set selected function to default
        self.__reset_selected_function()
        while (self.running):
            # Wait for hardware
            if (not self.__wait_for_ready()):
                break
            #
            function_value = []
            down_keys = []
            # First button press
            if (self.function_selected):
                # User has selected a function; wait up until timeout for next key
                c = self.keypad.getc(down_keys, self.keypad_press_timeout_s, self.running)
                if (len(c) == 0):
                    # Timeout with nothing entered
                    self.__reset_selected_function()
                    self.buzzerSignal.send(self.cancel_beep)
                    continue
            else:
                # Wait indefinitely for key
                c = self.keypad.getc(down_keys, -1, self.running)
            if (c is None or len(c) == 0):
                # There was an error; go to top of loop to wait for ready
                continue
            elif (KeypadPlugin.ENTER_KEY in c or KeypadPlugin.CANCEL_KEY in c):
                # No command or cancel received
                # buzz for cancel, reset, and go to next iteration
                self.buzzerSignal.send(self.cancel_beep) # Nack for no command or cancel
                function_value = []
            else:
                # Check if function key was pressed
                function_key = self.__get_first_function_key(c)
                if function_key is not None:
                    self.__function_key_down(function_key)
                    # Reset command and go to next iteration
                    function_value = []
                else:
                    # Check if number key is pressed
                    hasNumberKey = False
                    for v in c:
                        if v in KeypadPlugin.NUMBER_KEYS:
                            hasNumberKey = True
                            break
                    # handle value if not number or selected function is not none
                    if ( not hasNumberKey ) or ( self.selected_function != KeypadPlugin.FN_NONE ):
                        self.__handle_value(c, down_keys)
        print "Exiting keypad task"
        return
    
    def run(self):
        if (self.running and self.running_thread is not None):
            print "Keypad plugin is already running"
        elif (not keypad_plugin.init_pins()):
            print "Could not start keypad plugin: GPIO pins init failed"
        else:
            self.running = True
            self.running_thread = Thread(target = keypad_plugin.__keypad_plugin_task)
            self.running_thread.start()
        return self.running
    
    def stop(self):
        stopped = False
        if (self.running_thread is not None):
            self.running = False
            stopped = self.running_thread.join(0.5)
            if stopped:
                self.running_thread = None
        else:
            stopped = True
        return stopped
     
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
                value = (int(x) / 1000.0)
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
        self.__set_default_settings()
        if settings is None:
            return
        if settings.has_key("mstationtime"):
            self.keypad_manual_station_time_s = int(settings["mstationtime"]) * 60
        if settings.has_key("keytimeout"):
            self.keypad_press_timeout_s = int(settings["keytimeout"])
        if settings.has_key("hrraindelay"):
            self.rain_delay_hrs = int(settings["hrraindelay"])
        if settings.has_key("keyholdtime"):
            self.key_hold_time_s = int(settings["keyholdtime"])
        if settings.has_key("akeyfn") and settings.has_key("bkeyfn") and settings.has_key("ckeyfn") and settings.has_key("dkeyfn"):
            self.selectable_functions = {
                'A': int(settings["akeyfn"]), 
                'B': int(settings["bkeyfn"]),
                'C': int(settings["ckeyfn"]),
                'D': int(settings["dkeyfn"]),
            }
        if settings.has_key("aholdfn") and settings.has_key("bholdfn") and settings.has_key("choldfn") and settings.has_key("dholdfn"):
            self.hold_functions = {
                'A': int(settings["aholdfn"]),
                'B': int(settings["bholdfn"]),
                'C': int(settings["choldfn"]),
                'D': int(settings["dholdfn"]),
            }
        if settings.has_key("defaultfn"):
            self.default_function = int(settings["defaultfn"])
            self.__reset_selected_function()
        if settings.has_key("acknowledge_command_beep"):
            self.acknowledge_command_beep = KeypadPlugin.__string_to_button_list(settings["acknowledge_command_beep"])
        if settings.has_key("cancel_beep"):
            self.cancel_beep = KeypadPlugin.__string_to_button_list(settings["cancel_beep"])
        if settings.has_key("hold_function_executed_beep"):
            self.hold_function_executed_beep = KeypadPlugin.__string_to_button_list(settings["hold_function_executed_beep"])
        if settings.has_key("hold_function_toggle_on_beep"):
            self.hold_function_toggle_on_beep = KeypadPlugin.__string_to_button_list(settings["hold_function_toggle_on_beep"])
        if settings.has_key("hold_function_toggle_off_beep"):
            self.hold_function_toggle_off_beep = KeypadPlugin.__string_to_button_list(settings["hold_function_toggle_off_beep"])
        return
    
    def load_keypad_settings(self):
        # Get settings
        try:
            with open('./data/keypad.json', 'r') as f:
                self.load_from_dict(json.load(f))
        except:
            self.__set_default_settings()
        return
        
    def save_keypad_settings(self):
        settings = {
            "mstationtime": str(self.keypad_manual_station_time_s / 60),
            "keytimeout": str(self.keypad_press_timeout_s),
            "hrraindelay": str(self.rain_delay_hrs),
            "keyholdtime": str(self.key_hold_time_s),
            "akeyfn": str(self.selectable_functions['A']),
            "bkeyfn": str(self.selectable_functions['B']),
            "ckeyfn": str(self.selectable_functions['C']),
            "dkeyfn": str(self.selectable_functions['D']),
            "aholdfn": str(self.hold_functions['A']),
            "bholdfn": str(self.hold_functions['B']),
            "choldfn": str(self.hold_functions['C']),
            "dholdfn": str(self.hold_functions['D']),
            "defaultfn": str(self.default_function),
            "acknowledge_command_beep": KeypadPlugin.__button_list_to_string(self.acknowledge_command_beep),
            "cancel_beep": KeypadPlugin.__button_list_to_string(self.cancel_beep),
            "hold_function_executed_beep": KeypadPlugin.__button_list_to_string(self.hold_function_executed_beep),
            "hold_function_toggle_on_beep": KeypadPlugin.__button_list_to_string(self.hold_function_toggle_on_beep),
            "hold_function_toggle_off_beep": KeypadPlugin.__button_list_to_string(self.hold_function_toggle_off_beep),
        }
        with open('./data/keypad.json', 'w') as f:
            json.dump(settings, f) # save to file
        return
    
    ### Restart ###
    # Restart signal needs to be handled in 1 second or less
    def notify_restart(self, name, **kw):
        print "Keypad plugin received restart signal; stopping keypad task..."
        if self.stop():
            print "Keypad task stopped"
        else:
            print "Could not stop keypad task"

# Keypad plugin object
keypad_plugin = KeypadPlugin()
        
class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open('./data/keypad.json', 'r') as f:  # Read settings from json file if it exists
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
        qdict = web.input()  # Dictionary of values returned as query string from settings page.
        keypad_plugin.load_from_dict(qdict) # load settings from dictionary
        keypad_plugin.save_keypad_settings() # Save keypad settings
        raise web.seeother('/')  # Return user to home page.


# Attach to restart signal
restart = signal('restart')
restart.connect(keypad_plugin.notify_restart)

#  Run when plugin is loaded
keypad_plugin.run()
