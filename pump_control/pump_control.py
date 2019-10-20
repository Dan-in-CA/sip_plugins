from __future__ import print_function

# !/usr/bin/env python

from threading import Thread
from random import randint
import json
import time
import sys
import traceback
import web
import gv  # Get access to SIP's settings
from urls import urls  # Get access to SIP's URLs
from sip import template_render
from webpages import ProtectedPage
from helpers import get_rpi_revision
from blinker import signal

# I2C bus Rev Raspi RPI=1 rev1 RPI=0 rev0
try:
    import smbus  # for PCF 8591

    PC_i2C = smbus.SMBus(1 if get_rpi_revision() >= 2 else 0)
except ImportError:
    PC_i2C = None

# Add a new url to open the data entry page.
urls.extend(
    [
        "/pcontrol",
        "plugins.pump_control.settings",
        "/pcontrolj",
        "plugins.pump_control.settings_json",
        "/pcontrola",
        "plugins.pump_control.update",
        "/pcontroll",
        "plugins.pump_control.pump_control_log",
        "/pcontrolr",
        "plugins.pump_control.delete_log",
    ]
)

# Add this plugin to the home page plugins menu
gv.plugin_menu.append(["Pump Control settings", "/pcontrol"])

# Define Alarm Signal
alarm = signal("alarm_toggled")

################################################################################
# Main function loop:                                                          #
################################################################################
class PumpControlSender(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()
        self.status = ""

        self._sleep_time = 0

    def add_status(self, msg):
        if self.status:
            self.status += "\n" + msg
        else:
            self.status = msg
        print(msg)

    def update(self):
        self._sleep_time = 0
        nconf = get_pump_control_options()["pump_control_config"]
        if (
            get_now_config() != nconf
        ):  # if the new config is different from the one in arduino
            set_now_config(nconf)

    def _sleep(self, secs):
        self._sleep_time = secs
        while self._sleep_time > 0:
            time.sleep(1)
            self._sleep_time -= 1

    def run(self):
        time.sleep(
            randint(3, 10)
        )  # Sleep some time to prevent printing before startup information
        print("Pump Control plugin is active")
        last_time = gv.now
        self.update()
        while True:
            try:
                datapc = get_pump_control_options()  # load data from file
                if datapc["use_pc"] != "off":  # if pcf plugin is enabled
                    if (
                        datapc["use_log"] != "off" and datapc["time"] != "0"
                    ):  # if log is enabled and time is not 0 min
                        actual_time = gv.now
                        if actual_time - last_time > (
                            int(datapc["time"])
                        ):  # if is time for save
                            pressure = get_now_pressure()
                            pc_status = get_now_status()
                            last_time = actual_time
                            self.status = ""
                            TEXT = (
                                "On "
                                + time.strftime(
                                    "%d.%m.%Y at %H:%M:%S", time.localtime(time.time())
                                )
                                + " save Pump Control Pressure="
                                + str(pressure)
                                + " Pump Control Status="
                                + str(pc_status)
                            )
                            self.add_status(TEXT)
                            write_log(pressure, pc_status)
                            if "ALARM" in pc_status:
                                alarm.send("pump_control", txt=pc_status)
                self._sleep(1)

            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                err_string = "".join(
                    traceback.format_exception(exc_type, exc_value, exc_traceback)
                )
                self.add_status("Pump Control plugin encountered error: " + err_string)
                self._sleep(5)


checker = PumpControlSender()


################################################################################
# Helper functions:                                                            #
################################################################################


def get_now_pressure():
    try:
        return PC_i2C.read_word_data(0x09, 0x81)
    except AttributeError:
        return "0"


def get_now_status():
    out = "ERROR"
    try:
        s = PC_i2C.read_byte_data(0x09, 0x91)
        if s == 0:
            out = "Pump Off"
        elif s == 1:
            out = "Pump Starting"
        elif s == 2:
            out = "Pump Working OK"
        elif s == 10:
            out = "ALARM: Underpressure - PUMP OFF"
        elif s == 11:
            out = "ALARM: Overpressure - PUMP OFF"
    except:
        pass

    return out


def get_now_config():
    l = {"max_pressure": 0, "min_pressure": 0, "max_wait": 0}
    try:
        l["max_pressure"] = PC_i2C.read_word_data(0x09, 0x92)
        l["min_pressure"] = PC_i2C.read_word_data(0x09, 0x93)
        l["max_wait"] = PC_i2C.read_word_data(0x09, 0x94)
    except AttributeError:
        pass
    return l


def set_now_config(dict):
    try:
        PC_i2C.write_word_data(0x09, 0x0B, dict["max_pressure"])
        PC_i2C.write_word_data(0x09, 0x0C, dict["min_pressure"])
        PC_i2C.write_word_data(0x09, 0x0D, dict["max_wait"])
    except AttributeError:
        pass


def get_pump_control_options():
    """Returns the data form file."""
    datapc = {
        "use_pc": "off",
        "use_log": "off",
        "time": "0",
        "records": "0",
        "pressure_val": get_now_pressure(),
        "pump_status_val": get_now_status(),
        "pump_control_config": get_now_config(),
        "status": checker.status,
    }
    try:
        with open("./data/pump_control.json", "r") as f:  # Read the settings from file
            file_data = json.load(f)
        for key, value in file_data.iteritems():
            if key in datapc:
                datapc[key] = value
    except IOError:
        defaultpcf = {
            "use_pc": "off",
            "use_log": "off",
            "time": "0",
            "records": "0",
            "pressure_val": get_now_pressure(),
            "pump_status_val": get_now_status(),
            "pump_control_config": get_now_config(),
            "status": checker.status,
        }

        with open(
            "./data/pump_control.json", "w"
        ) as f:  # write defalult settings to file
            json.dump(defaultpcf, f)

    except Exception:
        pass

    return datapc


def read_log():
    """Read pump_control log"""
    try:
        with open("./data/pump_control_log.json") as logf:
            records = logf.readlines()
        return records
    except IOError:
        return []


def write_log(pressure, status):
    """Add run data to csv file - most recent first."""
    datapc = get_pump_control_options()
    logline = (
        '{"Time":"'
        + time.strftime('%H:%M:%S","Date":"%d-%m-%Y"', time.gmtime(gv.now))
        + ',"Pressure":"'
        + str(pressure)
        + '","Status":"'
        + str(status)
        + '"}\n'
    )
    log = read_log()
    log.insert(0, logline)
    with open("./data/pump_control_log.json", "w") as f:
        if int(datapc["records"]) != 0:
            f.writelines(log[: int(datapc["records"])])
        else:
            f.writelines(log)
    return


################################################################################
# Web pages:                                                                   #
################################################################################


class settings(ProtectedPage):
    """Load an html page for entering lcd adjustments."""

    def GET(self):
        return template_render.pump_control(get_pump_control_options())


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format."""

    def GET(self):
        web.header("Access-Control-Allow-Origin", "*")
        web.header("Content-Type", "application/json")
        return json.dumps(get_pump_control_options())


class update(ProtectedPage):
    """Save user input to pump_control.json file."""

    def GET(self):
        qdict = web.input()
        if "use_pc" not in qdict:
            qdict["use_pc"] = "off"
        if "use_log" not in qdict:
            qdict["use_log"] = "off"

        qdict["pump_control_config"] = {
            "max_pressure": int(qdict["max_pressure"]),
            "min_pressure": int(qdict["min_pressure"]),
            "max_wait": int(qdict["max_wait"]),
        }
        del qdict["max_pressure"]
        del qdict["min_pressure"]
        del qdict["max_wait"]
        with open("./data/pump_control.json", "w") as f:  # write the settings to file
            json.dump(qdict, f)
        checker.update()
        raise web.seeother("/")


class pump_control_log(ProtectedPage):  # save log file from web as csv file type
    """Simple PCF Log API"""

    def GET(self):
        records = read_log()
        data = "Date, Time, Pressure, Pump Control Status\n"
        for r in records:
            event = json.loads(r)
            data += (
                event["Date"]
                + ", "
                + event["Time"]
                + ", "
                + str(event["Pressure"])
                + ", "
                + str(event["Status"])
                + "\n"
            )
        web.header("Content-Type", "text/csv")
        return data


class delete_log(ProtectedPage):  # delete log file from web
    """Delete all pcflog records"""

    def GET(self):
        qdict = web.input()
        with open("./data/pump_control_log.json", "w") as f:
            f.write("")
        raise web.seeother("/pcontrol")
