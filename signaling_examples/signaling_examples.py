# !/usr/bin/env python

""""This plugin includes example functions that are triggered by events in sip.py"""

# Python 2/3 compatibility imports
from __future__ import print_function

# local module imports
from blinker import signal
import gv

### Alarm Signal ###
def notify_alarm_toggled(name, **kw):
    print(_(u"Messge from ") + u"{}!: {}".format(name, kw[u"txt"]))


alarm = signal(u"alarm_toggled")
alarm.connect(notify_alarm_toggled)

# Send an alarm!
# alarm.send(u"Signaling plugin", txt=u"Just an example!")

### login ###
def notify_login(name, **kw):
    print(_(u"someone logged in"))


loggedin = signal(u"loggedin")
loggedin.connect(notify_login)

### Option settings ###
def notify_option_change(name, **kw):
    print(_(u"Option settings changed in gv.sd"))
    #  gv.sd is a dictionary containing the setting that changed.
    #  See "from options" gv_reference.txt


option_change = signal(u"option_change")
option_change.connect(notify_option_change)

### program change ##
def notify_program_change(name, **kw):
    print(_(u"Programs changed"))
    #  Programs are in gv.pd and /data/programs.json


program_change = signal(u"program_change")
program_change.connect(notify_program_change)

### program deleted ###
def notify_program_deleted(name, **kw):
    print(_(u"Program deleted"))
    #  Programs are in gv.pd and /data/programs.json


program_deleted = signal(u"program_deleted")
program_deleted.connect(notify_program_deleted)

### program toggled ###
def notify_program_toggled(name, **kw):
    print(_(u"Program toggled on or off"))
    #  Programs are in gv.pd and /data/programs.json


program_toggled = signal(u"program_toggled")
program_toggled.connect(notify_program_toggled)

### Rain Changed ##
def notify_rain_changed(name, **kw):
    print(_(u"Rain changed (from plugin)"))
    #  Programs are in gv.pd and /data/programs.json


rain_changed = signal(u"rain_changed")
rain_changed.connect(notify_rain_changed)

### Reboot ###
def notify_rebooted(name, **kw):
    print(_(u"System rebooted"))


rebooted = signal(u"rebooted")
rebooted.connect(notify_rebooted)

### Restart ###
def notify_restart(name, **kw):
    print(_(u"System is restarting"))


restart = signal(u"restart")
restart.connect(notify_restart)

### Station Names ###
def notify_station_names(name, **kw):
    print(_(u"Station names changed"))
    # Station names are in gv.snames and /data/snames.json


station_names = signal(u"station_names")
station_names.connect(notify_station_names)

### Stations were sheduled to run ###
# gets triggered when:
#       - A program is run (Scheduled or "run now")
#       - Stations are manually started with RunOnce
def notify_station_scheduled(name, **kw):
    print(_(u"Some Stations hve been scheduled: ") + "{}".format(str(gv.rs)))


program_started = signal(u"stations_scheduled")
program_started.connect(notify_station_scheduled)

### Station Completed ###
def notify_station_completed(station, **kw):
    print(_(u"Station {} run completed").format(station))


complete = signal(u"station_completed")
complete.connect(notify_station_completed)

### System settings ###
def notify_value_change(name, **kw):
    print(_(u"Controller values changed in gv.sd"))
    #  gv.sd is a dictionary containing the setting that changed.
    #  See "from controller values (cvalues)" gv_reference.txt


value_change = signal(u"value_change")
value_change.connect(notify_value_change)

### valves ###
def notify_zone_change(name, **kw):
    print(_(u"zones changed"))
    print(gv.srvals)  #  This shows the state of the zones.


zones = signal(u"zone_change")
zones.connect(notify_zone_change)
