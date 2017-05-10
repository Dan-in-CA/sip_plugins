# !/usr/bin/env python

import time

import gv
from gpio_pins import GPIO, pin_relay
from urls import urls
import web
from webpages import ProtectedPage

if gv.use_pigpio:
    from gpio_pins import pi


urls.extend(['/tr', 'plugins.relay.toggle_relay'])  # Add a new url for this plugin.

gv.plugin_menu.append(['Test Relay', '/tr'])  # Add this plugin to the home page plugins menu


class toggle_relay(ProtectedPage):
    """Test relay by turning it on for a short time, then off."""
    def GET(self):
        global pi
        try:
            if gv.use_pigpio:
                pi.write(pin_relay, 1)  
            else:
                GPIO.output(pin_relay, GPIO.HIGH)  # turn relay on
            time.sleep(3)
            if gv.use_pigpio:
                pi.write(pin_relay, 0)
            else:
                GPIO.output(pin_relay, GPIO.LOW)  # Turn relay off
        except Exception, e:
#            print "Relay plugin error: ", e
            pass
        raise web.seeother('/')  # return to home page