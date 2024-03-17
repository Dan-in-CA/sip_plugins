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
from webpages import showInFooter  # Enable plugin to display readings in UI footer
from webpages import showOnTimeline  # Enable plugin to display station data on timeline


import datetime
import math

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/monthly_adjust_per_station", u"plugins.monthly_adjust_per_station.get_settings",
    u"/monthly_adjust_per_station-save", u"plugins.monthly_adjust_per_station.save_settings"

    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_("Monthly Adjust per Station"), "/monthly_adjust_per_station"])


# ADJUSTMENT_COLORS = ["#e8f4ea", "#e0f0e3", "#d2e7d6", "#c8e1cc", "#b8d8be"]
ADJUSTMENT_COLORS = ["#d4ffc5", "#b2eb99", "#87ca6a", "#6bac50", "#54883d"]
station_settings = {}


def validate_int(int_list):
    """Validate a list of integer strings and return result as a
    tuple. Invalid integers are returned as None
    """
    validated_list = []

    for index in range(len(int_list)):
        try:
            validated_list.append(int(int_list[index]))
        except (TypeError, ValueError):
            validated_list.append(None)

    return tuple(validated_list)


def notify_station_scheduled(station, **kw):
    """Apply the defined adjustment to the schedule running on the
    station if applicable (Not RUN NOW, enabled)
    """

    ts = datetime.datetime.fromtimestamp(gv.now)
    cur_month = ts.month
    station_index = station - 1

    # TODO honor "Ignore Plugin adjustments"

    if gv.rn or gv.rs[station_index][3] == 98:
        # Skip RUN NOW and RUN ONCE programs
        return

    st_enable_key = f"enable_{station_index}"
    st_mon_key = f"st_mon_{station_index}_{cur_month}"

    if st_enable_key not in station_settings:
        return

    if st_mon_key in station_settings:
        (adjustment,) = validate_int(
            [
                station_settings[st_mon_key],
            ]
        )

        if adjustment is None:
            if "default" not in station_settings:
                return
            else:
                (default,) = validate_int(
                    [
                        station_settings["default"],
                    ]
                )
                if default is None or default == 100:
                    return
                else:
                    adjustment = default

        if adjustment == 100:
            # Nothing to adjust
            return

        duration = gv.rs[station_index][2]

        duration = math.ceil(duration * adjustment / 100)
        gv.rs[station_index][1] = gv.rs[station_index][0] + duration
        gv.rs[station_index][2] = duration


scheduled_signal = signal("station_scheduled")
scheduled_signal.connect(notify_station_scheduled)


def load_settings():
    global station_settings

    try:
        with open(
            "./data/monthly_adjust_per_station.json", "r"
        ) as f:  # Read settings from json file if it exists
            station_settings = json.load(f)

    except IOError:
        # If file does not exist return empty value
        station_settings = {}


class get_settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):

        # open settings page
        return template_render.monthly_adjust_per_station(station_settings)


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def set_cell_decoration(self):
        """Set color of the cells containing adjustments using a
        gradient scheme."""

        global station_settings
        min_adj = math.inf
        max_adj = 0
        adjustments = {}

        for st in range(0, len(gv.rs)):  # Number of stations
            for mon in range(1, 13):  # 12 months of the year
                st_mon_key = f"st_mon_{st}_{mon}"
                (cur_adj,) = validate_int([station_settings[st_mon_key]])

                # Determine max and min value in range for each station
                if cur_adj is not None:
                    if cur_adj < min_adj:
                        min_adj = cur_adj
                    if cur_adj > max_adj:
                        max_adj = cur_adj

                    adjustments[st_mon_key] = cur_adj

        if len(adjustments) > 0:
            old_range = max_adj - min_adj

            for st_mon_key in adjustments.keys():
                cur_adj = adjustments[st_mon_key]

                if old_range == 0:
                    color_idx = 0
                else:
                    # Distribute adjustments evenly in range 0-4
                    color_idx = math.trunc((cur_adj - min_adj) * 4.9 / old_range)

                station_settings[f"c_{st_mon_key}"] = ADJUSTMENT_COLORS[color_idx]

    def GET(self):
        global station_settings

        # Dictionary of values returned as query string from settings page.
        qdict = web.input()

        station_settings = qdict

        save_settings.set_cell_decoration(self)

        with open("./data/monthly_adjust_per_station.json", "w") as f:
            json.dump(station_settings, f)

        # Return user to plugin page
        raise web.seeother("/monthly_adjust_per_station")


#  Run when plugin is loaded
load_settings()
