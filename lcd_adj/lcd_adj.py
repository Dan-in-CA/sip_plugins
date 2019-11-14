#!/usr/bin/env python
# This plugin sends data to I2C for LCD 16x2 char with PCF8574. Visit for more: www.pihrt.com/elektronika/258-moje-rapsberry-pi-i2c-lcd-16x2.

from __future__ import print_function
from threading import Thread, Lock
import json
import time
import sys
import traceback

import web
import gv  # Get access to SIP's settings
from urls import urls  # Get access to SIP's URLs
from sip import template_render
from webpages import ProtectedPage
from helpers import uptime, get_ip, get_cpu_temp, get_rpi_revision
from blinker import signal
import pylcd  # Library for LCD 16x2 PCF8574

# Add a new url to open the data entry page.
urls.extend(["/lcd", "plugins.lcd_adj.settings",
             "/lcdj", "plugins.lcd_adj.settings_json",
             "/lcda", "plugins.lcd_adj.update"])

# Add this plugin to the home page plugins menu
gv.plugin_menu.append(["LCD Settings", "/lcd"])

################################################################################
# Main function loop:                                                          #
################################################################################


class LCDSender(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()
        self.status = ""
        self.alarm_mode = False
        self.schedule_mode = False
        self._display = ["name"]
        self._addresses = set([0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x38, 0x39, 0x3a, 0x3b, 0x3c, 0x3d, 0x3e, 0x3f])
        self._sleep_time = 0
        self._lcd_lock = Lock()
        self._lcd = None

    def _lcd_print(self, report, txt=None):
        self._lcd_lock.acquire()
        """Print messages to LCD 16x2"""
        datalcd = get_lcd_options()
        adr = int(datalcd["adress"], 0)
        if adr not in self._addresses:
            self.status = ""
            self.add_status("Error: Address is not range 0x20-0x27 or 0x38-0x3F!")
            self._lcd_lock.release()
            self._sleep(5)
            return

        # If the address has changed: Turn off the backlight and clear the LCD then forget the pylcd object.
        if self._lcd is not None and self._lcd.lcd_device.addr != adr:
            self._lcd.backlight = 0 # takes effect during next update call on self._lcd
            self._lcd.lcd_clear()
            self._lcd = None

        # Create a pylcd object if necessary
        if self._lcd is None:
            self._lcd = pylcd.lcd(adr, (1 if get_rpi_revision() >= 2 else 0), 1)  # Address for PCF8574 = example 0x20, Bus Raspi = 1 (0 = 256MB, 1=512MB)
            if self._lcd.error is not None:
                self.status = ""
                self.add_status("Error: [Errno " + str(self._lcd.error.errno) + "] Display not found at address " + datalcd["adress"])
                self._lcd = None
                self._lcd_lock.release()
                self._sleep(5)
                return

        if report == "name":
            self._lcd.lcd_clear()
            self._lcd.lcd_puts(gv.sd["name"], 1)
            self._lcd.lcd_puts("Irrigation syst.", 2)
            self.add_status("SIP. / Irrigation syst.")
        elif report == "d_sw_version":
            self._lcd.lcd_clear()
            self._lcd.lcd_puts("Software SIP:", 1)
            self._lcd.lcd_puts(gv.ver_date, 2)
            self.add_status("Software SIP: / " + gv.ver_date)
        elif report == "d_ip":
            self._lcd.lcd_clear()
            ip = get_ip()
            self._lcd.lcd_puts("My IP is:", 1)
            self._lcd.lcd_puts(str(ip), 2)
            self.add_status("My IP is: / " + str(ip))
        elif report == "d_port":
            self._lcd.lcd_clear()
            self._lcd.lcd_puts("Port IP:", 1)
            self._lcd.lcd_puts(str(gv.sd["htp"]), 2)
            self.add_status("Port IP: / {}".format(gv.sd["htp"]))
        elif report == "d_cpu_temp":
            self._lcd.lcd_clear()
            temp = str(get_cpu_temp()) + " " + gv.sd["tu"]
            self._lcd.lcd_puts("CPU temperature:", 1)
            self._lcd.lcd_puts(temp, 2)
            self.add_status("CPU temperature: / " + temp)
        elif report == "d_date_time":
            self._lcd.lcd_clear()
            da = time.strftime("%d.%m.%Y", time.gmtime(gv.now))
            ti = time.strftime("%H:%M:%S", time.gmtime(gv.now))
            self._lcd.lcd_puts(da, 1)
            self._lcd.lcd_puts(ti, 2)
            self.add_status(da + " " + ti)
        elif report == "d_uptime":
            self._lcd.lcd_clear()
            up = uptime()
            self._lcd.lcd_puts("System run time:", 1)
            self._lcd.lcd_puts(up, 2)
            self.add_status("System run time: / " + up)
        elif report == "d_rain_sensor":
            self._lcd.lcd_clear()
            if gv.sd["rs"]:
                rain_sensor = "Active"
            else:
                rain_sensor = "Inactive"
            self._lcd.lcd_puts("Rain sensor:", 1)
            self._lcd.lcd_puts(rain_sensor, 2)
            self.add_status("Rain sensor: / " + rain_sensor)
        elif report == "d_running_stations":  # Report running Stations
            self._lcd.lcd_clear()
            if gv.pon is None:
                prg = "Idle"
            elif gv.pon == 98:  # something is running
                prg = "Run-once"
            elif gv.pon == 99:
                prg = "Manual Mode"
            else:
                prg = "Prog: {}".format(gv.pon)

            s = ""
            if prg != "Idle":
                # Get Running Stations from gv.ps
                for i in range(len(gv.ps)):
                    p, d = gv.ps[i]
                    if p != 0:
                        s += "S{} ".format(str(i + 1))
            self._lcd.lcd_puts(prg, 1)
            self._lcd.lcd_puts(s, 2)

        elif report == "d_alarm_signal":  # ALARM!!!!
            self._lcd.lcd_clear()
            self._lcd.lcd_puts("ALARM", 1)
            self._lcd.lcd_puts(txt, 2)
            self.add_status("Alarm! / " + txt)

        elif report == "d_stat_schedule_signal":  # A program has been scheduled
            self._lcd.lcd_clear()
            self._lcd.lcd_puts("New Program", 1)
            txt = "Running"  # Do not Know what else to display
            self._lcd.lcd_puts(txt, 2)
            self.add_status("New Program Running / " + txt)

        self._lcd_lock.release()

    def add_status(self, msg):
        if self.status:
            self.status += "\n" + msg
        else:
            self.status = msg
        print(msg)

    def update(self):
        lcd_opts = get_lcd_options()
        self._display = ["name"]
        for key in list(lcd_opts.keys()):
            if key.startswith("d_") and lcd_opts[key] == "on":
                self._display.append(key)
        self._sleep_time = 0

    def _sleep(self, secs):
        self._sleep_time = secs
        while self._sleep_time > 0:
            time.sleep(1)
            self._sleep_time -= 1

    def alarm(self, name, **kw):
        datalcd = get_lcd_options()
        if datalcd["use_lcd"] != "off" and not self.alarm_mode:  # if LCD plugin is enabled
            self.alarm_mode = True
        self._lcd_print("d_alarm_signal", txt=kw["txt"])

    def notify_station_scheduled(self, name, **kw):
        datalcd = get_lcd_options()
        if datalcd["use_lcd"] != "off" and not self.schedule_mode:  # if LCD plugin is enabled
            self.schedule_mode = True
            self._lcd_print("d_stat_schedule_signal")

    def run(self):
        time.sleep(3)  # Sleep 3 seconds to prevent printing before startup information (Will not prevent Alarm or Scheduled Station)
        print("LCD plugin is active")
        self.update()
        text_shift = 0
        while True:
            try:
                datalcd = get_lcd_options()  # load data from file
                if datalcd["use_lcd"] != "off":  # if LCD plugin is enabled
                    if text_shift >= len(self._display):
                        text_shift = 0
                        self.status = ""
                    if self.alarm_mode:
                        self._sleep(20)
                        self.alarm_mode = False
                    elif self.schedule_mode:
                        self._sleep(5)
                        self.schedule_mode = False
                        self._lcd_print("d_running_stations")
                        self._sleep(5)
                    else:
                        self._lcd_print(self._display[text_shift])
                        text_shift += 1  # Increment text_shift value
                self._sleep(4)

            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                err_string = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
                self.add_status("LCD plugin encountered error: " + err_string)
                self._sleep(5)


checker = LCDSender()
alarm = signal("alarm_toggled")
alarm.connect(checker.alarm)
program_started = signal("stations_scheduled")
program_started.connect(checker.notify_station_scheduled)
################################################################################
# Helper functions:                                                            #
################################################################################


def get_lcd_options():
    """Returns the data form file."""
    datalcd = {
        "use_lcd": "off",
        "adress": "0x20",
        "d_sw_version": "on",
        "d_ip": "on",
        "d_port": "on",
        "d_cpu_temp": "on",
        "d_date_time": "on",
        "d_uptime": "on",
        "d_rain_sensor": "on",
        "d_running_stations": "on",
        "status": checker.status,
    }
    try:
        with open("./data/lcd_adj.json", "r") as f:  # Read the settings from file
            file_data = json.load(f)
        for key, value in file_data.items():
            if key in datalcd:
                datalcd[key] = value
    except Exception:
        pass

    return datalcd

################################################################################
# Web pages:                                                                   #
################################################################################


class settings(ProtectedPage):
    """Load an html page for entering lcd adjustments."""

    def GET(self):
        return template_render.lcd_adj(get_lcd_options())


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format."""

    def GET(self):
        web.header("Access-Control-Allow-Origin", "*")
        web.header("Content-Type", "application/json")
        return json.dumps(get_lcd_options())


class update(ProtectedPage):
    """Save user input to lcd_adj.json file."""

    def GET(self):
        qdict = web.input()
        datalcd = {
            "use_lcd": "off",
            "adress": "0x20",
            "d_sw_version": "on",
            "d_ip": "on",
            "d_port": "on",
            "d_cpu_temp": "on",
            "d_date_time": "on",
            "d_uptime": "on",
            "d_rain_sensor": "on",
            "d_running_stations": "on",
            "status": checker.status,
        }
        for k in list(datalcd.keys()):
            if k in qdict:
                datalcd[k] = qdict[k]
            else:
                datalcd[k] = "off"

        with open("./data/lcd_adj.json", "w") as f:  # write the settings to file
            json.dump(datalcd, f, indent=4, sort_keys=True)
        checker.update()
        raise web.seeother(u"/")
