# !/usr/bin/env python

# This SIP plugin trap stdout and stderr and listens for SIP events.
# It print formatted SIP event to stdout. The intent is to facilitate
# development of SIP core and plugins, and for system diagnostic.

# __author__ = "@embak"
#

# standard library imports
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Final

# local module imports
import gv
import web  # web.py framework
from blinker import signal
from urls import urls  # Get access to SIP's URLs
from webpages import ProtectedPage  # Needed for security

from sip import template_render  # Needed for working with web.py templates

###################
# Local variables

DATA_FILE = "./data/a_system_log.json"

# Settings with default values
_settings = {
    "plugin_log_enable": False,
    "program_log_enable": False,
    "start_with_timestamp": False,
    "station_log_enable": False,
    "station_log_output_enable": False,
    "system_log_enable": False,
    "water_log_enable": False,
    "web_server_mute": True,
}


###################
# WebUI page functions and variables
#

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
        "/a_system_log-sp","plugins.a_system_log.settings",
        "/a_system_log-save","plugins.a_system_log.save_settings",
    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"].
gv.plugin_menu.append([("A SYSTEM LOG Plugin"), "/a_system_log-sp"])


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        settings = get_settings_from_file()
        return template_render.a_system_log(settings, "")  # open settings page


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict{} if they are checked.
    """

    def GET(self):
        new_settings = _settings.copy()

        qdict = (
            web.input()
        )  # Dictionary of values returned as query string from settings page.

        for key, value in new_settings.items():
            if isinstance(value, bool):  # Process CheckBoxes
                new_settings[key] = key in qdict
            else:
                if key in qdict:
                    new_settings[key] = qdict[key]

        apply_settings_and_save_to_file(new_settings)
        raise web.seeother("/")  # Return user to home page.


###################
# This plugin settings manipulations
#


def get_settings_from_file() -> dict:
    """
    Read settings from file
    """
    global _settings
    from os.path import exists

    # If file doesn't exist, create it with defaults
    if not exists(DATA_FILE):
        print("PLUGIN - A SYSTEM LOG : Creating default settings file")
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(_settings, f, indent=4, sort_keys=True)
        except OSError as e:
            print("A System Log Plugin couldn't create data file:", e)
        return _settings

    # Load existing settings
    try:
        with open(DATA_FILE, "r") as file:
            try:
                _settings = json.load(file)
            except ValueError as e:
                print("A SYSTEM LOG PLUGIN: couldn't parse data file:", e)
    except OSError as e:
        print("A SYSTEM LOG PLUGIN: couldn't open data file:", e)
    return _settings


def apply_settings_and_save_to_file(new_settings) -> None:
    """
    Apply settings changes
    """
    global _settings

    settings_changed = False
    for key, value in _settings.items():
        if new_settings[key] != value:
            settings_changed = True
    if settings_changed:
        _settings = new_settings

        with open(DATA_FILE, "w") as f:
            json.dump(_settings, f, indent=4, sort_keys=True)  # save to file

        apply_event_settings()
        apply_other_settings()
        report_plugin_setting_change("A System Log")


###################
# Helper functions
#

# TODO: move to helper.py
plugin_setting_change = signal("plugin_setting_change")


def report_plugin_setting_change(name, **kw) -> None:
    """
    Send blinker signal indicating that plugin settings changed.
    """
    plugin_setting_change.send(name, **kw)


def name_to_str(name=None) -> str:
    """
    Format signal name argument for logging
    Usually contain SIP or plugin name
    Return empty string by default
    """
    return f"[{name}] " if name else ""


def sid_to_str(sid) -> str:
    """
    Return station number and name for logging
    """
    return f"{(sid + 1):02d} - {gv.snames[sid]}"


def pid_to_str(pid) -> str:
    """Return program number and name for logging"""
    if 0 <= pid < len(gv.pd):
        return f"{(pid + 1):02d} - {gv.pnames[pid]}"
    pnum = pid + 1
    if pnum == 98:
        return "Run-once"
    elif pnum == 99:
        return "Manual Mode"
    elif pnum == 100:
        return "Node-red"
    return ""


def duration_to_hms(seconds) -> str:
    """From duration in seconds, return string in hh:mm:ss"""
    if seconds == float("inf"):
        return "Continuous"

    minutes, s = divmod(seconds, 60)
    h, m = divmod(minutes, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def boot_starttime() -> float:
    """
    Get boot starttime
    Return value in seconds since epoch
    """
    p = re.compile(r"^btime (\d+)$", re.MULTILINE)
    with open("/proc/stat") as f:
        m = p.search(f.read())
    return float(m.groups()[0])


# Get boot time on system start
_boot_time = boot_starttime()


def plugin_starttime() -> float:
    """
    Get starttime of this plugin
    Return an array with values in seconds since epoch
    """
    return float(time.time())


# Get SIP start time once
_starttime = plugin_starttime()


def os_and_process_uptime_str() -> str:
    now = time.time()
    b_uptime = timedelta(seconds=round(now - _boot_time))
    s_uptime = timedelta(seconds=round(now - _starttime))
    return f"OS Uptime {b_uptime}, SIP Uptime {s_uptime}"


# Method used to start SIP
RUN_FROM_CMD_LINE: Final = 0
RUN_FROM_SYSTEMD: Final = 1
RUN_FROM_DEBUGGER: Final = 2

RUN_FROM_STRING = {
    RUN_FROM_CMD_LINE: "command line",
    RUN_FROM_SYSTEMD: "systemd",
    RUN_FROM_DEBUGGER: "debugger",
}


def is_running_from() -> int:
    """
    Detect how SIP was started. Return one of:
    RUN_FROM_CMD_LINE, RUN_FROM_SYSTEMD, RUN_FROM_DEBUGGER
    """

    # from systemd
    if "INVOCATION_ID" in os.environ:
        return RUN_FROM_SYSTEMD

    # from standard pdb / trace-based debuggers
    ide_debuggers = {"debugpy", "pydevd"}
    if sys.gettrace() is not None or bool(
        any(debugger in sys.modules for debugger in ide_debuggers)
    ):
        return RUN_FROM_DEBUGGER

    # default
    return RUN_FROM_CMD_LINE


################
# STD Stream redirection functions
#

# parameters
_prepend_timestamp_to_std = False
_mute_web_server_logs = False


class StderrInterceptor:
    """Intercepts stderr messages and filters out HTTP GET and PUT access logs."""

    def __init__(self, stream) -> None:
        # Keep a reference to the original stderr stream
        self.original_stream = stream

    def _log_date_time_string(self) -> str:
        now = datetime.now(timezone.utc).astimezone()
        # RFC5424: ISO 8601 formatting with millisecond precision and timezone
        return now.isoformat(timespec="milliseconds")

    def write(self, message) -> None:
        # Skip empty messages
        if not message or message.strip() == "":
            # self.original_stream.write(message)
            return

        # Filter out GET and PUT HTTP access logs
        # These typically appear as: "HTTP/1.1 GET", "HTTP/1.1 POST", "HTTP/1.1 PUTT"
        if (
            _mute_web_server_logs
            and (" GET " in message or " POST " in message or " PUT " in message)
        ) and "HTTP" in message:
            return

        if _prepend_timestamp_to_std:
            # Add date and time to the message and write it to the original stdout
            msg = f"[{self._log_date_time_string()}] {message.rstrip()}\n"
        else:
            msg = f"{message.rstrip()}\n"

        self.original_stream.write(msg)

    def flush(self) -> None:
        # Forward flush commands to the original stream to prevent buffering lag
        self.original_stream.flush()

    def isatty(self) -> bool:
        return (
            self.original_stream.isatty()
            if hasattr(self.original_stream, "isatty")
            else False
        )


class StdOutInterceptor:
    """Intercepts stdout messages and adds date and time to each message."""

    def __init__(self, stream) -> None:
        # Keep a reference to the original stdout stream
        self.original_stream = stream
        self.toggle = True

    def _log_date_time_string(self) -> str:
        now = datetime.now(timezone.utc).astimezone()
        # RFC5424: ISO 8601 formatting with millisecond precision and timezone
        return now.isoformat(timespec="milliseconds")

    def write(self, message) -> None:
        # Skip empty messages
        if not message or message.strip() == "":
            # self.original_stream.write(message)
            return

        if _prepend_timestamp_to_std:
            # Add date and time to the message and write it to the original stdout
            msg = f"[{self._log_date_time_string()}] {message.rstrip()}\n"
        else:
            msg = f"{message.rstrip()}\n"

        self.original_stream.write(msg)

    def flush(self) -> None:
        # Forward flush commands to the original stream to prevent buffering lag
        self.original_stream.flush()


####################
# System Events
#


def asl_system_start_or_day_change(name, **kw) -> None:
    """
    System message on day change or system startup
    Reported by SIP timing_loop()
    Day change signal is sent at midnight local time.
    Startup message is deducted from uptime.
    """
    s_uptime = time.time() - _starttime
    if s_uptime < 3.0:  # Just started
        message = "Starting"
    else:
        message = "New day"

    print(f"{name_to_str(name)}SYSTEM - {message}: {os_and_process_uptime_str()}")


def asl_system_login(name, **kw) -> None:
    """
    SIP Web server user logged in message
    """
    print(f"{name_to_str(name)}SYSTEM - User logged in")


def asl_system_options_change(name, **kw) -> None:
    """
    SIP System options changed message
    """
    print(f"{name_to_str(name)}SYSTEM - Options Changed")


def asl_system_reboot(name, **kw) -> None:
    """
    System rebooting message
    Signal: "rebooted"
    """
    print(f"{name_to_str(name)}SYSTEM - Rebooting Now : {os_and_process_uptime_str()}")


def asl_system_restart(name, **kw) -> None:
    """
    System restarting message
    Signal: "restarting"
    """
    print(f"{name_to_str(name)}SYSTEM - Restarting Now : {os_and_process_uptime_str()}")


def asl_system_station_names_change(name, **kw) -> None:
    """
    System station names changed message
    Signal: "station_names"
    """
    print(f"{name_to_str(name)}SYSTEM - Station Names Changed")


def asl_system_value_change(name, values=None) -> None:
    """
    SIP System state (enable / disable) or mode (manual / auto) changed  message.
    Signal: "value_change"
    """
    if "en" in values:
        print(
            f"{name_to_str(name)}SYSTEM - State Changed : {'System ON' if values['en'] else 'System OFF'}"
        )
    if "mm" in values:
        print(
            f"{name_to_str(name)}SYSTEM - Mode Changed : {'Manual' if values['mm'] else 'Auto'}"
        )


####################
# Program Events
#


def asl_program_added(name, pid=None, **kw) -> None:
    """
    Program added message
    Signal: "program_added"
    """
    program_str = pid_to_str(pid)
    print(f"{name_to_str(name)}PROGRAM - Added: {program_str}")


def asl_program_change(name, pid=None, **kw) -> None:
    """
    Program change message
    Signal: "program_change"
    """
    program_str = pid_to_str(pid)
    print(f"{name_to_str(name)}PROGRAM - Changed: {program_str}")


def asl_program_deleted(name, pid=None, **kw) -> None:
    """Program deleted message
    Signal: "program_deleted"
    """
    if 0 <= pid <= 97:
        print(f"{name_to_str(name)}PROGRAM - Deleted : Number {(pid + 1):02d}")


def asl_program_deleted_all(name, **kw) -> None:
    """All program deleted
    Signal: "program_deleted_all"
    """
    print(f"{name_to_str(name)}PROGRAM - Deleted: All Programs")


# Program enable toggled
def asl_program_toggled(name, pid=None, state=None, **kw) -> None:
    """
    Program enable / disable message
    Signal: "program_toggled"
    """
    program_str = pid_to_str(pid)
    state_str = "Enabled" if state else "Disabled"
    print(f"{name_to_str(name)}PROGRAM - {state_str} : {program_str}")


####################
# Station Events
#


def asl_station_scheduled(station, pid=None, start=None, duration=None, **kw) -> None:
    """
    Station scheduled message sent when the station is turning on and a schedule is starting
    Signal: "station_scheduled"
    """
    sid = station - 1
    station_str = sid_to_str(sid)
    if start == None:
        start = gv.rs[sid][0]
    starttime_str = time.strftime("%H:%M:%S", time.localtime(start))
    if duration == None:
        duration = gv.rs[sid][2]
    if gv.rs[sid][1] == float("inf"):
        duration = float("inf")
    duration_str = duration_to_hms(duration)
    if pid == None:
        pid = gv.rs[sid][3] - 1
    program_str = pid_to_str(pid)

    print(
        f"{name_to_str(None)}STATION - Started : Station {station_str} | Start {starttime_str} Duration {duration_str} | Program {program_str}"
    )


def asl_station_completed(
    snum, pid=None, start=None, duration=None, duration_adj=None, **kw
) -> None:
    """
    Station completed message sent when a station schedule ended and turn off
    Signal: "station_completed"
    """
    sid = snum - 1
    station_str = sid_to_str(sid)
    if start == None:
        start = gv.rs[sid][0]
    starttime_str = time.strftime("%H:%M:%S", time.localtime(start))
    if duration == None:
        duration = gv.rs[sid][2]
    if gv.rs[sid][1] == float("inf"):
        duration = float("inf")
    duration_str = duration_to_hms(duration)
    if pid == None:
        pid = gv.rs[sid][3] - 1
    program_str = pid_to_str(pid)

    duration_adj_str = f" {duration_adj}%" if duration_adj else ""

    print(
        f"{name_to_str(None)}STATION - Ended: Station {station_str} | Start {starttime_str} Duration {duration_str}{duration_adj_str} | Program {program_str}"
    )


####################
# Station Output Events
#


def asl_system_zone_change(name, **kw) -> None:
    """
    Station Zone Change (Relays Output)
    Signal "zone_change"
    """
    print(f"{name_to_str(name)}STATION - Set Output : {gv.srvals}")


####################
# Plugin Events
#


def asl_plugin_alarm(name, **kw) -> None:
    """
    Plugin alarm message
    Signal: "alarm"
    """

    if "txt" in kw:
        print(f"PLUGIN Alarm - {name_to_str(name)} :  {kw['txt']}")
    else:
        print(f"PLUGIN Alarm - {name_to_str(name)}")


def asl_plugin_setting_change(name, **kw) -> None:
    """
    Plugin A System Log configuration change
    Signal:
    """

    if "txt" in kw:
        print(f"PLUGIN Config Change - {name_to_str(name)} :  {kw['txt']}")
    else:
        print(f"PLUGIN Config Change - {name_to_str(name)}")


####################
# Water Events
#


def asl_water_rain_detect_change(name, **kw) -> None:
    """
    Rain sensor state changed message
    Signal: "rain_changed"
    """
    print(
        f"{name_to_str(name)}WATER - Rain Sensor Changed to : {'TRUE' if gv.sd['rs'] else 'FALSE'}"
    )


def asl_water_rain_delay_change(name, **kw) -> None:
    """
    Rain delay timer state changed message
    Signal: "rain_delay_change"
    """
    if gv.sd["rd"]:
        print(f"{name_to_str(name)}WATER - Rain Delay Started: {gv.sd['rd']} hours")
    else:
        print(f"{name_to_str(name)}WATER - Rain Delay Ended")


def asl_water_level_change(name, water_level=None, **kw) -> None:
    """
    Include water level changed messages
    Signal: "water_level_change"
    """
    if water_level is not None:
        print(f"{name_to_str(name)}WATER - Water Level Changed : {water_level} %")


################
# This plugin relation between configuration options and signals
#

"""
Structure containing **groups** of **events** with its **setting** enabler
and event **receiver** functions
"""
_events_list = {
    "program": {
        "setting": {"program_log_enable": None},
        "events": {
            "program_added": {"receiver": asl_program_added},
            "program_change": {"receiver": asl_program_change},
            "program_deleted": {"receiver": asl_program_deleted},
            "program_deleted_all": {"receiver": asl_program_deleted_all},
            "program_toggled": {"receiver": asl_program_toggled},
        },
    },
    "station": {
        "setting": {"station_log_enable": None},
        "events": {
            "station_completed": {"receiver": asl_station_completed},
            "station_scheduled": {"receiver": asl_station_scheduled},
        },
    },
    "station_output": {
        "setting": {"station_log_output_enable": None},
        "events": {
            "zone_change": {"receiver": asl_system_zone_change},
        },
    },
    "plugins": {
        "setting": {"plugin_log_enable": None},
        "events": {
            "alarm": {"receiver": asl_plugin_alarm},
            "plugin_setting_change": {"receiver": asl_plugin_setting_change},
        },
    },
    "system": {
        "setting": {"system_log_enable": None},
        "events": {
            "loggedin": {"receiver": asl_system_login},
            "new_day": {"receiver": asl_system_start_or_day_change},
            "option_change": {"receiver": asl_system_options_change},
            "rebooted": {"receiver": asl_system_reboot},
            "restarting": {"receiver": asl_system_restart},
            "station_names": {"receiver": asl_system_station_names_change},
            "value_change": {"receiver": asl_system_value_change},
        },
    },
    "water": {
        "setting": {"water_log_enable": None},
        "events": {
            "rain_changed": {"receiver": asl_water_rain_detect_change},
            "rain_delay_change": {"receiver": asl_water_rain_delay_change},
            "water_level_change": {"receiver": asl_water_level_change},
        },
    },
}


def apply_event_settings() -> None:
    """
    Based on settings values, create signals and connect or disconnect receiver functions
    The _event_list{} contain groups of events. Messages are enabled per group based on settings.
    This functions process groups of events for which setting enable state have change.
    """

    for group_n, group_d in _events_list.items():
        group_setting_n, group_setting_v = next(
            iter(group_d["setting"].items()), (None, None)
        )

        if group_setting_n not in _settings:
            continue  # Mismatch configuration between _event_list and _settings

        if group_setting_v != _settings[group_setting_n]:
            for group_event_n, group_event_d in group_d["events"].items():
                if (
                    group_setting_v is None or "signal" not in group_event_d
                ) and _settings[group_setting_n]:
                    _events_list[group_n]["events"][group_event_n]["signal"] = signal(
                        group_event_n
                    )

                if "signal" in group_event_d:
                    if _settings[group_setting_n]:
                        group_event_d["signal"].connect(group_event_d["receiver"])
                    else:
                        group_event_d["signal"].disconnect(group_event_d["receiver"])

                _events_list[group_n]["setting"][group_setting_n] = _settings[
                    group_setting_n
                ]


def apply_other_settings() -> None:
    """
    Process non signal event related parameters of this plugin
    """
    global _prepend_timestamp_to_std
    global _mute_web_server_logs

    # Don't prepend timestamp to systemd logs
    _prepend_timestamp_to_std = bool(
        _settings["start_with_timestamp"] and is_running_from() != RUN_FROM_SYSTEMD
    )

    _mute_web_server_logs = bool(_settings["web_server_mute"])


##################
# This plugin startup
#


def asl_start() -> None:
    """
    Initialise A System Log plugin
    Reads the settings, apply signal receivers processing functions and set STD redirection
    """

    get_settings_from_file()
    apply_event_settings()
    apply_other_settings()

    # Intercept STD streams once per program execution
    if "ASL_STD_ALREADY_INTERCEPTED" in dir(sys.modules["__main__"]):
        print(
            f"PLUGIN - A SYSTEM LOG : Restarted in the same session from {RUN_FROM_STRING[is_running_from()]}!"
        )
    else:
        sys.modules["__main__"].ASL_STD_ALREADY_INTERCEPTED = True

        # Apply filter to stdout and stderr
        sys.stdout = StdOutInterceptor(sys.stdout)
        sys.stderr = StderrInterceptor(sys.stderr)

        print(
            f"PLUGIN - A SYSTEM LOG : SIP is running from {RUN_FROM_STRING[is_running_from()]}."
        )


asl_start()  # Start the plugin
