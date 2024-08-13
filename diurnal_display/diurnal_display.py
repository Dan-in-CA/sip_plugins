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
from datetime import datetime, timezone
import subprocess
try:
    from suncalc import get_times
except ModuleNotFoundError:
    command = "pip install suncalc"
    subprocess.call(command.split())
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

# Inject javascript to call our API for data and modify the display
gv.plugin_scripts.append("diurnal_display.js")


# Set a default location, roughly estimated to users time zone
default_settings = {"lat" : 45, "lon" : -gv.tz_offset/3600*15 }

# Package up data for access by javascript
def plugin_data(params):
    # load settings for lat/lon params
    try:
        with open(
            u"./data/diurnal_display.json", u"r"
        ) as f:  # Read settings from json file if it exists
            settings = json.load(f)
    except IOError:  # If file does not exist return empty value
        settings = default_settings

    # load date param from url to establish date to test
    if hasattr(params,"date"):
        parts = params.date.split("-")
        date = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        date = datetime.now()
    
    # calculate the sunrise/sunset times
    lon = float(settings["lon"])
    lat = float(settings["lat"])
    times = get_times(date.astimezone(timezone.utc), lon, lat)
    sunrise_time = times["sunrise"]
    sunset_time = times["sunset"]
    #print([sunrise_time, sunset_time])
    
    # convert to minutes-since-midnight format to return
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
    
## Handle settings
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
            settings = default_settings
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

