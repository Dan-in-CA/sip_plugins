'''
Created on Mar 24, 2019

@author: wenyu
'''
# !/usr/bin/env python
import datetime
from random import randint
from threading import Thread
import sys
import traceback
import shutil
import json
import time
import re
import os
import urllib
import urllib2
import errno
from datetime import timedelta

import web
import gv  # Get access to ospi's settings
from urls import urls  # Get access to ospi's URLs
#from ospi import template_render            altered this to show the webpage for further functionality changes. I guess it works....?
from sip import template_render
from webpages import ProtectedPage

def safe_float(s):
  try:
    return float(s)
  except:
    return 0

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

# Add a new url to open the data entry page.
urls.extend(['/lwa',  'plugins.weather_level_adj.settings',
             '/lwj',  'plugins.weather_level_adj.settings_json',
             '/luwa', 'plugins.weather_level_adj.update'])

# Add this plugin to the home page plugins menu
gv.plugin_menu.append(['Weather-based Water Level', '/lwa'])


################################################################################
# Main function loop:                                                          #
################################################################################

class WeatherLevelChecker(Thread):
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
        print msg

    def update(self):
        self._sleep_time = 0

    def _sleep(self, secs):
        self._sleep_time = secs
        while self._sleep_time > 0:
            time.sleep(1)
            self._sleep_time -= 1

    def run(self):
        time.sleep(randint(3, 10))  # Sleep some time to prevent printing before startup information

        while True:
            try:
                self.status = ''
                options = options_data()
                if options["auto_wl"] == "off":
                    if 'wl_weather' in gv.sd:
                        del gv.sd['wl_weather']
                else:

                    print "Checking weather status..."
                    
                    options = options_data()
                    today = today_info(self, options)
                    forecast = forecast_info(self, options, today)
                    history = history_info(self, today, options)

                    self.add_status('Using %d historical days, %d forecast days and today in calculations.' % (int(options['days_history']), int(options['days_history'])))

                    total_info = {
                        'temp_c': (today['temp_c'] + history['temp_c'] + forecast['temperature_trend']['temp_avg'])/3,
                        'rain_mm': (today['rain_mm'] + history['rain_mm'] + forecast['precip_accumulate']),
                        'wind_ms': (today['wind_ms'] + history['wind_ms'] + forecast['wind_average']['wind_speed_avg'])/3,
                        'humidity': (today['humidity'] + history['humidity'] + forecast['humidity_trend']['humid_avg'])/3
                    }

                    # We assume that the default 100% provides 4mm water per day (normal need)
                    # We calculate what we will need to provide using the mean data of X days around today

                    ini_water_needed = water_needed = int(options['rainfall_per_day']) * (int(options['days_forecast'])) + 1 # 4mm per day
                    water_needed *= 1 + (total_info['temp_c'] - 20) / 15        # 5 => 0%, 35 => 200%
                    water_needed *= 1 + (total_info['wind_ms'] / 100)           # 0 => 100%, 20 => 120%
                    water_needed *= 1 - (total_info['humidity'] - 50) / 200     # 0 => 125%, 100 => 75%
                    water_needed = round(water_needed, 1)

                    water_left = water_needed - total_info['rain_mm']
                    water_left = round(max(0, min(100, water_left)), 1)

                    water_adjustment = round((water_left / ini_water_needed)*100, 1)

                    water_adjustment = max(safe_float(options['wl_min']), min(safe_float(options['wl_max']), water_adjustment))

                    #Do not run if the current temperature is below the cutoff temperature and the option is enabled
                    if (safe_float(today['temp_c']) <= safe_float(options['temp_cutoff'])) and options["temp_cutoff_enable"] == "on":
                        water_adjustment = 0

                    self.add_status('Current temp in C    : %.1f' % today['temp_c'])
                    self.add_status('________________________________')
                    self.add_status('Water per day         : %.1fmm' % (int(options['rainfall_per_day'])))
                    self.add_status('Water needed (%d days) : %.1fmm' % (int(options['days_forecast']) + 1, water_needed))
                    self.add_status('Total rainfall        : %.1fmm' % total_info['rain_mm'])
                    self.add_status('________________________________')
                    self.add_status('Irrigation needed     : %.1fmm' % water_left)
                    self.add_status('Weather Adjustment    : %.1f%%' % water_adjustment)

                    gv.sd['wl_weather'] = water_adjustment

                    self._sleep(3600)

            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                err_string = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
                self.add_status('Weather-base water level encountered error:\n' + err_string)
                self._sleep(3600)
            time.sleep(0.5)

checker = WeatherLevelChecker()


################################################################################
# Web pages:                                                                   #
################################################################################
class settings(ProtectedPage):
    """Load an html page for entering weather-based irrigation adjustments"""

    def GET(self):
        return template_render.weather_level_adj(options_data())


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format"""

    def GET(self):
        web.header('Access-Control-Allow-Origin', '*')
        web.header('Content-Type', 'application/json')
        return json.dumps(options_data())


class update(ProtectedPage):
    """Save user input to weather_level_adj.json file"""
    def GET(self):
        qdict = web.input()
        if 'auto_wl' not in qdict:
            qdict['auto_wl'] = 'off'
        with open('./data/weather_level_adj.json', 'w') as f:  # write the settings to file
            json.dump(qdict, f)
        checker.update()
        raise web.seeother('/')

################################################################################
# Helper functions:                                                            #
################################################################################

def options_data():
    # Defaults:
    result = {
        'auto_wl': 'off',
        'temp_cutoff_enable': 'off',
        'temp_cutoff': 4,
        'wl_min': 0,
        'wl_max': 200,
        'days_history': 3,
        'days_forecast': 3,
        'apikey': '',
        'time_zone': 0,
        'rainfall_per_day': 4,
        'loc': 'Houston',
        'status': checker.status
    }
    try:
        with open('./data/weather_level_adj.json', 'r') as f:  # Read the settings from file
            file_data = json.load(f)
        for key, value in file_data.iteritems():
            if key in result:
                result[key] = value
        if result['days_history'] > 5:
            result['days_history'] = 5
        if result['days_forecast'] > 5:
            result['days_forecast'] = 5
        with open('./data/weather_decipher.json', 'r') as f:  # Read the settings from file
            result['weather_decipher'] = json.load(f)
            
    except Exception:
        pass

    return result

def get_data(filename, suffix, data_type, options):
    
    url = "https://api.openweathermap.org/data/2.5/" + data_type + "?" + suffix
    
    dirpath = os.path.join('.', 'data', 'weather_level_history')
    mkdir_p(os.path.dirname(dirpath))
    path = os.path.join(dirpath, filename)
    try_nr = 1
    while try_nr <= 2:
        try:
            if not os.path.exists(dirpath):
                os.mkdir(dirpath)
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

    now_time = datetime.datetime.now()
    day_delta = datetime.timedelta(days=int(options['days_history']))
   
    history = curr_conditions  
                
    path = os.path.join('.', 'data', 'weather_level_history')
    i = 1
    count = options['days_history']
    for filename in sorted(os.listdir(path)):
        tmp = re.split('_|-', filename)
        if tmp[0] == "history":
            tmp.pop(0)
            thisdate_time = datetime.datetime(int(tmp[0]), int(tmp[1]), int(tmp[2]), int(tmp[3]), int(tmp[4]))
            if (now_time - day_delta) < thisdate_time and count > 0:
                with open(os.path.join(path, filename), 'r') as fn2187:
                    jsonhistdata = json.loads(fn2187.read()) 
                history['temp_c'] = (history['temp_c']*i + (jsonhistdata['main']['temp'] - 273.15))/(i+1)
                if 'rain' in jsonhistdata:
                    history['rain_mm'] += jsonhistdata['rain'].get(next(iter(jsonhistdata['rain'])))
                history['wind_ms'] = (history['wind_ms']*i + jsonhistdata['wind']['speed'])/(i+1)
                history['humidity'] = (history['humidity']*i + jsonhistdata['main']['humidity'])/(i+1)
                i += 1
                count -= 1
            else:
                try:
                    os.remove(os.path.join(path, filename))
                except Exception as excp:
                    sys.stdout.write("Unable to remove file \'%s\': %s" % (filename, excp))

    return history

def today_info(obj, options):

    loc = options['loc']
    datestring = datetime.date.today().strftime('%Y%m%d')
    path = os.path.join('.', 'data', 'weather_level_history')
        
    request = "q="+loc
    name = "conditions_"+ loc + "-" + datestring + ".json"
    if name in os.listdir(path):
        os.remove(os.path.join(path, name))
    
    data = get_data(name, request, 'weather', options)

    del data['clouds']
    del data['base']
    del data['id']
    tmp_time = datetime.datetime.utcfromtimestamp(data['dt']) - timedelta(hours=int(options['time_zone']))
    file_time = tmp_time.strftime('%Y_%m_%d-%H_%M_%S') 
    del data['dt']

    result = {}
    try:
        if 'rain' in data.keys():
            precipd = data['rain'].get(next(iter(data['rain'])))
        else:
            precipd = 0
        id = next(iter(data['weather']))['id']
        for keycodes, codes in options['weather_decipher']['PrecipCodes'].items():
            if id in codes:
                weight = options['weather_decipher']['PrecipWeights'][keycodes]
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
    except:
        pass
        
    return result


def forecast_info(obj, options, curr_weather):

    loc = options['loc']
    date_now = datetime.datetime.today()        
    date_future = date_now + datetime.timedelta(days=int(options['days_history']))
    path = os.path.join('.', 'data', 'weather_level_history')
    
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
                count-=1
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
