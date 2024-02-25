# !/usr/bin/env python
# -*- coding: utf-8 -*-

# standard library imports
import json  # for working with data file
from threading import Thread
from threading import Event
from time import sleep

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  # Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security

import datetime
import jmespath
import os
from plugins import mqtt

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/moisture_sensor_data_mqtt", u"plugins.moisture_sensor_data_mqtt.get_settings",
    u"/moisture_sensor_data_mqtt-save", u"plugins.moisture_sensor_data_mqtt.save_settings"
    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_("Moisture Sensor Data MQTT"), "/moisture_sensor_data_mqtt"])

settings = {}
last_reading = {}
mqtt_readers = {}
SENSOR_DATA_PATH = "./static/data/moisture_sensor_data"
CONFIG_FILE_PATH = "./data/moisture_sensor_data_mqtt.json"
ATTRIBUTES = [
    "o_sensor",
    "sensor",
    "topic",
    "path",
    "interval",
    "driest",
    "wettest",
    "enable",
    "retention",
]


def validate_int_list(int_list):
    """Validates a list of possible integers and either returns each valid
    integer or None as a tuple

    """
    validated_list = []
    for index in range(len(int_list)):
        try:
            validated_list.append(int(int_list[index]))
        except (TypeError, ValueError):
            validated_list.append(None)

    return tuple(validated_list)


def create_sensor_data_file(new_file):
    """Use x and y as headings for the graph plugin"""
    with open(new_file, "w") as f:
        f.write("x,y\n")


def mqtt_reader(client, msg):
    """Sensor callback function for MQTT subscribe. Matches the topic
    back to the sensor in order to access additional
    attributes. Parses the message payload for an integer value. If
    the optional path attribute is set then jmsepath is used to parse
    an integer from the payload. This value is then converted to a
    percent value based on the wetest/driest attributes and it then
    stores it in the senors' data file.

    """
    global settings

    # Get sensor from topic
    sensor = [
        k
        for k, v in settings["sensors"].items()
        if "topic" in v and v["topic"] == msg.topic
    ]

    if len(sensor) > 0:
        # Could be that one topic is mapped to multiple sensors.
        # For now just take the first one.
        sensor = sensor[0]
        setting = settings["sensors"][sensor]
        sensor_file = f"{SENSOR_DATA_PATH}/{sensor}"

        #
        # Parse the payload
        #
        try:
            raw_reading = json.loads(msg.payload)
        except ValueError as e:
            print("mqtt_reader could not decode payload: ", msg.payload, e)
            return

        path = setting["path"]
        if path != "":
            try:
                raw_reading = jmespath.search(path, raw_reading)

            except Exception as e:
                print("mqtt_reader found invalid jmespath expression: ", path, e)
                return

        reading, interval, driest, wettest, retention = validate_int_list(
            [
                raw_reading,
                setting["interval"],
                setting["driest"],
                setting["wettest"],
                setting["retention"],
            ]
        )

        if reading is None:
            print(f"mqtt_reader did not find integer: {raw_reading}")
            return

        if driest is None or wettest is None:
            return

        ts_secs = gv.now
        ts = datetime.datetime.fromtimestamp(ts_secs)
        if interval is not None and sensor in last_reading:
            if last_reading[sensor] + datetime.timedelta(minutes=interval) > ts:
                return

        last_reading[sensor] = ts

        #
        # Convert reading to %
        #
        if driest < wettest:
            reading = (reading - driest) / (wettest - driest) * 100
        else:
            reading = (driest - reading) / (driest - wettest) * 100
        reading = round(reading)

        # Store reading for display purposes
        settings["sesnors"][sensor]["current"] = reading

        # Send msd signal
        msd_signal.send(
            "reading", data={"sensor": sensor, "timestamp": ts_secs, "value": reading}
        )

        print(f"reading {reading}")
        # Save reading data for graph plugin if retention specified
        if retention is not None and os.path.isfile(sensor_file):
            with open(sensor_file, "a") as f:
                f.write(f"{ts_secs},{reading}\n")


def create_mqtt_reader(setting):
    if ("enable" in setting) and ("topic" in setting):
        mqtt.subscribe(setting["topic"], mqtt_reader, qos=0)


def stop_mqtt_reader(setting):
    if "topic" in setting:
        mqtt.unsubscribe(settting["topic"])


def truncate_data_files(neme, **kw):
    """Remove readings from data files that are past the retention
    period. Only process files once a week to save disk IO. Store that
    last truncate timestamp as the new_day signal is also sent on
    startup.
    """
    last_truncate = settings["last_truncate"]

    # Only perform truncation once a week to limit IO?
    if last_truncate + (86400 * 7) < gv.now:
        return

    settings["last_truncate"] = gv.now
    with open(CONFIG_FILE_PATH, "w") as f:
        json.dump(settings, f)

    for sensor in settings["sensors"].keys():
        sensor_file = f"{SENSOR_DATA_PATH}/{sensor}"

        if os.path.isfile(sensor_file):
            sensor_file_tmp = f"/tmp/{sensor}.tmp"
            # Convert days to seconds
            retention = settings["sensors"][sensor]["retention"] * 86400

            with open("sensor_file", "r") as input:
                with open(sensor_file_tmp, "w") as output:
                    # Copy headers straight to output
                    output.write(input.readline())

                    for line in input:
                        fields = line.split(",")
                        if fields[0] + retention > gv.now:
                            output.write(line)

            try:
                # Best option as new sensor data my be being written to file
                os.replace(sensor_file_tmp, sensor_file)
            except OSError as e:
                print(f"Cannot replace {sensor_file}", e)
                os.remove(sensor_file_tmp)


def load_moisture_data_mqtt_settings():
    global settings

    try:
        with open(CONFIG_FILE_PATH, "r") as f:
            settings = json.load(f)

    except IOError:
        # If file does not exist return default value
        settings = {
            "sensors": {},
            "last_truncate": gv.now,
        }


def moisture_sensor_data_init():
    if not os.path.isdir(SENSOR_DATA_PATH):
        os.makedirs(SENSOR_DATA_PATH, exist_ok=True)

    load_moisture_data_mqtt_settings()

    for sensor in settings["sensors"].keys():
        sensor_file = f"{SENSOR_DATA_PATH}/{sensor}"
        if not os.path.isfile(sensor_file):
            create_sensor_data_file(sensor_file)

        create_mqtt_reader(settings["sensors"][sensor])


class get_settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        # open settings page
        return template_render.moisture_sensor_data_mqtt(settings["sensors"])


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def gather_attributes(qdict, index, old_setting):
        new_setting = {}

        for attribute in ATTRIBUTES:
            if f"{attribute}{index}" in qdict:
                new_setting[f"{attribute}"] = qdict[f"{attribute}{index}"]

        updated = old_setting == new_setting

        return updated, new_setting

    def GET(self):
        global settings

        qdict = web.input()
        new_settings = {}

        index = 0
        while f"sensor{index}" in qdict:
            old_sensor = qdict[f"o_sensor{index}"]
            if old_sensor == "":
                old_setting = {}
                old_file = ""
            else:
                old_setting = settings["sensors"][old_sensor]
                old_file = f"{SENSOR_DATA_PATH}/{old_sensor}"

            new_sensor = qdict[f"sensor{index}"]
            new_file = f"{SENSOR_DATA_PATH}/{new_sensor}"

            updated, new_setting = save_settings.gather_attributes(
                qdict, index, old_setting
            )

            if new_sensor == "":
                if old_sensor != "":
                    # Case: Delete sensor
                    stop_mqtt_reader(old_sensor)
                    msd_signal.send("delete", data={"sensor": f"{old_sensor}"})
                    if os.path.isfile(old_file):
                        # missing_ok=True
                        os.remove(old_file)

            elif new_sensor != old_sensor:
                if old_sensor == "":
                    # Case: New sensor
                    create_sensor_data_file(new_file)
                    msd_signal.send("add", data={"sensor": f"{new_sensor}"})
                    create_mqtt_reader(new_setting)
                else:
                    # Case: Rename sensor
                    stop_mqtt_reader(old_sensor)
                    create_mqtt_reader(new_setting)
                    msd_signal.send(
                        "rename",
                        data={"sensor": f"{new_sensor}", "old_sensor": f"{old_sensor}"},
                    )
                    if os.path.isfile(old_file) and not os.path.isfile(new_file):
                        os.rename(old_file, new_file)

            else:
                if updated:
                    # Case: Attributes updated
                    stop_mqtt_reader(old_sensor)
                    create_mqtt_reader(new_setting)

            if new_sensor != "":
                # Sensor was not deleted so store the attributes
                new_settings[new_sensor] = new_setting

            index += 1

        settings["sensors"] = new_settings
        with open(CONFIG_FILE_PATH, "w") as f:
            json.dump(settings, f)

        # Redisplay the plugin page
        raise web.seeother("/moisture_sensor_data_mqtt")


msd_signal = signal("moisture_sensor_data")

new_day_signal = signal("new_day")
new_day_signal.connect(truncate_data_files)

# Run when plugin is loaded
moisture_sensor_data_init()
