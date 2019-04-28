# !/usr/bin/env python

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
    if (gv.use_pigpio):
        import pigpio
        pi = pigpio.pi()
    else:
        import RPi.GPIO as GPIO
        pi = 0
except IOError:
    pass

# BUZZER VARIABLES
# Board pin where the buzzer is located (set to -1 to disable)
BUZZER_PIN = 32
# True if buzzer sounds when pin is HIGH; False if buzzer sounds when pin is LOW
BUZZER_ACTIVE_HIGH = True

# Add new URLs to access classes in this plugin.
urls.extend([
    '/buzzer-sp', 'plugins.buzzer.settings',
    '/buzzer-save', 'plugins.buzzer.save_settings'
    ])

# Add this plugin to the PLUGINS menu ['Menu Name', 'URL'], (Optional)
gv.plugin_menu.append(['Buzzer Plugin', '/buzzer-sp'])

# This class handles the buzzer hardware       
class Buzzer(Thread):    
    def __init__(self, pin, active_high):
        Thread.__init__(self)
        # set to true when buzzer pin is initialized
        self.pin_initialized = False
        # Board pin where buzzer is located (-1 to disable)
        self.pin = pin
        # True if buzzer sounds when pin is HIGH; False if buzzer sounds when pin is LOW
        self.active_high = active_high
        self.init_thread = None
        # Set all default settings
        self.__set_default_settings()
        return
        
    def __set_default_settings(self):
        # Beeps
        self.startup_beep = [0.050, 0.050, 0.050, 0.050, 0.050, 0.050, 0.100]
        
    @staticmethod
    def __button_list_to_string(l):
        return ", ".join(str(e) for e in [int(x * 1000) for x in l])
      
    @staticmethod
    def __string_to_button_list(s):
        str_list = s.split(",")
        flist = []
        total_time = 0
        for x in str_list:
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
        if (settings is None):
            return
        if (settings.has_key("startup_beep")):
            self.startup_beep = Buzzer.__string_to_button_list(settings["startup_beep"])
        return
        
    def load_settings(self):
        # Get settings
        try:
            with open('./data/buzzer.json', 'r') as f:
                self.load_from_dict(json.load(f))
        except:
            self.__set_default_settings()
        return
        
    def save_settings(self):
        settings = {
            "startup_beep": Buzzer.__button_list_to_string(self.startup_beep),
        }
        with open('./data/buzzer.json', 'w') as f:
            json.dump(settings, f) # save to file
        return
        
    def isReady(self):
        return (self.pin < 0 or self.pin_initialized)
    
    def init_pins(self):
        try:
            if (self.pin >= 0):
                # Initialize buzzer pin
                if (gv.use_pigpio):
                    pi.set_mode(gv.pin_map[self.pin], pigpio.OUTPUT)
                else:
                    GPIO.setmode(GPIO.BOARD)
                    GPIO.setup(self.pin, GPIO.OUT)
                # Output OFF
                self.__set_buzzer_pin(False)
                # Done!
                self.pin_initialized = True
            else: 
                self.pin_initialized = False
        except:
            self.pin_initialized = False
            return False
        return True
        
    def __set_buzzer_pin(self, is_on):
        pin_value = self.active_high if is_on else not self.active_high
        if (gv.use_pigpio):
            pi.write(gv.pin_map[self.pin], pin_value)
        else:
            GPIO.output(self.pin, pin_value)
        
    # time: Time value(s) in seconds
    #       If single value, on time for buzzer 
    #       If array, time values in the format [on time, off time, on time, ...]
    def buzz(self, time = 0.010):
        try:
            if (self.pin >= 0 and self.pin_initialized and time is not None):
                time_list = []
                if (isinstance(time, list)):
                    time_list = time
                else:
                    time_list.append(time)
                # First value is buzzer on
                buzz_on = True
                # Loop through each time in list
                for v in time_list:
                    # If this value is on time, turn on the buzzer
                    if (buzz_on and v > 0):
                        self.__set_buzzer_pin(True)
                    # Suspend for the given time
                    if (v > 0):
                        sleep(v)
                    # Always shut off buzzer before next iteration
                    self.__set_buzzer_pin(False)
                    # Invert 
                    buzz_on = not buzz_on
        except:
            self.pin_initialized = False
            return False
        return True
        
    def __wait_for_ready(self):
        MAX_INIT_RETRY = 15
        retry = 0
        # First attempt to initialize pins
        self.init_pins()
        # Wait for buzzer to be ready
        while (not self.isReady() and retry < MAX_INIT_RETRY):
            if (retry == 0):
                print "buzzer not ready yet"
            print "Attempting to reinitialize buzzer plugin..."
            #sleep for a moment and try to reinit
            sleep(1)
            if (self.init_pins()):
                print "Done"
            else:
                print "Failed"
            retry+=1
        if (retry >= MAX_INIT_RETRY):
            print "Buzzer failure"
            return False
        return True
        
    def __buzzer_init_task(self):
        # Load settings from file
        self.load_settings()
        # Wait for hardware init
        self.__wait_for_ready()
        # Ring startup beep
        self.buzz(self.startup_beep)
        
    def run(self):
        self.__buzzer_init_task()

buzzer = Buzzer(BUZZER_PIN, BUZZER_ACTIVE_HIGH)

class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open('./data/buzzer.json', 'r') as f:  # Read settings from json file if it exists
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
        qdict = web.input()  # Dictionary of values returned as query string from settings page.
        buzzer.load_from_dict(qdict) # load settings from dictionary
        buzzer.save_settings() # Save keypad settings
        raise web.seeother('/')  # Return user to home page.
        
# Setup buzzer signal notification
def notify_buzzer_beep(time,  **kw):
    return buzzer.buzz(time)
buzzer_beep = signal('buzzer_beep')
buzzer_beep.connect(notify_buzzer_beep)

# Run to get hardware initialized
buzzer.start()