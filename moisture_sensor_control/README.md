# Moisture Control Plugin

## Introduction

The Moisture Sensor Control plugin can be configure to either

- decrease the moisture level of plants by suppressing a schedule (program).
- increase the moisture level of plants by triggering a run once program.

The logic is base on the moisture reading captured by moisture sensors
and is applied on the station level.

The plugin only evaluates moisture sensor data but does not itself
capture the data so it requires that a moisture sensor data plugin be enable that
does so, for example the Moisture Sensor Data MQTT plugin.

## Dependencies

This plugin requires a moisture sensor data plugin to be installed, for example the Moisture Sensor Data MQTT plugin.

## For users

### Sensor
Select the moisture sensor that will be used to control the
station. The sensors must be configured a moisture sensor data plugin
that is used to capture the moisture sensor data (e.g. Moisture
Sensor Data MQTT plugin).

### Decrease moisture

The decrease moisture feature of the plugin is triggered when a
program is scheduled to run on a station and depending on the
configuration will suppress the schedule.

|Field |Description|
| :--- | :--- |
|Enable | Enable or disable the plugin's control of the station.|
|Threshold (required) | Schedules will be suppressed so long as the last available sensor reading is above this value (0 - 100%).|
|Stale reading (optional) | To protect against broken sensors the plugin will only interpret sensor reading younger than the configured number of minutes.|

If a required attribute is not set the plugin will quietly skip the station.

### Increase moisture

The increase moisture feature of the plugin is triggered when a
new sensor reading is received and depending on the
configuration will trigger a run once program.

|Field |Description|
| :--- | :--- |
|Enable| Enable or disable the plugin's control of the station.|
|Threshold (required)| A run once program will be started if the sensor reading is below the configured value (0 - 100%).|
|Duration (required)| The duration of the run once program.|
|Pause (optional)| The duration between repeated run of the run once program in order to give moisture sensors time to adjust.|

The increase moisture feature is only really useful in concurrent
station mode as in serial mode the triggering of a run once program
would stop all other programs on all stations.

If a required attribute is not set the plugin will quietly skip the station.

## For developers

On initialisation the plugin will list all the files in ./data/moisture\_sensor_data and use the file names to initialse a list of available sensors. The last entry of each file will be read and used as the last sensor reading value. Sensors and readings can be add by signaling the plugin.

This plugin listens for the signal "moisture\_sensor_data" with the following values:

|Name |Message (data)|
| :--- | :--- |
|reading| {"timestamp": "Timestamp object", "value": "Integer in the range 0 - 100"}
|add | {"sensor": "sensor name"}
