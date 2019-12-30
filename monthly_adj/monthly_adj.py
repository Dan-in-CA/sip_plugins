# !/usr/bin/env python

# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
from threading import Thread
import json
import time

import web
import gv  # Get access to sip's settings
from urls import urls  # Get access to sip's URLs
from sip import template_render
from webpages import ProtectedPage


# Add a new url to open the data entry page.
# fmt: off
urls.extend(
    [
        u"/ma", u"plugins.monthly_adj.monthly_percent",
        u"/uma", u"plugins.monthly_adj.update_percents",
    ]
)
# fmt: on

# Add this plugin to the home page plugins menu
gv.plugin_menu.append([u"Monthly Adjust", u"/ma"])


def set_wl(run_loop=False):
    """Adjust irrigation time by percent based on historical climate data."""
    if run_loop:
        time.sleep(2)  # Sleep some time to prevent printing before startup information

    last_month = 0
    while True:
        try:
            with open(
                u"./data/levels.json", u"r"
            ) as f:  # Read the monthly percentages from file
                levels = json.load(f)
        except IOError:  # If file does not exist
            levels = [100] * 12
            with open(
                u"./data/levels.json", u"w"
            ) as f:  # write default percentages to file
                json.dump(levels, f)
        month = time.localtime().tm_mon  # Get current month.
        if month != last_month:
            last_month = month
            gv.sd[u"wl_monthly_adj"] = levels[
                month - 1
            ]  # Set the water level% (levels list is zero based).
            print(
                u"Monthly Adjust: Setting water level to {}%".format(
                    gv.sd[u"wl_monthly_adj"]
                )
            )

        if not run_loop:
            break
        time.sleep(3600)


class monthly_percent(ProtectedPage):
    """Load an html page for entering monthly irrigation time adjustments"""

    def GET(self):
        try:
            with open(
                u"./data/levels.json", u"r"
            ) as f:  # Read the monthly percentages from file
                levels = json.load(f)
        except IOError:  # If file does not exist
            levels = [100] * 12
            with open(
                u"./data/levels.json", u"w"
            ) as f:  # write default percentages to file
                json.dump(levels, f)
        return template_render.monthly(levels)


class update_percents(ProtectedPage):
    """Save user input to levels.json file"""

    def GET(self):
        qdict = web.input()
        months = [
            u"jan",
            u"feb",
            u"mar",
            u"apr",
            u"may",
            u"jun",
            u"jul",
            u"aug",
            u"sep",
            u"oct",
            u"nov",
            u"dec",
        ]
        vals = []
        for m in months:
            vals.append(int(qdict[m]))
        with open(
            u"./data/levels.json", u"w"
        ) as f:  # write the monthly percentages to file
            json.dump(vals, f)
        set_wl()
        raise web.seeother(u"/")

wl = Thread(target=set_wl)
wll.daemon = True
wl.start()
