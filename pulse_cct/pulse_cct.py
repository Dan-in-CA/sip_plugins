#!/usr/bin/env python

"""Pulses a selected circuit with a 2.5 Hz signal for 30 sec
to discover the location of a valve"""

from __future__ import print_function
import web
from time import sleep
import gv  # Get access to SIP's settings
from urls import urls  # Get access to SIP's URLs
from sip import template_render  #  Needed for working with web.py templates
from helpers import stop_stations, jsave
from webpages import ProtectedPage  # Needed for security
from gpio_pins import set_output

# fmt: off
urls.extend(
    [
        u"/puls", u"plugins.pulse_cct.pulse",
        u"/puls-run", u"plugins.pulse_cct.p_run",
        u"/puls-stop", u"plugins.pulse_cct.p_stop",
        u"/puls-sen", u"plugins.pulse_cct.p_save_enabled",
    ]
)
# fmt: on

gv.plugin_menu.append(
    [_(u"Pulse Circuit"), u"/puls"]
)  # Add this plugin to the home page plugins menu

stop = True


def chatter(cct):
    stop_stations()
    t = 0
    for cnt in range(150):
        t = 1 - t  #  toggle cct
        gv.srvals[cct] = t
        set_output()
        sleep(0.2)
        if stop:
            break
    #  switch everything off
    stop_stations()


class pulse(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        return template_render.pulse()  # open settings page


class p_run:
    """ Start pulsing selected circuit"""

    def GET(self):
        global stop
        qdict = web.input()
        stop = False
        chatter(int(qdict[u"zone"]))
        raise web.seeother(u"/puls")


class p_stop:
    """Stop all pulsing."""

    def GET(self):
        global stop
        stop = True
        raise web.seeother(u"/puls")


class p_save_enabled:
    def GET(self):
        qdict = web.input()
        print(u"qdict: ", qdict)
        for i in range(gv.sd[u"nbrd"]):
            if u"sh" + str(i) in qdict:
                try:
                    gv.sd[u"show"][i] = int(qdict[u"sh" + str(i)])
                except ValueError:
                    gv.sd[u"show"][i] = 255
            if "d" + str(i) in qdict:
                try:
                    gv.sd[u"show"][i] = ~int(qdict[u"d" + str(i)]) & 255
                except ValueError:
                    gv.sd[u"show"][i] = 255
        jsave(gv.sd, u"sd")
        raise web.seeother(u"/")
