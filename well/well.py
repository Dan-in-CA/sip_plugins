# !/usr/bin/env python3
# -*- coding: utf-8 -*-

NAME = 'well.py'
VERSION = '0.6'
DESCRIPTION = 'Well pump control plugin for SIP'

'''
Well pump control plugin for SIP (Sustainable Irrigation Platform - see: https://dan-in-ca.github.io/SIP/)

This plugin will permit control a well pump according to certain user-configurable parameters.

Explanation:

Under times of heavy irrigation a well may run low or dry. Existing well installations
are likely to have a control mechanism to deal with this, but may require manual intervention
to reset the controller should they shut down. 

This plugin allows a SIP user to connect an error input, and well pump motor input, to SIP
and to connect an output to the well pump reset switch. 

The front page will display the error and motor status. If the error input logic switches true 
then a countdown timer is invoked that will then reset the controller after a period of time
specified by the user. 

An attempt has been made to deal with different logic inputs, and different controller reset
mechanisms. It should also be possible to use this plugin as a complete pump controller 
although I would stress that it has not been specifically written for this purpose, that it
is very experimental, and that I'm not sure that I'd entrust it to directly control your 
expensive well pump!

As of the time of writing this intro the plugin is only just out of alpha and it is likely to be 
buggy, as well as the code being more crappy/hacky than usual, even for me. Please be gentle 
if you wish to critique, and maybe wait for a few weeks before trialling it as there is likely
to be some updating as it is tested locally.

-------------------------------------------------------------------

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

# Import reqired libraries
import json
from threading import Thread
from time import sleep
import RPi.GPIO as GPIO
# local module imports
from blinker import signal
import gv  # Access SIP's settings
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Access SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from webpages import showInFooter # Enable plugin to display readings in UI footer
from webpages import showOnTimeline # Enable plugin to display station data on timeline
from helpers import stop_stations
import atexit
atexit.register(GPIO.cleanup) # Need to change this to set motor control relay to reflect correct sense

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/well-sp", u"plugins.well.settings",
    u"/well-save", u"plugins.well.save_settings"
    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"Well Plugin"), u"/well-sp"])
#
def well_options():
    try:
        with open("./data/well.json", "r") as f:  # Read the settings from file
            welldata = json.load(f)
        for key, value in file_data.iteritems():
            if key in welldata:
                welldata[key] = value
    except Exception:
        pass
    return welldata

#############################

pump = showInFooter() #  instantiate class to enable data in footer
pump.label = u"Well pump"
pump.val = ('NA')
pump.unit = u" "

pump_restart = showInFooter()  #  instantiate class to enable data in footer
pump_restart.label = u"Starting control "
pump_restart.val = ('working')
pump_restart.unit = u" "

options = well_options()
well_dry = False # Use for future latching operation

def outhi():
    return GPIO.output(37,1)

def outlo():
    return GPIO.output(37,0)

def prog():
    pump_restart.countdown = float(options["time"])
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO. BOARD)
    GPIO.setup(33, GPIO.IN,pull_up_down=GPIO.PUD_UP) # pump control input
    GPIO.setup(35, GPIO.IN,pull_up_down=GPIO.PUD_UP) # motor running input
    GPIO.setup(37, GPIO.OUT) # pump control reset
    # Set output initial resting state
    if options["out_act"] == ("high"):
        outlo()
    else:
        outhi()
    while True: #  Display simulated plugin data
        if ((options["in_act"] == "high") and (GPIO.input(33) == 1)) or (GPIO.input(33) == 0):
#          while (well_dry): # Use for future latching
            if (options["stns"] == ("on")):
                stop_stations()  # Stop irrigating (if enabled in options)
            if options["moment"] == ("off"):
                if options["out_act"] == ("high"):
                    outhi()
                else:
                    outlo()
            sleep(1)
            pump_restart.countdown -= 0.0166 #  update plugin data 1
            pump_restart.val = str(round(pump_restart.countdown,1))+(' mins')
            if pump_restart.countdown <= 0.0:
                pump_restart.countdown = float(options["time"])
                pump_restart.val = ('OK')
                if options["moment"] == ("off"):
                    if options["out_act"] == ("high"):
                        outlo()
                    else:
                        outhi()
                if options["moment"] == ("on"):
                    if options["out_act"] == ("high"):
                        outhi()
                        sleep(2)
                        outlo()
                    else:
                        outlo()
                        sleep(2)
                        outhi()
                       well_dry = False
        else:
            pump_restart.countdown = float(options["time"])       
            pump_restart.val = ('OK')

# -------------- Motor status information ------------------- #
        if GPIO.input(35) == 0: 
            pump.val = ('RUNNING') #+= 40 #  update plugin data 2
        else:
            pump.val = ('STOPPED') #+= 1          
#-------------------------------------------------------------#

    sleep(1)        

# Run data_test() in baskground thread
ft = Thread(target = prog)
ft.daemon = True
ft.start()

#################################

### Station Completed ###
def notify_station_completed(station, **kw):
    print(u"Station {} run completed".format(station))


complete = signal(u"station_completed")
complete.connect(notify_station_completed)

#################################

class settings(ProtectedPage):
    def GET(self):
        try:
            with open(
                u"./data/well.json", u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = {}  # Default settings. can be list, dictionary, etc.
        return template_render.well(settings)  # open settings page


class save_settings(ProtectedPage):
    def GET(self):
        qdict = web.input()
        if "stns" not in qdict:
            qdict["stns"] = "off"
        if "in_act" not in qdict:
            qdict["in_act"] = "low"
        if "moment" not in qdict:
            qdict["moment"] = "off"
        if "out_act" not in qdict:
            qdict["out_act"] = "low"
        with open("./data/well.json", "w") as f:  # write the settings to file
            json.dump(qdict, f)
#        checker.update()
        raise web.seeother(u"/")
