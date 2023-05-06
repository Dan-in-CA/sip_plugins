#!/usr/bin/env python

# Python 2/3 compatibility imports
from __future__ import print_function

__version__ = '0.4.0'

# standard library imports
import json
import subprocess
from sys import modules
import time
import platform
from urllib.request import urlopen, Request

blockedPlugin=False
#import smbus
try:
    import smbus
except ModuleNotFoundError:
    blockedPlugin=True
    pass

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings, gv = global variables
from sip import template_render
from urls import urls  # Get access to SIP's URLs
import web
from webpages import ProtectedPage

# Add a new url to open the data entry page.
# fmt: off
urls.extend(
    [
        u"/pcf857x", u"plugins.pcf857x.settings",
        u"/pcf857xj", u"plugins.pcf857x.settings_json",
        u"/pcf857xu", u"plugins.pcf857x.update",
        u"/pcf857xt", u"plugins.pcf857x.test",
        u"/pcf857x_scan", u"plugins.pcf857x.scan",
        u"/pcf857x_upd", u"plugins.pcf857x.plugupdate"
    ]
)
# fmt: on

# Add this plugin to the plugins menu
gv.plugin_menu.append([_(u"pcf857x"), u"/pcf857x"])

pcf = {}
#prior = [0] * len(gv.srvals)
demo_mode = True

if platform.machine() == "armv6l"  or platform.machine() == "armv7l":  # may be removed later but makes dev and testing possible without smbus
    demo_mode = False


def check_pcf_params(ForceSave):
    MustSave = False
    if not ("adr" in pcf):
        MustSave = True
        print("adr not found in dict")
        pcf[u"adr"] = [u""] * gv.sd[u"nbrd"]
        pcf[u"adr"][0] = u"0x20"
    if not ("bus" in pcf):
        MustSave = True
        print("bus not found in dict")
        pcf[u"bus"] = "1"
    if not ("ictype" in pcf):
        MustSave = True
        print("ictype not found in dict")
        pcf[u"ictype"] = "pcf8574"
    if not ("repo" in pcf):  # repo: S --> Stable or B --> Beta
        MustSave = True
        print("repo not found in dict")
        pcf[u"repo"] = "S"
    if not ("debug" in pcf):
        MustSave = True
        print("debug not found in dict")
        pcf[u"debug"] = "0"
    if (MustSave or ForceSave):
        with open(u"./data/pcf857x.json", u"w") as f:
            json.dump(pcf, f, indent=4)
    return

# Read in the pcfadr for this plugin from it's JSON file
def load_pcfadr():
    global pcf
    MustSave = False
    try:
        with open(u"./data/pcf857x.json", u"r") as f:
            pcf = json.load(f)  # Read the pcfadr from file
    except IOError:  #  If file does not exist create file with defaults.
        MustSave = True
        #pcf = {u"adr": [u""] * gv.sd[u"nbrd"], u"bus": 1, u"ictype":"pcf8574",u"repo":"S",u"debug":"0"}
        #pcf[u"adr"][0] = u"0x20"
    check_pcf_params(MustSave)
    return


load_pcfadr()
# disable gpio_pins. We can discuss later if a mix of gpio and i2c should be possible
gv.use_gpio_pins = False

pcf[u"devices"] = {}
pcf[u"version"] = __version__

if blockedPlugin:
    pcf[u"warnmsg"] = "Unable to load library. please follow instructions on the help page"
    print(u"\33[31mWARNING: SMBUS library was loaded,\nPCF857x plugin will NOT be activated.")
    print(u"See plugin help page for instructions.\33[0m")
else:
    pcf[u"warnmsg"] = {}



# for future use. No test devices available at the moment.
modbits=8   # default number op io pins on i2c module
if (pcf[u"ictype"]=="pcf8575"):
    modbits=16


#### output command when signal received ####
def on_zone_change(name, **kw):
    """ Send command when core program signals a change in station state."""
    if blockedPlugin:
        print("pcf857x plugin blocked due to missing library")
        return

    if len(pcf[u"adr"]) != gv.sd[u"nbrd"]:
        print("pcf857x plugin blocked due to incomplete settings")
        return

    if demo_mode==False:
        bus = smbus.SMBus(int(pcf[u"bus"]))

    i2c_bytes = []
    
    for b in range(gv.sd[u"nbrd"]):
        byte = 0xFF
        for s in range(8): # for each virtual board
            sid = b * 8 + s  # station index in gv.srvals           
            if gv.output_srvals[sid]:  # station is on
                byte = byte ^ (1 << s) # use exclusive or to set station bit to 0
        i2c_bytes.append(byte)

    for s in range(gv.sd[u"nbrd"]):
        if demo_mode:
            print("demo: bus.write_byte_data(" + pcf[u"adr"][s] + ",0," + hex(i2c_bytes[s]) + ")" )
            print("demo: bus.write_byte(" + pcf[u"adr"][s] + "," + hex(i2c_bytes[s]) + ")" )
            print("demo: bus.write_byte(" + str(int(pcf[u"adr"][s],16)) + "," + hex(i2c_bytes[s]) + ")" )
        else:
            # the real stuff here
            try:
                if pcf[u"debug"]=="1":
                  print("bus.write_byte(" + str(int(pcf[u"adr"][s],16)) + "," + hex(i2c_bytes[s]) + ")" )

                bus.write_byte(int(pcf[u"adr"][s],16) , i2c_bytes[s])
            except ValueError:
                print("ValueError: have you any i2c device configured?")
                pass
            except OSError:
                print("OSError: All i2c devices entered correctly?")
                pass

            


zones = signal(u"zone_change")
zones.connect(on_zone_change)

################################################################################
# Web pages:    needs to be regoranised, too much wrong stuff here             #
################################################################################


class settings(ProtectedPage):
    """Load an html page for entering pcf8575 pcfadr"""

    def GET(self):
        pcf[u"devices"] = []
        return template_render.pcf857x(pcf)


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format"""

    def GET(self):
        web.header(u"Access-Control-Allow-Origin", u"*")
        web.header(u"Content-Type", u"application/json")
        return json.dumps(pcf)


class update(ProtectedPage):
    """Save user input to pcf857x.json file"""

    def GET(self):
        global pcf
        qdict = web.input()
        if u"devices" in pcf:   # don't save temporary data
            del pcf[u"devices"]
        if u"warnmsg" in pcf:   # don't save temporary data
            del pcf[u"warnmsg"]

        if (
            len(pcf[u"adr"]) != gv.sd[u"nbrd"]
        ):  #  if number of boards has changed, adjust length of adr lists
            if gv.sd[u"nbrd"] > len(pcf[u"adr"]):
                increase = [""] * (gv.sd[u"nbrd"] - len(pcf[u"adr"]))
                pcf[u"adr"].extend(increase)
            elif gv.sd[u"nbrd"] < len(pcf[u"adr"]):
                pcf[u"adr"] = pcf[u"adr"][: gv.sd[u"nbrd"]]  
        for i in range(gv.sd[u"nbrd"]):
            pcf[u"adr"][i] = qdict[u"con" + str(i)]    
        if u"bus" in qdict:
            pcf[u"bus"] = qdict[u"bus"]
        else:
            pcf[u"bus"] = 1

        if u"ictype" in qdict:
            pcf[u"ictype"] = qdict[u"ictype"]
        else:
            pcf[u"ictype"] = "pcf8574"

        if u"repo" in qdict:
            pcf[u"repo"] = qdict[u"repo"]
        else:
            pcf[u"repo"] = "S"

        if u"debug" in qdict: 
            if qdict[u"debug"]=="on":
                pcf[u"debug"] = "1"
            else:
                pcf[u"debug"] = "0"
        else:
            pcf[u"debug"] = "0"

        with open(u"./data/pcf857x.json", u"w") as f:  # write the settings to file
            json.dump(pcf, f, indent=4)
        raise web.seeother(u"/restart")

class test(ProtectedPage):
    """ test i2c from setup plugin page"""

    # not used, might be usefull when called from browser?
    def GET(self):
        data = web.input()
        print("pcf-test-begin")
        for k, v in data.items():
          print(k, v)
        print("pct-test-end")

    def POST(self):
        data = web.input()
        print("pcf-post-test-begin")
        for k, v in data.items():
          print(k, v)
        if demo_mode:
            print("demo: bus.write_byte(" + data["tst_adres"] + "," + data["tst_value"] + ")" )
        else:
            bus = smbus.SMBus(int(data["tst_smbus"]))
            bus.write_byte(int(data["tst_adres"],16), int(data["tst_value"],16))

        print("pct-post-test-end")
        web.seeother(u"/pcf857x")



def getDevicesOnBus(busNo):
    devices = []
    bus = smbus.SMBus(busNo)
    for addr in range(3, 178):
        try:
            bus.write_quick(addr)
            devices += [addr]
        except IOError:
            pass
    return devices


def proc_files(uri, remote_file,target_dir):
    #uri = beta_repo + "/-/raw/" + beta_branch + "/" + remote_file
    response = urlopen(uri)
    f_data = response.read()
    try:
        f_data = f_data.decode('utf-8')
        print("writing w file")
        with open(target_dir + "/" + remote_file, "w") as next_file:
           next_file.write(f_data)
    except UnicodeDecodeError:
        print("writing wb file")
        with open(target_dir + "/" + remote_file, "wb") as next_file:
           next_file.write(f_data)



class scan(ProtectedPage):
    """
    i2c scan page
    """

    def GET(self):
        global pcf
        global demo_mode
        #data = web.input()
        if demo_mode:
            pcf[u"devices"] = [0x27,0x25,0x20]
        else:
            pcf[u"devices"] = getDevicesOnBus(int(pcf[u"bus"]))
        return template_render.pcf857x(pcf)

class plugupdate(ProtectedPage):
    """
    Plugin update
    """

    def GET(self):
        # beta repo file example: https://gitlab.com/seventer/pcf857x_plugin_sip/-/raw/dev-04/pcf857x.py
        beta_repo = "https://gitlab.com/seventer/pcf857x_plugin_sip"
        beta_branch = "main"
        stable_repo = "https://raw.github.com/Dan-in-CA/SIP_plugins/"
        stable_branch = "master"
        upd_files = {"pcf857x.py": "plugins", "pcf857x.html": "templates"}
        global pcf
        uri = ""
        
        #print("Update started for", pcf[u"repo"])
        if (pcf[u"repo"]=="S"):
            print("updating from stable")
            uri = stable_repo + "/" + stable_branch + "/pcf857x_plugin/"
        else:
            print("Updating from beta")
            uri = beta_repo + "/-/raw/" + beta_branch + "/"
            
        for p in list(upd_files.keys()):
            f_uri = uri + p
            print(p,"->",upd_files[p], " - " + f_uri)
            proc_files(f_uri,p,upd_files[p])
            
        #web.seeother(u"/pcf857x")
        raise web.seeother(u"/restart")