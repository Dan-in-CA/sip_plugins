# !/usr/bin/env python
# -*- coding: utf-8 -*-

# standard library imports
import json  # for working with data file
import threading
import serial
import time
import datetime
import urllib

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security


# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/pressure_monitor-sp", u"plugins.pressure_monitor.settings",
    u"/pressure_monitor-save", u"plugins.pressure_monitor.save_settings",
    u"/pressure_monitor-display", u"plugins.pressure_monitor.display"
    ])
# fmt: on

gv.plugin_scripts.append("pressure_monitor.js")

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"Pressure Monitor Plugin"), u"/pressure_monitor-sp"])

def load_settings():
    # load settings from file
    try:
        with open(
            u"./data/pressure_monitor.json", u"r"
        ) as f:  # Read settings from json file if it exists
            return json.load(f)
    except IOError:  # If file does not exist return default values
        return { "port" : "/dev/ttyUSB0", "url" : "" }
    
class display(ProtectedPage):
    """
    Load an htnml page containing a pressure graph
    """
    def GET(self):
        graph_date = web.input().date

        url = load_settings()["url"]
        if (url != ""):
            remote_response = urllib.request.urlopen(url + "/pressure_monitor-display?date=" + graph_date).read()
            return remote_response
        
        else:

            try:
                with open(
                    u"./data/pressure/psi_log_" + graph_date + ".csv", u"r"
                ) as f:  # Read settings from json file if it exists
                    lines = f.readlines()
                    data = []
                    for line in lines:
                        data.append(line.split(","))
            except IOError:  # If file does not exist return zero readings for the whole day
                data = [ ["00:00:30","0"], ["23:59:30","0"] ]
            points = ""
            last_point = 0
            first_point = -1
            
            for sample in data:
                timestamp = sample[0]
                timestamp_parts = timestamp.split(":")
                timevalue = int(timestamp_parts[0])*60 + int(timestamp_parts[1])
                psi = int(sample[1])
                points += str(timevalue) + "," + str(60-psi) + " "
                if first_point == -1:
                    first_point = timevalue
                last_point = timevalue

            points += str(last_point) + ",60 " + str(first_point) + ",60"
            
            return ("<svg width='100%' height='100%' viewBox='0 0 1440 60' preserveAspectRatio='none'>" + 
                    "   <rect x='0' y='0' width='1440' height='60' style='fill:#ccddff' /> " + 
                    "   <line x1='50' y1='10' x2='1440' y2='10' style='stroke:white' /> " + 
                    "   <line x1='50' y1='20' x2='1440' y2='20' style='stroke:white' /> " + 
                    "   <line x1='50' y1='30' x2='1440' y2='30' style='stroke:white' /> " + 
                    "   <line x1='50' y1='40' x2='1440' y2='40' style='stroke:white' /> " + 
                    "   <line x1='50' y1='50' x2='1440' y2='50' style='stroke:white' /> " + 
                    "   <text x='10' y='14' fill='white' font-size='10' font-weight='bold'>50 PSI</text> " + 
                    "   <text x='10' y='24' fill='white' font-size='10' font-weight='bold'>40 PSI</text> " + 
                    "   <text x='10' y='34' fill='white' font-size='10' font-weight='bold'>30 PSI</text> " + 
                    "   <text x='10' y='44' fill='white' font-size='10' font-weight='bold'>20 PSI</text> " + 
                    "   <text x='10' y='54' fill='white' font-size='10' font-weight='bold'>10 PSI</text> " + 
                    "   <polygon points='" + points + "' style='fill:#2211dd; fill-opacity:50%' />" + 
                    "</svg>")


def read_pressure():
    port = load_settings()["port"]
    
    # initiate serial communication
    try:
        ser = serial.Serial(port, 115200, timeout=1.0)
        time.sleep(3)
        ser.reset_input_buffer()
        print("Begin monitoring pressure")
    except:
        print("No pressure monitor detected")
        return

    try:    
        while True:
            if ser.in_waiting > 0:
                psi = ser.readline().decode('utf-8').rstrip()
                
                now = datetime.datetime.now()
                ts = now.strftime('%Y-%m-%d')
                logfile = "data/pressure/psi_log_" + now.strftime('%Y-%m-%d') + ".csv"
                
                try:
                    log = open(logfile,"a")
                except IOError:
                    log = open(logfile,"w")
                
                ts = now.strftime('%H:%M:%S')
                print("[" + ts + "] " + psi + " psi")
                line = ts + "," + psi + "\n"
                try:
                    log.write(line)
                except IOError:
                    print("error writing to pressure log")
                log.close()
            time.sleep(0.1)
    except Exception as e:
        print("pressure monitor failure: " + e)
        ser.close()

## Handle settings
class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open(
                u"./data/pressure_monitor.json", u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = default_settings
        return template_render.pressure_monitor(settings)  # open settings page


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
        with open(u"./data/pressure_monitor.json", u"w") as f:  # Edit: change name of json file
            json.dump(qdict, f)  # save to file
        raise web.seeother(u"/")  # Return user to home page.


pressure_thread = threading.Thread(target=read_pressure)

pressure_thread.start()
