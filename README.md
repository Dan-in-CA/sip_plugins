OSPi Plugins
============
###A collection of user contributed plugins for the Raspberry Pi based irrigation controll software  [OSPi](https://github.com/Dan-in-CA/OSPi).
**Please note:** Unless otherwise stated:  
This is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

These programs are distributed in the hope that they will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
<http://opensource.org/licenses/gpl-3.0.html>
******************
proto
---------
A bare bones plugin for use as a starting point for plugin authoring.  
(Installed by default)

system_update
----------
Allows updating OSPi software from integrated UI  
(Installed by default)

email_adj
----------
Sends status email to google email account

pressure_adj
----------
Checks water pressure when master station is switched on

lcd_adj
----------
Uses I2C for LCD 16x2 char data display  
Requires pylcd2 library

pfc_8591_adj
----------
Read sensor data (temp or voltage) from I2C PCF8591 ADC/DAC

pulse_cct
----------
Pulses a selected circuit with a 2.5 Hz signal for 30 sec
to discover the location of a valve

sms_adj
----------
Control your ospi using SMS (Short Message Service)

monthly_adj
----------
Adjust irrigation time each month

relay
----------
Example plugin to demonstrate OSPi on-board relay

signaling_examples
----------
Example plugin provides functions triggered by signals from core program (installed by default)

weather_adj
----------
Adjust irrigation schedule based on weather forecast

weather_level_adj
----------
Adjust irrigation time based on weather forecast
