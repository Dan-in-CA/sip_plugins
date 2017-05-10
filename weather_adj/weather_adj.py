# !/usr/bin/env python

import threading
import json
import time

import re
import urllib
import urllib2

import web
import gv  # Get access to ospi's settings
from urls import urls  # Get access to ospi's URLs
from ospi import template_render
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


def weather_to_delay(run_loop=False):
    if run_loop:
        t_start = gv.w_loop
        time.sleep(3)  # Sleep some time to prevent printing before startup information
    while True:
        data = get_weather_options()
        if data["auto_delay"] != "off":
            print("Checking rain status...")
            weather = get_weather_data() if data['weather_provider'] == "yahoo" else get_wunderground_weather_data()
            if weather:
                delay = code_to_delay(weather["code"])
                if delay > 0:
                    print("Rain detected: " + weather["text"] + ". Adding delay of " + str(delay))
                    gv.sd['rd'] = float(delay)
                    gv.sd['rdst'] = gv.now + gv.sd['rd'] * 3600 + 1  # +1 adds a smidge just so after a round trip the display hasn't already counted down by a minute.
                    stop_onrain()
                elif delay == 0:
                    print("No rain detected: " + weather["text"] + ". No action.")
                elif delay < 0:
                    if data["reset_delay"] == "off":
                      print("Good weather detected: " + weather["text"] + ". Ignoring change to rain delay.")
                    else:
                      print("Good weather detected: " + weather["text"] + ". Removing rain delay.")
                      gv.sd['rdst'] = gv.now

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
    try:
        with open('./data/weather_adj.json', 'r') as f:  # Read the rain delay configuration from json
            data = json.load(f)
    except IOError:
        data = {
                'auto_delay': 'off', 
                'delay_duration': 24, 
                'weather_provider': 'yahoo', 
                'wapikey': '', 
                'reset_delay': 'on' }
    if 'reset_delay' not in data:
      data['reset_delay'] = 'on'
    return data



# Resolve location to LID
def get_wunderground_lid():
    if re.search("pws:", gv.sd['loc']):
        lid = gv.sd['loc']
    else:
        req = urllib2.Request("http://autocomplete.wunderground.com/aq?h=0&query=" + urllib.quote_plus(gv.sd['loc']))
        try:
            response = urllib2.urlopen(req, timeout = 10)
        except urllib2.URLError as e:
            print "Error getting wundergound LID: ", e
            if do_log:
                with open("data/weather_log.txt", 'a') as wl:
                    wl.write(time.strftime("%c") + ", Error: " + e + '\n')
            return ""
        data = json.load(response)
        if data is None:
            return ""
        lid = "zmw:" + data['RESULTS'][0]['zmw']
    return lid


def get_woeid():
    req = urllib2.Request("http://query.yahooapis.com/v1/public/yql?q=select%20woeid%20from%20geo.placefinder%20where%20text=%22" +
        urllib.quote_plus(gv.sd["loc"]) + "%22")  
    try:
        response = urllib2.urlopen(req, timeout = 10)
    except urllib2.URLError as e:
        print 'Error getting woeid: ', e
        if do_log:
            with open("data/weather_log.txt", 'a') as wl:
                wl.write(time.strftime("%c") + ", Error: " + e + '\n')       
        return 0
    data = response.read()
    woeid = re.search("<woeid>(\d+)</woeid>", data)
    if woeid is None:
        return 0
    return woeid.group(1)


def get_weather_data():
    woeid = get_woeid()
    if woeid == 0:
        return {}
    req = urllib2.Request("http://weather.yahooapis.com/forecastrss?w=" + woeid)
    try:
        response = urllib2.urlopen(req, timeout = 10)
    except urllib2.URLError as e:
        print "Error getting weather data: ", e
        if do_log:
            with open("data/weather_log.txt", 'a') as wl:
                wl.write(time.strftime("%c") + ", Error: " + e + '\n')         
        return {}
    data = response.read()
    if data is None:
        return {}
    newdata = re.search("<yweather:condition\s+text=\"([\w|\s]+)\"\s+code=\"(\d+)\"\s+temp=\"(\d+)\"\s+date=\"(.*)\"",
                        data)
    weather = {"text": newdata.group(1),
               "code": newdata.group(2)}
    if do_log:
        with open("data/weather_log.txt", 'a') as wl:
            wl.write(time.strftime("%c") + ", " + weather["text"] + '\n')
    return weather


def get_wunderground_weather_data():
    options = get_weather_options()
    lid = get_wunderground_lid()
    if lid == "":
        return {}
    req = urllib2.Request("http://api.wunderground.com/api/" + options['wapikey'] + "/conditions/q/" + lid + ".json")   
    try:
        response = urllib2.urlopen(req, timeout=10)
    except urllib2.URLError as e:
        print "Error getting WU data: ", e
        if do_log:
            with open("data/weather_log.txt", 'a') as wl:
                wl.write(time.strftime("%c") + ", Error: " + e + '\n')         
        return {}
    data = json.load(response)
    if data is None:
        return {}
    if 'error' in data['response']:
        return {}
    weather = {"text": data['current_observation']['weather'],
               "code": data['current_observation']['icon']}
    print 'weather: ', weather
    if do_log:
        with open("data/weather_log.txt", "a") as wl:
            wl.write(time.strftime("%c") + ", " + weather["text"]+ '\n')  
    return weather


# Lookup code and get the set delay
def code_to_delay(code):
    data = get_weather_options()
    if data['weather_provider'] == "yahoo":
        adverse_codes = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 35, 37, 38, 39, 40, 41, 42,
                         43, 44, 45, 46, 47]
        reset_codes = [36]
    else:
        adverse_codes = ["flurries", "rain", "sleet", "snow", "tstorms"]
        adverse_codes += ["chance" + code_name for code_name in adverse_codes]
        reset_codes = ["sunny", "clear", "mostlysunny", "partlycloudy"]
    if code in adverse_codes:
        return float(data['delay_duration'])
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
