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
    u"/simple_chart", u"plugins.simple_chart.display_charts",
    u"/simple_chart-save", u"plugins.simple_chart.save_settings",
    u"/simple_chart_config", u"plugins.simple_chart.get_settings",

    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([("Simple Chart"), "/simple_chart"])

settings = {}
CONFIG_FILE_PATH = "./data/simple_chart.json"
CONFIG_DIR_PATH = "./data/simple_chart"


def load_settings():
    global settings

    settings = {}

    try:
        # Read settings from json file if it exists
        with open(CONFIG_FILE_PATH, "r") as f:
            settings = json.load(f)

    except IOError:
        settings = {}

    filenames = os.listdir(CONFIG_DIR_PATH)
    for filename in filenames:
        try:
            with open(os.path.join(CONFIG_DIR_PATH, filename), "r") as f:
                chart_defaults = json.load(f)

            chart_name = os.path.splitext(filename)[0]

            if chart_name in settings:
                if settings[chart_name]["options"] == "":
                    settings[chart_name]["options"] = chart_defaults["options"]
            else:
                settings[chart_name] = {}
                settings[chart_name]["file"] = filename
                settings[chart_name]["enabled"] = ""
                settings[chart_name]["options"] = chart_defaults["options"]

            settings[chart_name]["data"] = chart_defaults["data"]

            # print(settings)
            settings[chart_name]["data"] = []
            if os.path.isdir(chart_defaults["data"]):
                filenames = os.listdir(chart_defaults["data"])
                for filename in filenames:
                    settings[chart_name]["data"].append(
                        f"{chart_defaults['data']}/{filename}"
                    )
            else:
                settings[chart_name]["data"] = chart_defaults["data"]

        except IOError as Exception:
            print(Exception)
            # If files do not exist go with what we have
            pass
    # print(settings)


class display_charts(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        global settings

        load_settings()

        # print(settings)
        # open settings page
        return template_render.simple_chart(settings)


class get_settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        global settings

        load_settings()

        # open config page
        return template_render.simple_chart_config(settings)


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):
        global settings

        # Dictionary of values returned as query string from settings page.
        qdict = web.input()

        del_list = []
        for chart in settings.keys():
            settings[chart]["options"] = qdict[f"{chart}_options"]
            settings[chart]["options"] = re.sub(
                r"\r\n *\r\n *|\r\n *$", "", settings[chart]["options"]
            )

            if settings[chart]["options"] == "":
                del_list.append(chart)
                continue

            if f"{chart}_enabled" in qdict:
                settings[chart]["enabled"] = ""
            else:
                settings[chart].pop("enabled", "")

        for chart in del_list:
            del settings[chart]

        with open(CONFIG_FILE_PATH, "w") as f:
            json.dump(settings, f)

        # Redisplay the plugin page
        raise web.seeother("/simple_chart")


#  Run when plugin is loaded
load_settings()
