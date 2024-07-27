# !/usr/bin/env python
# -*- coding: utf-8 -*-

# standard library imports
import json  # for working with data file
from threading import Thread
from time import sleep

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from webpages import showInFooter # Enable plugin to display readings in UI footer
from webpages import showOnTimeline # Enable plugin to display station data on timeline
from datetime import datetime, UTC
from suncalc import get_times

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/diurnal_display-sp", u"plugins.diurnal_display.settings",
    u"/diurnal_display-save", u"plugins.diurnal_display.save_settings",
    u"/diurnal_display-data", u"plugins.diurnal_display.fetch_data",
    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"Diurnal Display Plugin"), u"/diurnal_display-sp"])

# Add plugin-specific javascript that may be required for the plug-in to make arbitrary UI changes
# This is advanced capability with lots of rope to hang yourself, for simple data display we recommend showInFooter or showInTimeline
gv.plugin_scripts.append("diurnal_display.js")

def empty_function():  # Only a place holder
    """
    Functions defined here can be called by classes
    or run when the plugin is loaded. See comment at end.
    """
    pass

#############################
### Data display examples ###

def plugin_data(params):
    # Package up data for access by javascript
    try:
        with open(
            u"./data/diurnal_display.json", u"r"
        ) as f:  # Read settings from json file if it exists
            settings = json.load(f)
    except IOError:  # If file does not exist return empty value
        settings = {"lon" : 0, "lat" : 0}  # Default settings

    if hasattr(params,"date"):
        parts = params.date.split("-")
        date = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        date = datetime.now()
    lon = float(settings["lon"])
    lat = float(settings["lat"])
    
    times = get_times(date.astimezone(UTC), lon, lat)
    
    sunrise_time = times["sunrise"]
    sunset_time = times["sunset"]
    #print([sunrise_time, sunset_time])
    
    sunrise_minutes = sunrise_time.hour * 60 + sunrise_time.minute - gv.tz_offset/60
    sunset_minutes = sunset_time.hour * 60 + sunset_time.minute - gv.tz_offset/60
    if (sunrise_minutes < 0):
        sunrise_minutes += 24*60
    if (sunset_minutes < 0):
        sunset_minutes += 24*60
    
    return {
        "sunrise" : sunrise_minutes,
        "sunset" : sunset_minutes
    }


class fetch_data(ProtectedPage):
    """
    Provide fresh data as json to the plugin javascript through an API
    """

    def GET(self):
        web.header("Content-Type", "application/json")
        return json.dumps(plugin_data(web.input()))
    

# End data display examples

class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open(
                u"./data/diurnal_display.json", u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = {"lon" : 0, "lat" : 0}  # Default settings
        return template_render.diurnal_display(settings)  # open settings page


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
        #        print qdict  # for testing
        with open(u"./data/diurnal_display.json", u"w") as f:  # Edit: change name of json file
            json.dump(qdict, f)  # save to file
        raise web.seeother(u"/")  # Return user to home page.


    
#  Run when plugin is loaded
empty_function()
