from __future__ import print_function

# !/usr/bin/env python

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
from threading import Thread, Timer, BoundedSemaphore, RLock, Condition

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

# BUZZER VARIABLES
# Board pin where the buzzer is located (set to -1 to disable)
BUZZER_PIN = 32
# True if buzzer sounds when pin is HIGH; False if buzzer sounds when pin is LOW
BUZZER_ACTIVE_HIGH = True

# Add new URLs to access classes in this plugin.
urls.extend(
    [
        u"/buzzer-sp", u"plugins.buzzer.settings",
        u"/buzzer-save", u"plugins.buzzer.save_settings",
    ]
)

# Add this plugin to the PLUGINS menu ['Menu Name', 'URL'], (Optional)
gv.plugin_menu.append([_(u"Buzzer Plugin"), u"/buzzer-sp"])

class Buzzer(Thread):
    """
    This class handles the buzzer hardware
    """
    def __init__(self, pin, active_high):
        """
        Initializes a Buzzer object
        Inputs: pin - The hardware pin the buzzer is connected to
        """
        Thread.__init__(self)
        # set to true when buzzer pin is initialized
        self.pin_initialized = False
        # Board pin where buzzer is located (-1 to disable)
        self.pin = pin
        # True if buzzer sounds when pin is HIGH; False if buzzer sounds when pin is LOW
        self.active_high = active_high
        # Set all default settings
        self._set_default_settings()
        # Used in buzz thread
        self._current_buzz_list = []
        self._buzz_sem = BoundedSemaphore(1)
        self._buzz_sem.acquire()
        self._buzz_cancel = False
        self._buzz_data_lock = RLock()
        self._buzz_condition = Condition()
        # Running flag just to ensure that we stop buzzing when shutting down
        self._running = True

    def _set_default_settings(self):
        """
        Sets the json settings to their defaults
        """
        self.startup_beep = [0.050, 0.050, 0.050, 0.050, 0.050, 0.050, 0.100]

    @staticmethod
    def _beep_list_to_string(l):
        """
        Returns the string representation of the given beep list
        """
        return ", ".join(str(e * 1000) for e in l)

    @staticmethod
    def _string_to_beep_list(s):
        """
        Returns the beep list for the given string representation
        """
        str_list = s.split(",")
        beep_list = []
        total_time = 0
        for x in str_list:
            try:
                value = int(x) / 1000.0
                # single value cannot be more than 5 seconds
                if value > 5:
                    value = 5
                # total time cannot be more than 10 seconds
                total_time += value
                if total_time > 10:
                    break
                beep_list.append(value)
            except ValueError:
                # do nothing
                pass
        return beep_list

    def load_from_dict(self, settings):
        """
        Loads settings from a given dictionary
        """
        self._set_default_settings()
        if settings is None:
            return
        if u"startup_beep" in settings:
            self.startup_beep = Buzzer._string_to_beep_list(settings["startup_beep"])
        return

    def _load_settings(self):
        """
        Loads settings from the settings json file for this plugin
        """
        # Get settings
        try:
            with open(u"./data/buzzer.json", u"r") as f:
                self.load_from_dict(json.load(f))
        except:
            self._set_default_settings()
        return

    def save_settings(self):
        """
        Saves these settings to the json file for this plugin
        """
        settings = {u"startup_beep": Buzzer._beep_list_to_string(self.startup_beep)}
        with open(u"./data/buzzer.json", u"w") as f:
            json.dump(settings, f)  # save to file
        return

    def is_ready(self):
        """
        Returns True if the hardware is ready; False otherwise
        """
        return self.pin < 0 or self.pin_initialized

    def _init_pins(self):
        """
        Initializes the buzzer pins in the selected IO library
        """
        try:
            if self.pin >= 0:
                # Initialize buzzer pin
                if gv.use_pigpio:
                    pi.set_mode(gv.pin_map[self.pin], pigpio.OUTPUT)
                else:
                    GPIO.setmode(GPIO.BOARD)
                    GPIO.setup(self.pin, GPIO.OUT)
                # Output OFF
                self._set_buzzer_pin(False)
                # Done!
                self.pin_initialized = True
            else:
                self.pin_initialized = False
        except:
            self.pin_initialized = False
            return False
        return True

    def _set_buzzer_pin(self, is_on, force=False):
        """
        Sets the state of the buzzer pin to ON or OFF
        Inputs: is_on - True for ON; False for OFF
                force - True to force OFF, even when not running
        """
        if self._running or force:
            try:
                pin_value = self.active_high if is_on else not self.active_high
                if gv.use_pigpio:
                    pi.write(gv.pin_map[self.pin], pin_value)
                else:
                    GPIO.output(self.pin, pin_value)
            except Exception as e:
                self.pin_initialized = False
                print(u"Buzzer plugin: set failed:\n{}".format(e))
                return False

    def _execute_buzz(self, time_list):
        """
        Execute buzzer sequence (blocking)
        Inputs: time_list - Time values in seconds in the format [on time, off time, on time, ...]
        """
        # First value is buzzer on
        buzz_on = True
        # Loop through each time in list
        for v in time_list:
            if not self._running or self._buzz_cancel:
                break
            # If this value is on time, turn on the buzzer
            if buzz_on and v > 0:
                self._set_buzzer_pin(True)
            # Suspend for the given time
            if v > 0:
                self._buzz_condition.acquire()
                self._buzz_condition.wait(v)
                self._buzz_condition.release()
            # Always shut off buzzer before next iteration
            self._set_buzzer_pin(False)
            # Invert
            buzz_on = not buzz_on

    def buzz(self, time=0.010):
        """
        Activate the buzzer for the given time (non-blocking)
        Inputs: time - Time value(s) in seconds
                If single value, on time for buzzer
                If array, time values in the format [on time, off time, on time, ...]
        Returns: True always
        """
        if self.pin >= 0 and self.pin_initialized and time is not None:
            # Generate the list of times
            if isinstance(time, list):
                time_list = time
            else:
                time_list = [time]
            self._buzz_data_lock.acquire()
            # Spin off an execute thread so this call is non-blocking
            self._current_buzz_list = time_list
            self._buzz_cancel = True # To cancel current buzz
            self._buzz_condition.acquire()
            self._buzz_condition.notify_all()
            self._buzz_condition.release()
            self._buzz_data_lock.release()
            try:
                self._buzz_sem.release()
            except ValueError:
                # This is fine; something else already released it
                pass
        return True

    def _wait_for_ready(self):
        """
        Waits up to 15 seconds for hardware to be ready
        Returns: True if hardware is ready; False if timeout occurred
        """
        MAX_INIT_RETRY = 15
        retry = 0
        # First attempt to initialize pins
        self._init_pins()
        # Wait for buzzer to be ready
        while not self.is_ready() and retry < MAX_INIT_RETRY:
            if retry == 0:
                print(u"Buzzer plugin: Waiting for buzzer hardware to be ready")
            print(u"Buzzer plugin: Attempting to reinitialize buzzer plugin...")
            # sleep for a moment and try to reinit
            sleep(1)
            if self._init_pins():
                print(u"Buzzer plugin: Done")
            else:
                print(u"Buzzer plugin: Failed")
            retry += 1
        if retry >= MAX_INIT_RETRY:
            print(u"Buzzer plugin: Hardware failure")
            return False
        return True

    def _buzzer_init_task(self):
        """
        Performs all of the initialization tasks
        """
        # Load settings from file
        self._load_settings()
        # Wait for hardware init
        self._wait_for_ready()
        # Ring startup beep
        self.buzz(self.startup_beep)

    def run(self):
        """
        Main execution method which is executed when the super class (Thread) is started
        """
        self._buzzer_init_task()
        while self._running:
            self._buzz_sem.acquire()
            self._buzz_data_lock.acquire()
            buzz_list = self._current_buzz_list
            self._buzz_cancel = False
            self._buzz_data_lock.release()
            if self._running:
                self._execute_buzz(buzz_list)

    ### Restart ###
    # Restart signal needs to be handled in 1 second or less
    def notify_restart(self, name, **kw):
        # Make sure whatever timers running don't turn the buzzer on as we are restarting
        self._running = False
        self._set_buzzer_pin(is_on=False, force=True)
        # Release the thread
        try:
            self._buzz_sem.release()
        except ValueError:
            # This is fine; something else already released it
            pass


# Our main Buzzer object for this module
buzzer = Buzzer(BUZZER_PIN, BUZZER_ACTIVE_HIGH)

# Setup buzzer signal notification
def notify_buzzer_beep(time, **kw):
    return buzzer.buzz(time)

# Tell the notification system what to call on buzzer_beep
buzzer_beep = signal(u"buzzer_beep")
buzzer_beep.connect(notify_buzzer_beep)

# Attach to restart signal
restart = signal("restart")
restart.connect(buzzer.notify_restart)

# Run to get hardware initialized
buzzer.start()

################################################################################
# Web pages:                                                                   #
################################################################################

class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open(
                u"./data/buzzer.json", u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = {}  # Default settings. can be list, dictionary, etc.
        return template_render.buzzer(settings)  # open settings page


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
        buzzer.load_from_dict(qdict)  # load settings from dictionary
        buzzer.save_settings()  # Save keypad settings
        raise web.seeother(u"/")  # Return user to home page.