# !/usr/bin/env python
# -*- coding: utf-8 -*-

# standard library imports
import json  # for working with data file
from threading import Thread
from threading import Event
from time import sleep

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings

# from sip import template_render  # Needed for working with web.py templates
# from urls import urls  # Get access to SIP's URLs
# import web  # web.py framework
# from webpages import ProtectedPage  # Needed for security

import datetime
import jmespath
import os

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
# gv.plugin_menu.append([_("Schedule Data Collector"), "/schedule_data_collector"])

settings = {}
SCHEDULE_DATA_PATH = "./static/data/schedule_data"
CONFIG_FILE_PATH = "./data/schedule_data_collector.json"
# 60 days, in seconds
RETENTION = 86400 * 60


def validate_int_list(int_list):
    """Validates a list of possible integers and either returns each valid
    integer or None as a tuple

    """
    validated_list = []
    for index in range(len(int_list)):
        try:
            validated_list.append(int(int_list[index]))
        except (TypeError, ValueError):
            validated_list.append(None)

    return tuple(validated_list)


def create_station_data_file(new_file):
    """Use x and y as headings for the graph plugin"""
    with open(new_file, "w") as f:
        f.write("x,y\n")


def log_stat(timestamp, value, station, period, stat):
    """Log scheduling statistic. Required directories are created at startup."""
    data_file_path = os.path.join(
        SCHEDULE_DATA_PATH, period, station + "_" + stat + ".csv"
    )

    if not os.path.isfile(data_file_path):
        create_station_data_file(data_file_path)

    with open(data_file_path, "w") as f:
        # Log timestamp as milliseconds for chart.js
        f.write(f"{timestamp * 1000},{value}")


def accumulate_data_files():
    """ """
    now = int(gv.now)

    # for station in settings["stations"].keys():
    for station in range(0, len(gv.snames)):
        for stat in ["planned", "actual", "diff"]:
            discrete_data_file = os.path.join(
                SCHEDULE_DATA_PATH, "discrete", station + "_" + stat + ".csv"
            )
            accumulated_data_file = os.path.join(
                SCHEDULE_DATA_PATH, "daily", station + "_" + stat + ".csv"
            )
            if os.path.isfile(discrete_data_file):
                if os.path.isfile(accumulated_data_file):
                    # Could read the file contents to get last entry but is it
                    # worth it?
                    last_accumulated = datetime.fromtimestamp(
                        os.path.getmtime(accumulated_data_file)
                    )
                else:
                    last_accumulated = datetime.datetime.now() - datetime.timedelta(
                        days=5
                    )

                next_accumulate_midnight = int(
                    (
                        last_accumulated.replace(
                            hour=0, minute=0, second=0, microsecond=0
                        )
                        + datetime.timedelta(days=2)
                    ).timestamp()
                )

                if next_accumulate_midnight > now:
                    continue

                period_start = next_accumulate_midnight * 1000
                period_end = (next_accumulate_midnight - 86400) * 1000
                duration = 0
                with open(discrete_data_file, "r") as f:
                    for line in f:
                        fields = line.split(",")
                        if fields[0] >= period_start and fields[0] < period_end:
                            duration += fields[1]
                        elif fields[0] >= period_end:
                            log_stat(fields[0], duration, station, "daily", stat)
                            duration = fields[1]


def truncate_data_files():
    """Remove readings from data files that are past the retention
    period. Only process files once a week to save disk IO. Store that
    last truncate timestamp as the new_day signal is also sent on
    startup.
    """

    # Signal new_day is also sent a program start, but we only want to
    # truncate once a week once a week to limit IO?
    if settings["last_truncate"] + (86400 * 7) > now:
        return

    now = int(gv.now)
    # Convert seconds to miliseconds
    retention = RETENTION * 1000
    now_milli = now * 1000

    settings["last_truncate"] = now
    with open(CONFIG_FILE_PATH, "w") as f:
        json.dump(settings, f)

    # for station in settings["stations"].keys():
    for station in range(0, len(gv.snames)):
        for stat in ["planned", "actual", "diff"]:
            for period in ["discrete", "daily"]:
                data_file = os.path.join(
                    SCHEDULE_DATA_PATH, period, station + "_" + stat + ".csv"
                )
                data_file_tmp = f"/tmp/{station}.tmp"

                if os.path.isfile(data_file):
                    with open(data_file, "r") as input:
                        with open(data_file_tmp, "w") as output:
                            # Copy headers straight to output
                            output.write(input.readline())

                            for line in input:
                                fields = line.split(",")
                                if int(fields[0]) + retention > now_milli:
                                    output.write(line)

                    try:
                        # Best option as new sensor data my be being written to file
                        os.replace(data_file_tmp, data_file)
                    except OSError as e:
                        print(f"Cannot replace {data_file}", e)
                        os.remove(data_file_tmp)


def process_data_files(name, **kw):
    """Remove readings from data files that are past the retention
    period. Only process files once a week to save disk IO. Store that
    last truncate timestamp as the new_day signal is also sent on
    startup.
    """
    truncate_data_files()
    accumulate_data_files()


def notify_station_completed(station, **kw):
    """
    based on log_run() from helpers.py
    gv.lrun = [station index, program number, duration, end time]
    """
    # station_idx = station - 1
    station_idx = gv.lrun[0]
    prog = gv.lrun[1]
    dur_actual = gv.lrun[2]

    if prog >= 98:
        # Handle special programs
        dur_planned = dur_actual
    else:
        dur_planned = gv.pd[prog - 1]["duration_sec"][station_idx]

    dur_diff = dur_actual - dur_planned
    start_time = gv.rs[station_idx][0]

    log_stat(start_time, dur_actual, station_idx, "discrete", "actual")
    log_stat(start_time, dur_planned, station_idx, "discrete", "planned")
    log_stat(start_time, dur_diff, station_idx, "discrete", "diff")


def load_schedule_data_collector_settings():
    global settings

    try:
        with open(CONFIG_FILE_PATH, "r") as f:
            settings = json.load(f)

    except IOError:
        # If file does not exist return default value
        settings = {"stations": {}, "last_accumulate": int(gv.now)}


def schedule_data_collector_init():
    if not os.path.isdir(SCHEDULE_DATA_PATH):
        os.makedirs(SCHEDULE_DATA_PATH, exist_ok=True)
        os.makedirs(os.path.join(SCHEDULE_DATA_PATH, "discrete"), exist_ok=True)
        os.makedirs(os.path.join(SCHEDULE_DATA_PATH, "daily"), exist_ok=True)

    load_schedule_data_collector_settings()


new_day_signal = signal("new_day")
new_day_signal.connect(process_data_files)

completed_signal = signal("station_completed")
completed_signal.connect(notify_station_completed)

# Run when plugin is loaded
schedule_data_collector_init()
