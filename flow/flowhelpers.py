from __future__ import print_function
# !/usr/bin/env python
# -*- coding: utf-8 -*-
import gv
from os.path import exists
import json
import codecs
import io
import ast
import threading
import datetime
from blinker import signal

# Variables for flow measurement
IGNORE_INITIAL = 15  # Time at beginning of flow window to ignore for rate measurement purposes (push air out of system)
MEASURE_TIME = 30  # Amount of time needed for a flow measurement

"""
**********************************************
Flow Plugin Helper functions
**********************************************
"""


class LocalSettings:

    def __init__(self):
        self.pulses_per_measure = 0
        self.enable_logging = False
        self.volume_measure = ""
        self.max_log_entries = 0
        self.email_events = []
        self.sms_events = []
        self.voice_events = []
        self.email_variance = 1000.1
        self.sms_variance = 1000.1
        self.voice_variance = 1000.1
        self.load_settings()
        self.valve_flow_data = {}

    def load_settings(self):
        self.pulses_per_measure = 0
        self.enable_logging = False
        self.max_log_entries = 0
        self.volume_measure = ""
        if exists(u"./data/flow.json"):
            with open(u"./data/flow.json", u"r") as f:
                saved_settings = json.load(f)
            if u"text-pulses-per-measure" in saved_settings.keys():
                pulses_per_measure = saved_settings["text-pulses-per-measure"]
                if pulses_per_measure.replace(".", "").isnumeric():
                    self.pulses_per_measure = float(saved_settings["text-pulses-per-measure"])
            if u"enable-logging" in saved_settings.keys():
                self.enable_logging = True
            if u"text-volume-measure" in saved_settings.keys():
                vm = saved_settings["text-volume-measure"]
                if len(vm.strip()) != 0:
                    self.volume_measure = saved_settings["text-volume-measure"]
                else:
                    self.volume_measure = "?"
            else:
                self.volume_measure = "?"
            if u"chk-enable-logging" in saved_settings.keys():
                self.enable_logging = True
            if u"text-max-log-entries" in saved_settings.keys():
                textmax = saved_settings["text-max-log-entries"]
                if textmax.isnumeric():
                    self.max_log_entries = int(textmax)
                else:
                    self.max_log_entries = 0
            else:
                self.max_log_entries = 0
            if u"email-events" in saved_settings.keys():
                self.email_events = saved_settings["email-events"]
            if u"sms-events" in saved_settings.keys():
                self.sms_events = saved_settings["sms-events"]
            if u"voice-events" in saved_settings.keys():
                self.voice_events = saved_settings["voice-events"]
            if u"email-variance" in saved_settings.keys():
                try:
                    self.email_variance = float(saved_settings["email-variance"].replace("%", "")) / 100
                except:
                    self.email_variance = 0.5
            if u"sms-variance" in saved_settings.keys():
                try:
                    self.sms_variance = float(saved_settings["sms-variance"].replace("%", "")) / 100
                except:
                    self.sms_variance = 0.5
            if u"voice-variance" in saved_settings.keys():
                try:
                    self.voice_variance = float(saved_settings["voice-variance"].replace("%", "")) / 100
                except:
                    self.voice_variance = 0.5

    def load_avg_flow_data(self):
        if exists(u"./data/flow_valve_data.json"):
            with open(u"./data/flow_valve_data.json", u"r") as f:
                self.valve_flow_data = json.load(f)
        else:
            self.valve_flow_data = {}
        return self.valve_flow_data

    def save_ave_flow_data(self, flow_data):
        with codecs.open(u"./data/flow_valve_data.json", u"w", encoding=u"utf-8") as f:
            json.dump(flow_data, f)


class WarningNotice:
    #  1: SIP flow sensor is reporting water movement, but all valves should be off
    #  2: SIP has stations on, but sensor is not reporting water movement
    #  3: Flow variance when compared with prior runs

    def __init__(self):
        self.subj_email = ""
        self.msg_email = ""
        self.msg_sms = ""
        self.msg_voice = ""
        self.email_alert = signal("email_alert")  # instantiate blinker signal that email plugin responds to.
        self.sms_alert = signal("sms_alert")  # instantiate blinker signal that sms plugin responds to.
        self.voice_alert = signal("voice_alert")  # instantiate blinker signal that voice plugin responds to.

    def send_notice(self):
        # Send an email
        if len(self.subj_email) > 0 or len(self.msg_email) > 0:
            self.email_alert.send("SIP flow", subj=self.subj_email, msg=self.msg_email)
            self.subj_email = ""
            self.msg_email = ""
        if len(self.msg_sms) > 0:
            self.sms_alert.send("SIP flow", msg=self.msg_sms)
            self.msg_sms = ""
        if len(self.msg_voice) > 0:
            self.voice_alert.send("SIP flow", msg=self.msg_voice)
            self.msg_voice = ""


class FlowWindow:
    # Flow window class holds data about the current open valves
    def __init__(self, local_settings):
        self.ls = local_settings
        self._lock = threading.Lock()
        self._start_time = datetime.datetime.now()
        self.end_time = datetime.datetime.now()
        self.start_pulses = 0
        self.end_pulses = 0
        self._pulse_rate = 0
        self.ave_flow_rate = 0
        self._open_valves = []
        self._open_valves_names = []
        self._valve_states = []
        self._valve_open = False
        self.formatted_flow_rates = ""
        self.load_valve_states()
        self._flow_warning1_given = False
        self._flow_warning2_given = False
        self._flow_warning3a_email_given = False
        self._flow_warning3a_sms_given = False
        self._flow_warning3a_voice_given = False
        self._flow_warning3b_email_given = False
        self._flow_warning3b_sms_given = False
        self._flow_warning3b_voice_given = False
        self._warning_notice = WarningNotice()

        # Variables for measuring flow rate
        self.wndw_flow_rate = 0
        self._ave_flow_rate = {}  # Average flow rate from prior run
        self._flow_tracking_started = False
        self._flow_measure_st_time = datetime.datetime.now()
        self._flow_measure_st_count = 0
        self._flow_next_start_time = datetime.datetime.now() + datetime.timedelta(weeks=520)
        self._flow_rate_read_time = datetime.datetime.now()
        self.recorded_time = datetime.datetime.now()

    def load_valve_states(self):
        i = 0
        self._valve_open = False
        self.ave_flow_rate = 0
        self.formatted_flow_rates = ""
        ave_flow_rates = self.ls.load_avg_flow_data()
        missing_flow_rate = False

        while i < len(gv.srvals):
            self._valve_states.append(gv.srvals[i])
            if i != gv.sd["mas"] - 1:
                # Ignore status of or changes in the master valve
                if gv.srvals[i] == 1:
                    # Determine open valves
                    self._open_valves.append(i)
                    self._open_valves_names.append(gv.snames[i])
                    self._valve_open = True

                    if str(self._open_valves[0]) in ave_flow_rates.keys() and not missing_flow_rate:
                        # Calculate the last rate for the open valves
                        self.ave_flow_rate += ave_flow_rates[str(i)]["rate"]

                        if len(self.formatted_flow_rates) > 0:
                            self.formatted_flow_rates += "\n\n"

                        # Create formatted flow rate string
                        self.formatted_flow_rates += gv.snames[i] + "\n"
                        station_flow_rate = round(ave_flow_rates[str(i)]["rate"] / self.ls.pulses_per_measure, 1)
                        self.recorded_time = datetime.datetime.strptime(ave_flow_rates[str(i)]["time"],
                                                                        '%Y-%m-%d %H:%M:%S')
                        self.formatted_flow_rates += "\trate: {:,.1f} {}/hr".format(station_flow_rate,
                                                                                    self.ls.volume_measure)
                        self.formatted_flow_rates += "\n\trecorded: {:%-d %B %Y  %H:%M:%S}".format(self.recorded_time)

                    else:
                        missing_flow_rate = True

            i = i + 1

        if missing_flow_rate:
            self.ave_flow_rate = -1
            self.formatted_flow_rates = ""

    def valve_states(self):
        return self._valve_states

    def open_valves(self):
        # List does not include master valve
        return self._open_valves

    def open_valves_names(self):
        # List does not include master valve
        return self._open_valves_names

    def valve_open(self):
        # Returns True if a valve is open, else False
        return self._valve_open

    def add_open_valve(self, valve_number):
        self._open_valves.append(valve_number)

    @property
    def start_time(self):
        return self._start_time

    @start_time.setter
    def start_time(self, val):
        self._start_time = val
        self.clear_warning_flags()

    def pulse_rate(self):
        return self._pulse_rate

    def valves_status_str(self):
        # Returns string noting which valves are open
        # Does not include master valve
        if len(self._open_valves_names) == 0:
            status_str = "All valves closed"
        else:
            status_str = self._open_valves_names[0]
            i = 1
            while i < len(self._open_valves_names):
                status_str = status_str + ", " + self._open_valves_names[i]
                i = i + 1
        return status_str

    def set_pulse_values(self, rate, count):
        self._pulse_rate = rate
        current_time = datetime.datetime.now()
        delta = current_time - self.start_time
        duration = delta.total_seconds()

        if not self._flow_warning2_given and duration > 3 and not self.valve_open() and rate > 3:
            # Water is flowing but the valves show as off. Send error message.
            print("Flow error 2 encountered")
            self._execute_notification_2(rate)
            self._flow_warning1_given = True

        # Track and save valve flow rate if only a single valve is open
        if not self._flow_tracking_started:
            if duration > IGNORE_INITIAL:  # Ignore the first 15 seconds of flow to push air out of the system
                self._flow_measure_st_time = current_time
                self._flow_measure_st_count = count
                self._flow_next_start_time = current_time + datetime.timedelta(seconds=MEASURE_TIME)  #
                self._flow_tracking_started = True

        elif current_time > self._flow_next_start_time:
            # Completed measurement window.  Collect last flow rate.
            time_delta = current_time - self._flow_measure_st_time
            flow_delta = count - self._flow_measure_st_count
            self.wndw_flow_rate = round(flow_delta / time_delta.total_seconds() * 3600, 1)
            self._flow_rate_read_time = current_time

            # Evaluate flow error conditions
            if not self._flow_warning1_given and self.valve_open() and self.wndw_flow_rate == 0:
                # Water should be flowing, but it does not appear to be.
                print("Flow error 1 encountered:", self.valves_status_str())
                self._execute_notification_1()
                self._flow_warning1_given = True

            if self.ave_flow_rate > 0 and self.valve_open():
                # Current flow rate is less than historical rate
                self._check_notification_3a(rate)
                self._check_notification_3b(rate)

            self._flow_measure_st_time = current_time
            self._flow_measure_st_count = count
            self._flow_next_start_time = current_time + datetime.timedelta(seconds=MEASURE_TIME)

    def _execute_notification_1(self):
        # Water should be flowing, but it does not appear to be.
        text = "SIP {} flow plugin reports flow expected but not detected".format(gv.sd["name"])
        self._warning_notice.subj_email = text
        if len(self._open_valves) == 1:
            text = "SIP {} flow plugin is reporting that {} station should be active, ".format(gv.sd["name"],
                                                                                               self.valves_status_str())
        else:
            text = "SIP {} flow plugin is reporting that {} stations should be active, ".format(gv.sd["name"],
                                                                                                self.valves_status_str())
        text += "but the flow sensor is not detecting any water flow."
        if "1" in self.ls.email_events:
            self._warning_notice.msg_email = text
        if "1" in self.ls.sms_events:
            self._warning_notice.msg_sms = text
        if "1" in self.ls.voice_events:
            self._warning_notice.msg_voice = text
        self._warning_notice.send_notice()

    def _execute_notification_2(self, rate):
        # Water is flowing but the valves show as off.
        flow_rate = round(rate * 3600 / self.ls.pulses_per_measure, 1)
        text = "SIP {} reports unexpected irrigation flow".format(gv.sd["name"])
        self._warning_notice.subj_email = text
        text = "SIP {} flow plugin is reporting that all stations should be shut off, but a flow ".format(
            gv.sd["name"])
        text += "rate of {:,.1f} {} per hour has been detected from the sensor.".format(flow_rate,
                                                                                        self.ls.volume_measure)
        if "2" in self.ls.email_events:
            self._warning_notice.msg_email = text
        if "2" in self.ls.sms_events:
            self._warning_notice.msg_sms = text
        if "2" in self.ls.voice_events:
            self._warning_notice.msg_voice = text
        self._warning_notice.send_notice()

    def _check_notification_3a(self, rate):
        # Current flow rate exceeds historical rate
        flow_ratio = self.wndw_flow_rate / self.ave_flow_rate
        if "3" in self.ls.email_events and flow_ratio >= (
                1 + self.ls.email_variance) and not self._flow_warning3a_email_given:
            # Flow rate is higher than prior runs
            print("Flow error 3a (email) encountered")
            measured_rate = round(self.wndw_flow_rate / self.ls.pulses_per_measure, 2)
            last_rate = round(self.ave_flow_rate / self.ls.pulses_per_measure, 2)
            text = "SIP {} reports higher than expected irrigation flow".format(gv.sd["name"])
            self._warning_notice.subj_email = text
            text = "SIP {} flow plugin is reporting water flow above prior run rates".format(gv.sd["name"])
            if len(self._open_valves) == 1:
                text += " for the station ""{}"".".format(self._open_valves_names[0])
                text += " A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                              self.ls.volume_measure)
                text += "This exceeds the last measured rate of {:,.1f} {}/hr (recorded on {:%-d %B %Y} at {:%H:%M:%S} ) "\
                    .format(last_rate, self.ls.volume_measure, self.recorded_time, self.recorded_time)
                text += "by {:,.1f}%.\n".format((round(measured_rate / last_rate, 1) - 1) * 100)
            else:
                text += ". A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                               self.ls.volume_measure)
                text += "This exceeds the last measured rate of {:,.1f} {}/hr ".format(last_rate,
                                                                                       self.ls.volume_measure)
                text += "by {:,.1f}%.\n\n".format((round(measured_rate / last_rate, 1) - 1) * 100)
                text += "Rates used:\n\n"
                text += self.formatted_flow_rates

            self._warning_notice.msg_email = text
            self._warning_notice.send_notice()
            self._flow_warning3a_email_given = True

        if "3" in self.ls.sms_events and flow_ratio >= (
                1 + self.ls.sms_variance) and not self._flow_warning3a_sms_given:
            # Flow rate is higher than prior runs
            print("Flow error 3a (sms) encountered")
            measured_rate = round(self.wndw_flow_rate / self.ls.pulses_per_measure, 2)
            last_rate = round(self.ave_flow_rate / self.ls.pulses_per_measure, 2)
            text = "SIP {} flow plugin is reporting water flow above the last measured run rate" .format(gv.sd["name"])
            if len(self._open_valves) == 1:
                text += "for the station ""{}"".".format(self._open_valves_names[0])
                text += ". A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                             self.ls.volume_measure)
                text += "This exceeds the last measured rate of {:,.1f} {}/hr ".format(last_rate,
                                                                                            self.ls.volume_measure)
                text += "by {:,.1f}%.\n".format((1 - round(measured_rate / last_rate, 3)) * 100)
            else:
                text += ". A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                               self.ls.volume_measure)
                text += "This exceeds the last measured rate of {:,.1f} {}/hr ".format(last_rate,
                                                                                            self.ls.volume_measure)
                text += "by {:,.1f}% ".format((round(measured_rate / last_rate, 1) - 1) * 100)
                text += "for the following active stations: {}.".format(self.valves_status_str)

            self._warning_notice.msg_sms = text
            self._warning_notice.send_notice()
            self._flow_warning3a_sms_given = True

        if "3" in self.ls.voice_events and flow_ratio >= (
                1 + self.ls.voice_variance) and not self._flow_warning3a_voice_given:
            # Flow rate is higher than prior runs
            print("Flow error 3a (voice) encountered")
            measured_rate = round(self.wndw_flow_rate / self.ls.pulses_per_measure, 2)
            last_rate = round(self.ave_flow_rate / self.ls.pulses_per_measure, 2)
            text = "SIP {} flow plugin is reporting water flow above the last measured run rate" .format(gv.sd["name"])
            if len(self._open_valves) == 1:
                text += "for the station ""{}"".".format(self._open_valves_names[0])
                text += ". A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                             self.ls.volume_measure)
                text += "This exceeds the last measured rate of {:,.1f} {}/hr ".format(last_rate,
                                                                                            self.ls.volume_measure)
                text += "by {:,.1f}%.\n".format((1 - round(measured_rate / last_rate, 3)) * 100)
            else:
                text += ". A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                               self.ls.volume_measure)
                text += "This exceeds the last measured rate of {:,.1f} {}/hr ".format(last_rate,
                                                                                            self.ls.volume_measure)
                text += "by {:,.1f}% ".format((round(measured_rate / last_rate, 1) - 1) * 100)
                text += "for the following active stations: {}.".format(self.valves_status_str)

            self._warning_notice.msg_voice = text
            self._warning_notice.send_notice()
            self._flow_warning3a_voice_given = True

    def _check_notification_3b(self, rate):
        #  Current flow rate is less than historical rate
        flow_ratio = self.wndw_flow_rate / self.ave_flow_rate
        if "3" in self.ls.email_events and self.wndw_flow_rate > 0 and flow_ratio <= (
                1 - self.ls.email_variance) and not self._flow_warning3b_email_given:
            # Flow rate is slower than prior runs
            print("Flow error 3b (email) encountered")
            measured_rate = round(self.wndw_flow_rate / self.ls.pulses_per_measure, 1)
            last_rate = round(self.ave_flow_rate / self.ls.pulses_per_measure, 1)
            text = "SIP {} reports irrigation flow less than expected".format(gv.sd["name"])
            self._warning_notice.subj_email = text
            text = "SIP {} flow plugin is reporting water flow below the last measured run rate. ".format(gv.sd["name"])
            if len(self._open_valves) == 1:
                text += " for the station ""{}"".".format(self._open_valves_names[0])
                text += "A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                             self.ls.volume_measure)
                text += "This is less than the last measured rate of {:,.1f} {}/hr (recorded on {:%-d %B %Y} at {:%H:%M:%S} ) "\
                    .format(last_rate, self.ls.volume_measure, self.recorded_time, self.recorded_time)
                text += "by {:,.1f}%.\n".format((1 - round(measured_rate / last_rate, 3)) * 100)
            else:
                text += "A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                             self.ls.volume_measure)
                text += "This is less than the last measured rate of {:,.1f} {}/hr ".format(last_rate,
                                                                                            self.ls.volume_measure)
                text += "by {:,.1f}%.\n\n".format((1 - round(measured_rate / last_rate, 3)) * 100)
                text += "Rates used:\n\n"
                text += self.formatted_flow_rates

            self._warning_notice.msg_email = text
            self._warning_notice.send_notice()
            self._flow_warning3b_email_given = True

        if "3" in self.ls.sms_events and self.wndw_flow_rate > 0 and flow_ratio <= (
                1 - self.ls.sms_variance) and not self._flow_warning3b_sms_given:
            # Flow rate is slower than prior runs
            print("Flow error 3b (sms) encountered")
            measured_rate = round(self.wndw_flow_rate / self.ls.pulses_per_measure, 1)
            last_rate = round(self.ave_flow_rate / self.ls.pulses_per_measure, 1)
            text = "SIP {} flow plugin is reporting water flow below the last measured run rate".format(gv.sd["name"])
            if len(self._open_valves) == 1:
                text += " for the station ""{}"".".format(self._open_valves_names[0])
                text += ". A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                             self.ls.volume_measure)
                text += "This is less than the last measured rate of {:,.1f} {}/hr ".format(last_rate,
                                                                                            self.ls.volume_measure)
                text += "by {:,.1f}%.\n".format((1 - round(measured_rate / last_rate, 3)) * 100)
            else:
                text += ". A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                             self.ls.volume_measure)
                text += "This is less than the last measured rate of {:,.1f} {}/hr ".format(last_rate,
                                                                                            self.ls.volume_measure)
                text += "by {:,.1f}% ".format((1 - round(measured_rate / last_rate, 3)) * 100)
                text += "for the following active stations: {}.".format(self.valves_status_str)

            self._warning_notice.msg_sms = text
            self._warning_notice.send_notice()
            self._flow_warning3b_sms_given = True

        if "3" in self.ls.voice_events and self.wndw_flow_rate > 0 and flow_ratio <= (
                1 - self.ls.voice_variance) and not self._flow_warning3b_voice_given:
            # Flow rate is slower than prior runs
            print("Flow error 3b (voice) encountered")
            measured_rate = round(self.wndw_flow_rate / self.ls.pulses_per_measure, 1)
            last_rate = round(self.ave_flow_rate / self.ls.pulses_per_measure, 1)
            text = "SIP {} flow plugin is reporting water flow below the last measured run rate".format(gv.sd["name"])
            if len(self._open_valves) == 1:
                text += " for the station ""{}"".".format(self._open_valves_names[0])
                text += ". A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                             self.ls.volume_measure)
                text += "This is less than the last measured rate of {:,.1f} {}/hr ".format(last_rate,
                                                                                            self.ls.volume_measure)
                text += "by {:,.1f}%.\n".format((1 - round(measured_rate / last_rate, 3)) * 100)
            else:
                text += ". A rate of {:,.1f} {}/hr has been detected from the sensor. ".format(measured_rate,
                                                                                             self.ls.volume_measure)
                text += "This is less than the last measured rate of {:,.1f} {}/hr ".format(last_rate,
                                                                                            self.ls.volume_measure)
                text += "by {:,.1f}% ".format((1 - round(measured_rate / last_rate, 3)) * 100)
                text += "for the following active stations: {}.".format(self.valves_status_str)

            self._warning_notice.msg_voice = text
            self._warning_notice.send_notice()
            self._flow_warning3b_voice_given = True

    def usage(self):
        # Returns water usage in current flow window
        if self.ls.pulses_per_measure > 0:
            return round(((self.end_pulses - self.start_pulses) / self.ls.pulses_per_measure) * 10) / 10
        else:
            return 0

    def duration(self):
        delta = self.end_time - self._start_time
        return int(delta.total_seconds())

    def write_log(self):
        """
        Add flow window data to json log file - most recent first.
        If a record limit is specified (limit) the number of records is truncated.
        """
        if not self._lock.locked():
            # if locked, then this write_log request came right on the heels of the last one.  Valve changes come
            # in one at a time, even if they are shut off simultaneously.  The flow window needs to
            # collect these in a group. To make this work, the program puts write_log actions on a
            # short delay ignoring requests that come in quickly on the heels of the last one.  All changes
            # are then collected at the end of the delay
            with self._lock:
                if self.ls.enable_logging:
                    open_valves = ""
                    open_valves_str = ""
                    i = 0
                    for valve in self._open_valves:
                        # Create the string of valve numbers separated by commas
                        open_valves = open_valves + str(valve)
                        open_valves_str = open_valves_str + gv.snames[valve]
                        i = i + 1
                        if i < len(self._open_valves):
                            open_valves = open_valves + ","
                            open_valves_str = open_valves_str + ","

                    logline = (
                        u'{"'
                        + u"valves"
                        + u'":"'
                        + open_valves
                        + u'","'
                        + u'stations'
                        + u'":"'
                        + open_valves_str
                        + u'","'
                        + "usage"
                        + u'":'
                        + str(FlowWindow.usage(self))
                        + u',"'
                        + u'measure'
                        + u'":"'
                        + self.ls.volume_measure
                        + u'","'
                        + u'duration'
                        + u'":"'
                        + timestr(FlowWindow.duration(self))
                        + u'","'
                        + u'date'
                        + u'":"'
                        + self.start_time.strftime(u'%Y-%m-%d')
                        + '","'
                        + u'start'
                        + u'":"'
                        + self.start_time.strftime(u'%H:%M:%S')
                        + u'"}'
                    )
                    lines = [logline + u"\n"]
                    log = read_log()
                    for r in log:
                        lines.append(json.dumps(r) + u"\n")
                    with codecs.open(u"./data/flowlog.json", u"w", encoding=u"utf-8") as f:
                        if self.ls.max_log_entries > 0:
                            f.writelines(lines[: self.ls.max_log_entries])
                        else:
                            f.writelines(lines)

        # Write out valve flow rate if only a single valve running
        if len(self._open_valves) == 1 and self.wndw_flow_rate > 0:
            valve_entry = {"rate": self.wndw_flow_rate,
                           "time": self._flow_rate_read_time.strftime(u'%Y-%m-%d %H:%M:%S')}
            flow_data = self.ls.load_avg_flow_data()
            flow_data.update({str(self._open_valves[0]): valve_entry})
            self.ls.save_ave_flow_data(flow_data)
            # Refresh the flow data in local settings
            self.ls.load_avg_flow_data

    def clear_warning_flags(self):
        self._flow_warning1_given = False
        self._flow_warning2_given = False


class ValveNotice:
    def __init__(self, switchtime, counter):
        self.switch_time = switchtime
        self.counter = counter


class FlowSmoother:
    # Averages the flow readings for a smoother readout
    def __init__(self, average_period):
        self._average_period = average_period
        self._readings = [0] * average_period
        self._last_reading = float(0)
        self._i = 0

    def add_reading(self, reading):
        self._last_reading = reading
        self._readings[self._i % self._average_period] = reading
        self._i = self._i + 1

    def last_reading(self):
        return self._last_reading

    def ave_reading(self):
        reading_sum = 0
        i = 0
        while i < self._average_period:
            reading_sum = reading_sum + self._readings[i]
            i = i + 1
        return reading_sum / self._average_period


def timestr(t):
    """
    Convert duration in seconds to string in the form mm:ss.
    """
    return (
            str((t // 60 >> 0) // 10 >> 0)
            + str((t // 60 >> 0) % 10)
            + u":"
            + str((t % 60 >> 0) // 10 >> 0)
            + str((t % 60 >> 0) % 10)
    )


def read_log():
    """
    Read data from irrigation log file.
    """
    result = []
    try:
        with io.open(u"./data/flowlog.json") as logf:
            records = logf.readlines()
            for i in records:
                try:
                    rec = ast.literal_eval(json.loads(i))
                except ValueError:
                    rec = json.loads(i)
                result.append(rec)
        return result
    except IOError:
        return result
