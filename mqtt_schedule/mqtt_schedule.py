# !/usr/bin/env python

""" SIP plugin uses mqtt plugin to receive run once program commands over MQTT
__author__ = "Daniel Casner <daniel@danielcasner.org>"
"""

# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
import json  # for working with data file

# local module imports
from blinker import signal  # To receive station notifications
import gv  # Get access to SIP's settings
from helpers import schedule_stations
from plugins import mqtt
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend(
    [
        u"/mr1-sp", u"plugins.mqtt_schedule.settings",
        u"/mr1-save", u"plugins.mqtt_schedule.save_settings",
    ]
)
# fmt: on
gv.plugin_menu.append([u"MQTT scheduler", u"/mr1-sp"])


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        settings = mqtt.get_settings()
        zone_topic = settings.get(u"schedule_topic", gv.sd[u"name"] + u"/schedule")
        return template_render.mqtt_schedule(zone_topic, "")  # open settings page


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
    if not gv.sd[u"en"]:  # check operation status
        return
    num_brds = gv.sd[u"nbrd"]
    num_sta = num_brds * 8
    try:
        cmd = json.loads(msg.payload)
    except ValueError as e:
        print(u"MQTT Schedule could not decode command: ", msg.payload, e)
        return
    if type(cmd) is list:
        if len(cmd) < num_sta:
            print(
                u"MQTT schedule, not enough stations specified, assuming first {} of {}".format(
                    len(cmd), num_sta
                )
            )
            rovals = cmd + ([0] * (num_sta - len(cmd)))
        elif len(cmd) > num_sta:
            print(
                u"MQTT schedule, too many stations specified, truncating to {}".format(
                    num_sta
                )
            )
            rovals = cmd[0:num_sta]
        else:
            rovals = cmd
    elif type(cmd) is dict:
        rovals = [0] * num_sta
        for k, v in list(cmd.items()):
            if k not in gv.snames:
                print(u"MQTT schedule, no station named:", k)
            else:
                rovals[gv.snames.index(k)] = v
    else:
        print(u"MQTT schedule unexpected command: ", msg.payload)
        return
    if any(rovals):
        print(u"MQTT schedule:", rovals)
        gv.rovals = rovals
        stations = [0] * num_brds
        gv.ps = []  # program schedule (for display)
        gv.rs = []  # run schedule
        for i in range(gv.sd[u"nst"]):
            gv.ps.append([0, 0])
            gv.rs.append([0, 0, 0, 0])
        for i, v in enumerate(gv.rovals):
            if v:  # if this element has a value
                gv.rs[i][0] = gv.now
                gv.rs[i][2] = v
                gv.rs[i][3] = 98
                gv.ps[i][0] = 98
                gv.ps[i][1] = v
                stations[i // 8] += 2 ** (i % 8)
        schedule_stations(stations)


def subscribe():
    """
    Subscribe to messages
    """
    topic = mqtt.get_settings().get(u"schedule_topic")
    if topic:
        mqtt.subscribe(topic, on_message, 2)


subscribe()
