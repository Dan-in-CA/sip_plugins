# !/usr/bin/env python

from __future__ import print_function
""" SIP plugin uses mqtt plugin to receive station status data over MQTT and control local stations
"""
__author__ = "Orginally written by Daniel Casner <daniel@danielcasner.org> Modified from mqtt_schedule by Dan K."

import web  # web.py framework
import gv  # Get access to SIP's settings
from urls import urls  # Get access to SIP's URLs
from sip import template_render  #  Needed for working with web.py templates
from webpages import ProtectedPage  # Needed for security
# # from gpio_pins import set_output
import json  # for working with data file
from plugins import mqtt
from time import sleep

DATA_FILE = "./data/mqtt.json"

# Add new URLs to access classes in this plugin.
urls.extend([
    '/mr2-sp', 'plugins.mqtt_slave.settings',
    '/mr2-save', 'plugins.mqtt_slave.save_settings'
    ])
gv.plugin_menu.append(['MQTT slave', '/mr2-sp'])

class settings(ProtectedPage):
    """Load an html page for entering plugin settings.
    """
    def GET(self):
        settings = mqtt.get_settings()
        settings['control_topic'] = '' 
        settings['first_station'] = ''
        settings['station_count'] = ''
        return template_render.mqtt_slave(settings, "")  # open settings page

class save_settings(ProtectedPage):
    """Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """
    def GET(self):
        qdict = web.input()  # Dictionary of values returned as query string from settings page.
        settings = mqtt.get_settings()
        settings.update(qdict)
        with open(DATA_FILE, 'w') as f:
            json.dump(settings, f, indent=4, sort_keys=True) # save to file
        subscribe()
        raise web.seeother('/')  # Return user to home page.

def on_message(client, msg):
    "Callback when MQTT message is received."
    if not gv.sd['en']: # check operation status
        return
    
    num_brds = gv.sd['nbrd']
    num_sta  = num_brds * 8
    try:
        cmd = json.loads(msg.payload)
    except ValueError as e:
        print("MQTT Slave could not decode command: ", msg.payload, e)
        return
    
    zones = cmd['zone_list'] #  list of all zones sent from master
    first = int(mqtt.get_settings().get('first_station')) - 1
    count = int(mqtt.get_settings().get('station_count'))
    local_zones = zones[first : first + count] 
    for i in range(len(local_zones)):
        if (local_zones[i]   # if this element has a value and is not on
            and not gv.srvals[i]
            ):
            gv.rs[i][0] = gv.now
            gv.rs[i][1] = float('inf')
            gv.rs[i][3] = 99
            gv.ps[i][0] = 99 
        elif (gv.srvals[i]
            and not local_zones[i]
            ):
            gv.rs[i][1] = gv.now
    if any(gv.rs):
        gv.sd['bsy'] = 1
    sleep(1)
    
def subscribe():
    "Subscribe to messages"
    topic = mqtt.get_settings().get('control_topic')
    if topic:
        mqtt.subscribe(topic, on_message, 2)

subscribe()
