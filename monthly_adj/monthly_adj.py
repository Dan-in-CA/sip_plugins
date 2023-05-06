# !/usr/bin/env python

# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
import json
import time

# local module imports
from blinker import signal
import gv  # Get access to sip's settings
from sip import template_render
from urls import urls  # Get access to sip's URLs
import web
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

# Add this plugin to the plugins menu
gv.plugin_menu.append([_(u"Monthly Adjust"), u"/ma"])


# def set_wl(run_loop=False):
def set_wl(month):
    """Adjust irrigation time by percent per month."""
    
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
    gv.sd[u"wl_monthly_adj"] = levels[
        month - 1
    ]  # Set the water level % (levels list is zero based).
    print(
        u"Monthly Adjust: Setting water level to {}%".format(
            gv.sd[u"wl_monthly_adj"]
        )
    )


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
        set_wl(gv.sd["month"])
        raise web.seeother(u"/")
    
def update_wl_monthly(name, **kw):
    month = time.localtime().tm_mon
    if not u"month" in gv.sd:
        gv.sd["month"] = month
        set_wl(month)
    elif  month != gv.sd["month"]:
        gv.sd["month"] = month
        set_wl(month)

# check for new month each day
new_day = signal(u"new_day")
new_day.connect(update_wl_monthly)
