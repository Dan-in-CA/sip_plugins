# !/usr/bin/env python


""" SIP plugin adds an MQTT client to SIP for other plugins to broadcast and receive via MQTT
The intent is to facilitate joining SIP to larger automation systems
__author__ = "Daniel Casner <daniel@danielcasner.org>"
"""

# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
import atexit  # For publishing down message
import json  # for working with data file

# local module imports
import gv  # Get access to SIP's settings
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print(u"ERROR: MQTT Plugin requires paho mqtt.")
    print(u"\ttry: pip install paho-mqtt")
    print(u"or for Python 3 pip3 install paho-mqtt ")
    mqtt = None

DATA_FILE = u"./data/mqtt.json"

_client = None
_settings = {
    u"broker_host": u"localhost",
    u"broker_port": 1883,
    u"broker_username": u"user",
    u"broker_password": u"pass",
    u"publish_up_down": u"",
}
_subscriptions = {}

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend(
    [
        u"/mqtt-sp", u"plugins.mqtt.settings", 
        u"/mqtt-save", u"plugins.mqtt.save_settings"
     ]
)
# fmt: on

gv.plugin_menu.append([u"MQTT", u"/mqtt-sp"])

NO_MQTT_ERROR = u"MQTT plugin requires paho mqtt python library. On the command line run `pip install paho-mqtt` and restart SIP to get it."


class settings(ProtectedPage):
    """Load an html page for entering plugin settings.
    """

    def GET(self):
        settings = get_settings()
        return template_render.mqtt(
            settings, gv.sd[u"name"], NO_MQTT_ERROR if mqtt is None else u""
        )  # open settings page


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
        with open(DATA_FILE, u"w") as f:
            try:
                port = int(qdict[u"broker_port"])
                assert port > 80 and port < 65535
                _settings[u"broker_port"] = port
                _settings[u"broker_username"] = qdict[u"broker_username"]
                _settings[u"broker_password"] = qdict[u"broker_password"]
                _settings[u"broker_host"] = qdict[u"broker_host"]
                _settings[u"publish_up_down"] = qdict[u"publish_up_down"]
            except:
                return template_render.proto(
                    qdict,
                    gv.sd[u"name"],
                    u"Broker port must be a valid integer port number",
                )
            else:
                json.dump(_settings, f, indent=4, sort_keys=True)  # save to file
                publish_status()
        raise web.seeother(u"/")  # Return user to home page.


def get_settings():
    global _settings
    try:
        fh = open(DATA_FILE, "r")
        try:
            _settings = json.load(fh)
        except ValueError as e:
            print(u"MQTT pluging couldn't parse data file:", e)
        finally:
            fh.close()
    except IOError as e:
        print(u"MQTT Plugin couldn't open data file:", e)
    return _settings


def on_message(client, userdata, msg):
    """
    Callback for MQTT data recieved
    """
    global _subscriptions
    if not msg.topic in _subscriptions:
        print(u"MQTT plugin got unexpected message on topic:", msg.topic)
    else:
        for cb in _subscriptions[msg.topic]:
            cb(client, msg)


def get_client():
    global _client
    if _client is None and mqtt is not None:
        try:
            _client = mqtt.Client(gv.sd[u"name"])  # Use system name as client ID
            if _settings[u"publish_up_down"]:
                _client.will_set(
                    _settings[u"publish_up_down"], json.dumps(u"DOWN"), qos=1, retain=True
                )
            _client.on_message = on_message
            _client.username_pw_set(
                _settings[u"broker_username"], _settings[u"broker_password"]
            )
            _client.connect(_settings[u"broker_host"], _settings[u"broker_port"])
            _client.loop_start()
        except Exception as e:
            print(u"MQTT plugin couldn't initalize client:", e)
    return _client


def publish_status(status=u"UP"):
    global _settings
    if _settings[u"publish_up_down"]:
        print(u"MQTT publish", status)
        client = get_client()
        if client:
            client.publish(
                _settings[u"publish_up_down"], json.dumps(status), qos=1, retain=True
            )


def subscribe(topic, callback, qos=0):
    """
    Subscribes to a topic with the given callback
    """
    global _subscriptions
    client = get_client()
    if client:
        if topic not in _subscriptions:
            _subscriptions[topic] = [callback]
            client.subscribe(topic, qos)
        else:
            _subscriptions[topic].append(callback)


def on_restart():
    global _client
    if _client is not None:
        publish_status(u"DOWN")
        _client.disconnect()
        _client.loop_stop()
        _client = None


atexit.register(on_restart)

get_settings()

publish_status()
