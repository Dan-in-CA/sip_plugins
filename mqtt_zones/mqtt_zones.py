# !/usr/bin/env python
from __future__ import print_function
""" SIP plugin uses mqtt plugin to broadcast station status every time it changes.
"""
__author__ = "Daniel Casner <daniel@danielcasner.org>"

import web  # web.py framework
import gv  # Get access to SIP's settings
from urls import urls  # Get access to SIP's URLs
from sip import template_render  #  Needed for working with web.py templates
from webpages import ProtectedPage  # Needed for security
from blinker import signal # To receive station notifications
import json  # for working with data file
from plugins import mqtt

# Add new URLs to access classes in this plugin.
urls.extend([
    '/zone2mqtt-sp', 'plugins.mqtt_zones.settings',
    '/zone2mqtt-save', 'plugins.mqtt_zones.save_settings'
    ])
gv.plugin_menu.append(['MQTT zone broadcaster', '/zone2mqtt-sp'])

class settings(ProtectedPage):
    """Load an html page for entering plugin settings.
    """
    def GET(self):
        settings = mqtt.get_settings()
        zone_topic = settings.get('zone_topic', gv.sd[u'name'] + '/zones')
        return template_render.mqtt_zones(zone_topic, "")  # open settings page

class save_settings(ProtectedPage):
    """Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """
    def GET(self):
        qdict = web.input()  # Dictionary of values returned as query string from settings page.
        settings = mqtt.get_settings()
        settings.update(qdict)
        with open(mqtt.DATA_FILE, 'w') as f:
            json.dump(settings, f) # save to file
        raise web.seeother('/')  # Return user to home page.

### valves ###
def notify_zone_change(name, **kw):
    names = gv.snames
    mas = gv.sd['mas']
    vals = gv.srvals
    payload = {
        'zone_list': vals,
        'zone_dict': {name: status for name, status in zip(names, vals)},
        'master_on': 0 if mas == 0 else vals[mas-1]
    }
    zone_topic = mqtt.get_settings().get('zone_topic')
    if zone_topic:
        client = mqtt.get_client()
        if client:
            client.publish(zone_topic, json.dumps(payload), qos=1, retain=True)

zones = signal('zone_change')
zones.connect(notify_zone_change)
