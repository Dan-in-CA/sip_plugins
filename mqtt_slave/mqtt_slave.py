# !/usr/bin/env python

""" SIP plugin uses mqtt plugin to receive station status data over MQTT and control local stations
__author__ = "Orginally written by Daniel Casner <daniel@danielcasner.org> Modified from mqtt_schedule by Dan K."
"""


# Python 2/3 compatibility imports
from __future__ import print_function
from six.moves import range

# standard library imports
import json  # for working with data file
from time import sleep

# local module imports
import gv  # Get access to SIP's settings
from plugins import mqtt
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security

DATA_FILE = "./data/mqtt.json"

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend(
    [
        u"/mr2-sp", u"plugins.mqtt_slave.settings",
        u"/mr2-save", u"plugins.mqtt_slave.save_settings",
    ]
)
# fmt: on
gv.plugin_menu.append([u"MQTT slave", u"/mr2-sp"])


class settings(ProtectedPage):
    """Load an html page for entering plugin settings.
    """

    def GET(self):
        settings = mqtt.get_settings()
        settings[u"control_topic"] = ""
        settings[u"first_station"] = ""
        settings[u"station_count"] = ""
        return template_render.mqtt_slave(settings, "")  # open settings page


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
        with open(DATA_FILE, u"w") as f:
            json.dump(settings, f, indent=4, sort_keys=True)  # save to file
        subscribe()
        raise web.seeother(u"/")  # Return user to home page.


def on_message(client, msg):
    "Callback when MQTT message is received."
    if not gv.sd[u"en"]:  # check operation status
        return

    num_brds = gv.sd[u"nbrd"]
    num_sta = num_brds * 8
    try:
        cmd = json.loads(msg.payload)
    except ValueError as e:
        print(u"MQTT Slave could not decode command: ", msg.payload, e)
        return

    zones = cmd["zone_list"]  #  list of all zones sent from master
    first = int(mqtt.get_settings().get(u"first_station")) - 1
    count = int(mqtt.get_settings().get(u"station_count"))
    local_zones = zones[first : first + count]
    for i in range(len(local_zones)):
        if (
            local_zones[i]  # if this element has a value and is not on
            and not gv.srvals[i]
        ):
            gv.rs[i][0] = gv.now
            gv.rs[i][1] = float("inf")
            gv.rs[i][3] = 99
            gv.ps[i][0] = 99
        elif gv.srvals[i] and not local_zones[i]:
            gv.rs[i][1] = gv.now
    if any(gv.rs):
        gv.sd[u"bsy"] = 1
    sleep(1)


def subscribe():
    "Subscribe to messages"
    topic = mqtt.get_settings().get(u"control_topic")
    if topic:
        mqtt.subscribe(topic, on_message, 2)


subscribe()
