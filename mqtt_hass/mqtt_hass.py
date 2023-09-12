# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
import json  # for working with data file
import uuid
import re
import slugify as unicode_slug  # python-slugify package
import socket


# local module imports
from blinker import signal  # To receive station notifications
import gv  # Get access to SIP's settings
from plugins import mqtt
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from helpers import stop_onrain  # For rain delay timer


# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
        u"/mqtt_hass-sp", u"plugins.mqtt_hass.settings",
        u"/mqtt_hass-save", u"plugins.mqtt_hass.save_settings",
    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"].
gv.plugin_menu.append([(u"MQTT HASS Plugin"), u"/mqtt_hass-sp"])



# local defines
HASS_ON = u"On"
HASS_OFF = u"Off"

HASS_MQTT_DATA_FILE = u"./data/mqtt_hass.json"
MQTT_HASS_DISCOVERY_TOPIC_PREFIX = u"homeassistant"
MQTT_HASS_SYSTEM_NAME_DEFAULT = u"sip"
MQTT_HASS_SYSTEM_ENABLE_SUB_TOPIC = u"/system/enable"

# Base MQTT settings
BASE_MQTT_BROKER_HOST = u"broker_host"
BASE_MQTT_STATE_TOPIC = u"publish_up_down"
BASE_MQTT_STATE_ON = u'"UP"'
BASE_MQTT_STATE_OFF = u'"DOWN"'

# MQTT HASS settings
MQTT_HASS_TOPIC = u"hass_sip_topic"
MQTT_HASS_TOPIC_DEFAULT = u""
MQTT_HASS_NAME = u"hass_sip_name"
MQTT_HASS_NAME_DEFAULT = u""
MQTT_HASS_SIP_FQDN = u"hass_sip_fqdn"
MQTT_HASS_SIP_FQDN_DEFAULT = u""
MQTT_HASS_DEVICE_IS_STATION_NAME = u"hass_device_is_station_name"
MQTT_HASS_DEVICE_IS_STATION_NAM_DEFAULT = HASS_OFF
MQTT_HASS_PUB_DISABLED = u"hass_pub_disabled"
MQTT_HASS_PUB_DISABLED_DEFAULT = HASS_OFF
MQTT_HASS_UUID = u"hass_uuid"
MQTT_HASS_UUID_DEFAULT = u"sip_uuid"

# local globals
_settings = {}
_settings_stored = {}
_settings_base_mqtt = {}
_sip_web_url = u""


# Helper functions
def sip_program_to_name(value):
    """Convert program number to string"""
    if value == None:
        value = u"None"
    elif value == 98:
        value = u"Run Once"
    elif value == 99:
        value = u"Manual"
    return str(value)


def get_local_ip(destination="10.255.255.255"):
    """Return the interface ip to a destination server"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect((destination, 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def is_fqdn(hostname):
    """
    https://en.m.wikipedia.org/wiki/Fully_qualified_domain_name
    """
    if not hostname:
        return False

    if not 1 < len(hostname) < 253:
        return False

    # Remove trailing dot
    if hostname[-1] == ".":
        hostname = hostname[0:-1]

    #  Split hostname into list of DNS labels
    labels = hostname.split(".")

    #  Define pattern of DNS label
    #  Can begin and end with a number or letter only
    #  Can contain hyphens, a-z, A-Z, 0-9
    #  1 - 63 chars allowed
    fqdn = re.compile(r"^[a-z0-9]([a-z-0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)

    # Check that all labels match that pattern.
    return all(fqdn.match(label) for label in labels)


def sip_web_url(host=None):
    """Return SIP web server URL"""
    # First:  Valid host setting
    if not is_fqdn(host):
        # Second: System hostname
        host = socket.getfqdn()
        if not is_fqdn(host):
            # Third : System IP used to connect with MQTT broker
            if BASE_MQTT_BROKER_HOST in _settings_base_mqtt:
                host = get_local_ip(_settings_base_mqtt[BASE_MQTT_BROKER_HOST])
    if not host:
        return None

    # Format web server URL according to SIP port
    if gv.sd["htp"] == 443:
        return "https://" + host
    elif gv.sd["htp"] == 80:
        return "http://" + host
    else:
        return "http://" + host + ":" + str(gv.sd[u"htp"])


def mqtt_topic_slugify(text):
    """Slugify a given text to a valid MQTT topic."""
    # Apply good practice MQTT topic format
    # - Translate Unicode to ASCII characters keep case
    # - No Unicode space between words use "_"
    # - No MQTT level wildcards (#, +). Not supported by SIP base MQTT plugin
    # - No leading and trailing forward slash and spaces
    if text == u"":
        return u""
    regex_pattern = r"[^-a-zA-Z0-9_/]+"
    slug = unicode_slug.slugify(text, separator="_", regex_pattern=regex_pattern)
    slug = slug.lstrip("/_").rstrip("/_")
    return slug


def hass_entity_ID_slugify(name):
    """Slugify name to HASS Entity ID format."""
    if name == u"":
        return u""
    slug = unicode_slug.slugify(name, separator="_")
    return slug


def mqtt_hass_system_name(slugify=False):
    """Return a valid System name from Options setting (Default: SIP)"""
    name = gv.sd[u"name"] if len(gv.sd[u"name"]) else MQTT_HASS_SYSTEM_NAME_DEFAULT
    if slugify:
        name = hass_entity_ID_slugify(name)
    return name


def mqtt_hass_get_setting(settings, key, slugify):
    """Return key value from setting or System name if not present"""
    value = settings.get(key, u"")
    value = value if len(value) else mqtt_hass_system_name(slugify)
    return value


class settings(ProtectedPage):
    """Load an html page for entering plugin settings."""

    def GET(self):
        settings = _settings_stored
        return template_render.mqtt_hass(settings, u"")  # open settings page


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):
        global _settings_stored
        qdict = (
            web.input()
        )  # Dictionary of values returned as query string from settings page.

        qdict[MQTT_HASS_TOPIC] = mqtt_topic_slugify(qdict[MQTT_HASS_TOPIC])

        if not is_fqdn(qdict[MQTT_HASS_SIP_FQDN]):
            qdict[MQTT_HASS_SIP_FQDN] = MQTT_HASS_SIP_FQDN_DEFAULT

        qdict[MQTT_HASS_PUB_DISABLED] = (
            HASS_ON if MQTT_HASS_PUB_DISABLED in qdict else HASS_OFF
        )

        qdict[MQTT_HASS_DEVICE_IS_STATION_NAME] = (
            HASS_ON if MQTT_HASS_DEVICE_IS_STATION_NAME in qdict else HASS_OFF
        )

        _settings_stored.update(qdict)
        write_settings()
        hass.notify_mqtt_hass_settings_change()  # process new plugin settings
        raise web.seeother(u"/")  # Return user to home page.


def write_settings():
    with open(HASS_MQTT_DATA_FILE, u"w") as f:
        json.dump(_settings_stored, f, indent=4, sort_keys=True)  # save to file


def read_settings():
    global _settings_stored
    try:
        fh = open(HASS_MQTT_DATA_FILE, "r")
        try:
            _settings_stored = json.load(fh)
        except ValueError as e:
            print(u"MQTT HASS pluging couldn't parse data file:", e)
        finally:
            fh.close()
    except IOError as e:
        print(u"MQTT HASS Plugin couldn't open data file:", e)
    return


# MQTT HASS base class
class mqtt_hass_base:
    """
    MQTT HASS base class.
    Base functions for MQTT discovery (HASS feature), state publish and state subscription
    """

    def __init__(
        self,
        name=None,
        component=None,
        category=None,
        options={},
        icon=None,
        min=None,
        max=None,
        unit=None,
    ):
        self._name = name
        self._component = component
        self._category = category
        self._options = options
        self._icon = icon
        self._min = min
        self._max = max
        self._unit = unit

        self._value = None
        self._json_state = True

        self.discovery_topic = self.discovery_topic_get()
        self.state_topic = self.state_topic_get()
        self.set_topic = self.set_topic_get()
        self.availability_topic = self.availability_topic_get()

        return

    def _system_version(self):
        """SIP version and date"""
        return gv.ver_str + u" " + gv.ver_date

    def _system_UID(self):
        """SIP UUID based on the network adapter MAC address"""
        return _settings[MQTT_HASS_UUID]

    def _system_web_url(self):
        """URL to access SIP web user interface.
        Redirection displayed in HASS devices user interface options"""
        return _sip_web_url

    def _publish(self, topic, payload=u""):
        """
        MQTT publish helper function.
        Publish dictionary as JSON
        """
        client = mqtt.get_client()
        if client:
            if isinstance(payload, dict):
                payload = json.dumps(payload, sort_keys=True)

            client.publish(topic, payload, qos=1, retain=True)

    def _publish_disabled(self):
        """Return True if publish and control is disabled"""
        return False

    def update_settings(self, force_enable=False):
        """Update topics and discovery according to MQTT HASS settings"""
        availability_topic = self.availability_topic_get()
        set_topic = self.set_topic_get()
        state_topic = self.state_topic_get()

        if availability_topic != self.availability_topic or force_enable:
            self.availability_unpublish(force_enable)
            self.availability_topic = availability_topic
            self.availability_publish()

        if set_topic != self.set_topic or force_enable:
            self.set_unsubscribe(force_enable)
            self.set_topic = set_topic
            self.set_subscribe()

        if state_topic != self.state_topic or force_enable:
            self.state_unpublish(force_enable)
            self.state_topic = state_topic
            self.state_publish(force_enable=False, force_update=True)

        if force_enable:
            self.discovery_unpublish(force_enable)
        self.discovery_publish()

    def sip_set_value(self, value):
        """
        Set SIP parameter according to value
        Stub. To be implemented in children class
        """
        return

    def sip_get_value(self):
        """
        Return processed value from SIP parameter
        Stub. To be implemented in children class
        """
        return

    def device_name(self):
        """
        HASS Device name
        To be supplemented by children class
        """
        return _settings[MQTT_HASS_NAME]

    def device_uid(self):
        """
        HASS Device unique ID
        Default to System UID.
        """
        return self._system_UID()

    def entity_name(self):
        """
        HASS slugified Entity name
        To be supplemented by children class
        """
        return ""

    def entity_uid(self):
        """
        HASS slugified Entity ID
        Stub. To be implemented in children class
        """
        return

    def start_publish(self, force_update=False):
        """
        MQTT actions to publish discovery, state and subcribe
        force = True will resend previous state value
        """
        self.state_publish(force_update=force_update)
        self.availability_publish()
        self.discovery_publish()
        self.set_subscribe()

    def stop_publish(self):
        """MQTT actions to remove discovery, state and subcribe"""
        self.set_unsubscribe()
        self.discovery_unpublish()
        self.availability_unpublish()
        self.state_unpublish()

    def discovery_topic_get(self):
        """Return HASS Discovery topic for the entity"""
        return (
            MQTT_HASS_DISCOVERY_TOPIC_PREFIX
            + u"/"
            + self._component
            + u"/"
            + self.entity_uid()
            + u"/"
            + self._component
            + u"/config"
        )

    def discovery_payload(self):
        """Compose HASS discovery payload"""
        payload = {}

        # Entity basic attributes
        payload.update(
            {
                u"icon": self._icon,
                u"json_attributes_topic": self.state_topic,
                u"name": self.entity_name(),
                u"state_topic": self.state_topic,
                u"unique_id": self.entity_uid(),
                u"value_template": self.state_value_template(),
            }
        )

        # Entity availability state depending on other entities or topic values
        payload[u"availability_mode"] = u"all"
        payload[u"availability"] = []
        if _settings_base_mqtt[BASE_MQTT_STATE_TOPIC]:
            payload["availability"].append(
                {  # Status of base MQTT
                    u"topic": _settings_base_mqtt[BASE_MQTT_STATE_TOPIC],
                    u"payload_available": BASE_MQTT_STATE_ON,
                    u"payload_not_available": BASE_MQTT_STATE_OFF,
                }
            )
        if (
            self.state_topic
            != _settings[MQTT_HASS_TOPIC] + MQTT_HASS_SYSTEM_ENABLE_SUB_TOPIC
        ):
            payload[u"availability"].append(
                {  # Status of SIP System Enable state
                    u"topic": _settings[MQTT_HASS_TOPIC]
                    + MQTT_HASS_SYSTEM_ENABLE_SUB_TOPIC,
                    u"payload_available": HASS_ON,
                    u"payload_not_available": HASS_OFF,
                    u"value_template": "{{ value_json.state }}",
                }
            )

        # Device attributes
        payload[u"device"] = {
            u"identifiers": [self.device_uid()],
            u"manufacturer": "SIP",
            u"model": "controler",
            u"name": self.device_name(),
            u"sw_version": self._system_version(),
            u"configuration_url": self._system_web_url(),
        }

        # Device vs Entity relation
        if self._category:
            payload[u"entity_category"] = self._category

        # Entity component specific attributes
        if self._component == u"select":
            payload[u"options"] = list(self._options.keys())
            payload[u"command_topic"] = self.set_topic

        elif self._component == u"number":
            payload[u"min"] = self._min
            payload[u"max"] = self._max
            payload[u"command_topic"] = self.set_topic
            if self._unit:
                payload[u"unit_of_measurement"] = self._unit

        elif self._component == u"switch":
            payload[u"command_topic"] = self.set_topic
            payload[u"payload_off"] = HASS_OFF
            payload[u"payload_on"] = HASS_ON

        elif self._component == u"binary_sensor":
            payload[u"payload_off"] = HASS_OFF
            payload[u"payload_on"] = HASS_ON

        elif self._component == u"sensor":
            if self._unit:
                payload[u"unit_of_measurement"] = self._unit

        return payload

    def discovery_publish(self, force_enable=False):
        """Publish MQTT HASS Discovery config to HASS"""
        payload = self.discovery_payload()
        self._publish(self.discovery_topic, payload)

    def discovery_unpublish(self, force_enable=False):
        """Remove MQTT HASS Discovery config"""
        self._publish(self.discovery_topic)

    def state_topic_get(self):
        """Return entity state MQTT topic"""
        return _settings[MQTT_HASS_TOPIC] + "/" + self._name

    def state_value_template(self):
        """Return state value decoding template"""
        if self._json_state:
            return "{{ value_json.state }}"
        return "{{ value }}"

    def state_publish(self, force_enable=False, force_update=False):
        """
        Publish system value if updated
        force = True will republish the value
        """
        value = self.get_sip_value()

        # Don't publish the same value
        if value == self._value and not force_update:
            return
        self._value = value
        if self._json_state:
            payload = {}
            payload[u"state"] = value
        else:
            payload = value
        self._publish(self.state_topic, payload)

    def state_unpublish(self, force_enable=False):
        """Remove published state topic from the MQTT broker"""
        self._publish(self.state_topic)

    def availability_topic_get(self):
        """
        Return entity state MQTT topic
        Stub. To be implemented by children class
        """
        return

    def availability_publish(self, force_enable=False):
        """
        Publish entity specific availability
        Stub. To be implemented by children class
        """
        return

    def availability_unpublish(self, force_enable=False):
        """
        Remove published entity availability topic from the MQTT broker
        Stub. To be implemented by children class
        """
        return

    def set_topic_get(self):
        """Return MQTT listening topic to set internal SIP state"""
        return self.state_topic_get() + u"/set"

    def set_subscribe(self, force_enable=False):
        """Start listening to MQTT messages"""
        if self._component in [u"sensor", u"binary_sensor"]:
            return
        mqtt.subscribe(self.set_topic, self.set_incoming_message)

    def set_unsubscribe(self, force_enable=False):
        """Stop listening to MQTT messages"""
        if self._component in [u"sensor", u"binary_sensor"]:
            return
        mqtt.unsubscribe(self.set_topic)
        self._publish(self.set_topic)  # Clear set topic

    def set_incoming_message(self, client, msg):
        """
        Callback when MQTT message is received from the MQTT broker
        Stub. To be implemented by children class
        """
        return


# MQTT HASS system parameter classes
class mqtt_hass_system_param(mqtt_hass_base):
    """
    MQTT HASS class for SIP system parameter in gv.sd[]
    Each paramater is a single HASS Entity
    A single HASS Device regroup all parameters (Entities)
    """

    def __init__(
        self,
        name=None,
        component=None,
        category=None,
        options={},
        icon=u"mdi:application-cog-outline",
        min=None,
        max=None,
        unit=None,
        gv_sd=None,
    ):
        super().__init__(
            name=name,
            component=component,
            category=category,
            options=options,
            icon=icon,
            min=min,
            max=max,
            unit=unit,
        )
        self._gv_sd = gv_sd
        if self._component == u"binary_sensor":
            self._options = {HASS_OFF: 0, HASS_ON: 1}

    def set_sip_value(self, value):
        """Set SIP setting according to direct value or key name in option{}"""
        if self._component == u"number":
            if value.isdigit():
                gv.sd[self._gv_sd] = int(value)

        elif self._component == u"select":
            if value in self._options:
                gv.sd[self._gv_sd] = self._options[value]

    def get_sip_value(self):
        "According to SIP setting, return direct value or corresponding option key name"
        if self._gv_sd == None:
            return None
        s = gv.sd[self._gv_sd]
        if self._component in [u"select", u"binary_sensor"]:
            for option, state in self._options.items():
                if state == s:
                    return option
        return s

    def entity_name(self):
        """System parameter entity name"""
        """Parameter name - HA discovery will prepend device name"""
        return self._name

    def entity_uid(self):
        """System parameter entity UID"""
        return self._system_UID() + "_" + self._name

    def state_topic_get(self):
        """System parameter Entity state topic"""
        return _settings[MQTT_HASS_TOPIC] + "/system/" + self._name

    def set_incoming_message(self, client, msg):
        """Callback when MQTT set message is received from MQTT broker."""
        if self._component not in [u"select", u"number"]:
            return

        try:
            cmd = json.loads(msg.payload)
            # decode command as json
            if type(cmd) is dict:
                if u"state" not in cmd:
                    return
                value = str(cmd[u"state"])
            else:
                value = msg.payload.decode("utf-8")

        except ValueError as e:
            # decode direct command
            value = msg.payload.decode("utf-8")

        value = value.strip().capitalize()

        if value == self._value:
            return

        self.set_sip_value(value)
        self.state_publish()


class mqtt_hass_rain_delay_timer(mqtt_hass_system_param):
    """MQTT HASS system setting for rain delay timer (gv.sd[u"rd"])"""

    def __init__(self):
        super().__init__(
            name=u"rain_delay_timer",
            component=u"number",
            category=u"config",
            icon=u"mdi:timer-cog-outline",
            min=0,
            max=24,
            unit=u"h",
        )
        self._sd_param = u"rd"
        self._json_state = True

    def get_sip_value(self):
        return gv.sd[self._sd_param]

    def set_sip_value(self, value):
        """Set SIP settings for rain delay timer according to direct value"""
        if value.isdigit():
            gv.sd[self._sd_param] = int(value)
            gv.sd[u"rdst"] = int(gv.now + gv.sd[self._sd_param] * 3600)
            stop_onrain()

    def state_publish(self, force_update=False):
        """
        Publish system value if updated
        force = True will republish the value
        """
        value = self.get_sip_value()

        # Don't publish the same value
        if value == self._value and not force_update:
            return
        self._value = value
        duration = gv.sd[self._sd_param] * 3600
        if duration:
            start_time = gv.sd[u"rdst"]
        else:
            start_time = "None"

        payload = {
            "state": value,
            "start_time": start_time,
            "duration": duration,
        }
        self._publish(self.state_topic, payload)


class mqtt_hass_running_program(mqtt_hass_system_param):
    """MQTT HASS system sensor for running program number (gv.pon)"""

    def __init__(self):
        super().__init__(
            name=u"running_program",
            component=u"sensor",
            category=u"diagnostic",
            icon=u"mdi:application-outline",
        )
        self._value = -1  # Default gv.pon = None

    def get_sip_value(self):
        """Return running program number or name"""
        return sip_program_to_name(gv.pon)


# MQTT HASS zone class
class mqtt_hass_zone(mqtt_hass_base):
    """
    MQTT HASS class for SIP zones
    Each zone is a distinct HASS Device with a single switch Entity
    """

    def __init__(self, index):
        self._index = index
        self._enable = self._get_enable_option()
        self._json_state = True
        super().__init__(
            name=self._get_name_option(),
            component=u"switch",
            category=None,  # Control
            options={HASS_OFF: 0, HASS_ON: 1},
            icon=u"mdi:water",
        )
        self._json_state = True

    def _publish_disabled(self, force_enable=False):
        """
        Return if zone publish and control is disabled
        Don't publish disabled zones unless override by MQTT HASS option
        """
        if force_enable:
            return False

        if _settings[MQTT_HASS_PUB_DISABLED] == HASS_OFF and self._enable == 0:
            return True
        else:
            return False

    def _get_enable_option(self):
        """Return zone enable state"""
        bid = int(self._index / 8)
        s = self._index % 8
        return (gv.sd[u"show"][bid] >> s) & 1

    def _get_name_option(self):
        return gv.snames[self._index]

    def update_options(self):
        """Updated zone name and enable option"""
        ZONE_RESTART = 1
        ZONE_DISCOVERY = 2
        update = None

        name = self._get_name_option()
        if name != self._name:
            self._name = name
            update = ZONE_DISCOVERY

        enable = self._get_enable_option()
        if enable != self._enable:
            update = ZONE_RESTART

        if update == ZONE_RESTART:
            self.stop_publish()
            self._enable = enable
            self.start_publish(force_update=True)
        elif update == ZONE_DISCOVERY:
            self.discovery_publish()

    def set_sip_value(self, value):
        """Set SIP zone state according to options name"""
        if value in self._options:
            gv.srvals[self._index] = self._options[value]
        return

    def get_sip_value(self):
        """Return SIP zone state name according to options"""
        sip_state = gv.srvals[self._index]
        for value, state in self._options.items():
            if state == sip_state:
                return value
        return None

    def device_name(self):
        """Return zone Device name"""
        if _settings[MQTT_HASS_DEVICE_IS_STATION_NAME] == HASS_ON:
            return super().device_name() + u" - " + self._name
        else:
            return super().device_name() + u" Z" + u"{0:02d}".format(self._index + 1)

    def device_uid(self):
        """Return zone Device UID"""
        return self._system_UID() + "_Z" + "{0:02d}".format(self._index + 1)

    def entity_name(self):
        """Return zone switch Entity name"""
        """Empty - HA discovery default to device name for device with single entity"""
        return ""

    def entity_uid(self):
        """Return zone Entity UID"""
        return self._system_UID() + "_Z" + "{0:02d}".format(self._index + 1)

    def discovery_payload(self):
        """Return zone HASS Discovery configuration attributes"""
        payload = super().discovery_payload()
        payload["availability"].append(
            {
                "topic": self.state_topic + u"/availability",
                "payload_available": u"online",
                "payload_not_available": u"offline",
            }
        )
        payload["device"]["via_device"] = self._system_UID()
        return payload

    def discovery_publish(self, force_enable=False):
        """Publish HASS Discovery configuration for enabled zones"""
        if self._publish_disabled(force_enable):
            return
        return super().discovery_publish()

    def discovery_unpublish(self, force_enable=False):
        """Publish HASS Discovery configuration for enabled zones"""
        if self._publish_disabled(force_enable):
            return
        return super().discovery_unpublish()

    def state_topic_get(self):
        """Return zone MQTT state topic"""
        return _settings[MQTT_HASS_TOPIC] + "/zone/" + "{0:02d}".format(self._index + 1)

    def state_publish(self, force_enable=False, force_update=False):
        """
        Publish zone state only if changed unless forces to do it
        Attributes includes state, start time, total duration in seconds and the program that trigered the state "ON" """
        if self._publish_disabled(force_enable):
            return

        value = self.get_sip_value()

        if value == self._value and not force_update:
            return

        self._value = value
        if value == HASS_ON:
            start_time = gv.rs[self._index][0]
            duration = gv.rs[self._index][2]
            if duration == float(u"inf") or duration == 0:
                duration = u"inf"
            program = sip_program_to_name(gv.rs[self._index][3])
        else:
            start_time = u"None"
            duration = u"inf"
            program = u"None"

        payload = {
            u"state": value,
            u"start_time": start_time,
            u"duration": duration,
            u"program": program,
        }
        self._publish(self.state_topic, payload)

    def state_unpublish(self, force_enable=False):
        """Remove zone state from MQTT broker"""
        if self._publish_disabled(force_enable):
            return
        super().state_unpublish()

    def availability_topic_get(self):
        """Return zone availability topic"""
        return self.state_topic_get() + "/availability"

    def availability_publish(self, force_enable=False):
        """Publish zone availability matching enabled state"""
        if self._publish_disabled(force_enable):
            return

        payload = "online" if self._get_enable_option() else "offline"
        self._publish(self.availability_topic, payload)

    def availability_unpublish(self, force_enable=False):
        """Remove zone availability from MQTT broker"""
        if self._publish_disabled(force_enable):
            return
        self._publish(self.availability_topic)

    def set_subscribe(self, force_enable=False):
        """Listen to zone state change requests"""
        if self._publish_disabled(force_enable):
            return
        super().set_subscribe()

    def set_unsubscribe(self, force_enable=False):
        """Stop listening to zone state change requests"""
        if self._publish_disabled(force_enable):
            return
        super().set_unsubscribe()

    def set_incoming_message(self, client, msg):
        """Process MQTT received zone set messages."""
        # Don't execute if system is disabled
        if gv.sd[u"en"] == 0:
            return

        duration = 0
        try:
            cmd = json.loads(msg.payload)
        except ValueError as e:
            # decode direct command
            state = msg.payload.decode("utf-8")
        else:
            # decode command as json
            if u"state" in cmd:
                state = str(cmd[u"state"])
            if u"duration" in cmd:
                duration = int(cmd[u"duration"])

        state = state.strip().capitalize()
        index = self._index
        # set station to run
        if state != self.get_sip_value():
            if state == HASS_ON:
                # Start station
                gv.rs[index][0] = gv.now
                if duration:
                    gv.rs[index][1] = gv.now + duration
                    gv.rs[index][2] = duration
                    gv.rs[index][3] = 98  # Run Once
                else:

                    gv.rs[index][1] = float(u"inf")
                    gv.rs[index][2] = float(u"inf")
                    gv.rs[index][3] = 98  # Run Once
            elif state == HASS_OFF:
                # Stop station
                gv.rs[index][1] = gv.now

        # Execute
        if any(gv.rs):
            gv.sd[u"bsy"] = 1


# MQTT HASS SIP integration class
class mqtt_hass_to_sip:
    """MQTT HASS plugin SIP integration"""

    def __init__(self):
        """Initialize MQTT HASS plugin components"""
        self._system = {}
        self._zone = {}

        # Init base mqtt settings
        self.apply_base_mqtt_settings(init=True)

        # Init global settings
        self.apply_hass_settings(init=True)

        # Init system parameters and sensors
        self.system_init()

        # Init zones
        self.zone_init()

    def apply_base_mqtt_settings(self, init=False):
        """Initialize MQTT HASS plugin options from saved setting in mqtt_hass.json"""
        global _settings_base_mqtt

        _settings_base_mqtt = mqtt.get_settings()
        base_topic = _settings_base_mqtt.get(BASE_MQTT_STATE_TOPIC, u"")
        if base_topic != _settings_base_mqtt[BASE_MQTT_STATE_TOPIC]:
            _settings_base_mqtt[BASE_MQTT_STATE_TOPIC] = base_topic
            if not init:
                self.system_discovery_publish()
                self.zone_discovery_publish()

    def apply_hass_settings(self, init=False):
        """Initialize MQTT HASS plugin options from saved setting in mqtt_hass.json"""
        global _settings
        global _settings_stored
        global _sip_web_url

        if init:
            read_settings()

        if init and MQTT_HASS_UUID not in _settings_stored:
            _settings_stored[MQTT_HASS_UUID] = hex(uuid.getnode())
            write_settings()

        _settings[MQTT_HASS_UUID] = _settings_stored.get(
            MQTT_HASS_UUID, MQTT_HASS_UUID_DEFAULT
        )

        _settings[MQTT_HASS_TOPIC] = mqtt_hass_get_setting(
            _settings_stored, key=MQTT_HASS_TOPIC, slugify=True
        )

        _settings[MQTT_HASS_NAME] = mqtt_hass_get_setting(
            _settings_stored, key=MQTT_HASS_NAME, slugify=False
        )

        _settings[MQTT_HASS_SIP_FQDN] = _settings_stored.get(
            MQTT_HASS_SIP_FQDN, MQTT_HASS_SIP_FQDN_DEFAULT
        )

        _sip_web_url = sip_web_url(_settings[MQTT_HASS_SIP_FQDN])

        pub_disabled = _settings_stored.get(
            MQTT_HASS_PUB_DISABLED, MQTT_HASS_PUB_DISABLED_DEFAULT
        )
        if MQTT_HASS_PUB_DISABLED in _settings.keys():
            force_enable = (
                True if pub_disabled != _settings[MQTT_HASS_PUB_DISABLED] else False
            )
        else:
            force_enable = False
        _settings[MQTT_HASS_PUB_DISABLED] = pub_disabled

        _settings[MQTT_HASS_DEVICE_IS_STATION_NAME] = _settings_stored.get(
            MQTT_HASS_DEVICE_IS_STATION_NAME,
            MQTT_HASS_DEVICE_IS_STATION_NAM_DEFAULT,
        )

        self.system_update_settings()
        self.zone_update_settings(force_enable)

    # System parameters - helper functions
    def system_init(self):
        """Initialize supported system parameters, sensors and start interactions with MQTT broker and HASS"""
        self._system[u"enable"] = mqtt_hass_system_param(
            name=u"enable",
            component=u"select",
            category=None,  # Control
            gv_sd=u"en",
            options={HASS_OFF: 0, HASS_ON: 1},
        )

        self._system[u"mode"] = mqtt_hass_system_param(
            name=u"mode",
            component=u"select",
            category=u"config",
            gv_sd=u"mm",
            options={u"Automatic": 0, u"Manual": 1},
        )

        self._system[u"rain_sensor_enable"] = mqtt_hass_system_param(
            name=u"rain_sensor_enable",
            component=u"select",
            category=u"config",
            gv_sd=u"urs",
            options={HASS_OFF: 0, HASS_ON: 1},
        )

        self._system[u"rain_delay_timer"] = mqtt_hass_rain_delay_timer()

        self._system[u"water_level_adjust"] = mqtt_hass_system_param(
            name=u"water_level_adjust",
            component=u"number",
            category=u"config",
            gv_sd=u"wl",
            icon=u"mdi:car-coolant-level",
            min=0,
            max=100,
            unit=u"%",
        )

        self._system[u"rain_detect"] = mqtt_hass_system_param(
            name=u"rain_detect",
            component=u"binary_sensor",
            category=u"diagnostic",  # Sensor
            gv_sd=u"rs",
            options=({HASS_OFF: 0, HASS_ON: 1}),
            icon=u"mdi:weather-rainy",
        )

        self._system[u"running_program"] = mqtt_hass_running_program()

        self.system_start_publish()

    def system_discovery_publish(self):
        """Publish system parameters Discovery configuraton to HASS"""
        for k in self._system.keys():
            self._system[k].discovery_publish()

    def system_start_publish(self):
        """Start publishing system parameters state to MQTT"""
        for k in self._system.keys():
            self._system[k].start_publish(force_update=True)

    def system_stop_publish(self):
        """Stop publishing and clear system parameters state to MQTT"""
        for k in self._system.keys():
            self._system[k].stop_publish()

    def system_update_settings(self):
        """Update system parameters state to MQTT"""
        for k in self._system.keys():
            self._system[k].update_settings()

    # Zones - helper functions
    def zone_init(self):
        """Initialize zones and start interactions with MQTT broker and HASS"""
        # zones : MQTT HASS switches with timer attribute
        nb_zones = int(gv.sd[u"nbrd"] * 8)
        for k in range(nb_zones):
            self._zone[k] = mqtt_hass_zone(k)
        self.zone_start_publish()

    def zone_discovery_publish(self):
        """Publish zones Discovery configuraton to HASS"""
        for k in self._zone.keys():
            self._zone[k].discovery_publish()

    def zone_start_publish(self):
        """Start publishing zones state change to MQTT"""
        for k in self._zone.keys():
            self._zone[k].start_publish(force_update=True)

    def zone_stop_publish(self):
        """Stop publishing and clear zone state to MQTT"""
        for k in self._zone.keys():
            self._zone[k].stop_publish()

    def zone_update_settings(self, force_enable):
        """Stop publishing and clear zone state to MQTT"""
        for k in self._zone.keys():
            self._zone[k].update_settings(force_enable)

    # Handle system signaling - changes coming from SIP
    def notify_mqtt_hass_settings_change(self):
        """Handle MQTT HASS plugin options changed (from Web page)"""
        self.apply_hass_settings()

    def notify_base_mqtt_settings_change(self, name, **kw):
        """Handle base MQTT plugin options changed (from Web page)"""
        self.apply_base_mqtt_settings()

    def notify_system_settings_change(self, name, **kw):
        """Handle SIP Settings changed (from web page)"""
        # Do nothing on HTTP port or HTTP IP addr changed.  SIP will reboot.
        global _settings
        global _sip_web_url

        # System name changed -> adjust MQTT topic and HASS name prefix
        _settings[MQTT_HASS_TOPIC] = mqtt_hass_get_setting(
            _settings_stored, key=MQTT_HASS_TOPIC, slugify=True
        )
        _settings[MQTT_HASS_NAME] = mqtt_hass_get_setting(
            _settings_stored, key=MQTT_HASS_NAME, slugify=False
        )

        # Check change to gv.sd[u"htp"] -> Update discovery
        _sip_web_url = sip_web_url()

        # Number of zones changed
        nb_zones_new = gv.sd[u"nst"]
        nb_zones = len(self._zone)
        if nb_zones_new < nb_zones:
            for k in range(nb_zones_new, nb_zones):
                if k in self._zone:
                    self._zone[k].stop_publish()
                    del self._zone[k]
        elif nb_zones_new > nb_zones:
            for k in range(nb_zones, nb_zones_new):
                self._zone[k] = mqtt_hass_zone(k)
                self._zone[k].start_publish()

        # For all remaining zones
        for k in range(0, min(nb_zones_new, nb_zones)):
            self._zone[k].update_settings()

        # For all system settings zones
        for k in self._system.keys():
            self._system[k].update_settings()

        # Rain sensor logic
        self._system[u"rain_sensor_enable"].start_publish()

    def notify_system_options_change(self, name, **kw):
        """Handle SIP options from main web page"""
        for k in [u"enable", u"mode", u"rain_delay_timer", u"water_level_adjust"]:
            self._system[k].state_publish()

    def notify_rain_change(self, name, **kw):
        """Handle Rain sensor state change"""
        self._system[u"rain_detect"].state_publish()

    def notify_rain_delay_change(self, name, **kw):
        """Handle Rain delay timer change from main web page"""
        self._system[u"rain_delay_timer"].state_publish()

    def notify_running_program_change(self, name, **kw):
        """Handle Running program number change"""
        self._system[u"running_program"].state_publish()

    def notify_zones_options_change(self, name, **kw):
        """Handle Station names changed in gv.snames[nb_zones]"""
        for k in self._zone.keys():
            self._zone[k].update_options()

    def notify_zone_states_change(self, name, **kw):
        """Handle Zone(s) state changed"""
        for k in self._zone.keys():
            self._zone[k].state_publish()

    def notify_restart_before(self, name, **kw):
        """Handle System shutdown"""
        return

    def notify_restart_after(self, name, **kw):
        """Handle System restart"""
        return


# start MQTT HASS
hass = mqtt_hass_to_sip()

### Subscribe MQTT HASS to SIP system notifications
option_change = signal(u"option_change")
option_change.connect(hass.notify_system_settings_change)

mqtt_settings_change = signal(u"mqtt_settings_change")
mqtt_settings_change.connect(hass.notify_base_mqtt_settings_change)

value_change = signal(u"value_change")
value_change.connect(hass.notify_system_options_change)

rain_change = signal(u"rain_changed")
rain_change.connect(hass.notify_rain_change)

rain_delay_change = signal(u"rain_delay_change")
rain_delay_change.connect(hass.notify_rain_delay_change)

running_program_change = signal(u"running_program_change")
running_program_change.connect(hass.notify_running_program_change)

zone_names = signal(u"station_names")
zone_names.connect(hass.notify_zones_options_change)

zones_change = signal(u"zone_change")
zones_change.connect(hass.notify_zone_states_change)

rebooted = signal(u"rebooted")
rebooted.connect(hass.notify_restart_after)

restart = signal(u"restart")
restart.connect(hass.notify_restart_before)
