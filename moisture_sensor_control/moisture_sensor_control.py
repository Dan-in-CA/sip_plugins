# !/usr/bin/env python
# -*- coding: utf-8 -*-

# standard library imports
import json  # for working with data file

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  # Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from webpages import showInFooter  # Enable plugin to display readings in UI footer
from webpages import showOnTimeline  # Enable plugin to display station data on timeline

from helpers import run_once
import datetime
import os
import re

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
moisture_sensor_data = {}
station_last_run = {}
DATA_DIR_PATH = "./static/data/moisture_sensor_data"
CONFIG_FILE_PATH = "./data/moisture_sensor_control.json"


def validate_int(int_list):
    validated_list = []

    for index in range(len(int_list)):
        try:
            validated_list.append(int(int_list[index]))
        except (TypeError, ValueError):
            validated_list.append(None)

    return tuple(validated_list)


def trigger_run_once(sensor, value):
    """Processes a new reading. Checks if all the required fields are
    set, checks to see if the pause and threshold values apply and if
    required triggers an run once for the set time.
    """
    for station_index in range(0, len(gv.srvals)):
        if gv.srvals[station_index] == 1:
            # Program already running on station, no need to start
            # another one
            continue

        mins_key = f"i_mins{station_index}"
        secs_key = f"i_secs{station_index}"
        enable_key = f"i_enable{station_index}"
        threshold_key = f"i_threshold{station_index}"
        pause_key = f"i_pause{station_index}"

        # If no threshold has been configured for the station or the
        # sensor has not been enabled take not action
        if (threshold_key not in moisture_sensor_settings) or (
            enable_key not in moisture_sensor_settings
        ):
            continue

        threshold, mins, secs, pause = validate_int(
            [
                moisture_sensor_settings[threshold_key],
                moisture_sensor_settings[mins_key],
                moisture_sensor_settings[secs_key],
                moisture_sensor_settings[pause_key],
            ]
        )

        if threshold is None or (mins is None and secs is None):
            # Required variable not set, do nothing
            return

        if (
            pause is not None
            and station_index in station_last_run
            and station_last_run[station_index] + (pause * 60) > gv.now
        ):
            continue

        if value < threshold:
            duration = 0
            if mins is not None:
                duration = mins * 60
            if secs is not None:
                duration = duration + secs

            if duration > 0:
                gv.rovals[station_index] = duration
                run_once()


def notify_moisture_sensor_data(action, **kw):
    """Handles signals (reading, add, rename, delete) from a Moisture
    Sensor Data plugin and triggers the appropriate action.

    """
    data = kw["data"]

    if action == "reading":
        moisture_sensor_data[data["sensor"]] = {
            "timestamp": data["timestamp"],
            "value": int(data["value"]),
        }

        trigger_run_once(data["sensor"], data["value"])

    elif action == "add":
        moisture_sensor_data[data["sensor"]] = {}

    elif action == "rename":
        for k, v in moisture_sensor_settings.items():
            if re.match(r"sensor\d+", k) and v == data["old_sensor"]:
                moisture_sensor_settings[k] = data["sensor"]
        moisture_sensor_data[data["sensor"]] = moisture_sensor_data[data["old_sensor"]]
        del moisture_sensor_data[data["old_sensor"]]

    elif action == "delete":
        for k, v in moisture_sensor_settings.items():
            if re.match(r"sensor\d+", k) and v == data["sensor"]:
                moisture_sensor_settings[k] = ""
        del moisture_sensor_data[data["sensor"]]

    else:
        print(f"notify_moisture_sensor_data unknown action {action} {data}")


msd_signal = signal("moisture_sensor_data")
msd_signal.connect(notify_moisture_sensor_data)


def notify_station_completed(station, **kw):
    """Capture the last station run end time. Required for the pause
    feature.
    """

    station_index = station - 1
    station_last_run[station_index] = gv.rs[station_index][1]


completed_signal = signal("station_completed")
completed_signal.connect(notify_station_completed)


def notify_stations_scheduled(station, **kw):
    """Suppress a schedule from running if the station has an active
    (enabled) moisture sensor assigned and the current moisture
    reading from the sensor is above the threshold value."""

    if gv.rn:
        # Skip RUN NOW schedules
        return

    station_index = station - 1

    # TODO honor "Ignore Plugin adjustments"

    sensor_key = f"sensor{station_index}"
    enable_key = f"enable{station_index}"
    threshold_key = f"threshold{station_index}"
    stale_key = f"stale{station_index}"

    # If no sensor has been configured for the station or the
    # sensor has not be enabled take no action
    if (sensor_key not in moisture_sensor_settings) or (
        enable_key not in moisture_sensor_settings
    ):
        return

    sensor = moisture_sensor_settings[sensor_key]
    threshold, stale = validate_int(
        [
            moisture_sensor_settings[threshold_key],
            moisture_sensor_settings[stale_key],
        ]
    )

    if sensor == "" or threshold is None:
        # Required fields not present silently skip station
        return

    if "value" not in moisture_sensor_data[sensor]:
        # Sensor has not sent any values yet
        return

    value = moisture_sensor_data[sensor]["value"]
    if value > threshold:
        # Check for stale value
        ts_secs = moisture_sensor_data[sensor]["timestamp"]
        ts = datetime.datetime.fromtimestamp(ts_secs)

        if stale is not None and ts + datetime.timedelta(
            minutes=stale
        ) < datetime.datetime.fromtimestamp(gv.now):
            return

        # Suppress schedule
        gv.rs[station_index] = [0, 0, 0, 0]


scheduled_signal = signal("station_scheduled")
scheduled_signal.connect(notify_stations_scheduled)


def load_moisture_sensor_settings():
    global moisture_sensor_settings
    global moisture_sensor_data

    try:
        with open(
            CONFIG_FILE_PATH, "r"
        ) as f:  # Read settings from json file if it exists
            moisture_sensor_settings = json.load(f)

    except IOError:
        # If file does not exist return empty value
        moisture_sensor_settings = {}

    # Initialise list of sensors from file names. Ideally this should
    # be via a signal but the order in which plugins are loaded might
    # affect this.
    if os.path.isdir(DATA_DIR_PATH):
        files = os.listdir(DATA_DIR_PATH)
        for file in files:
            moisture_sensor_data[file] = {}


class get_settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        moisture_sensor_settings["sensors"] = list(moisture_sensor_data.keys())

        # open settings page
        return template_render.moisture_sensor_control(moisture_sensor_settings)


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):
        global moisture_sensor_settings

        # Dictionary of values returned as query string from settings page.
        qdict = web.input()

        moisture_sensor_settings = qdict

        with open(CONFIG_FILE_PATH, "w") as f:
            json.dump(qdict, f)

        # Redisplay the plugin page
        raise web.seeother("/moisture_sensor_control")


#  Run when plugin is loaded
load_moisture_sensor_settings()
