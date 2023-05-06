# !/usr/bin/env python

""" SIP plugin uses mqtt plugin to send values every time they change.
__author__ = "Modified from mqtt_zones originally written by Daniel Casner"
"""


# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
import json  # for working with data file

# local module imports
from blinker import signal  # To receive station notifications
import gv  # Get access to SIP's settings
from plugins import mqtt
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from helpers import get_cpu_temp

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend(
    [
        u"/mqtt_get_values-sp", u"plugins.mqtt_get_values.settings",
        u"/mqtt_get_values-save", u"plugins.mqtt_get_values.save_settings",
    ]
)
# fmt: on
gv.plugin_menu.append([$_(u"MQTT Get Values Plugin"), u"/mqtt_get_values-sp"])


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        settings = mqtt.get_settings()
        get_values_topic = settings.get(u"get_values_topic", gv.sd[u"name"] + u"/get_values")
        return template_render.mqtt_get_values(get_values_topic, "")  # open settings page


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
        settings = mqtt.get_settings()
        settings.update(qdict)
        with open(mqtt.DATA_FILE, u"w") as f:
            json.dump(settings, f, indent=4, sort_keys=True)  # save to file
        raise web.seeother(u"/")  # Return user to home page.


### System settings ###
def notify_value_change(name, **kw):
    payload = {
        u"devt": gv.now,
        u"nbrd": gv.sd[u"nbrd"],
        u"en": gv.sd[u"en"],
        u"rd": gv.sd[u"rd"],
        u"rs": gv.sd[u"rs"],
        u"mm": gv.sd[u"mm"],
        u"rdst": gv.sd[u"rdst"],
        u"loc": gv.sd[u"loc"],
        u"wl": gv.sd[u"wl"],
        u"sbits": gv.sbits,
        u"ps": gv.ps,
        u"lrun": gv.lrun,
        u"ct": get_cpu_temp(),
        u"tu": gv.sd[u"tu"]
    }
    # for plugin compatibility read all water level adjustment settings (wl_*)
    for entry in gv.sd:
        if entry.startswith(u"wl_"):
            payload[entry] = gv.sd[entry]

    get_values_topic = mqtt.get_settings().get(u"get_values_topic")
    if get_values_topic:
        client = mqtt.get_client()
        if client:
            client.publish(get_values_topic, json.dumps(payload), qos=1, retain=True)


value = signal(u"value_change")
value.connect(notify_value_change)
