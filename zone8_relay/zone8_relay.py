# !/usr/bin/env python
#  This plugin includes implements an 8th zone using the relay on gpio 10

from blinker import signal
from gpio_pins import GPIO
import gv

def notify_zone_change(name, **kw):
    relayGPIO = 10 
    targetZone = 8

    if len(gv.srvals) >= targetZone:
        if gv.srvals[targetZone] == 1:
            GPIO.output(relayGPIO, GPIO.HIGH)
        else:
            GPIO.output(relayGPIO, GPIO.LOW)

zones = signal('zone_change')
zones.connect(notify_zone_change)
