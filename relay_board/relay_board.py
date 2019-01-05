#!/usr/bin/env python

from blinker import signal
import web, json, time
import gv  # Get access to SIP's settings, gv = global variables
from urls import urls  # Get access to SIP's URLs
from sip import template_render
from webpages import ProtectedPage

gv.use_gpio_pins = False  # Signal SIP to not use GPIO pins

# Load the Raspberry Pi GPIO (General Purpose Input Output) library
try:
    if gv.platform == 'pi' or gv.platform == 'bo':
        if gv.use_pigpio:
            import pigpio
            pi = pigpio.pi()
        else:
            import RPi.GPIO as GPIO
            pi = 0
    elif gv.platform == 'odroid-c2':
        import wiringpi as GPIO
        GPIO.wiringPiSetup() 
except GPIOError:
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
        if not gv.use_pigpio:
            GPIO.setmode(GPIO.BOARD) #IO channels are identified by header connector pin numbers. Pin numbers are 
        relay_pins = [11,12,13,15,16,18,22,7,3,5,24,26,29,31,32,33,35,36,37,38]
    elif gv.platform == 'odroid-c2':
        relay_pins = [11,12,13,15,16,18,22,24,26,29,31,32,33,35,36]
    else:
        print 'relay board plugin only supported on pi.'
        raise ValueError('relay board plugin not compatible with your hardware...')
    
    for i in range(len(relay_pins)):
        try:
            relay_pins[i] = gv.pin_map[relay_pins[i]]
        except:
            relay_pins[i] = 0
    pin_rain_sense = gv.pin_map[8]
    pin_relay = gv.pin_map[10]
except:
  print 'Relay board: GPIO pins not set'
  pass

  
from gpio_pins import set_pin_mode_output
from gpio_pins import set_pin_high
from gpio_pins import set_pin_low

#### setup GPIO pins as output and either high or low ####
def init_pins():
  global pi

  try:
    for i in range(params['relays']):
        set_pin_mode_output(relay_pins[i])
        if params['active'] == 'low':
            set_pin_high(relay_pins[i])
        else:
            set_pin_low(relay_pins[i])
        time.sleep(0.1)
  except:
    pass

#### change outputs when blinker signal received ####
def on_zone_change(arg): #  arg is just a necessary placeholder.
    """ Switch relays when core program signals a change in zone state."""

    global pi

    with gv.output_srvals_lock:
        for i in range(params['relays']):
            try:
                if gv.output_srvals[i]:  # if station is set to on
                    if params['active'] == 'low':  # if the relay type is active low, set the output low
                        set_pin_low(relay_pins[i])
                    else:  # otherwise set it high
                        set_pin_high(relay_pins[i])
#                    print 'relay switched on', i + 1, "pin", relay_pins[i]  #  for testing #############
                else:  # station is set to off
                    if params['active'] == 'low':  # if the relay type is active low, set the output high
                        set_pin_high(relay_pins[i])
                    else:  # otherwise set it low
                        set_pin_low(relay_pins[i])
#                    print 'relay switched off', i + 1, "pin", relay_pins[i]  #  for testing ############
            except Exception, e:
                print "Problem switching relays", e, relay_pins[i]
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
