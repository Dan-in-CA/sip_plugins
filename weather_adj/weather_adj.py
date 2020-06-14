# !/usr/bin/env python

import threading
import json
import time

import re
import os
import errno
import urllib
import urllib2

import web
import gv  # Get access to ospi's settings
from urls import urls  # Get access to ospi's URLs
#from ospi import template_render                 #altered this to show the webpage for further functionality changes. I guess it works....?
from sip import template_render
from webpages import ProtectedPage
from helpers import stop_onrain

#  For testing only. Keeping this enabled will shorten the life of your SD card.
do_log = True #  Change to True to enable, False to disable logging

# Add a new url to open the data entry page.
urls.extend(['/wa', 'plugins.weather_adj.settings',
             '/wj', 'plugins.weather_adj.settings_json',
             '/uwa', 'plugins.weather_adj.update'])

# Add this plugin to the home page plugins menu
gv.plugin_menu.append(['Weather-based Rain Delay', '/wa'])

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def weather_to_delay(run_loop=False):
    if run_loop:
        t_start = gv.w_loop
        time.sleep(3)  # Sleep some time to prevent printing before startup information
    while True:
        options = get_weather_options()
        if options["auto_delay"] != "off":
            print("Checking rain status...")
            weather = get_openweather_data(options['loc'], options)
            if weather:
                weather_code = next(iter(weather['weather']))['main']
                delay = code_to_delay(weather_code, options)
                if delay > 0:
                    print("Rain detected: " + weather_code + ". Adding delay of " + str(delay))
                    gv.sd['rd'] = float(delay)
                    gv.sd['rdst'] = gv.now + gv.sd['rd'] * 3600 + 1  # +1 adds a smidge just so after a round trip the display hasn't already counted down by a minute.
                    stop_onrain()
                elif delay == 0:
                    print("No rain detected: " + weather_code + ". No action.")
                elif delay < 0:
                    if options["reset_delay"] == "off":
                        print("Good weather detected: " + weather_code + ". Ignoring change to rain delay.")
                    else:
                        print("Good weather detected: " + weather_code + ". Removing rain delay.")
                        #gv.sd['rdst'] = gv.now

        if not run_loop:
            return

        for i in range(3600):     
            if not t_start == gv.w_loop:  #  Should stop thread after program restart
                if do_log:
                    with open("data/weather_log.txt", 'a') as wl:
                        wl.write(time.strftime("%c") + ", Exiting Thread\n") 
                return
            time.sleep(1)


def get_weather_options():
    result = {
            'auto_delay': 'off', 
            'delay_duration': 24,
            'apikey': '', 
            'reset_delay': True,
            'loc': 'Houston'
        }
    try:
        with open('./data/weather_adj.json', 'r') as f:  # Read the settings from file
            file_data = json.load(f)
        for key, value in file_data.iteritems():
            if key in result:
                result[key] = value
            
    except Exception:
        pass
        
    if 'reset_delay' not in result:
        result['reset_delay'] = 'on'
    return result

def get_openweather_data(suffix, options):
    
    dirpath = os.path.join('.', 'data', 'weather_current')
    mkdir_p(os.path.dirname(dirpath))
    path = os.path.join(dirpath, "temp")
    
    url = "https://api.openweathermap.org/data/2.5/weather?q=" + suffix
    
    try:
        os.remove(path)
    except:
        pass
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

# Lookup code and get the set delay
def code_to_delay(code, options):
    adverse_codes = ["flurries", "rain", "sleet", "snow", "tstorms"]
    adverse_codes += ["chance" + code_name for code_name in adverse_codes]
    reset_codes = ["sunny", "clear", "mostlysunny", "partlycloudy"]
    if code in adverse_codes:
        return float(options['delay_duration'])
    if code in reset_codes:
        return -1
    return 0

class settings(ProtectedPage):
    """Load an html page for entering weather-based irrigation adjustments"""

    def GET(self):
        return template_render.weather_adj(get_weather_options())


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format"""
 
    def GET(self):
        web.header('Access-Control-Allow-Origin', '*')
        web.header('Content-Type', 'application/json')
        return json.dumps(get_weather_options())


class update(ProtectedPage):
    """Save user input to weather_adj.json file"""

    def GET(self):
        qdict = web.input()
        print 'qdict: ', qdict
        if 'auto_delay' not in qdict:
            qdict['auto_delay'] = 'off'
        if 'reset_delay' not in qdict:
            qdict['reset_delay'] = 'off'
        with open('./data/weather_adj.json', 'w') as f:  # write the rain delay configuration to json
            json.dump(qdict, f)
        weather_to_delay()
        raise web.seeother('/')

gv.w_loop = time.time()
tw = threading.Thread(target=weather_to_delay, args=(True,))
tw.daemon = True
tw.start()
