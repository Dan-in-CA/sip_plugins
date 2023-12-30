#!/usr/bin/env python

# Python 2/3 compatibility imports
from __future__ import print_function
from six.moves import range

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
        u"/wrb", u"plugins.waveshare_relay_board.settings",
        u"/wrbj", u"plugins.waveshare_relay_board.settings_json",
        u"/wrbu", u"plugins.waveshare_relay_board.update",
    ]
)
# fmt: on

# Add this plugin to the home page plugins menu
gv.plugin_menu.append([_(u"Waveshare Relay Board"), u"/wrb"])

params = {}

# Read in the parameters for this plugin from it's JSON file
def load_params():
    global params
    try:
        with open(u"./data/waveshare_relay_board.json", u"r") as f:  # Read the settings from file
            params = json.load(f)
    except IOError:  #  If file does not exist create file with defaults.
        params = {u"relays": 8, u"active": u"low"}
        with open(u"./data/waveshare_relay_board.json", u"w") as f:
            json.dump(params, f, indent=4, sort_keys=True)
    return params


load_params()

#### define the GPIO pins that will be used ####
try:
    if gv.platform == u"pi":  # If this will run on Raspberry Pi:
        if not gv.use_pigpio:
            GPIO.setmode(
                GPIO.BOARD
            )  # IO channels are identified by header connector pin numbers. Pin numbers are
        relay_pins = [
            29,
            31,
            33,
            36,
            35,
            38,
            40,
            37,
            3,
            5,
            24,
            26,
            11,
            12,
            13,
            15,
            16,
            18,
            22,
            7,
        ]
        for i in range(len(relay_pins)):
            try:
                relay_pins[i] = gv.pin_map[relay_pins[i]]
            except:
                relay_pins[i] = 0
        pin_rain_sense = gv.pin_map[8]
        pin_relay = gv.pin_map[10]
    else:
        print(u"relay board plugin only supported on pi.")
except:
    print(u"Relay board: GPIO pins not set")
    pass


#### setup GPIO pins as output and either high or low ####
def init_pins():
    global pi

    try:
        for i in range(params[u"relays"]):
            if gv.use_pigpio:
                pi.set_mode(relay_pins[i], pigpio.OUTPUT)
            else:
                GPIO.setup(relay_pins[i], GPIO.OUT)
            if params[u"active"] == u"low":
                if gv.use_pigpio:
                    pi.write(relay_pins[i], 1)
                else:
                    GPIO.output(relay_pins[i], GPIO.HIGH)
            else:
                if gv.use_pigpio:
                    pi.write(relay_pins[i], 0)
                else:
                    GPIO.output(relay_pins[i], GPIO.LOW)
            time.sleep(0.1)
    except:
        pass


#### change outputs when blinker signal received ####
def on_zone_change(arg):  #  arg is just a necessary placeholder.
    """ Switch relays when core program signals a change in zone state."""

    global pi

    with gv.output_srvals_lock:
        for i in range(params[u"relays"]):
            try:
                if gv.output_srvals[i]:  # if station is set to on
                    if (
                        params[u"active"] == u"low"
                    ):  # if the relay type is active low, set the output low
                        if gv.use_pigpio:
                            pi.write(relay_pins[i], 0)
                        else:
                            GPIO.output(relay_pins[i], GPIO.LOW)
                    else:  # otherwise set it high
                        if gv.use_pigpio:
                            pi.write(relay_pins[i], 1)
                        else:
                            GPIO.output(relay_pins[i], GPIO.HIGH)
                else:  # station is set to off
                    if (
                        params[u"active"] == u"low"
                    ):  # if the relay type is active low, set the output high
                        if gv.use_pigpio:
                            pi.write(relay_pins[i], 1)
                        else:
                            GPIO.output(relay_pins[i], GPIO.HIGH)
                    else:  # otherwise set it low
                        if gv.use_pigpio:
                            pi.write(relay_pins[i], 0)
                        else:
                            GPIO.output(relay_pins[i], GPIO.LOW)
            #                    print 'relay switched off', i + 1, "pin", relay_pins[i]  #  for testing ############
            except Exception as e:
                print(u"Problem switching relays", e, relay_pins[i])
                pass


init_pins()

zones = signal(u"zone_change")
zones.connect(on_zone_change)

################################################################################
# Web pages:                                                                   #
################################################################################


class settings(ProtectedPage):
    """Load an html page for entering relay board adjustments"""

    def GET(self):
        with open(u"./data/waveshare_relay_board.json", u"r") as f:  # Read the settings from file
            params = json.load(f)
        return template_render.waveshare_relay_board(params)


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format"""

    def GET(self):
        web.header(u"Access-Control-Allow-Origin", u"*")
        web.header(u"Content-Type", u"application/json")
        return json.dumps(params)


class update(ProtectedPage):
    """Save user input to waveshare_relay_board.json file"""

    def GET(self):
        qdict = web.input()
        changed = False
        if params[u"relays"] != int(
            qdict[u"relays"]
        ):  # if the number of relay channels changed, update the params
            params[u"relays"] = int(qdict[u"relays"])
            changed = True
        if params[u"active"] != str(
            qdict[u"active"]
        ):  # if active low/high changed, update the params
            params[u"active"] = str(qdict[u"active"])
            params[
                u"relays"
            ] = (
                1
            )  # since changing active could turn all the relays on, reduce the relay channels to 1
            changed = True
        if changed:
            init_pins()
            with open(
                u"./data/waveshare_relay_board.json", u"w"
            ) as f:  # write the settings to file
                json.dump(params, f, indent=4, sort_keys=True)
        raise web.seeother(u"/")