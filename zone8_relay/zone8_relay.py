# !/usr/bin/env python
#  This plugin includes implements an 8th zone using the relay on gpio 10

from blinker import signal
from gpio_pins import GPIO
import gv

def notify_zone_change(name, **kw):
    if gv.srvals[8] == 1:
       #print "zone 9 is on"
       GPIO.output(10, GPIO.HIGH)
    else:
       #print "zone 9 is off"
       GPIO.output(10, GPIO.LOW)

zones = signal('zone_change')
zones.connect(notify_zone_change)
