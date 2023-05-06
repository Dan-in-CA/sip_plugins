#!/usr/bin/env python

# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
import json
import subprocess
import time

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings, gv = global variables
from sip import template_render
from urls import urls  # Get access to SIP's URLs
import web
from webpages import ProtectedPage

# Add a new url to open the data entry page.
# fmt: off
urls.extend(
    [
        u"/clic", u"plugins.cli_control.settings",
        u"/clicj", u"plugins.cli_control.settings_json",
        u"/clicu", u"plugins.cli_control.update",
    ]
)
# fmt: on

# Add this plugin to the plugins menu
gv.plugin_menu.append([_(u"CLI Control"), u"/clic"])

commands = {}
prior = [0] * len(gv.srvals)

# Read in the commands for this plugin from it's JSON file
def load_commands():
    global commands
    try:
        with open(u"./data/cli_control.json", u"r") as f:
            commands = json.load(f)  # Read the commands from file
    except IOError:  #  If file does not exist create file with defaults.
        commands = {u"on": [u""] * gv.sd[u"nst"], u"off": [u""] * gv.sd[u"nst"], u"gpio": 0}
        commands[u"on"][0] = u"echo 'example start command for station 1'"
        commands[u"off"][0] = u"echo 'example stop command for station 1'"
        with open(u"./data/cli_control.json", u"w") as f:
            json.dump(commands, f, indent=4)
    return


load_commands()

if commands["gpio"]:
    gv.use_gpio_pins = False
else:
    gv.use_gpio_pins = True


#### output command when signal received ####
def on_zone_change(name, **kw):
    """ Send command when core program signals a change in station state."""
    global prior
    if gv.srvals != prior:  # check for a change
        for i in range(len(gv.srvals)):
            if gv.srvals[i] != prior[i]:  #  this station has changed
                if gv.srvals[i]:  # station is on
                    command = commands[u"on"][i]
                    if command:  #  If there is a command for this station:
                        subprocess.call(command.split())
                else:
                    command = commands[u"off"][i]
                    if command:
                        subprocess.call(command.split())
        prior = gv.srvals[:]
    return


zones = signal(u"zone_change")
zones.connect(on_zone_change)

################################################################################
# Web pages:                                                                   #
################################################################################


class settings(ProtectedPage):
    """Load an html page for entering cli_control commands"""

    def GET(self):
        return template_render.cli_control(commands)


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format"""

    def GET(self):
        web.header(u"Access-Control-Allow-Origin", u"*")
        web.header(u"Content-Type", u"application/json")
        return json.dumps(commands)


class update(ProtectedPage):
    """Save user input to cli_control.json file"""

    def GET(self):
        global commands
        qdict = web.input()
        if (
            len(commands[u"on"]) != gv.sd[u"nst"]
        ):  #  if number of stations has changed, adjust length of on and off lists
            if gv.sd[u"nst"] > len(commands[u"on"]):
                increase = [""] * (gv.sd[u"nst"] - len(commands[u"on"]))
                commands[u"on"].extend(increase)
                commands[u"off"].extend(increase)
            elif gv.sd[u"nst"] < len(commands[u"on"]):
                commands[u"on"] = commands[u"on"][: gv.sd[u"nst"]]
                commands[u"off"] = commands[u"off"][: gv.sd[u"nst"]]
        for i in range(gv.sd[u"nst"]):
            commands[u"on"][i] = qdict[u"con" + str(i)]
            commands[u"off"][i] = qdict[u"coff" + str(i)]        
        if u"gpio" in qdict:
            commands[u"gpio"] = 1
            gv.use_gpio_pins = False
        else:
            commands[u"gpio"] = 0
            gv.use_gpio_pins = True
        with open(u"./data/cli_control.json", u"w") as f:  # write the settings to file
            json.dump(commands, f, indent=4)
        raise web.seeother(u"/restart")
