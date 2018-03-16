#!/usr/bin/env python
'''Pulses a selected circuit with a 2.5 Hz signal for 30 sec
to discover the location of a valve'''
import web
from time import sleep
import gv # Get access to SIP's settings
from urls import urls # Get access to SIP's URLs
from sip import template_render  #  Needed for working with web.py templates
from helpers import stop_stations, jsave
from webpages import ProtectedPage  # Needed for security
from gpio_pins import set_output


urls.extend([
             '/puls', 'plugins.pulse_cct.pulse',
             '/puls-run', 'plugins.pulse_cct.p_run',
             '/puls-stop', 'plugins.pulse_cct.p_stop',
             '/puls-sen', 'plugins.pulse_cct.p_save_enabled'
             ]) 
gv.plugin_menu.append(['Pulse Circuit', '/puls']) # Add this plugin to the home page plugins menu

stop = True

def chatter(cct):
    stop_stations()
    t = 0
    for cnt in range(150):      
        t = 1 - t #  toggle cct
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


class p_run():
    """ Start pulsing selected circuit"""     
    def GET(self):
        global stop
        qdict = web.input()
 #       print 'qdict: ', qdict
        stop = False
        chatter(int(qdict['zone']))
        raise web.seeother('/puls')

    
class p_stop():
    """Stop all pulsing."""  
    def GET(self):
        global stop
        stop = True
        raise web.seeother('/puls')
    
class p_save_enabled():
    
    def GET(self):
        qdict = web.input()
        print 'qdict: ', qdict
        for i in range(gv.sd['nbrd']):
            if 'sh' + str(i) in qdict:
                try:
                    gv.sd['show'][i] = int(qdict['sh' + str(i)])
                except ValueError:
                    gv.sd['show'][i] = 255
            if 'd' + str(i) in qdict:
                try:
                    gv.sd['show'][i] = ~int(qdict['d' + str(i)])&255
                except ValueError:
                    gv.sd['show'][i] = 255
        jsave(gv.sd, 'sd')
        raise web.seeother('/')   