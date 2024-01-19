# !/usr/bin/env python
# -*- coding: utf-8 -*-

# standard library imports
import json  # for working with data file
from threading import Thread
from time import sleep

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from webpages import showInFooter  # Enable plugin to display readings in UI footer
from webpages import showOnTimeline  # Enable plugin to display station data on timeline

import os
import csv

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/moisture_sensor_control", u"plugins.moisture_sensor_control.get_settings",
    u"/moisture_sensor_control-save", u"plugins.moisture_sensor_control.save_settings"

    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([("Moisture Sensor Control"), "/moisture_sensor_control"])

moisture_sensor_settings = {}


def empty_function():  # Only a place holder
    """
    Functions defined here can be called by classes
    or run when the plugin is loaded. See comment at end.
    """
    pass


def load_moisture_sensor_settings():
    global moisture_sensor_settings
    try:
        with open(
            "./data/moisture_sensor_control.json", "r"
        ) as f:  # Read settings from json file if it exists
            moisture_sensor_settings = json.load(f)

    except IOError:  # If file does not exist return empty value
        moisture_sensor_settings = {}

    moisture_sensor_settings["sensors"] = []
    if os.path.isdir("./data/moisture_sensor_data"):
        files = os.listdir("./data/moisture_sensor_data")
        for file in files:
            moisture_sensor_settings["sensors"].append(file)

    print(moisture_sensor_settings)  # for testing


#
#
# https://stackoverflow.com/questions/46258499/how-to-read-the-last-line-of-a-file-in-python#:~:text=seek(%2D200%2C%202)%20will,from%20readlines()%20and%20decoded.
#
#
# Station Schedule
def notify_stations_scheduled(station, **kw):
    print("Station {} run started".format(station))
    print(f"srvals {gv.srvals}")
    print(f"rs before {gv.rs}")
    print(f"rs before {gv.ps}")
    print(moisture_sensor_settings)

    for station_index in range(0, len(gv.rs)):
        if gv.rs[station_index][0] != 0:
            sensor_key = f"sensor{station_index}"

            if sensor_key not in moisture_sensor_settings:
                continue

            sensor = moisture_sensor_settings[sensor_key]
            threshold = moisture_sensor_settings[f"threshold{station_index}"]

            # with open(f"./data/moisture_sensor_data/{sensor}", newline="") as csvfile:
            #    sensor_data = csv.reader(csvfile)
            #    current_reading = next(sensor_data)

            with open(f"./data/moisture_sensor_data/{sensor}") as f:
                for sensor_data in f:
                    pass
                current_reading = sensor_data.split(",")

            if current_reading[1] > threshold:
                gv.rs[station_index] = [0, 0, 0, 0]

    print(f"rs after {gv.rs}")


complete = signal("stations_scheduled")
complete.connect(notify_stations_scheduled)


class get_settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        load_moisture_sensor_settings()

        return template_render.moisture_sensor_control(
            moisture_sensor_settings
        )  # open settings page

        try:
            with open(
                "./data/moisture_sensor_control.json", "r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)

        except IOError:  # If file does not exist return empty value
            settings = {}  # Default settings. can be list, dictionary, etc.

        settings["sensors"] = []
        if os.path.isdir("./data/moisture_sensor_data"):
            files = glob.glob("./data/moisture_sensor_data/*.current")
            for file in files:
                settings["sensors"].append(os.path.splitext(os.path.basename(file))[0])

        print(settings)  # for testing

        return template_render.moisture_sensor_control(settings)  # open settings page


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):
        global moisture_sensor_settings
        qdict = (
            web.input()
        )  # Dictionary of values returned as query string from settings page.
        print(qdict)  # for testing
        with open(
            "./data/moisture_sensor_control.json", "w"
        ) as f:  # Edit: change name of json file
            json.dump(qdict, f)  # save to file
            # json.dump(dict(sorted(qdict.items())), f)  # save to file
            moisture_sensor_settings = qdict

        # Redisplay the plugin page
        raise web.seeother("/moisture_sensor_control")


#  Run when plugin is loaded
load_moisture_sensor_settings()
