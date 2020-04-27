# !/usr/bin/env python

""" SIP plugin uses mqtt plugin to broadcast station status every time it changes.
__author__ = "Daniel Casner <daniel@danielcasner.org>"
"""


# Python 2/3 compatibility imports
from __future__ import print_function
from six.moves import zip

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

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend(
    [
        u"/zone2mqtt-sp", u"plugins.mqtt_zones.settings",
        u"/zone2mqtt-save", u"plugins.mqtt_zones.save_settings",
    ]
)
# fmt: on
gv.plugin_menu.append([u"MQTT zone broadcaster", u"/zone2mqtt-sp"])


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        settings = mqtt.get_settings()
        zone_topic = settings.get(u"zone_topic", gv.sd[u"name"] + u"/zones")
        return template_render.mqtt_zones(zone_topic, "")  # open settings page


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


### valves ###
def notify_zone_change(name, **kw):
    names = gv.snames
    mas = gv.sd[u"mas"]
    vals = gv.srvals
    payload = {
        u"zone_list": vals,
        u"zone_dict": {name: status for name, status in zip(names, vals)},
        u"master_on": 0 if mas == 0 else vals[mas - 1],
    }  
    zone_topic = mqtt.get_settings().get(u"zone_topic")
    if zone_topic:
        client = mqtt.get_client()
        if client:
            client.publish(zone_topic, json.dumps(payload), qos=1, retain=True)


zones = signal(u"zone_change")
zones.connect(notify_zone_change)
