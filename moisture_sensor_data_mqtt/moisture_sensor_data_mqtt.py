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

import datetime
import copy
import os
from plugins import mqtt

try:
    import jmespath
except ImportError:
    print("Trying to install missing Python module jmespath")
    os.system("python3 -m pip install jmespath")
    import jmespath

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
    "enable",
    "o_sensor",
    "sensor",
    "topic",
    "path",
    "driest",
    "wettest",
    # "reading_ts",
    # "reading_value",
    "interval",
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

    # Get sensors matching this topic
    matching_sensors = [
        k
        for k, v in settings["sensors"].items()
        if "topic" in v and v["topic"] == msg.topic
    ]

    if len(matching_sensors) == 0:
        return

    # Parse the payload once (same for all sensors)
    try:
        raw_payload = json.loads(msg.payload)
    except ValueError as e:
        print("mqtt_reader could not decode payload: ", msg.payload, e)
        return

    # Process EACH sensor that matches this topic
    for sensor_name in matching_sensors:
        setting = settings["sensors"][sensor_name]
        sensor_file = f"{SENSOR_DATA_PATH}/{sensor_name}"

        # Parse the specific path for this sensor
        path = setting["path"]
        if path != "":
            try:
                raw_reading = jmespath.search(path, raw_payload)
            except Exception as e:
                print(f"mqtt_reader found invalid jmespath expression for {sensor_name}: {path}, {e}")
                continue
        else:
            raw_reading = raw_payload

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
            print(f"mqtt_reader did not find integer for {sensor_name}: {raw_reading}")
            continue

        if driest is None or wettest is None:
            continue

        ts_secs = int(gv.now)
        ts = datetime.datetime.fromtimestamp(ts_secs)
        if interval is not None and sensor_name in last_reading:
            if last_reading[sensor_name]["ts"] + datetime.timedelta(minutes=interval) > ts:
                continue

        #
        # Convert reading to %
        #
        if driest < wettest:
            reading = (reading - driest) / (wettest - driest) * 100
        else:
            reading = (driest - reading) / (driest - wettest) * 100
        reading = round(reading)

        # Store reading for display purposes
        last_reading[sensor_name] = {"ts": ts, "reading": reading}

        # Send msd signal
        msd_signal.send(
            "reading", data={"sensor": sensor_name, "timestamp": ts_secs, "value": reading}
        )

        # Save reading data for graph plugin if retention specified.
        # Note the timestamp is in milliseconds!
        if retention is not None and retention != 0 and os.path.isfile(sensor_file):
            with open(sensor_file, "a") as f:
                f.write(f"{ts_secs * 1000},{reading}\n")


def create_mqtt_reader(setting):
    if ("enable" in setting) and ("topic" in setting) and (setting["topic"] != ""):
        mqtt.subscribe(setting["topic"], mqtt_reader, qos=0)


def stop_mqtt_reader(setting):
    if "topic" in setting:
        mqtt.unsubscribe(setting["topic"], mqtt_reader)


def truncate_data_files(neme, **kw):
    """Remove readings from data files that are past the retention
    period. Only process files once a week to save disk IO. Store that
    last truncate timestamp as the new_day signal is also sent on
    startup.
    """
    last_truncate = settings["last_truncate"]

    # Only perform truncation once a week to limit IO?
    if last_truncate + (86400 * 7) > gv.now:
        return

    settings["last_truncate"] = int(gv.now)
    with open(CONFIG_FILE_PATH, "w") as f:
        f.write(json.dumps(settings, indent=2))

    for sensor in settings["sensors"].keys():
        sensor_file = f"{SENSOR_DATA_PATH}/{sensor}"
        sensor_file_tmp = f"/tmp/{sensor}.tmp"

        if os.path.isfile(sensor_file):
            (retention,) = validate_int_list([settings["sensors"][sensor]["retention"]])
            if retention is None:
                retention = 0

            # Convert days/seconds to miliseconds
            retention = retention * 86400 * 1000
            now = int(gv.now) * 1000

            with open(sensor_file, "r") as input:
                with open(sensor_file_tmp, "w") as output:
                    # Copy headers straight to output
                    output.write(input.readline())

                    for line in input:
                        fields = line.split(",")
                        # timestamp can be float or int
                        if int(float(fields[0])) + retention > now:
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
            "last_truncate": int(gv.now),
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
        # If we add this to settings we run into datetime
        # serialization issues when dumping settings, hence the copy.
        display_sensors = copy.deepcopy(settings["sensors"])

        for sensor in last_reading.keys():
            display_sensors[sensor]["reading_ts"] = last_reading[sensor]["ts"]
            display_sensors[sensor]["reading_value"] = last_reading[sensor]["reading"]

        # open settings page
        return template_render.moisture_sensor_data_mqtt(display_sensors)


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

        updated = old_setting != new_setting

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
                    last_reading.pop(old_sensor, None)
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
                    if old_sensor in last_reading:
                        last_reading[new_sensor] = last_reading.pop(old_sensor)

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
            f.write(json.dumps(settings, indent=2))

        # Redisplay the plugin page
        raise web.seeother("/moisture_sensor_data_mqtt")


msd_signal = signal("moisture_sensor_data")

new_day_signal = signal("new_day")
new_day_signal.connect(truncate_data_files)

# Run when plugin is loaded
moisture_sensor_data_init()
