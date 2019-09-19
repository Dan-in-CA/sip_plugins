# !/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
# from random import randint
from threading import Thread
import sys
import traceback
# import shutil
import json
import time
import re
import os
# import urllib
import urllib2
import errno
# from datetime import timedelta

import web
import gv  # Get access to SIP's settings
from urls import urls  # Get access to SIP's URLs
#from sip import template_render            altered this to show the webpage for further functionality changes. I guess it works....?
from sip import template_render
from webpages import ProtectedPage

def safe_float(s):
    """
    Return a valid float regardless of input.
    """
    try:
        return float(s)
    except Exception:
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
urls.extend(['/lwa', 'plugins.weather_level_adj.settings',
             '/lwj', 'plugins.weather_level_adj.settings_json',
             '/luwa', 'plugins.weather_level_adj.update'])

# Add this plugin to the home page plugins menu
gv.plugin_menu.append(['Weather-based Water Level', '/lwa'])

lwa_options = {}
lwa_decipher = {}
prior = {"temp_cutoff": 0, "water_needed": 0}


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
        self.status = ''

        self._sleep_time = 0

    def add_status(self, msg):
        if self.status:
            self.status += '\n' + msg
        else:
            self.status = msg
        if msg:
            lwa_options['status'] = self.status
        print msg

    def update(self):
        self._sleep_time = 0

    def _sleep(self, secs):
        self._sleep_time = secs
        while self._sleep_time > 0:
            time.sleep(1)
            self._sleep_time -= 1

    def run(self):
        time.sleep(3)  # Sleep some time to prevent printing before startup information

        while True:
            try:
                self.status = ''
                options = lwa_options
                if options["auto_wl"] == "off":
                    if 'wl_weather' in gv.sd:
                        del gv.sd['wl_weather']
                else:
                    print "Checking weather status..."                
#                     options = options_data()
                    today = today_info(self, options)
                    forecast = forecast_info(self, options, today)
                    history = history_info(self, today, options)

                    total_info = {
                        'temp_c': (today['temp_c'] + history['temp_c'] + forecast['temperature_trend']['temp_avg'])/3,
                        'rain_mm': (today['rain_mm'] + history['rain_mm'] + forecast['precip_accumulate']),
                        'wind_ms': (today['wind_ms'] + history['wind_ms'] + forecast['wind_average']['wind_speed_avg'])/3,
                        'humidity': (today['humidity'] + history['humidity'] + forecast['humidity_trend']['humid_avg'])/3
                    }

                    # We assume that the default 100% provides 4mm water per day (normal need)
                    # We calculate what we will need to provide using the mean data of X days around today

                    ini_water_needed = water_needed = float(options['daily_irrigation']) * (int(options['days_forecast'])) + 1 # 4mm per day
                    water_needed *= 1 + (total_info['temp_c'] - 20) / 15        # 5 => 0%, 35 => 200%
                    water_needed *= 1 + (total_info['wind_ms'] / 100)           # 0 => 100%, 20 => 120%
                    water_needed *= 1 - (total_info['humidity'] - 50) / 200     # 0 => 125%, 100 => 75%
                    water_needed = round(water_needed, 1)

                    water_left = water_needed - total_info['rain_mm']
                    water_left = round(max(0, min(100, water_left)), 1)

                    water_adjustment = round((water_left / ini_water_needed)*100, 1)

                    water_adjustment = max(safe_float(options['wl_min']), min(safe_float(options['wl_max']), water_adjustment))

                    #Do not run if the current temperature is below the cutoff temperature and the option is enabled
                    if ((safe_float(today['temp_c']) <= safe_float(options['temp_cutoff']))
                            and options["temp_cutoff_enable"] == "on"
                    ):
                        water_adjustment = 0
                    if lwa_options['units'] == "US":
                        self.add_status('Current temperature   : {}deg.{}'.format(to_f(today['temp_c']), "F"))
                        self.add_status('________________________________')
                        self.add_status('Daily irrigation      : {}{}'.format(to_in(options['daily_irrigation']), "in"))
                        self.add_status("Total rainfall        : {}{}".format(to_in(total_info['rain_mm']), "in"))
                        self.add_status('Water needed ({}days)  : {}{}'.format(int(options['days_forecast']) + 1, to_in(water_needed), "in"))
                        self.add_status('________________________________')
                        self.add_status('Irrigation needed     : {}{}'.format(to_in(water_left), "in"))
                        self.add_status('Weather Adjustment    : {}{}'.format(water_adjustment, "%"))
                    else:
                        self.add_status('Current temperature   : {}deg.{}'.format(round(today['temp_c'], 1), "C"))
                        self.add_status('________________________________')
                        self.add_status('Daily irrigation      : {}{}'.format(safe_float(options['daily_irrigation']), "mm"))
                        self.add_status('Total rainfall        : {}{}'.format(safe_float(total_info['rain_mm']), "mm"))
                        self.add_status('Water needed ({}days)  : {}{}'.format(int(options['days_forecast']) + 1, water_needed, "mm"))
                        self.add_status('________________________________')
                        self.add_status('Irrigation needed     : {}{}'.format(safe_float(water_left), "mm"))
                        self.add_status('Weather Adjustment    : {}{}'.format(water_adjustment, "%"))

                    gv.sd['wl_weather'] = water_adjustment

                    self._sleep(3600)

            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                err_string = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
                self.add_status('Weather-based water level encountered error:\n' + err_string)
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
        web.header('Access-Control-Allow-Origin', '*')
        web.header('Content-Type', 'application/json')
        return json.dumps(lwa_options)


class update(ProtectedPage):
    """Save user input to weather_level_adj.json file"""
    def GET(self):
        global lwa_options
        global prior

        qdict = web.input()
        if qdict['units'] == "US" and  lwa_options['units'] == "SI": #  Units type has changed SI to US.
            qdict = lwa_options #  Ignore any other changes
            qdict['units'] = "US"
            prior['temp_cutoff'] = round(((float(qdict['temp_cutoff']) - 32) * 5) / 9, 1)
            prior['water_needed'] = round(float(qdict['daily_irrigation']) * 25.4, 1)
 
        if qdict['units'] == "SI" and  lwa_options['units'] == "US": #  Units type has changed US to SI.
            qdict = lwa_options #  Ignore any other changes
            qdict['units'] = "SI"
            prior['temp_cutoff'] = lwa_options['temp_cutoff']
            prior['water_needed'] = lwa_options['daily_irrigation']

        if qdict['units'] == "US":
            temp_setting = round(((float(qdict['temp_cutoff']) - 32) * 5) / 9, 1) #  cnvert to SI vals.
            if prior['temp_cutoff'] != temp_setting: #  If changed
                prior['temp_cutoff'] = temp_setting
                qdict['temp_cutoff'] = temp_setting
            else:
                qdict['temp_cutoff'] = lwa_options['temp_cutoff'] #  No change
                
            per_day_setting = round(float(qdict['daily_irrigation']) * 25.4, 1) # inches to mm
            if prior['water_needed'] != per_day_setting:
                prior['water_needed'] = per_day_setting
                qdict['water_needed'] = per_day_setting           
            else:
                qdict['water_needed'] = lwa_options['daily_irrigation'] # No change
            
        for key, value in qdict.iteritems(): # Convert format from storage to dictionary
            if key in qdict:
                lwa_options[key] = value
        lwa_options['status'] = '' #  clear any existing text.
        if 'auto_wl' not in qdict:
            lwa_options['auto_wl'] = 'off'
        if 'temp_cutoff_enable' not in qdict:
            lwa_options['temp_cutoff_enable'] = 'off'
        if lwa_options['days_history'] > 5:
            lwa_options['days_history'] = 5
        if lwa_options['days_forecast'] > 5:
            lwa_options['days_forecast'] = 5

        # write the settings to file
        with open('./data/weather_level_adj.json', 'w') as f:
            json.dump(lwa_options, f, indent=4, sort_keys=True)
#         checker.update()
        raise web.seeother('/lwa')

################################################################################
# Helper functions:                                                            #
################################################################################
def make_history_dir():
    """
    Create needed weather_level_history folder if needed.
    """
    dirpath = "./data/weather_level_history"
    mkdir_p(dirpath)

def to_c(temp_k):
    """ convert temperature in degrees kelvin to degrees celsius."""
    temp_c = safe_float(temp_k) - 273.15
    return temp_c

def to_f(temp_c):
    """ convert temperature in degrees celsius to degrees farenheight."""
    temp_F = round((temp_c * 1.8) + 32, 1)
    return temp_F

def to_in(len_mm):
    """ convert length in milimeters to inches."""
    len_in = round(safe_float(len_mm) / 25.4, 1)
    return len_in

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
        'units': 'SI',
        'auto_wl': 'off',
        'temp_cutoff_enable': 'off',
        'temp_cutoff': 4,
        'wl_min': 0,
        'wl_max': 200,
        'days_history': 3,
        'days_forecast': 3,
        'apikey': '',
        'time_zone': 0,
        'water_needed': 4,
        'loc': '',
        'status': ""
    }

    default_decipher = { 
        'Description': 'WeatherCodes and Weights',
        'PrecipCodes': {
            "HeavyRain": [210, 211, 212, 502, 503, 504, 522, 531],
            "Rain": [200, 201, 230, 231, 232, 313, 314, 500, 501],
            "Drizzle": [300, 301, 302, 310, 311, 312, 321, 520, 804],
            "Clear": [800, 801],
            "Overcast": [802, 803],
        },
        'PrecipWeights': {
            "HeavyRain": 0,
            "Rain": 10,
            "Drizzle": 30,
            "Clear": 100,
            "Overcast": 80
            }
    }

    try:
        with open('./data/weather_level_adj.json', 'r') as f:  # Read the settings from file
            lwa_options = json.load(f)
    except IOError:
        lwa_options = default_options
        with open('./data/weather_level_adj.json', 'w') as r:  # write the settings to file
            json.dump(lwa_options, r, indent=4, sort_keys=True)
            
    try:
        with open('./data/weather_decipher.json', 'r') as f:  # Read the settings from file
            lwa_decipher = json.load(f)
    except IOError:
        lwa_decipher = default_decipher
        with open('./data/weather_decipher.json', 'w') as wd:  # write the settings to file
            json.dump(lwa_decipher, wd, indent=4, sort_keys=True)
            
    prior["temp_cutoff"] = float(lwa_options["temp_cutoff"])
    prior['water_needed'] = float(lwa_options["daily_irrigation"])

def get_data(filename, suffix, data_type, options):
    """
    Retrieve data from OpenWeather using:
    data_type = weather (current conditions), or forcast (5 day/3hr forcast),
    suffix = location
    """  
    url = "https://api.openweathermap.org/data/2.5/" + data_type + "?" + suffix
    
    dirpath = "./data/weather_level_history"
#     mkdir_p(os.path.dirname(dirpath))
    path = os.path.join(dirpath, filename)
    try_nr = 1
    while try_nr <= 2:
        try:
#             if not os.path.exists(dirpath):
#                 os.mkdir(dirpath)
            with open(path, 'wb') as fh:
                req = urllib2.urlopen(url + "&appid=" + options['apikey'])
                while True:
                    chunk = req.read(20480)
                    if not chunk:
                        break
                    fh.write(chunk)

            try:
                with file(path, 'r') as fh:
                    data = json.load(fh)
            except ValueError:
                raise Exception('Failed to read ' + path + '.')

            if data is not None:
                if 'error' in data:
                    raise Exception(str(data['response']['error']))
            else:
                raise Exception('JSON decoding failed.')

            # If we made it here, we were successful, break
            break

        except Exception as err:
            if try_nr < 2:
                print str(err), 'Retrying.'
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
    day_delta = datetime.timedelta(days=int(options['days_history']))
   
    history = curr_conditions  
                
    path = "./data/weather_level_history"
    i = 1
    count = options['days_history']
    for filename in sorted(os.listdir(path)):
        tmp = re.split('_|-', filename)
        if tmp[0] == "history":
            tmp.pop(0)
            thisdate_time = datetime.datetime(int(tmp[0]), int(tmp[1]), int(tmp[2]), int(tmp[3]), int(tmp[4]))
            if (time_now - day_delta) < thisdate_time and count > 0:
                with open(os.path.join(path, filename), 'r') as fn2187:
                    jsonhistdata = json.loads(fn2187.read()) 
                history['temp_c'] = (history['temp_c']*i + (jsonhistdata['main']['temp'] - 273.15))/(i+1)
                if 'rain' in jsonhistdata:
                    history['rain_mm'] += jsonhistdata['rain'].get(next(iter(jsonhistdata['rain']))) #  Add rain
                history['wind_ms'] = (history['wind_ms']*i + jsonhistdata['wind']['speed'])/(i+1) #  average wind speed
                history['humidity'] = (history['humidity']*i + jsonhistdata['main']['humidity'])/(i+1) # Aberage humidity
                i += 1
                count -= 1
            else:
                try:
                    os.remove(os.path.join(path, filename))
                except Exception as excp:
                    sys.stdout.write("Unable to remove file {}: \n{}".format(filename, excp))

    return history

def today_info(obj, options):
    """Get today's weather info."""
    date_now = datetime.datetime.today()
    loc = options['loc']
    
    if loc[:4] == "lat=":
        loc = loc.replace('_', "&")
        loc = loc.replace(',', ".")
        request = loc        
    else:
        request = "q="+loc
        
    datestring = date_now.strftime('%Y%m%d')
    path = "./data/weather_level_history"

    name = "conditions_"+ loc + "-" + datestring + ".json"
    if name in os.listdir(path):
        os.remove(os.path.join(path, name))
    
    data = get_data(name, request, 'weather', options)

    del data['clouds']
    del data['base']
    del data['id']
    file_time = date_now.strftime('%Y_%m_%d-%H_%M_%S')
    del data['dt']

    result = {}
    try:
        if 'rain' in data.keys():
            precipd = data['rain'].get(next(iter(data['rain'])))
        else:
            precipd = 0
        id = next(iter(data['weather']))['id']
        for keycodes, codes in lwa_decipher['PrecipCodes'].items():
            if id in codes:
                weight = lwa_decipher['PrecipWeights'][keycodes]
                data['weight'] = weight
                break
        result = {
            'temp_c': safe_float(data['main']['temp']) - 273.15,
            'rain_mm': safe_float(precipd),
            'wind_ms': safe_float(data['wind']['speed']),
            'humidity': safe_float(data['main']['humidity']),
            'pressure': safe_float(data['main']['pressure'])
        }
    except ValueError as excp:
        obj.add_status("An error occurred parsing data: %s" % excp)
        
    try:
        os.rename(os.path.join(path, name), os.path.join(path, 'history_' + file_time + '.json')) 
    except Exception:
        pass
        
    return result


def forecast_info(obj, options, curr_weather):

    loc = options['loc']
    date_now = datetime.datetime.today()        
    date_future = date_now + datetime.timedelta(days=int(options['days_history']))
    path = "./data/weather_level_history"
    
    if loc[:4] == "lat=":
        loc = loc.replace('_', "&")
        loc = loc.replace(',', ".")
        request = loc        
    else:
        request = "q="+loc
        
    name = "forecast5day_"+loc + "-" + date_now.strftime('%Y%m%d_%H') + ".json"
    
    hfiles = []
    count = options['days_forecast']
    for fname in reversed(sorted(os.listdir(path))):
        if 'forecast' not in fname:
            continue 
        else:
            file_date = datetime.datetime.strptime(next(iter(fname.split('-')[-1].split('.'))), '%Y%m%d_%H')
            if file_date < date_future and count > 0: 
                hfiles.append(os.path.join(path, fname))
                count -= 1
            else:
                try:
                    os.remove(os.path.join(path, fname))
                except Exception as excp:
                    sys.stdout.write("Unable to remove file \'%s\': %s" % (fname, excp))
            
    data = get_data(name, request, 'forecast', options)

    del data['cnt']
    del data['cod']
    data['precip_accumulate'] = 0
    data['temperature_trend'] = {'temp_avg': curr_weather['temp_c'], 'tot_elems' : 1, 'trend_up_down': 0, \
                                 'temp_max': curr_weather['temp_c'], 'temp_min': curr_weather['temp_c']}
    data['humidity_trend'] = {'humid_avg': curr_weather['humidity'], 'tot_elems' : 1, 'trend_up_down': 0}
    data['wind_average'] = {'wind_speed_avg': curr_weather['wind_ms'], 'tot_elems' : 1}
    data['baro_press_trend'] = {'press_avg': curr_weather['pressure'], 'tot_elems' : 1, 'trend_up_down': 0}
    for entry in data['list']:
        try:
            del entry['dt']
            del entry['sys']
            del entry['clouds']
            id = next(iter(entry['weather']))['id']
            for keycodes, codes in options['weather_decipher']['PrecipCodes'].items():
                if id in codes:
                    weight = options['weather_decipher']['PrecipWeights'][keycodes]
                    entry['weight'] = weight
                    break
            if 'rain' in entry:
                _precip_time = datetime.datetime.strptime(entry['dt_txt'], '%Y-%m-%d %H:%M:%S')
                if date_future > _precip_time and entry['rain'] != {}:
                    data['precip_accumulate'] += entry['rain'].get(next(iter(entry['rain'])))
            data['temperature_trend']['tot_elems'] += 1
            data['humidity_trend']['tot_elems'] += 1
            curr_temp_cel = entry['main']['temp'] - 273.15      
            data['temperature_trend']['temp_avg'] = (data['temperature_trend']['temp_avg']*(data['temperature_trend']['tot_elems']-1) + curr_temp_cel)/data['temperature_trend']['tot_elems']
            data['temperature_trend']['trend_up_down'] = data['temperature_trend']['temp_avg'] - curr_weather['temp_c']
            data['humidity_trend']['humid_avg'] = (data['humidity_trend']['humid_avg']*(data['humidity_trend']['tot_elems']-1) + entry['main']['humidity'])/data['humidity_trend']['tot_elems']
            data['humidity_trend']['trend_up_down'] = data['humidity_trend']['humid_avg'] - curr_weather['humidity']
            data['wind_average']['wind_speed_avg'] = (data['wind_average']['wind_speed_avg']*(data['wind_average']['tot_elems']-1) + entry['wind']['speed'])/data['wind_average']['tot_elems']
            data['baro_press_trend']['press_avg'] = (data['baro_press_trend']['press_avg']*(data['baro_press_trend']['tot_elems']-1) + entry['main']['pressure'])/data['baro_press_trend']['tot_elems']
            data['baro_press_trend']['trend_up_down'] = data['baro_press_trend']['press_avg'] - curr_weather['pressure'] 
            if curr_temp_cel > data['temperature_trend']['temp_max']:
                data['temperature_trend']['temp_max'] = curr_temp_cel
            if curr_temp_cel < data['temperature_trend']['temp_min']:
                data['temperature_trend']['temp_min'] = curr_temp_cel
          
        except KeyError:
            continue
    
    with open(os.path.join(path, name), 'w') as jdata:
        json.dump(data, jdata)

    precip_avg = data['precip_accumulate']
    precip_cnt = 1
    temp_avg = data['temperature_trend']['temp_avg']
    temp_cnt = 1
    temp_max = data['temperature_trend']['temp_max']
    temp_max_cnt = 1
    temp_min = data['temperature_trend']['temp_min']
    temp_min_cnt = 1
    for i, _file in enumerate(hfiles):            
        with open(_file, 'r') as fd:
            new_old_data = json.loads(fd.read())
        if 'precip_accumulate' in new_old_data: 
            precip_avg = (precip_avg*precip_cnt + new_old_data['precip_accumulate'])/(precip_cnt + 1)
            precip_cnt += 1
        if 'temperature_trend' in new_old_data:
            if 'temp_avg' in new_old_data['temperature_trend']:
                temp_avg = (temp_avg*temp_cnt + new_old_data['temperature_trend']['temp_avg'])/(temp_cnt + 1)
                temp_cnt += 1
            if 'temp_max' in new_old_data['temperature_trend']:
                temp_max = (temp_max*temp_max_cnt + new_old_data['temperature_trend']['temp_max'])/(temp_max_cnt + 1)
                temp_max_cnt += 1
            if 'temp_min' in new_old_data['temperature_trend']:
                temp_min = (temp_min*temp_min_cnt + new_old_data['temperature_trend']['temp_min'])/(temp_min_cnt + 1)
                temp_min_cnt += 1

    if abs(data['precip_accumulate'] - precip_avg)/100 < .10:
        data['precip_accumulate'] = precip_avg
    if abs(data['temperature_trend']['temp_avg'] - temp_avg)/100 < .10:
        data['temperature_trend']['temp_avg'] = temp_avg
    if abs(data['temperature_trend']['temp_max'] - temp_max)/100 < .10:
        data['temperature_trend']['temp_max'] = temp_max
    if abs(data['temperature_trend']['temp_min'] - temp_min)/100 < .10:
        data['temperature_trend']['temp_min'] = temp_min
    return data

make_history_dir()
options_data()
