# !/usr/bin/env python

import threading
import json
import time

import re
import urllib
import urllib2

import uuid, urllib, urllib2
import hmac, hashlib
from base64 import b64encode

import web
import gv  # Get access to SIP's settings
from urls import urls  # Get access to SIP's URLs
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
                'yapiappid': '', 
                'yconkey': '',
                'yconsec': '',
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


def get_weather_data():

    options = get_weather_options()
    
    """
    Basic info
    """
    url = 'https://weather-ydn-yql.media.yahoo.com/forecastrss'
    method = 'GET'
    app_id = options['yapiappid'].encode('utf-8')
    consumer_key = options['yconkey'].encode('utf-8')
    consumer_secret = options['yconsec'].encode('utf-8')
    concat = '&'
    query = {'location': gv.sd['loc'], 'format': 'json'}
    oauth = {
        'oauth_consumer_key': consumer_key,
        'oauth_nonce': uuid.uuid4().hex,
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp': str(int(time.time())),
        'oauth_version': '1.0'
    }

    """
    Prepare signature string (merge all params and SORT them)
    """
    merged_params = query.copy()
    merged_params.update(oauth)
    sorted_params = [k + '=' + urllib.quote(merged_params[k], safe='') for k in sorted(merged_params.keys())]
    signature_base_str =  method + concat + urllib.quote(url, safe='') + concat + urllib.quote(concat.join(sorted_params), safe='')

    """
    Generate signature
    """
    composite_key = urllib.quote(consumer_secret, safe='') + concat
    oauth_signature = b64encode(hmac.new(composite_key, signature_base_str, hashlib.sha1).digest())

    """
    Prepare Authorization header
    """
    oauth['oauth_signature'] = oauth_signature
    auth_header = 'OAuth ' + ', '.join(['{}="{}"'.format(k,v) for k,v in oauth.iteritems()])
    try:
        url = url + '?' + urllib.urlencode(query)
        request = urllib2.Request(url)
        request.add_header('Authorization', auth_header)
        request.add_header('X-Yahoo-App-Id', app_id)
        data = urllib2.urlopen(request).read()
    except urllib2.URLError as e:
        print "Error getting weather data: ", e
        if do_log:
            with open("data/weather_log.txt", 'a') as wl:
                wl.write(time.strftime("%c") + ", Error: " + e + '\n')         
        return {}
    if data is None:
        return {}
    newdata = re.search('condition\":{\"text\":\"([A-Za-z ]+)[",]+code\":(\d+)',
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
