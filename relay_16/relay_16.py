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
        u"/rb16", u"plugins.relay_16.settings",
        u"/rbu16", u"plugins.relay_16.update",
    ]
)
# fmt: on

# Add this plugin to the home page plugins menu
gv.plugin_menu.append([u"Relay 16", u"/rb16"])

params = {}

# Read in the parameters for this plugin from it's JSON file
def load_params():
    global params
    try:
        with open(u"./data/relay_16.json", u"r") as f:  # Read the settings from file
            params = json.load(f)
    except IOError:  #  If file does not exist create file with defaults.
        params = {u"enabled": u"off", u"relays": 1, u"active": u"low"}
        with open(u"./data/relay_16.json", u"w") as f:
            json.dump(params, f, indent=4, sort_keys=True)
    return params


load_params()

if params[u"enabled"] == u"on":
    gv.use_gpio_pins = False  # Signal SIP to not use GPIO pins

#### define the GPIO pins that will be used ####
try:
    if gv.platform == u"pi":  # If this will run on Raspberry Pi:
        if not gv.use_pigpio:
            GPIO.setmode(
                GPIO.BOARD
            )  # IO channels are identified by header connector pin numbers. Pin numbers are
        relay_pins = [18, 22, 24, 26, 32, 36, 38, 40, 19, 21, 23, 29, 31, 33, 35, 37]
        for i in range(len(relay_pins)):
            try:
                relay_pins[i] = gv.pin_map[relay_pins[i]]
            except:
                relay_pins[i] = 0
        pin_rain_sense = gv.pin_map[8]
        pin_relay = gv.pin_map[10]
    else:
        print(u"relay_16 plugin only supported on pi.")
except:
    print(u"Relay_16: GPIO pins not set")
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
        with open(u"./data/relay_16.json", u"r") as f:  # Read the settings from file
            params = json.load(f)
        return template_render.relay_16(params)


class update(ProtectedPage):
    """Save user input to relay_16.json file"""

    def GET(self):
        qdict = web.input()
        changed = False
        if params[u"enabled"] != (qdict[u"enabled"]):
            params[u"enabled"] = qdict[u"enabled"]
            changed = True
        if params[u"relays"] != int(
            qdict[u"relays"]
        ):  # if the number of relay channels changed, update the params
            params[u"relays"] = int(qdict[u"relays"])
            changed = True
        if params[u"active"] != str(
            qdict[u"active"]
        ):  # if the number of relay channels changed, update the params
            params[u"active"] = str(qdict[u"active"])
            params[
                u"relays"
            ] = (
                1
            )  # since changing active could turn all the relays on, reduce the relay channels to 1
            changed = True
        if changed:
            init_pins()
            with open(u"./data/relay_16.json", u"w") as f:  # write the settings to file
                json.dump(params, f, indent=4, sort_keys=True)
        raise web.seeother(u"/")
