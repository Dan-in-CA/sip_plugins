# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
import json  # for working with data file
from threading import Thread
from time import sleep
import subprocess

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from webpages import showInFooter # Enable plugin to display readings in UI footer
from webpages import showOnTimeline # Enable plugin to display station data on timeline


# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/shutdown", u"plugins.shutdown_button.settings",
    u"/endSip", u"plugins.shutdown_button.stop",

    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"Shutdown button"), u"/shutdown"])


# def end_sip():
#     """
#     Functions defined here can be called by classes
#     or run when the plugin is loaded. See comment at end.
#     """
#     subprocess.call(poweroff)       


class settings(ProtectedPage):
    """
    Load an html page containing stop SIP button.
    """
    def GET(self):
        return template_render.shutdown_button()  # open shutdown page

class stop(object):
    """
    Load an html page containing stop SIP button.
    """
    def GET(self):
        subprocess.call("poweroff") 
