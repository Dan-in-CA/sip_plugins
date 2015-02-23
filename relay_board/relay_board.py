#!/usr/bin/env python

from blinker import signal
import web, json, time
import gv  # Get access to ospi's settings, gv = global variables
from urls import urls  # Get access to ospi's URLs
from ospi import template_render
from webpages import ProtectedPage

gv.use_gpio_pins = False  # Signal OSPi to not use GPIO pins

# Load the Raspberry Pi GPIO (General Purpose Input Output) library
try:
    import RPi.GPIO as GPIO
except IOError:
    pass

# Add a new url to open the data entry page.
urls.extend(['/rb', 'plugins.relay_board.settings',
	'/rbj', 'plugins.relay_board.settings_json',
	'/rbu', 'plugins.relay_board.update']) 

# Add this plugin to the home page plugins menu
gv.plugin_menu.append(['Relay Board', '/rb'])

params = {}

# Read in the parameters for this plugin from it's JSON file
def load_params():
    global params
    try:
        with open('./data/relay_board.json', 'r') as f:  # Read the settings from file
            params = json.load(f)
    except IOError: #  If file does not exist create file with defaults.
        params = {
            'relays': 1,
            'active': 'low'
        }
        with open('./data/relay_board.json', 'w') as f:
            json.dump(params, f)
    return params

load_params()

#### define the GPIO pins that will be used ####
try:
    if gv.platform == 'pi': # If this will run on Raspberry Pi:
        GPIO.setmode(GPIO.BOARD) #IO channels are identified by header connector pin numbers. Pin numbers are always the same regardless of Raspberry Pi board revision.
        relay_pins = ["11","12","13","15","16","18","22","7","3","5","24","26"]
        pin_rain_sense = 8
        pin_relay = 10
    # elif gv.platform == 'bo': # If this will run on Beagle Bone Black:
    #     relay_pins = ["P9_11","P9_12","P9_13","P9_14","P9_15","P9_16","P9_17","P9_18","P9_21","P9_22","P9_23","P9_24"]
    #     pin_rain_sense = "P9_41"
    #     pin_relay = "P9_42"
#    except AttributeError:
except:
#    print 'GPIO pins not set'
  pass


#### setup GPIO pins as output and either high or low ####
def init_pins():
  try:
#    for j in range(len(relay_pins)):
    for j in range(params['relays']):
        GPIO.setup(eval(relay_pins[j]), GPIO.OUT)
        if params['active'] == 'low':
            GPIO.output(eval(relay_pins[j]), GPIO.HIGH)
        else:
            GPIO.output(eval(relay_pins[j]), GPIO.LOW)
        time.sleep(0.1)
  except:
    pass

#### change outputs when blinker signal received ####
def on_zone_change(arg): #  arg is just a necessary placeholder.
    """ Switch relays when core program signals a change in zone state."""

    for i in range(params['relays']):
        try:
            if gv.srvals[i]:  # if station is set to on
                if params['active'] == 'low':  # if the relay type is active low, set the output low
                    GPIO.output(int(relay_pins[i]), GPIO.LOW)
                else:  # otherwise set it high
                    GPIO.output(int(relay_pins[i]), GPIO.HIGH)
#                print 'relay switched on', i + 1  #  for testing #############
            else:  # station is set to off
                if params['active'] == 'low':  # if the relay type is active low, set the output high
                    GPIO.output(int(relay_pins[i]), GPIO.HIGH)
                else:  # otherwise set it low
                    GPIO.output(int(relay_pins[i]), GPIO.LOW)
#                print 'relay switched off', i + 1  #  for testing ############
        except Exception, e:
            print "Problem switching relays", e, int(relay_pins[i])
            pass

init_pins();

zones = signal('zone_change')
zones.connect(on_zone_change)

################################################################################
# Web pages:                                                                   #
################################################################################

class settings(ProtectedPage):
    """Load an html page for entering relay board adjustments"""

    def GET(self):
        with open('./data/relay_board.json', 'r') as f:  # Read the settings from file
            params = json.load(f)
        return template_render.relay_board(params)


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format"""

    def GET(self):
        web.header('Access-Control-Allow-Origin', '*')
        web.header('Content-Type', 'application/json')
        return json.dumps(params)


class update(ProtectedPage):
    """Save user input to relay_board.json file"""

    def GET(self):
        qdict = web.input()
        changed = False
        if params['relays'] != int(qdict['relays']):  # if the number of relay channels changed, update the params
           params['relays'] = int(qdict['relays'])
           changed = True
        if params['active'] != str(qdict['active']):  # if the number of relay channels changed, update the params
           params['active'] = str(qdict['active'])
           params['relays'] = 1  # since changing active could turn all the relays on, reduce the relay channels to 1
           changed = True
        if changed:
           init_pins();
           with open('./data/relay_board.json', 'w') as f:  # write the settings to file
              json.dump(params, f)
        raise web.seeother('/')
