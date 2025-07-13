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
import threading

# local module imports
from blinker import signal  # To receive station notifications
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

_connection_thread = None
_connection_stop_event = threading.Event()
_client_lock = threading.Lock()
_is_connected = False
_reconnect_interval = 30  # seconds

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

mqtt_settings_change = signal(u"mqtt_settings_change")


def report_mqtt_settings_change():
    """
    Send blinker signal indicating that mqtt settings changed.
    """
    mqtt_settings_change.send()


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        settings = get_settings()
        return template_render.mqtt(
            settings,
            gv.sd[u"name"],
            NO_MQTT_ERROR if mqtt is None else u"",
            is_connected()
        )  # open settings page


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):
        previous = _settings.copy()
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
                apply_new_mqtt_settings(previous)
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


def apply_new_mqtt_settings(previous):
    """
    Apply MQTT server and up/down topic status on settings change
    """
    global _settings
    global _client

    status_topic_change = False
    if (
        previous[u"publish_up_down"] != _settings[u"publish_up_down"]
        and previous[u"publish_up_down"] != ""
    ):
        status_topic_change = True

    server_change = False
    for i in [
        u"broker_port",
        u"broker_username",
        u"broker_password",
        u"broker_host",
    ]:
        if previous[i] != _settings[i]:
            server_change = True

    if _client:
        if status_topic_change:
            # Update previous status
            _client.publish(
                previous[u"publish_up_down"], json.dumps("Down"), qos=1, retain=True
            )
            # Clear out previous status
            _client.publish(previous[u"publish_up_down"], "", qos=1, retain=True)

        # Close previous connection
        if server_change:
            on_restart()

    if status_topic_change or server_change:
        report_mqtt_settings_change()

    publish_status()  # Continu or restart session with the new settings


def on_message(client, userdata, msg):
    """
    Callback for MQTT data recieved
    """
    global _subscriptions
    topic_string = ""
    valid_topic = False
    for topic in _subscriptions:
        topic_string = topic
        if topic[-1:] == "#":
            if topic[:len(topic)-2] == msg.topic[:len(topic)-2]:
                valid_topic = True
                break
            elif topic[:len(topic)-2] == msg.topic:
                valid_topic = True
                break
        elif topic == msg.topic:
            valid_topic = True
            break
    if not valid_topic:    
        print(u"MQTT plugin got unexpected message on topic:", msg.topic, msg.payload)
    else:
        for cb in _subscriptions[topic_string]:
            cb(client, msg)


def get_client():
    """Get MQTT client, ensuring connection monitor is running"""
    global _client

    # Always ensure connection monitor is running
    start_connection_monitor()

    with _client_lock:
        return _client

def on_connect(client, userdata, flags, rc):
    """Callback for successful MQTT connection"""
    global _is_connected

    if rc == 0:
        print("MQTT: Connected successfully")
        _is_connected = True

        # Re-subscribe to all topics that were previously subscribed
        print(f"MQTT: Re-subscribing to {len(_subscriptions)} topics")
        for topic in _subscriptions:
            try:
                client.subscribe(topic, 0)
                print(f"MQTT: Subscribed to {topic}")
            except Exception as e:
                print(f"MQTT: Failed to subscribe to {topic}: {e}")

        # Publish UP status
        if _settings[u"publish_up_down"]:
            try:
                client.publish(
                    _settings[u"publish_up_down"], json.dumps(u"UP"), qos=1, retain=True
                )
                print("MQTT: Published UP status")
            except Exception as e:
                print(f"MQTT: Failed to publish UP status: {e}")
    else:
        print(f"MQTT: Connection failed with result code {rc}")
        _is_connected = False


def on_disconnect(client, userdata, rc):
    """Callback for MQTT disconnection"""
    global _is_connected
    _is_connected = False

    if rc == 0:
        print("MQTT: Disconnected normally")
    else:
        print(f"MQTT: Unexpected disconnection (code: {rc}), will attempt reconnection")


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
    """Subscribe to a topic - updated to work with reconnection and handle duplicates"""
    global _subscriptions

    # Ensure connection monitor is running
    start_connection_monitor()

    # Check if this is a new topic subscription
    is_new_topic = topic not in _subscriptions

    # Add callback to subscriptions list (for reconnection)
    if is_new_topic:
        _subscriptions[topic] = [callback]
        print(f"MQTT: New topic subscription: {topic}")
    else:
        _subscriptions[topic].append(callback)
        print(f"MQTT: Added callback to existing topic: {topic} (total callbacks: {len(_subscriptions[topic])})")

    # Only subscribe to broker if this is a new topic
    if is_new_topic:
        with _client_lock:
            if _client and _is_connected:
                try:
                    _client.subscribe(topic, qos)
                    print(f"MQTT: Subscribed to broker for topic: {topic}")
                    return True
                except Exception as e:
                    print(f"MQTT: Failed to subscribe to {topic}: {e}")
                    return False
            else:
                print(f"MQTT: Queued broker subscription to {topic} (will subscribe when connected)")
                return True
    else:
        print(f"MQTT: Topic {topic} already subscribed to broker, just added callback")
        return True


def unsubscribe(topic, callback=None):
    """
    Unsubscribe from a topic - improved to handle multiple callbacks per topic
    If callback is provided, only remove that specific callback.
    Method will only unsubscribe from broker when no callbacks remain for the topic.
    If no callback provided, remove all callbacks for the topic.
    """
    global _subscriptions

    if topic not in _subscriptions:
        print(f"MQTT: Topic {topic} not found in subscriptions")
        return False

    if callback is None:
        # Remove all callbacks for this topic (backward compatibility)
        del _subscriptions[topic]
        print(f"MQTT: Removed all callbacks for topic: {topic}")
        should_unsubscribe_broker = True
    else:
        # Remove specific callback
        try:
            _subscriptions[topic].remove(callback)
            print(f"MQTT: Removed specific callback for topic: {topic}")
            # Only unsubscribe from broker if no callbacks remain
            should_unsubscribe_broker = len(_subscriptions[topic]) == 0
            if should_unsubscribe_broker:
                del _subscriptions[topic]
                print(f"MQTT: No callbacks remain for topic: {topic}")
        except ValueError:
            print(f"MQTT: Callback not found for topic: {topic}")
            return False

    # Unsubscribe from broker only if no callbacks remain for this topic
    if should_unsubscribe_broker:
        with _client_lock:
            if _client and _is_connected:
                try:
                    _client.unsubscribe(topic)
                    print(f"MQTT: Unsubscribed from broker for topic: {topic}")
                except Exception as e:
                    print(f"MQTT: Failed to unsubscribe from {topic}: {e}")
                    return False
            else:
                print(f"MQTT: Queued broker unsubscription from {topic}")

    return True


def publish(topic, payload, qos=0, retain=False):
    """Publish a message - safe version that handles disconnection"""
    with _client_lock:
        if _client and _is_connected:
            try:
                _client.publish(topic, payload, qos=qos, retain=retain)
                return True
            except Exception as e:
                print(f"MQTT: Failed to publish to {topic}: {e}")
                return False
        else:
            print(f"MQTT: Cannot publish to {topic} - not connected")
            return False


def is_connected():
    """Check if MQTT client is connected"""
    return _is_connected


def on_restart():
    """Updated restart function"""
    global _client, _is_connected

    print("MQTT: Shutting down...")

    # Stop the connection monitor
    stop_connection_monitor()

    # Disconnect client
    if _client is not None:
        try:
            if _is_connected and _settings[u"publish_up_down"]:
                _client.publish(
                    _settings[u"publish_up_down"], json.dumps(u"DOWN"), qos=1, retain=True
                )
            _client.disconnect()
            _client.loop_stop()
        except Exception as e:
            print(f"MQTT: Error during shutdown: {e}")
        _client = None

    _is_connected = False


def connection_monitor():
    """Background thread to monitor and maintain MQTT connection"""
    global _client, _is_connected

    print("MQTT: Connection monitor thread started")

    while not _connection_stop_event.is_set():
        try:
            with _client_lock:
                if not _is_connected and mqtt is not None:
                    print(f"MQTT: Attempting to connect to {_settings['broker_host']}:{_settings['broker_port']}")

                    # Clean up old client if it exists
                    if _client is not None:
                        try:
                            _client.disconnect()
                            _client.loop_stop()
                        except:
                            pass
                        _client = None

                    try:
                        # Create new client
                        _client = mqtt.Client(gv.sd[u"name"])

                        if _settings[u"publish_up_down"]:
                            _client.will_set(
                                _settings[u"publish_up_down"], json.dumps(u"DOWN"), qos=1, retain=True
                            )

                        _client.on_message = on_message
                        _client.on_connect = on_connect
                        _client.on_disconnect = on_disconnect

                        _client.username_pw_set(
                            _settings[u"broker_username"], _settings[u"broker_password"]
                        )

                        _client.connect(_settings[u"broker_host"], _settings[u"broker_port"], keepalive=60)
                        _client.loop_start()

                        print("MQTT: Connection attempt initiated")

                    except Exception as e:
                        print(f"MQTT connection attempt failed: {e}")
                        _client = None
                        _is_connected = False

        except Exception as e:
            print(f"MQTT monitor thread error: {e}")

        # Wait before next check/retry
        _connection_stop_event.wait(_reconnect_interval)

    print("MQTT: Connection monitor thread stopped")


def start_connection_monitor():
    """Start the background connection monitor thread"""
    global _connection_thread
    if _connection_thread is None or not _connection_thread.is_alive():
        _connection_stop_event.clear()
        _connection_thread = threading.Thread(target=connection_monitor, daemon=True)
        _connection_thread.start()


def stop_connection_monitor():
    """Stop the background connection monitor thread"""
    global _connection_thread
    _connection_stop_event.set()
    if _connection_thread and _connection_thread.is_alive():
        _connection_thread.join(timeout=5)


if mqtt is not None:
    start_connection_monitor()
else:
    print("MQTT: paho-mqtt not available, connection monitoring disabled")

atexit.register(on_restart)

get_settings()

publish_status()
