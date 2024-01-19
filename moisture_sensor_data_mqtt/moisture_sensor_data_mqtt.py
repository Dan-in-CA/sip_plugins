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
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from webpages import showInFooter  # Enable plugin to display readings in UI footer
from webpages import showOnTimeline  # Enable plugin to display station data on timeline

import os
import datetime
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
mqtt_readers = {}
SENSOR_DATA_PATH = "./data/moisture_sensor_data"
ATTRIBUTES = [
    "o_sensor",
    "sensor",
    "topic",
    "path",
    "dryest",
    "wetest",
    "enabled",
    "retention",
]


def create_sensor_data_file(new_file):
    with open(new_file, "w") as f:
        f.write("Timestamp,Reading\n")


def mqtt_readerx(setting, stop_flag):
    sensor = setting["sensor"]
    sensor_file = f"{SENSOR_DATA_PATH}/{sensor}"

    while not stop_flag.is_set():
        if os.path.isfile(sensor_file):
            with open(sensor_file, "a") as f:
                ts = datetime.datetime.now()
                ts.strftime("%Y-%m-%dT%H:%M:%S")
                f.write(f"{ts},{setting}\n")

        else:
            print(f"File does not exist {sensor_file}")

        sleep(int(setting["poll"]) * 60)


def mqtt_reader(client, msg):
    print(f"reader {settings}")
    sensor = [
        k for k, v in settings.items() if "topic" in v and v["topic"] == msg.topic
    ]
    print(sensor)

    if len(sensor) > 0:
        sensor = sensor[0]
        setting = settings[sensor]
        sensor_file = f"{SENSOR_DATA_PATH}/{sensor}"

        try:
            reading = json.loads(msg.payload)
        except ValueError as e:
            print("mqtt_reader could not decode reading: ", msg.payload, e)
            return

        if ("jsonata" in setting) and (setting["jsonata"] != ""):
            pass

        if os.path.isfile(sensor_file):
            with open(sensor_file, "a") as f:
                ts = msg.timestamp
                # ts.strftime("%Y-%m-%dT%H:%M:%S")
                # reading = msg.payload
                f.write(f"{ts},{reading}\n")


def create_mqtt_readerx(setting):
    stop_flag = Event()
    reader = Thread(target=mqtt_reader, args=(setting, stop_flag))
    reader.daemon = True
    reader.start()

    mqtt_readers[setting["sensor"]] = {"reader": reader, "stop_flag": stop_flag}
    print(f"reader created for {setting['sensor']}")


def create_mqtt_reader(setting):
    if "topic" in setting:
        mqtt.subscribe(setting["topic"], mqtt_reader, qos=0)


def stop_mqtt_readerx(sensor):
    if sensor in mqtt_readers:
        stop_flag = mqtt_readers[sensor]["stop_flag"]
        stop_flag.set()

    print(f"reader stopped for {sensor}")


def stop_mqtt_reader(setting):
    if "topic" in setting:
        mqtt.unsubscribe(settting["topic"])


def load_moisture_data_mqtt_settings():
    global settings

    try:
        with open("./data/moisture_sensor_data_mqtt.json", "r") as f:
            settings = json.load(f)
            # If file does not exist return empty value
    except IOError:
        settings = {}


def moisture_sensor_data_init():
    if not os.path.isdir(SENSOR_DATA_PATH):
        os.mkdir(SENSOR_DATA_PATH)

    load_moisture_data_mqtt_settings()

    for sensor in settings.keys():
        sensor_file = f"{SENSOR_DATA_PATH}/{sensor}"
        if not os.path.isfile(sensor_file):
            create_sensor_data_file(sensor_file)

        create_mqtt_reader(settings[sensor])


class get_settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        load_moisture_data_mqtt_settings()

        # Add empty place holder for new sensor
        # settings["."] = {}

        # open settings page
        return template_render.moisture_sensor_data_mqtt(settings)


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def gather_attributes(qdict, index, old_setting):
        setting = {}
        updates = False

        for attribute in ATTRIBUTES:
            if f"{attribute}{index}" in qdict:
                setting[f"{attribute}"] = qdict[f"{attribute}{index}"]
                if (attribute not in old_setting) or (
                    qdict[f"{attribute}{index}"] != old_setting[attribute]
                ):
                    updates = True

        print(f"Gather attrs {index} {old_setting} {updates} {setting}")

        return updates, setting

    def GET(self):
        global settings
        print(settings)
        # Dictionary of values returned as query string from settings page.
        qdict = web.input()

        new_settings = {}

        index = 0
        while f"sensor{index}" in qdict:
            updated = False
            new_setting = None

            old_sensor = qdict[f"o_sensor{index}"]
            if old_sensor == "":
                old_setting = {}
                old_file = ""
            else:
                old_setting = settings[old_sensor]
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
                    if os.path.isfile(old_file):
                        # missing_ok=True
                        os.remove(old_file)
            elif new_sensor != old_sensor:
                if old_sensor == "":
                    # Case: New sensor
                    create_sensor_data_file(new_file)
                    create_mqtt_reader(new_setting)
                else:
                    # Case: Rename sensor
                    stop_mqtt_reader(old_sensor)
                    create_mqtt_reader(new_setting)
                    if os.path.isfile(old_file) and not os.path.isfile(new_file):
                        os.rename(old_file, new_file)

            else:
                if updated:
                    stop_mqtt_reader(old_sensor)
                    create_mqtt_reader(new_setting)

                # Do we really need this?
                # if not os.path.isfile(old_file):
                #     create_sensor_data_file(new_file)

            if new_sensor != "":
                # Sensor was not deleted so store the attributes
                new_settings[new_sensor] = new_setting

            index += 1

        settings = new_settings

        with open("./data/moisture_sensor_data_mqtt.json", "w") as f:
            json.dump(settings, f)

        # Redisplay the plugin page
        raise web.seeother("/moisture_sensor_data_mqtt")


#  Run when plugin is loaded
moisture_sensor_data_init()
