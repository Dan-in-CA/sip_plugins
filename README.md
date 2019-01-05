SIP Plugins
============
###A collection of user contributed plugins for the Raspberry Pi based irrigation controll software  [SIP](https://github.com/Dan-in-CA/SIP).

####To ask questions and learn more about SIP and plugins please visit the **[SIP Forum](http://nosack.com/sipforum/index.php)**

**Please note:** Unless otherwise stated:
This is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

These programs are distributed in the hope that they will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
<http://opensource.org/licenses/gpl-3.0.html>
******************
buzzer
---------
This plugin has been created to provide simple audio feedback. This plugin is intended to be controlled through other
plugins through the "buzzer_beep" signal. Buzzer should be connected to GPIO pin 32.

california_monthly
---------
Provides automatic monthly adjustment of irrigation times based on historical weather data.

cli_control
----------
Replaces rf_control.
Sends command line commands to control remote stations e.g. RF devices.

email_adj
----------
Sends status email to google email account

keypad
----------
A plugin for using an 4X4 scanning keypad and buzzer to execute simple functions without the use of an external peripheral

lcd_adj
----------
Uses I2C for LCD 16x2 char data display
Requires pylcd2 library

monthly_adj
----------
Adjust irrigation time each month

mqtt
----------
This is the base mqtt plugin,
it provides a shared MQTT client object for other plugins.
Requires paho mqtt.

mqtt_schedule
--------------
Relies on MQTT, subscribes to a control topic and schedules
run once programs as command by MQTT.

mqtt_slave
--------------
Relies on MQTT, subscribes to a control topic and allows
one SIP system to control other SIPs using MQTT.

mqtt_zones
-------------
Relies on MQTT, broadcasts the current status of all zones.

pcf_8591_adj
----------
Read sensor data (temp or voltage) from I2C PCF8591 ADC/DAC

pressure_adj
----------
Checks water pressure when master station is switched on

proto
---------
A bare bones plugin for use as a starting point for plugin authoring.
(Installed by default)

pulse_cct
----------
Pulses a selected circuit with a 2.5 Hz signal for 30 sec
to discover the location of a valve

pump_control
------------
Controls a pump relay via an Arduino over i2C.
Checks pressure in pipe ensuring proper operation.

relay
----------
Example plugin to demonstrate OSPi on-board relay

relay_16
----------
A relaly_board update for use on 40 pin GPIO headers.
Supports up to 16 relays. Requires SIP 3.2.43 or later.

relay_board
----------
A plugin for using relay boards to control sprinkler valves, etc

signaling_examples
----------
Example plugin provides functions triggered by signals from core program (installed by default)

sms_adj
----------
Control your ospi using SMS (Short Message Service)

ssd1306
----------
Plugin for SSD1306 128x64 pixel display connected to I2C interface with HW address 0x3c.

system_update
----------
Allows updating OSPi software from integrated UI  S
(Installed by default)

telegram_bot
-------------
A simple telegram.org bot to interface with a SIP installation.

Run "pip install python-telegram-bot --upgrade" before installing this plugin.

weather_adj
----------
Adjust irrigation schedule based on weather forecast

weather_level_adj
----------
Adjust irrigation time based on weather forecast

