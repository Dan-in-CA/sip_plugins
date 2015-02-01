OSPi Plugins
============
###A collection of user contributed plugins for the Raspberry Pi based irrigation controller OSPi software.
**Please note:** Unless otherwise stated:</br>
This is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

These programs are distributed in the hope that they will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>
******************
proto
---------
A bare bones plugin for use as a starting point for plugin authoring.

system_update
----------
Allows updating OSPi software from integrated UI

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


