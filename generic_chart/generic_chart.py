# !/usr/bin/env python
# -*- coding: utf-8 -*-

# standard library imports
import json  # for working with data file

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  # Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from webpages import showInFooter  # Enable plugin to display readings in UI footer
from webpages import showOnTimeline  # Enable plugin to display station data on timeline

from helpers import run_once
import datetime
import os
import re

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/generic_chart", u"generic_chart.get_settings",
    u"/generic_chart-save", u"plugins.generic_chart.save_settings"

    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([("Generic Chart"), "/generic_chart"])


class get_settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        # load_moisture_sensor_settings()

        settings = {}

        # open settings page
        return template_render.generic_chart(settings)


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):

        # Dictionary of values returned as query string from settings page.
        qdict = web.input()

        with open("./data/generic_chart.json", "w") as f:
            json.dump(qdict, f)

        # Redisplay the plugin page
        raise web.seeother("/generic_chart")


#  Run when plugin is loaded
# load_moisture_sensor_settings()
