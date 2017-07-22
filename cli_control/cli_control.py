#!/usr/bin/env python

from blinker import signal

# import urllib
# import urllib2

import subprocess
import web, json, time
import gv  # Get access to sip's settings, gv = global variables
from urls import urls  # Get access to sip's URLs
from sip import template_render
from webpages import ProtectedPage

gv.use_gpio_pins = False  # Signal sip to not use GPIO pins


# Add a new url to open the data entry page.
urls.extend(['/clic', 'plugins.cli_control.settings',
	'/clicj', 'plugins.cli_control.settings_json',
	'/clicu', 'plugins.cli_control.update']) 

# Add this plugin to the plugins menu
gv.plugin_menu.append(['CLI Control', '/clic'])

commands = {}
prior = [0] * len(gv.srvals)

# Read in the parameters for this plugin from it's JSON file
def load_params():
    global commands
    try:
        with open('./data/cli_control.json', 'r') as f:  # Read the settings from file
            commands = json.load(f)
    except IOError: #  If file does not exist create file with defaults.
        commands = {
    "on": [
    	"echo 'example start command for station1'",
    	"",
    	"",
    	"",
    	"",
    	"",
    	"",
    	"" 
    ], 
    "off": [
    	"echo 'example stop command for station 1'",
    	"",
    	"",
    	"",
    	"",
    	"",
    	"",
    	""     
    ]
}
        with open('./data/cli_control.json', 'w') as f:
            json.dump(commands, f, indent=4)
    return

load_params()

#### output command when signal received ####
def on_zone_change(name, **kw):
    """ Switch relays when core program signals a change in station state."""
    global prior
#     print 'change signaled'
#     print prior
#     print gv.srvals
    if gv.srvals != prior: # check for a change   
        for i in range(len(gv.srvals)):
            if gv.srvals[i] != prior[i]: #  this station has changed
                if gv.srvals[i]: # station is on
# 					command = "wget http://xxx.xxx.xxx.xxx/relay1on"
                    command = commands['on'][i]
                    if command:
                    	subprocess.call(command.split())
                else:              	
	                command = commands['off'][i]
	                if command:	                	
						subprocess.call(command.split())                 
        prior = gv.srvals[:]
    return


zones = signal('zone_change')
zones.connect(on_zone_change)

################################################################################
# Web pages:                                                                   #
################################################################################

class settings(ProtectedPage):
    """Load an html page for entering cli_control commands"""

    def GET(self):
        with open('./data/cli_control.json', 'r') as f:  # Read the settings from file
            commands = json.load(f)
        return template_render.cli_control(commands)


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format"""

    def GET(self):
        web.header('Access-Control-Allow-Origin', '*')
        web.header('Content-Type', 'application/json')
        return json.dumps(commands)


class update(ProtectedPage):
    """Save user input to cli_control.json file"""

    def GET(self):
        qdict = web.input()
#         print 'qdict: ', qdict
#         print 'commands: ', commands
		### add code to update commands ###
        commands = {u'on': [], u'off': [] }
        for i in range(gv.sd['nst']):
            commands['on'].append(qdict['con'+str(i)])
            commands['off'].append(qdict['coff'+str(i)])
        	
#         print 'new commands: ', commands
        with open('./data/cli_control.json', 'w') as f:  # write the settings to file
          	json.dump(commands, f, indent=4)
        raise web.seeother('/')
