#!/usr/bin/env python

from blinker import signal
import subprocess
import web, json, time
import gv  # Get access to sip's settings, gv = global variables
from urls import urls  # Get access to sip's URLs
from sip import template_render
from webpages import ProtectedPage

gv.use_gpio_pins = False  # Signal sip to not use GPIO pins


# Add a new url to open the data entry page.
urls.extend(['/rfc', 'plugins.rf_control.settings',
	'/rfcj', 'plugins.rf_control.settings_json',
	'/rfcu', 'plugins.rf_control.update']) 

# Add this plugin to the plugins menu
gv.plugin_menu.append(['RF Control', '/rfc'])

commands = {}
prior = [0] * len(gv.srvals)

# Read in the parameters for this plugin from it's JSON file
def load_params():
    global commands
    try:
        with open('./data/rf_control.json', 'r') as f:  # Read the settings from file
            commands = json.load(f)
    except IOError: #  If file does not exist create file with defaults.
        commands = {
    "on": [
    	"on command for station 1",
    	"on command for station 2",
    	"on command for station 3",
    	"on command for station 4",
    	"on command for station 5",
    	"on command for station 6",
    	"on command for station 7",
    	"on command for station 8" 
    ], 
    "off": [
    	"off command for station 1",
    	"off command for station 2",
    	"off command for station 3",
    	"off command for station 4",
    	"off command for station 5",
    	"off command for station 6",
    	"off command for station 7",
    	"off command for station 8"     
    ]
}
        with open('./data/rf_control.json', 'w') as f:
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
                if gv.srvals[i]:
                	
# 					print "issue on command for station ", i+1
# 					command = ['echo'] 
# 					command.append(commands['on'][i])

#                     command = commands['on'][i])
					command = "pilight-control -d station{0} -s on".format(str(i))
					subprocess.call(command)
                else:
#                     print "issue off command for station ", i+1
#                     command = ['echo'] 
#                     command.append(commands['off'][i])

#                     command = commands['off'][i])
                    command = "pilight-control -d station{0} -s off".format(str(i))
                    subprocess.call(command)                   
        prior = gv.srvals[:]
    return


zones = signal('zone_change')
zones.connect(on_zone_change)

################################################################################
# Web pages:                                                                   #
################################################################################

class settings(ProtectedPage):
    """Load an html page for entering rf_control adjustments"""

    def GET(self):
        with open('./data/rf_control.json', 'r') as f:  # Read the settings from file
            commands = json.load(f)
        return template_render.rf_control(commands)


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format"""

    def GET(self):
        web.header('Access-Control-Allow-Origin', '*')
        web.header('Content-Type', 'application/json')
        return json.dumps(commands)


class update(ProtectedPage):
    """Save user input to rf_control.json file"""

    def GET(self):
        qdict = web.input()
        changed = False
        if commands['relays'] != int(qdict['relays']):  # if the number of relay channels changed, update the commands
           commands['relays'] = int(qdict['relays'])
           changed = True
        if commands['active'] != str(qdict['active']):  # if the number of relay channels changed, update the commands
           commands['active'] = str(qdict['active'])
           commands['relays'] = 1  # since changing active could turn all the relays on, reduce the relay channels to 1
           changed = True
        if changed:
           init_pins();
           with open('./data/rf_control.json', 'w') as f:  # write the settings to file
              json.dump(commands, f)
        raise web.seeother('/')
