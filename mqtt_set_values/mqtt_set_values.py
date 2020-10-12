# !/usr/bin/env python

""" SIP plugin uses mqtt plugin to set SIP values over MQTT
__author__ = "Modified from mqtt_schedule originally written by Daniel Casner"
"""

# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
import json  # for working with data file

# local module imports
from blinker import signal  # To receive station notifications
import gv  # Get access to SIP's settings
from helpers import stop_onrain, stop_stations
from plugins import mqtt
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import (
    ProtectedPage, # Needed for security
    report_value_change,
)

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend(
    [
        u"/mqtt_set_values-sp", u"plugins.mqtt_set_values.settings",
        u"/mqtt_set_values-save", u"plugins.mqtt_set_values.save_settings",
    ]
)
# fmt: on
gv.plugin_menu.append([u"MQTT Set Values Plugin", u"/mqtt_set_values-sp"])


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        settings = mqtt.get_settings()
        set_values_topic = settings.get(u"set_values_topic", gv.sd[u"name"] + u"/set_values")
        return template_render.mqtt_set_values(set_values_topic, "")  # open settings page


class save_settings(ProtectedPage):
    """Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):
        qdict = (
            web.input()
        )  # Dictionary of values returned as query string from settings page.
        settings = mqtt.get_settings()
        settings.update(qdict)
        with open(mqtt.DATA_FILE, u"w") as f:
            json.dump(settings, f, indent=4, sort_keys=True)  # save to file
        subscribe()
        raise web.seeother(u"/")  # Return user to home page.


def on_message(client, msg):
    """Callback when MQTT message is received."""
    try:
        values = json.loads(msg.payload)
    except ValueError as e:
        print(u"MQTT Values could not decode command: ", msg.payload, e)
        return
    # Rain Delay
    if 'rd' in values:
        gv.sd['rd'] = float(values['rd'])
        gv.sd['rdst'] = gv.now + gv.sd['rd'] * 3600 + 1  # +1 adds a smidge just so after a round trip the display hasn't already counted down by a minute.
        if float(gv.sd['rd']) > .0:
            stop_onrain()
        report_value_change()
    # Water level
    if 'wl' in values:
        gv.sd['wl'] = float(values['wl'])
        report_value_change()
    # Manual mode
    if 'mm' in values:
        gv.sd['mm'] = int(values['mm'])
        report_value_change()
    # Enable
    if 'en' in values:
        gv.sd['en'] = int(values['en'])
        report_value_change()
    # Reset (stop) all stations
    if 'rsn' in values:
        gv.sd['rsn'] = int(values['rsn'])
        stop_stations()
        report_value_change()
    return


def subscribe():
    """
    Subscribe to messages
    """
    topic = mqtt.get_settings().get(u"set_values_topic")
    if topic:
        mqtt.subscribe(topic, on_message, 2)


subscribe()
