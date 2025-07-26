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
from sip import template_render  # Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security

try:
    import paho.mqtt.client as mqtt

    # Detect Paho MQTT version - more robust detection
    PAHO_VERSION = getattr(mqtt, '__version__', '1.0.0')

    # Also check for v2-specific features
    try:
        from paho.mqtt.client import CallbackAPIVersion

        PAHO_V2 = True
        print(f"MQTT: Detected Paho MQTT v2 via CallbackAPIVersion (reported version: {PAHO_VERSION})")
    except ImportError:
        PAHO_V2 = PAHO_VERSION.startswith('2.') if PAHO_VERSION != '1.0.0' else False
        print(f"MQTT: Detected Paho MQTT v1 (version: {PAHO_VERSION})")

    print(f"MQTT: Using Paho MQTT version {PAHO_VERSION} (v2 mode: {PAHO_V2})")
except ImportError:
    print(u"ERROR: MQTT Plugin requires paho mqtt.")
    print(u"\ttry: pip install paho-mqtt")
    print(u"or for Python 3 pip3 install paho-mqtt ")
    mqtt = None
    PAHO_V2 = False

_connection_thread = None
_connection_stop_event = threading.Event()
_client_lock = threading.Lock()
_is_connected = False
_reconnect_interval = 30  # seconds
_initial_reconnect_interval = 5
_connection_attempts = 0

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
        version_info = f"Paho MQTT {PAHO_VERSION}" if mqtt else "Not available"
        return template_render.mqtt(
            settings,
            gv.sd[u"name"],
            NO_MQTT_ERROR if mqtt is None else f"Using {version_info}",
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

    publish_status()  # Continue or restart session with the new settings


def on_message(client, userdata, msg):
    """
    Callback for MQTT data received
    Compatible with both Paho v1.x and v2.x
    """
    global _subscriptions
    topic_string = ""
    valid_topic = False

    # Extract topic from message (compatible with both versions)
    topic = msg.topic if hasattr(msg, 'topic') else str(msg.topic)

    for subscription_topic in _subscriptions:
        topic_string = subscription_topic
        if subscription_topic[-1:] == "#":
            if subscription_topic[:len(subscription_topic) - 2] == topic[:len(subscription_topic) - 2]:
                valid_topic = True
                break
            elif subscription_topic[:len(subscription_topic) - 2] == topic:
                valid_topic = True
                break
        elif subscription_topic == topic:
            valid_topic = True
            break

    if not valid_topic:
        print(u"MQTT plugin got unexpected message on topic:", topic, msg.payload)
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


def on_connect(client, userdata, flags, rc, properties=None):
    """
    Callback for successful MQTT connection
    Compatible with both Paho v1.x (4 args) and v2.x (5 args)
    """
    global _is_connected, _connection_attempts

    # Handle both v1 and v2 callback signatures
    if PAHO_V2:
        # In v2, rc is a ReasonCode object
        success = (rc.value == 0) if hasattr(rc, 'value') else (rc == 0)
        rc_value = rc.value if hasattr(rc, 'value') else rc
    else:
        # In v1, rc is an integer
        success = (rc == 0)
        rc_value = rc

    if success:
        print(f"MQTT: Connected successfully after {_connection_attempts} attempts")
        _is_connected = True
        _connection_attempts = 0  # Reset attempt counter on successful connection

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
        print(f"MQTT: Connection failed with result code {rc_value} (attempt #{_connection_attempts})")
        _is_connected = False


def on_disconnect(client, userdata, rc, properties=None):
    """
    Callback for MQTT disconnection
    Compatible with both Paho v1.x (3 args) and v2.x (4 args)
    """
    global _is_connected
    _is_connected = False

    # Handle both v1 and v2 callback signatures
    rc_value = rc.value if (PAHO_V2 and hasattr(rc, 'value')) else rc

    if rc_value == 0:
        print("MQTT: Disconnected normally")
    else:
        print(f"MQTT: Unexpected disconnection (code: {rc_value}), will attempt reconnection")


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
    global _client, _is_connected, _connection_attempts

    while not _connection_stop_event.is_set():
        try:
            with _client_lock:
                if not _is_connected and mqtt is not None:
                    _connection_attempts += 1
                    import time
                    start_time = time.time()

                    print(
                        f"MQTT: Connection attempt #{_connection_attempts} to {_settings['broker_host']}:{_settings['broker_port']} at {time.strftime('%H:%M:%S')}")

                    # Clean up old client if it exists
                    if _client is not None:
                        try:
                            _client.disconnect()
                            _client.loop_stop()
                            time.sleep(0.5)  # Brief pause for cleanup
                        except Exception as cleanup_error:
                            print(f"MQTT: Cleanup error: {cleanup_error}")
                        _client = None

                    try:
                        # Create new client - compatible with both versions
                        if PAHO_V2:
                            try:
                                from paho.mqtt.client import CallbackAPIVersion
                                client_id = f"{gv.sd[u'name']}_sip_{int(time.time())}"
                                _client = mqtt.Client(client_id=client_id,
                                                      callback_api_version=CallbackAPIVersion.VERSION1)
                                print(f"MQTT: Created v2 client with ID: {client_id}")
                            except ImportError:
                                client_id = f"{gv.sd[u'name']}_sip_{int(time.time())}"
                                _client = mqtt.Client(client_id=client_id)
                                print(f"MQTT: Created v2 fallback client with ID: {client_id}")
                        else:
                            client_id = f"{gv.sd[u'name']}_sip_{int(time.time())}"
                            _client = mqtt.Client(client_id)
                            print(f"MQTT: Created v1 client with ID: {client_id}")

                        # Set up will message
                        if _settings[u"publish_up_down"]:
                            _client.will_set(
                                _settings[u"publish_up_down"], json.dumps(u"DOWN"), qos=1, retain=True
                            )

                        # Set callbacks
                        _client.on_message = on_message
                        _client.on_connect = on_connect
                        _client.on_disconnect = on_disconnect

                        # Set credentials
                        if _settings[u"broker_username"] and _settings[u"broker_password"]:
                            _client.username_pw_set(
                                _settings[u"broker_username"], _settings[u"broker_password"]
                            )

                        # Connect
                        _client.connect(_settings[u"broker_host"], _settings[u"broker_port"], keepalive=60)
                        _client.loop_start()

                        print(
                            f"MQTT: Connection call completed in {time.time() - start_time:.3f}s, waiting for callback...")

                    except Exception as e:
                        duration = time.time() - start_time
                        print(f"MQTT connection attempt #{_connection_attempts} failed after {duration:.3f}s: {e}")
                        print(f"MQTT: Exception type: {type(e).__name__}")
                        _client = None
                        _is_connected = False

        except Exception as e:
            print(f"MQTT monitor thread error: {e}")

        # Use shorter intervals for initial connection attempts
        if _connection_attempts < 10:
            wait_time = _initial_reconnect_interval
        else:
            wait_time = _reconnect_interval

        # Wait before next check/retry
        _connection_stop_event.wait(wait_time)

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


# Initialize the plugin with startup delay
if mqtt is not None:
    import time
    import threading


    def delayed_start():
        print("MQTT: Waiting 3 seconds for other plugins to initialize...")
        time.sleep(3)
        # print("MQTT: Starting connection monitor...")
        start_connection_monitor()


    # Start in a separate thread to avoid blocking other plugins
    startup_thread = threading.Thread(target=delayed_start, daemon=True)
    startup_thread.start()
else:
    print("MQTT: paho-mqtt not available, connection monitoring disabled")

atexit.register(on_restart)

get_settings()

publish_status()