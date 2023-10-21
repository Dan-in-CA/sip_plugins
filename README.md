SIP Plugins
============
###A collection of user contributed plugins for the Raspberry Pi based irrigation controll software  [SIP](https://github.com/Dan-in-CA/SIP).

####To ask questions and learn more about SIP and plugins please visit the **[SIP Forum](http://nosack.com/sipforum/index.php)**

**Please note:** Unless otherwise stated:
This is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

These programs are distributed in the hope that they will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
<http://opensource.org/licenses/gpl-3.0.html>
******************
backup_settings
---------
This plugin allows remote access (download and upload) of all the 
settings data necessary for SIP configuration.  This facilitates complete rebuild or
replacement of the system without losing any SIP settings or log data.

buzzer
---------
This plugin has been created to provide simple audio feedback.  This plugin is intended to be controlled through other
plugins through the "buzzer_beep" signal. Buzzer should be connected to GPIO pin 32.

california_monthly
---------
Provides automatic monthly adjustment of irrigation times based on historical weather data.  
Requires SIP version 4.1.7 or later.

cli_control
---------- 
Sends command line commands to control remote stations e.g. RF devices.  
Replaces rf_control. 

combine_stations
----------
Allows multiple stations to be run at the same time (concurrently) when SIP is in sequential mode.

email_adj
----------
Sends status email to google email account. **NOTE: This plugin runs under Python2x only**.  
may use obsolete code - see **sip_email** plugin for updated version.

flow
----------
Allows the addition of a water flow sensor to enable real-time flow data and logging of water usage.
Requires SIP v4.1.46 (or later) or the most current version of the plugin_manager from the plugins list.
Requires Python 3.

keypad
----------
A plugin for using an 4X4 scanning keypad to execute simple functions without the use of an external peripheral.  
This plugin interfaces with buzzer and ssd1306 plugins through signals.

lcd_adj
----------
Uses I2C for LCD 16x2 char data display

monthly_adj
----------
Adjust irrigation time each month.  
Requires SIP version 4.1.7 or later.

mqtt
----------
This is the base mqtt plugin.   
It provides a shared MQTT client object for other plugins.  
Requires paho mqtt.

mqtt_get_values
----------
Requires base mqtt plugin.  
Can be used to read SIP's gv.* settings.  
See gv_reference.txt in the SIP folder for a list of settings.

mqtt_hass
----------
Home Assistant integration using MQTT autodiscovery.
Requires SIP version 4.1.25 or later, and base mqtt plugin
Run "python3 -m pip install python-slugify --upgrade" before installing this plugin.  

mqtt_set_values
----------
Requires base mqtt plugin.  
Can be used to change SIP's gv.* settings.  
See gv_reference.txt in the SIP folder for a list of settings.

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

node_red
-------------
Under development. Not fully documented. Use with caution.

pcf857x_plugin
----------
Provides an easy, inexpensive solution for adding a large number of stations.
Requires Python 3.

pcf_8591_adj
----------
Read sensor data (temp or voltage) from I2C PCF8591 ADC/DAC

plugin_manager
----------
Allows SIP to install plugins (installed by default)

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

relay_16
----------
A relaly_board update for use on 40 pin GPIO headers.  
Supports up to 16 relays. Requires SIP 3.2.43 or later.

relay_board
----------
A plugin for using relay boards to control sprinkler valves, etc

sip_email
----------
Sends email notifications of important SIP events.
Python 3 only.

shutdown_button
----------
Provides a means of stopping the SIP program from the UI.

signaling_examples
----------
Example plugin provides functions triggered by signals from core program (installed by default)

sms_adj
----------
Control your SIP using SMS (Short Message Service)

sms_plivo
----------
Allows plugins that are configured to this messaging framework to send SMS and voice messages through the [Plivo](https://www.plivo.com) service.
Requires Python 3 and a Plivo account.

ssd1306
----------
Plugin for SSD1306 128x64 pixel display connected to I2C interface.

system_update
----------
Allows updating SIP software from integrated UI  
(Installed by default)

telegram_bot
-------------
A simple telegram.org bot to interface with a SIP installation.  
Run "pip install python-telegram-bot --upgrade" before installing this plugin.

weather_level_adj
----------
Adjust irrigation time based on weather forecast

advance_control
----------
Plug-in to control valves in shelly, in the future son-off will be supported and more shelly versions. Use HTTP DD commands.
