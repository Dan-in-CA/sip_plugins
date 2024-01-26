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


def validate_int(int_list):
    validated_list = []
    for index in range(len(int_list)):
        try:
            validated_list.append(int(int_list[index]))
        except (TypeError, ValueError):
            validated_list.append(None)

    return tuple(validated_list)


def trigger_run_once(sensor, value):
    for station_index in range(0, len(gv.srvals)):
        if gv.srvals[station_index] == 1:
            # Program already running on station, no need to start
            # another one
            continue

        mins_key = f"i_mins{station_index}"
        secs_key = f"i_secs{station_index}"
        enable_key = f"i_enable{station_index}"
        threshold_key = f"i_threshold{station_index}"

        # If no program has been configured for the station or the
        # sensor has not be enabled take not action
        if (threshold_key not in moisture_sensor_settings) or (
            enable_key not in moisture_sensor_settings
        ):
            continue

        threshold, mins, secs = validate_int(
            [
                moisture_sensor_settings[threshold_key],
                moisture_sensor_settings[mins_key],
                moisture_sensor_settings[secs_key],
            ]
        )

        if threshold is None or mins is None or secs is None:
            # Required variable not set, do nothing
            return

        if value < threshold:
            duration = 0
            if mins is not None:
                duration = mins * 60
            if secs is not None:
                duration = duration + secs

            if duration > 0:
                # Trigger run once on station

                # TODO
                pass


def notify_moisture_sensor_data(action, **kw):
    """
    Functions defined here can be called by classes
    or run when the plugin is loaded. See comment at end.
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


def notify_stations_scheduled(station, **kw):
    """Suppress a schedule from running if the station has an active
    (enabled) moisture sensor assigned and the current moisture
    reading from the sensor is above the threshold value."""

    print("Station {} run started".format(station))
    print(f"srvals {gv.srvals}")
    print(f"ps {gv.ps}")
    print(f"pd {gv.pd}")
    print(f"pon {gv.pon}")
    print(f"rs before {gv.rs}")
    print(json.dumps(moisture_sensor_settings, sort_keys=True))
    print(moisture_sensor_data)

    for station_index in range(0, 1):  # range(0, len(gv.rs)):
        if gv.rs[station_index][0] != 0:
            sensor_key = f"sensor{station_index}"
            enable_key = f"enable{station_index}"
            threshold_key = f"threshold{station_index}"
            stale_key = f"stale{station_index}"

            # If no sensor has been configured for the station or the
            # sensor has not be enabled take not action
            if (sensor_key not in moisture_sensor_settings) or (
                enable_key not in moisture_sensor_settings
            ):
                continue

            sensor = moisture_sensor_settings[sensor_key]
            threshold, stale = validate_int(
                [
                    moisture_sensor_settings[threshold_key],
                    moisture_sensor_settings[stale_key],
                ]
            )

            if sensor == "" or threshold is None:
                # Required fields not present silently skip station
                continue

            if "value" not in moisture_sensor_data[sensor]:
                # Sensor has not sent any values yet
                continue

            value = moisture_sensor_data[sensor]["value"]
            if value > threshold:
                # Check for stale value
                ts = moisture_sensor_data[sensor]["timestamp"]
                ts = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")

                print(f"stale value{stale}")
                if (stale is not None) and (
                    ts + datetime.timedelta(minutes=stale)
                    < datetime.datetime.fromtimestamp(gv.now)
                ):
                    print(f"notify_stations_scheduled stale value {ts} {value}")
                    continue

                # Suppress schedule
                gv.rs[station_index] = [0, 0, 0, 0]

    print(f"rs after {gv.rs}")


scheduled_signal = signal("stations_scheduled")
scheduled_signal.connect(notify_stations_scheduled)


def load_moisture_sensor_settings():
    global moisture_sensor_settings
    global moisture_sensor_data

    try:
        with open(
            "./data/moisture_sensor_control.json", "r"
        ) as f:  # Read settings from json file if it exists
            moisture_sensor_settings = json.load(f)

    except IOError:  # If file does not exist return empty value
        moisture_sensor_settings = {}

    if os.path.isdir("./data/moisture_sensor_data"):
        files = os.listdir("./data/moisture_sensor_data")
        for file in files:
            sensor = file

            # Get last entry in sensor data file, this could get slow
            # for large files. See solution based on seek
            # https://stackoverflow.com/questions/46258499/how-to-read-the-last-line-of-a-file-in-python
            with open(f"./data/moisture_sensor_data/{sensor}") as f:
                for sensor_data in f:
                    pass

                current_reading = sensor_data.rstrip().split(",")

                if current_reading[0] == "Timestamp":
                    # Not data in file yet
                    moisture_sensor_data[sensor] = {}
                else:
                    moisture_sensor_data[sensor] = {
                        "timestamp": current_reading[0],
                        "value": int(current_reading[1]),
                    }

    print(moisture_sensor_settings)  # for testing
    print(moisture_sensor_data)  # for testing


class get_settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        # load_moisture_sensor_settings()

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
        # print(qdict)

        moisture_sensor_settings = qdict

        with open("./data/moisture_sensor_control.json", "w") as f:
            json.dump(qdict, f)

        # Redisplay the plugin page
        raise web.seeother("/moisture_sensor_control")


#  Run when plugin is loaded
load_moisture_sensor_settings()
