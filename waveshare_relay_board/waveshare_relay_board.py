#!/usr/bin/env python

# standard library imports
import json
import time

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings, gv = global variables
from sip import template_render
from urls import urls  # Get access to SIP's URLs
import web
from webpages import ProtectedPage

gv.use_gpio_pins = False  # Signal SIP to not use GPIO pins

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

# Add a new url to open the data entry page.
# fmt: off
urls.extend(
    [
        "/wrb", "plugins.waveshare_relay_board.settings",
        "/wrbu", "plugins.waveshare_relay_board.update",
    ]
)
# fmt: on

# Add this plugin to the home page plugins menu
gv.plugin_menu.append([_("Waveshare Relay Board"), "/wrb"])

params = {}

# Read in the parameters for this plugin from it's JSON file
def load_params():
    global params
    try:
        with open("./data/waveshare_relay_board.json", "r") as f:  # Read the settings from file
            params = json.load(f)
    except IOError:  #  If file does not exist create file with defaults.
        params = {"relays": 8, "active": "low"}
        with open("./data/waveshare_relay_board.json", "w") as f:
            json.dump(params, f, indent=4, sort_keys=True)

load_params()

#### define the GPIO pins that will be used ####
try:
    if gv.platform == "pi":  # If this will run on Raspberry Pi:
        if not gv.use_pigpio:
            GPIO.setmode(
                GPIO.BOARD
            )  # IO channels are identified by header connector pin numbers. Pin numbers are
        relay_pins = [
            29,  # GPIO 5 relay 1
            31,  # GPIO 6 relay 2
            33,  # GPIO 13 relay 3
            36,  # GPIO 16 relay 4
            35,  # GPIO 19 relay 5
            38,  # GPIO 20 relay 6
            40,  # GPIO 21 relay 7
            37,  # GPIO 26 relay 8          
            11,  # GPIO 17 relay 9
            12,  # GPIO 18 relay 10
            13,  # GPIO 27 relay 11
            15,  # GPIO 22 relay 12
            16,  # GPIO 23 relay 13
            18,  # GPIO 24 relayl 14
            22,  # GPIO 25 relay 15
            26,  # GPIO 7 relay 16
        ]
        for i in range(len(relay_pins)):
            try:
                relay_pins[i] = gv.pin_map[relay_pins[i]]
            except:
                relay_pins[i] = 0
    else:
        print("relay board plugin only supported on pi.")
except:
    print("Relay board: GPIO pins not set")
    pass


#### setup GPIO pins as output and high ####
def init_pins():
    global pi

    try:
        for i in range(params["relays"]):
            if gv.use_pigpio:
                pi.set_mode(relay_pins[i], pigpio.OUTPUT)
                pi.write(relay_pins[i], 1)
            else:
                GPIO.setup(relay_pins[i], GPIO.OUT)
                GPIO.output(relay_pins[i], GPIO.HIGH)
            time.sleep(0.1)
    except:
        pass


#### change outputs when blinker signal received ####
def on_zone_change(arg):  #  arg is just a necessary placeholder.
    """ Switch relays when core program signals a change in zone state."""
    global pi
    with gv.output_srvals_lock:
        for i in range(params["relays"]):
            try:
                if gv.output_srvals[i]:  # if station is set to on
                    if gv.use_pigpio:
                        pi.write(relay_pins[i], 0)
                    else:
                        GPIO.output(relay_pins[i], GPIO.LOW)
                else:  # station is set to off
                    if gv.use_pigpio:
                        pi.write(relay_pins[i], 1)
                    else:
                        GPIO.output(relay_pins[i], GPIO.HIGH)
            except Exception as e:
                print("Problem switching relays", e, relay_pins[i])
                pass


init_pins()

zones = signal("zone_change")
zones.connect(on_zone_change)

################################################################################
# Web pages:                                                                   #
################################################################################

class settings(ProtectedPage):
    """Load an html page for entering relay board adjustments"""

    def GET(self):
        with open("./data/waveshare_relay_board.json", "r") as f:  # Read the settings from file
            params = json.load(f)
        return template_render.waveshare_relay_board(params)


class update(ProtectedPage):
    """Save user input to waveshare_relay_board.json file"""

    def GET(self):
        qdict = web.input()
        changed = False
        if params["relays"] != int(qdict["relays"]
        ):  # if the number of relay channels changed, update the params
            params["relays"] = int(qdict["relays"])
            changed = True
        if changed:
            init_pins()
            with open(
                "./data/waveshare_relay_board.json", "w"
            ) as f:  # write the settings to file
                json.dump(params, f, indent=4, sort_keys=True)
        raise web.seeother("/")