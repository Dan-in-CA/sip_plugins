# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Python 2/3 compatibility imports
from __future__ import print_function
from __future__ import division
from six import next

# standard library imports
import datetime
import errno
import json
import os
import re
import sys
from threading import Thread
import time
import traceback
try:
    from urllib.request import urlopen, Request
except ImportError:
    from six.moves.urllib.request import urlopen, Request

# local module imports
import gv  # Get access to SIP's settings
from sip import template_render
from urls import urls  # Get access to SIP's URLs
import web
from webpages import ProtectedPage


def safe_float(s):
    """
    Return a valid float regardless of input.
    """
#     print("safe_float param is: ", s)
    try:
        return float(s)
    except TypeError:
        return 0.0


def mkdir_p(path):
    """
    Creates a new directory or nested directories at the supplied path.
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


# Add a new url to open the data entry page.
# fmt: off
urls.extend(
    [
        u"/lwa", u"plugins.weather_level_adj.settings",
        u"/lwj", u"plugins.weather_level_adj.settings_json",
        u"/luwa", u"plugins.weather_level_adj.update",
    ]
)
# fmt: on

# Add this plugin to the home page plugins menu
gv.plugin_menu.append([_(u"Weather-based Water Level"), u"/lwa"])

lwa_options = {}
lwa_decipher = {}
prior = {u"temp_cutoff": 0, u"water_needed": 0, u"daily_irrigation": 0}


################################################################################
# Main function loop:                                                          #
################################################################################


class WeatherLevelChecker(Thread):
    """
    Get weather data from online source in a separate thread.
    """

    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()
        self.status = u""

        self._sleep_time = 0

    def add_status(self, msg):
        if self.status:
            self.status += u"\n" + msg
        else:
            self.status = msg
        if msg:
            lwa_options[u"status"] = self.status
        print(msg.encode('utf-8'))

    def update(self):
        self._sleep_time = 0

    def _sleep(self, secs):
        self._sleep_time = secs
        while self._sleep_time > 0:
            time.sleep(1)
            self._sleep_time -= 1

    def run(self):
        time.sleep(4)  # Sleep some time to prevent printing before startup information
        
        while True:
            try:
                self.status = ""
                options = lwa_options
                if options[u"auto_wl"] == u"off":
                    if u"wl_weather" in gv.sd:
                        del gv.sd[u"wl_weather"]
                else:
                    print((_(u"Checking weather status") + "...").encode('utf-8'))
                    today = today_info(self, options)
                    forecast = forecast_info(self, options, today)
                    history = history_info(self, today, options)

                    total_info = {
                        u"temp_c": (
                            today[u"temp_c"]
                            + history[u"temp_c"]
                            + forecast[u"temperature_trend"][u"temp_avg"]
                        )
                        // 3,
                        u"rain_mm": (
                            today[u"rain_mm"]
                            + history[u"rain_mm"]
                            + forecast[u"precip_accumulate"]
                        ),
                        u"wind_ms": (
                            today[u"wind_ms"]
                            + history[u"wind_ms"]
                            + forecast[u"wind_average"][u"wind_speed_avg"]
                        )
                        // 3,
                        u"humidity": (
                            today[u"humidity"]
                            + history[u"humidity"]
                            + forecast[u"humidity_trend"][u"humid_avg"]
                        )
                        // 3,
                    }

                    # We assume that the default 100% provides 4mm water per day (normal need)
                    # We calculate what we will need to provide using the mean data of X days around today

                    ini_water_needed = water_needed = (
                        float(options[u"daily_irrigation"])
                        * (int(options[u"days_forecast"]))
                        + 1
                    )  # 4mm per day
                    water_needed *= (
                        1 + (total_info[u"temp_c"] - 20) / 15.0
                    )  # 5 => 0%, 35 => 200%
                    water_needed *= 1 + (
                        total_info[u"wind_ms"] / 100.0
                    )  # 0 => 100%, 20 => 120%
                    water_needed *= (
                        1 - (total_info[u"humidity"] - 50) / 200.0
                    )  # 0 => 125%, 100 => 75%
                    water_needed = round(water_needed, 1)
                    water_left = water_needed - total_info[u"rain_mm"]
                    water_left = round(max(0, min(100, water_left)), 1)

                    water_adjustment = round((water_left / ini_water_needed) * 100.0, 1)

                    water_adjustment = max(
                        safe_float(options[u"wl_min"]),
                        min(safe_float(options[u"wl_max"]), water_adjustment),
                    )

                    # Do not run if the current temperature is below the cutoff temperature and the option is enabled
                    if (
                        safe_float(today[u"temp_c"])
                        <= safe_float(options[u"temp_cutoff"])
                        and options[u"temp_cutoff_enable"] == u"on"):
                        water_adjustment = 0
                    if lwa_options[u"units"] == u"US":
                        self.add_status(
                            _(u"Current temperature") + u":" + u"\n{}deg.{}".format(
                                to_f(today[u"temp_c"]), u"F"
                            )
                        )
                        self.add_status(u"________________________________")
                        self.add_status(
                            _(u"Daily irrigation") + u":" + u"\n{}{}".format(
                                to_in(safe_float(options[u"daily_irrigation"])), u"in"
                            )
                        )
                        self.add_status(
                            _(u"Total rainfall") + u":" + u"\n{}{}".format(
                                to_in(total_info[u"rain_mm"]), u"in"
                            )
                        )
                        self.add_status(
                            (_(u"Water needed") + u"({}" + _(u"days)") + u":"  + u"\n{}{}").format(
                                int(options[u"days_forecast"]) + 1,
                                to_in(water_needed),
                                u"in",
                            )
                        )
                        self.add_status(u"________________________________")
                        self.add_status(
                            _(u"Irrigation needed") + u":" + u"\n{}{}".format(
                                to_in(water_left), u"in"
                            )
                        )
                        self.add_status(
                            _(u"Weather Adjustment") + u":" + u"\n{}{}".format(
                                water_adjustment, u"%"
                            )
                        )
                    else:
                        self.add_status(
                            _(u"Current temperature") + u":"  + u"\n{}deg.{}".format(
                                round(today[u"temp_c"], 1), "C"
                            )
                        )
                        self.add_status(u"________________________________")
                        self.add_status(
                            _(u"Daily irrigation") + u":"  + u"\n{}{}".format(
                                safe_float(options[u"daily_irrigation"]), u"mm"
                            )
                        )
                        self.add_status(
                            _(u"Total rainfall") + u":"  + u"\n{}{}".format(
                                safe_float(total_info[u"rain_mm"]), u"mm"
                            )
                        )
                        self.add_status(
                            (_(u"Water needed") + u" ({}" + _(u"days)") + u":"  + u"\n{}{}").format(
                                int(options[u"days_forecast"]) + 1, 
                                water_needed, u"mm"
                            )
                        )
                        self.add_status(u"________________________________")
                        self.add_status(
                            _(u"Irrigation needed") + u":"  + u"\n{}{}".format(
                                safe_float(water_left), u"mm"
                            )
                        )
                        self.add_status(
                            _(u"Weather Adjustment") + u":" + u"\n{}{}".format(
                                water_adjustment, u"%"
                            )
                        )

                    gv.sd[u"wl_weather"] = water_adjustment

                    self._sleep(3600)

            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                err_string = "".join(
                    traceback.format_exception(exc_type, exc_value, exc_traceback)
                )
                self.add_status(
                    _(u"Weather-based water level encountered error") + u":\n" + err_string
                )
                self._sleep(3600)
            time.sleep(0.5)


checker = WeatherLevelChecker()


################################################################################
# Web pages:                                                                   #
################################################################################
class settings(ProtectedPage):
    """Load an html page for entering weather-based irrigation adjustments"""

    def GET(self):
        return template_render.weather_level_adj(lwa_options)


class settings_json(ProtectedPage):
    """
    Returns plugin settings in JSON format for mobile app.
    """

    def GET(self):
        web.header(u"Access-Control-Allow-Origin", u"*")
        web.header(u"Content-Type", u"application/json")
        return json.dumps(lwa_options)


class update(ProtectedPage):
    """Save user input to weather_level_adj.json file"""

    def GET(self):
        global lwa_options
        global prior

        qdict = web.input()
        # fmt: off
        if (
            qdict[u"units"] == u"US" 
            and lwa_options[u"units"] == u"SI"
        ):  #  Units type has changed SI to US.
            qdict = lwa_options  #  Ignore any other changed
        # fmt: on    
            qdict[u"units"] = u"US"
            prior[u"temp_cutoff"] = round(
                ((float(qdict[u"temp_cutoff"]) - 32) * 5) // 9, 1
            )
            prior[u"water_needed"] = round(safe_float(qdict[u"daily_irrigation"]) * 25.4, 1)

        # fmt: off
        if (
            qdict[u"units"] == u"SI" 
            and lwa_options[u"units"] == u"US"
        ):  #  Units type has changed US to SI.
        # fmt: on
            qdict = lwa_options  #  Ignore any other changes
            qdict[u"units"] = u"SI"
            prior[u"temp_cutoff"] = safe_float(lwa_options[u"temp_cutoff"])
            prior[u"water_needed"] = safe_float(lwa_options[u"daily_irrigation"])

        if qdict[u"units"] == u"US":
            temp_setting = round(
                ((float(qdict[u"temp_cutoff"]) - 32) * 5) // 9, 1
            )  #  cnvert to SI vals.
            if prior[u"temp_cutoff"] != temp_setting:  #  If changed
                prior[u"temp_cutoff"] = temp_setting
                qdict[u"temp_cutoff"] = temp_setting
            else:
                qdict[u"temp_cutoff"] = float(lwa_options[u"temp_cutoff"])  #  No change

            per_day_setting = round(
                float(qdict[u"daily_irrigation"]) * 25.4, 2
            )  # inches to mm
            qdict[u"daily_irrigation"] = per_day_setting
            if prior[u"water_needed"] != per_day_setting:
                prior[u"water_needed"] = per_day_setting
                qdict[u"water_needed"] = per_day_setting
            else:
                qdict[u"water_needed"] = safe_float(lwa_options[u"daily_irrigation"])  # No change

        print(u"qdict: ", qdict)
        for (
            key,
            value,
        ) in list(qdict.items()):  # Convert format from storage to dictionary
            if key in qdict:
                lwa_options[key] = value
        lwa_options[u"status"] = u""  #  clear any existing text.
        if u"auto_wl" not in qdict:
            lwa_options[u"auto_wl"] = u"off"
        if u"temp_cutoff_enable" not in qdict:
            lwa_options[u"temp_cutoff_enable"] = u"off"
        if int(lwa_options[u"days_history"]) > 5:
            lwa_options[u"days_history"] = 5
        if int(lwa_options[u"days_forecast"]) > 5:
            lwa_options[u"days_forecast"] = 5

        # write the settings to file
        with open(u"./data/weather_level_adj.json", u"w") as f:
            json.dump(lwa_options, f, indent=4, sort_keys=True)
        raise web.seeother(u"/lwa")


################################################################################
# Helper functions:                                                            #
################################################################################
def make_history_dir():
    """
    Create needed weather_level_history folder if needed.
    """
    dirpath = u"./data/weather_level_history"
    mkdir_p(dirpath)


def to_c(temp_k):
    """ convert temperature in degrees kelvin to degrees celsius."""
    temp_c = temp_k - 273.15
    return temp_c


def to_f(temp_c):
    """ convert temperature in degrees celsius to degrees farenheight."""
    temp_F = round((temp_c * 1.8) + 32, 1)
    return temp_F

def to_in(len_mm):
    """ convert length in milimeters to inches."""
    len_in = round(safe_float(len_mm) * 0.03937, 1)
    return len_in

def to_mm(len_in):
    """ convert length in inches to milimeters."""
    len_mm = round(safe_float(len_in) * 25.4, 0)
    return len_mm 

def options_data():
    """
    Read user supplied option and decipher values from files or 
    use default values and store them into files.
    """
    global lwa_options
    global lwa_decipher
    global prior
    # Defaults:
    default_options = {
        u"units": u"SI",
        u"auto_wl": u"off",
        u"daily_irrigation": 4,
        u"temp_cutoff_enable": u"off",
        u"temp_cutoff": 4,
        u"wl_min": 0,
        u"wl_max": 100,
        u"days_history": 3,
        u"days_forecast": 3,
        u"apikey": "",
        u"time_zone": 0,
        u"water_needed": 4,
        u"loc": "",
        u"status": u"",
    }

    default_decipher = {
        u"Description": u"WeatherCodes and Weights",
        u"PrecipCodes": {
            u"HeavyRain": [210, 211, 212, 502, 503, 504, 522, 531],
            u"Rain": [200, 201, 230, 231, 232, 313, 314, 500, 501],
            u"Drizzle": [300, 301, 302, 310, 311, 312, 321, 520, 804],
            u"Clear": [800, 801],
            u"Overcast": [802, 803],
        },
        u"PrecipWeights": {
            u"HeavyRain": 0,
            u"Rain": 10,
            u"Drizzle": 30,
            u"Clear": 100,
            u"Overcast": 80,
        },
    }

    try:
        with open(
            u"./data/weather_level_adj.json", u"r"
        ) as f:  # Read the settings from file
            lwa_options = json.load(f)
    except IOError:
        lwa_options = default_options
        with open(
            u"./data/weather_level_adj.json", u"w"
        ) as r:  # write the settings to file
            json.dump(lwa_options, r, indent=4, sort_keys=True)

    try:
        with open(
            u"./data/weather_decipher.json", u"r"
        ) as f:  # Read the settings from file
            lwa_decipher = json.load(f)
    except IOError:
        lwa_decipher = default_decipher
        with open(
            u"./data/weather_decipher.json", u"w"
        ) as wd:  # write the settings to file
            json.dump(lwa_decipher, wd, indent=4, sort_keys=True)

    prior[u"temp_cutoff"] = safe_float(lwa_options[u"temp_cutoff"])
    prior[u"water_needed"] = safe_float(lwa_options[u"daily_irrigation"])


def get_data(filename, suffix, data_type, options):
    """
    Retrieve data from OpenWeather using:
    data_type = weather (current conditions), or forcast (5 day/3hr forcast),
    suffix = location
    """
    url = u"https://api.openweathermap.org/data/2.5/" + data_type + u"?" + suffix

    dirpath = u"./data/weather_level_history"
    path = os.path.join(dirpath, filename)
    try_nr = 1
    while try_nr <= 2:
        try:
            with open(path, u"wb") as fh:
                req = urlopen(url + u"&appid=" + options[u"apikey"])
                while True:
                    chunk = req.read(20480)
                    if not chunk:
                        break
                    fh.write(chunk)

            try:
#                 with file(path, u"r") as fh:
                with open(path, u"r") as fh:
                    data = json.load(fh)
            except ValueError:
                raise Exception(u"Failed to read " + path + u".")

            if data is not None:
                if u"error" in data:
                    raise Exception(str(data[u"response"][u"error"]))
            else:
                raise Exception(u"JSON decoding failed.")

            # If we made it here, we were successful, break
            break

        except Exception as err:
            if try_nr < 2:
                print(str(err).encode('utf-8'), u"Retrying.")
                os.remove(path)
                # If we had an exception, this is where we need to increase
                # our count retry
                try_nr += 1
            else:
                raise

    return data


################################################################################
# Info queries:                                                                #
################################################################################


def history_info(obj, curr_conditions, options):

    time_now = datetime.datetime.now()
    day_delta = datetime.timedelta(days = float(options[u"days_history"]))

    history = dict(curr_conditions)

    path = u"./data/weather_level_history"
    i = 1
    count = int(options[u"days_history"])
    for filename in sorted(os.listdir(path)):
        tmp = re.split("_|-", filename)
        if tmp[0] == u"history":
            tmp.pop(0)
            thisdate_time = datetime.datetime(
                int(tmp[0]), int(tmp[1]), int(tmp[2]), int(tmp[3]), int(tmp[4])
            )
            if (time_now - day_delta) < thisdate_time and count > 0:
                with open(os.path.join(path, filename), u"r") as fn2187:
                    jsonhistdata = json.loads(fn2187.read())
                history[u"temp_c"] = (
                    history[u"temp_c"] * i + (jsonhistdata[u"main"][u"temp"] - 273.15)
                ) // (i + 1)
                if (
                    "rain" in jsonhistdata
                    and jsonhistdata[u"rain"]
                    ):
                    history[u"rain_mm"] += jsonhistdata[u"rain"].get(
                        next(iter(jsonhistdata[u"rain"]))
                    )  #  Add rain
                history[u"wind_ms"] = (
                    history[u"wind_ms"] * i + jsonhistdata[u"wind"][u"speed"]
                ) // (
                    i + 1
                )  #  average wind speed
                history[u"humidity"] = (
                    history[u"humidity"] * i + jsonhistdata[u"main"][u"humidity"]
                ) // (
                    i + 1
                )  # Aberage humidity
                i += 1
                count -= 1
            else:
                try:
                    os.remove(os.path.join(path, filename))
                except Exception as excp:
                    sys.stdout.write(
                        u"Unable to remove file {}: \n{}".format(filename, excp)
                    )
    return history


def today_info(obj, options):
    """Get today's weather info."""
    date_now = datetime.datetime.today()
    loc = options[u"loc"]

    if loc[:4] == u"lat=":
        loc = loc.replace(u"_", u"&")
        loc = loc.replace(u",", u".")
        request = loc
    else:
        request = u"q=" + loc

    datestring = date_now.strftime(u"%Y%m%d")
    path = u"./data/weather_level_history"

    name = u"conditions_" + loc + u"-" + datestring + u".json"
    if name in os.listdir(path):
        os.remove(os.path.join(path, name))

    data = get_data(name, request, u"weather", options)

    del data[u"clouds"]
    del data[u"base"]
    del data[u"id"]
    file_time = date_now.strftime(u"%Y_%m_%d-%H_%M_%S")
    del data[u"dt"]

    result = {}
    try:
        if (
            u"rain" in list(data.keys())
            and data[u"rain"]
            ):
            precipd = data[u"rain"].get(next(iter(data[u"rain"])))
        else:
            precipd = 0
        id = next(iter(data[u"weather"]))[u"id"]
        for keycodes, codes in list(lwa_decipher[u"PrecipCodes"].items()):
            if id in codes:
                weight = lwa_decipher[u"PrecipWeights"][keycodes]
                data[u"weight"] = weight
                break
        result = {
            u"temp_c": round(safe_float(data[u"main"][u"temp"]) - 273.15, 2),
            u"rain_mm": safe_float(precipd),
            u"wind_ms": safe_float(data[u"wind"][u"speed"]),
            u"humidity": safe_float(data[u"main"][u"humidity"]),
            u"pressure": safe_float(data[u"main"][u"pressure"]),
        }
    except ValueError as excp:
        obj.add_status(u"An error occurred parsing data: %s" % excp)

    try:
        os.rename(
            os.path.join(path, name),
            os.path.join(path, u"history_" + file_time + u".json"),
        )
    except Exception:
        pass
    return result


def forecast_info(obj, options, curr_weather):

    loc = options[u"loc"]
    date_now = datetime.datetime.today()
    date_future = date_now + datetime.timedelta(days = int(options[u"days_history"]))
    path = u"./data/weather_level_history"

    if loc[:4] == u"lat=":
        loc = loc.replace(u"_", u"&")
        loc = loc.replace(u",", u".")
        request = loc
    else:
        request = u"q=" + loc

    name = u"forecast5day_" + loc + u"-" + date_now.strftime(u"%Y%m%d_%H") + u".json"

    hfiles = []
    count = int(options[u"days_forecast"])
    for fname in reversed(sorted(os.listdir(path))):
        if u"forecast" not in fname:
            continue
        else:
            file_date = datetime.datetime.strptime(
                next(iter(fname.split("-")[-1].split(u"."))), u"%Y%m%d_%H"
            )
            if file_date < date_future and count > 0:
                hfiles.append(os.path.join(path, fname))
                count -= 1
            else:
                try:
                    os.remove(os.path.join(path, fname))
                except Exception as excp:
                    sys.stdout.write(u"Unable to remove file '%s': %s" % (fname, excp))

    data = get_data(name, request, u"forecast", options)

    del data[u"cnt"]
    del data[u"cod"]
    data[u"precip_accumulate"] = 0
    data[u"temperature_trend"] = {
        u"temp_avg": curr_weather[u"temp_c"],
        u"tot_elems": 1,
        u"trend_up_down": 0,
        u"temp_max": curr_weather[u"temp_c"],
        u"temp_min": curr_weather[u"temp_c"],
    }
    data[u"humidity_trend"] = {
        u"humid_avg": curr_weather[u"humidity"],
        u"tot_elems": 1,
        u"trend_up_down": 0,
    }
    data[u"wind_average"] = {u"wind_speed_avg": curr_weather[u"wind_ms"], u"tot_elems": 1}
    data[u"baro_press_trend"] = {
        u"press_avg": curr_weather[u"pressure"],
        u"tot_elems": 1,
        u"trend_up_down": 0,
    }
    for entry in data[u"list"]:
        try:
            del entry[u"dt"]
            del entry[u"sys"]
            del entry[u"clouds"]
            id = next(iter(entry[u"weather"]))[u"id"]
            for keycodes, codes in list(options[u"weather_decipher"][u"PrecipCodes"].items()):
                if id in codes:
                    weight = options[u"weather_decipher"][u"PrecipWeights"][keycodes]
                    entry[u"weight"] = weight
                    break
            if u"rain" in entry:
                _precip_time = datetime.datetime.strptime(
                    entry[u"dt_txt"], u"%Y-%m-%d %H:%M:%S"
                )
                if date_future > _precip_time and entry[u"rain"] != {}:
                    data[u"precip_accumulate"] += entry[u"rain"].get(
                        next(iter(entry[u"rain"]))
                    )
            data[u"temperature_trend"][u"tot_elems"] += 1
            data[u"humidity_trend"][u"tot_elems"] += 1
            curr_temp_cel = entry[u"main"][u"temp"] - 273.15
            data[u"temperature_trend"][u"temp_avg"] = (
                data[u"temperature_trend"][u"temp_avg"]
                * (data[u"temperature_trend"][u"tot_elems"] - 1)
                + curr_temp_cel
            ) // data[u"temperature_trend"][u"tot_elems"]
            data[u"temperature_trend"][u"trend_up_down"] = (
                data[u"temperature_trend"][u"temp_avg"] - curr_weather[u"temp_c"]
            )
            data[u"humidity_trend"][u"humid_avg"] = (
                data[u"humidity_trend"][u"humid_avg"]
                * (data[u"humidity_trend"][u"tot_elems"] - 1)
                + entry[u"main"][u"humidity"]
            ) // data[u"humidity_trend"][u"tot_elems"]
            data[u"humidity_trend"][u"trend_up_down"] = (
                data[u"humidity_trend"][u"humid_avg"] - curr_weather[u"humidity"]
            )
            data[u"wind_average"][u"wind_speed_avg"] = (
                data[u"wind_average"][u"wind_speed_avg"]
                * (data[u"wind_average"][u"tot_elems"] - 1)
                + entry[u"wind"][u"uspeed"]
            ) // data[u"wind_average"][u"tot_elems"]
            data[u"baro_press_trend"][u"press_avg"] = (
                data[u"baro_press_trend"][u"press_avg"]
                * (data[u"baro_press_trend"][u"tot_elems"] - 1)
                + entry[u"main"][u"pressure"]
            ) // data[u"baro_press_trend"][u"tot_elems"]
            data[u"baro_press_trend"][u"trend_up_down"] = (
                data[u"baro_press_trend"][u"press_avg"] - curr_weather[u"pressure"]
            )
            if curr_temp_cel > data[u"temperature_trend"][u"temp_max"]:
                data[u"temperature_trend"][u"temp_max"] = curr_temp_cel
            if curr_temp_cel < data[u"temperature_trend"][u"temp_min"]:
                data[u"temperature_trend"][u"temp_min"] = curr_temp_cel

        except KeyError:
            continue

    with open(os.path.join(path, name), u"w") as jdata:
        json.dump(data, jdata, indent=4, sort_keys=True)

    precip_avg = data[u"precip_accumulate"]
    precip_cnt = 1
    temp_avg = data[u"temperature_trend"][u"temp_avg"]
    temp_cnt = 1
    temp_max = data[u"temperature_trend"][u"temp_max"]
    temp_max_cnt = 1
    temp_min = data[u"temperature_trend"][u"temp_min"]
    temp_min_cnt = 1
    for i, _file in enumerate(hfiles):
        with open(_file, u"r") as fd:
            new_old_data = json.loads(fd.read())
        if u"precip_accumulate" in new_old_data:
            precip_avg = (
                precip_avg * precip_cnt + new_old_data[u"precip_accumulate"]
            ) // (precip_cnt + 1)
            precip_cnt += 1
        if u"temperature_trend" in new_old_data:
            if u"temp_avg" in new_old_data[u"temperature_trend"]:
                temp_avg = (
                    temp_avg * temp_cnt + new_old_data[u"temperature_trend"][u"temp_avg"]
                ) // (temp_cnt + 1)
                temp_cnt += 1
            if u"temp_max" in new_old_data[u"temperature_trend"]:
                temp_max = (
                    temp_max * temp_max_cnt
                    + new_old_data[u"temperature_trend"][u"temp_max"]
                ) // (temp_max_cnt + 1)
                temp_max_cnt += 1
            if u"temp_min" in new_old_data[u"temperature_trend"]:
                temp_min = (
                    temp_min * temp_min_cnt
                    + new_old_data[u"temperature_trend"][u"temp_min"]
                ) // (temp_min_cnt + 1)
                temp_min_cnt += 1

    if abs(data[u"precip_accumulate"] - precip_avg) // 100 < 0.10:
        data[u"precip_accumulate"] = precip_avg
    if abs(data[u"temperature_trend"][u"temp_avg"] - temp_avg) // 100 < 0.10:
        data[u"temperature_trend"][u"temp_avg"] = temp_avg
    if abs(data[u"temperature_trend"][u"temp_max"] - temp_max) // 100 < 0.10:
        data[u"temperature_trend"][u"temp_max"] = temp_max
    if abs(data[u"temperature_trend"][u"temp_min"] - temp_min) // 100 < 0.10:
        data[u"temperature_trend"][u"temp_min"] = temp_min
    return data


make_history_dir()
options_data()
