from __future__ import print_function
# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Flow SIP addin
import sys
sys.path.insert(0, '/home/pi/SIP/plugins/flowhelpers')
import flowhelpers
import ast
from blinker import signal
import datetime
import gv  # Get access to SIP's settings
import io
import queue
import json  # for working with data file
from sip import template_render  #  Needed for working with web.py templates
from smbus import SMBus
import threading
import time
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage, WebPage  # Needed for security
from webpages import showInFooter  # Enable plugin to display station data on timeline
# from webpages import showOnTimeline  # Enable plugin to display station data on timeline

# Global variables
sensor_register = 0x00  # 0x00 to receive sensor readings, 0x01 to have the sensor send random numbers to use for testing
# Number of readings to average for the flow rate reading display passed to flow smoother.
# This is for display purposes only and does not change the usage
# calculation in any way
fs = flowhelpers.FlowSmoother(4)
settings_b4 = {}
changed_valves = {}
all_pulses = 0  # Calculated pulses since beginning of time
master_sensor_addr = 0
pulse_rate = 0  # holds last captured flow rate
flow_loop_running = False  # Notes if the main loop has started
valve_loop_running = False  # Notes if the valve loop has started
# valve_open = False  # Shows as true if any valve is open
ls = flowhelpers.LocalSettings()
fw = flowhelpers.FlowWindow(ls)
valve_messages = queue.Queue()  # Carries messages from notify_zone_change to the changed_valves_loop

# Variables for the flow controller client
client_addr = 0x44
bus = SMBus(1)

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/flow-sp", u"plugins.flow.flow",
    u"/flow-save", u"plugins.flow.save_settings",
    u"/flow-data", u"plugins.flow.flowdata",
    u"/flow-settings", u"plugins.flow.settings",
    u"/cfl", u"plugins.flow.clear_log",
    u"/wfl", u"plugins.flow.download_csv"
    ])

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"Flow Plugin"), u"/flow-sp"])


def save_prior_settings():
    """
    Save prior settings dictionary to local variable settings_b4
    """
    global settings_b4

    try:
        with open(
            u"./data/flow.json", u"r"
        ) as f:  # Read settings from json file if it exists
            prior_settings = json.load(f)
    except IOError:
        prior_settings = {}
    finally:
        settings_b4 = prior_settings


def print_settings(lpad=2):
    """
    Prints the flow settings
    """
    print(u"{}Master flow sensor address: {}".format(" " * lpad, u"0x%02X" % client_addr))
   
        
def update_options():
    """
    Read key main program options into local variables
    """
    print(gv.sd["mas"])

def changed_valves_loop():
    """
    Monitors valve_messages queue for notices that the valve state has changed and takes appropriate action
    """
    global changed_valves
    # global valve_open
    global fw
    global valve_loop_running

    valve_loop_running = True
    while True:
        
        while not valve_messages.empty():
            # sleep here to ensure that if multiple valves are closed at the same time,
            # the main program has time to update all the valves in gv.sd
            time.sleep(0.25)
            valve_notice = valve_messages.get()
            if str(gv.srvals) != str(fw.valve_states()):               
                capture_time = valve_notice.switch_time
                capture_flow_counter = valve_notice.counter
                i = 0
                fw_new = flowhelpers.FlowWindow(ls)
                fw_new.start_time = capture_time
                fw_new.start_pulses = capture_flow_counter
                vs = fw.valve_states()
                while i < len(vs):
                    if i != gv.sd["mas"] - 1:
                        # Ignore changes in the master valve
                        if vs[i] != gv.srvals[i]:
                            # Determine changed valves
                            if gv.srvals[i] == 1:
                                changed_valves[i] = u"on"
                            else:
                                changed_valves[i] = u"off"
                    i = i + 1
                if fw.valve_open() and not fw_new.valve_open():
                    # All valves are now closed end current flow window
                    fw.end_pulses = capture_flow_counter
                    fw.end_time = capture_time
                    fw.write_log()
            
                elif  not fw.valve_open() and fw_new.valve_open():
                    #Flow has started.  Start a new flow window
                    pass
            
                elif fw.valve_open() and fw_new.valve_open():
                    # Flow is still running but through different valve(s)
                    # End current flow window
                    fw.end_pulses = capture_flow_counter
                    fw.end_time = capture_time
                    fw.write_log()
                # print("valves changed: ", changed_valves)
                fw = fw_new
        
        time.sleep(0.25)

class clear_log(ProtectedPage):
    """
    Delete all log records
    """
    def GET(self):
        with io.open(u"./data/flowlog.json", u"w") as f:
            f.write(u"")
        raise web.seeother(u"/flow-log")


class download_csv(ProtectedPage):
    """
    Downloads log as csv
    """
    def GET(self):
        records = flowhelpers.read_log()
        data = _(u"Date, Start Time, Duration, Stations, Valves, Usage, Units") + u"\n"
        for r in records:
            event = ast.literal_eval(json.dumps(r))
            data += (
                event[u"date"]
                + u', '
                + event[u"start"]
                + u', '
                + event[u"duration"]
                + u', "'
                + event[u"stations"]
                + u'", "'
                + event[u"valves"]
                + u'", '
                + str(event[u"usage"])
                + u', '
                + event[u"measure"] 
                + u'\n'
            )

        web.header(u"Content-Type", u"text/csv")
        return data


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """ 
    global master_sensor_addr
    settings_b4 = {}
    def GET(self):
        
        try:
            runtime_values = {"sensor-addr":u"0x%02X" % client_addr}
            if pulse_rate >=0:
                runtime_values.update({"sensor-connected":"yes"})
            else:
                runtime_values.update({"sensor-connected":"no"})
            
            with open(
                u"./data/flow.json", u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = {}

        log = flowhelpers.read_log()
        return template_render.flowsettings(settings, runtime_values, log)  # open flow settings page


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):
        save_prior_settings()
        qdict = (
            web.input()
        )  # Dictionary of values returned as query string from settings page.
        
        with open(u"./data/flow.json", u"w") as f:  # Edit: change name of json file
            json.dump(qdict, f)  # save to file
        ls.load_settings()
        # print(u"Flow settings after update")
        # print_settings()
        # actions_on_change_settings()
        raise web.seeother(u"/")  # Return user to home page.
 
   
class flowdata(ProtectedPage):
    """
    Return flow values to the web page in JSON form
    """
    global pulse_rate
    
    def GET(self):
        web.header(b"Access-Control-Allow-Origin", b"*")
        web.header(b"Content-Type", b"application/json")
        web.header(b"Cache-Control", b"no-cache")
        qdict = {u"pulse_rate": pulse_rate}
        qdict.update({u"total_pulses": all_pulses})
        if ls.pulses_per_measure > 0:
            if fs.last_reading() >= 0:
                flow_rate = round(fs.ave_reading() * 3600 / ls.pulses_per_measure, 3)
                flow_rate_raw = round(fs.last_reading() * 3600 / ls.pulses_per_measure, 3)
                qdict.update({u"flow_rate": f'{round(flow_rate, 1):,}'})
                qdict.update({u"flow_rate_raw": f'{round(flow_rate_raw, 1):,}'})
            else:
                qdict.update({u"flow_rate": "N/A"})
                qdict.update({u"flow_rate_raw": "N/A"})
        else:
            qdict.update({u"flow_rate": 0})
            qdict.update({u"flow_rate_raw": 0})
        qdict.update({u"volume_measure": ls.volume_measure + "/hr"})
        
        # Water usage since beginning of window
        if ls.pulses_per_measure > 0:
            water_use = round((all_pulses - fw.start_pulses) / ls.pulses_per_measure, 1)
        else:
            water_use = 0
        water_use_str = str(water_use) + " " + ls.volume_measure
        qdict.update({u"water_use": water_use_str})
        
        # Create valve status string
        qdict.update({u"valve_status": fw.valves_status_str()})
        
        return json.dumps(qdict)

class flow(ProtectedPage):
    """View Log"""

    def GET(self):
        try:
            runtime_values = {"sensor-addr": u"0x%02X" % client_addr}
            if pulse_rate >= 0:
                runtime_values.update({"sensor-connected": "no"})
            else:
                runtime_values.update({"sensor-connected": "no"})
            with open(
                    u"./data/flow.json", u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
                print(settings)
        except IOError:  # If file does not exist return empty value
            settings = {}
            # Default settings. can be list, dictionary, etc.

        records = flowhelpers.read_log()

        return template_render.flow(settings, runtime_values, records)


class LoopThread (threading.Thread):
    def __init__(self, fn, thread_id, name, counter):
        threading.Thread.__init__(self)
        self.fn = fn
        self.threadID = thread_id
        self.name = name
        self.counter = counter

    def run(self):
        self.fn()


def main_loop():
    """
    **********************************************
    PROGRAM MAIN LOOP
    runs on separate thread
    **********************************************
    """
    global flow_loop_running
    global pulse_rate
    # global valve_open
    global all_pulses
    flow_loop_running = True
    print(u"Flow plugin main loop initiated.")
    start_time = datetime.datetime.now()
    while True:
        try:
            bytes = bus.read_i2c_block_data(client_addr, sensor_register, 4)
            pulse_rate = int.from_bytes(bytes, u"little")
            fs.add_reading(pulse_rate)

        except IOError:
            pulse_rate = -1
            fs.add_reading(pulse_rate)

        if not pulse_rate == -1:
            stop_time = datetime.datetime.now()
            time_elapsed = stop_time - start_time
            all_pulses = all_pulses + time_elapsed.total_seconds() * pulse_rate
            start_time = stop_time

        # Update the application footer with flow information
        rate_footer.label = u"Flow rate"
        rate_footer.unit = u" " + ls.volume_measure + u"/hr"
        if fs.last_reading() >= 0:
            rate_footer.val = f'{round(fs.ave_reading() * 3600 / ls.pulses_per_measure, 1):,}'
        else:
            rate_footer.val = "N/A"

        volume_footer.label = u"Water usage"
        volume_footer.val = f'{round((all_pulses - fw.start_pulses) / ls.pulses_per_measure, 1):,}'
        volume_footer.unit = u" " + ls.volume_measure

        time.sleep(1)

flow_loop = LoopThread(main_loop, 1, "FlowLoop", 1)
valve_loop = LoopThread(changed_valves_loop, 2, "ValveLoop", 2)

    
"""
Event Triggers
"""
def notify_zone_change(name, **kw):
    """
    This event tells us a valve was turned on or off
    """
    valve_notice = flowhelpers.ValveNotice(datetime.datetime.now(), all_pulses)
    valve_messages.put(valve_notice)


zones = signal(u"zone_change")
zones.connect(notify_zone_change)


def notify_new_day(name, **kw):
    """
    App sends a new_day message after plugins are loaded.
    We'll use this as a trigger to start the threaded loops
    """
    if not flow_loop_running:
        # This loop watches the flow
        flow_loop.start()
    if not valve_loop_running:
        # This loop watches for valve changes
        valve_loop.start()


new_day = signal(u"new_day")
new_day.connect(notify_new_day)


# Function to be run when signal is recieved.
def notify_alarm_toggled(name, **kw):
    pass


# instance of named signal
alarm = signal(u"alarm_toggled")  
# Connect signal to function to be run.
alarm.connect(notify_alarm_toggled)


# Option settings
def notify_option_change(name, **kw):
    update_options()
    #  gv.sd is a dictionary containing the setting that changed.
    #  See "from options" in gv_reference.txt


option_change = signal(u"option_change")
option_change.connect(notify_option_change)


"""
Run when plugin is loaded
"""
print(u"Flow Settings")
print_settings()
ls.load_settings()

rate_footer = showInFooter()  # instantiate class to enable data in footer
rate_footer.label = u"Flow rate"
rate_footer.val = "N/A"
rate_footer.unit = u" ?/hr"

volume_footer = showInFooter()  # instantiate class to enable data in footer
volume_footer.label = u"Water usage"
volume_footer.val = 0
volume_footer.unit = u" ?"
