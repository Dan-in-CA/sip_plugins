# Moisture Control Plugin

## Introduction

The Moisture Sensor Control plugin can be configured to either

- decrease the watering time for plants by suppressing a schedule (program).
- increase the watering time for plants by triggering a RUN ONCE program.

The logic is base on the moisture readings captured by moisture sensors
and is applied on the station level.

The plugin only evaluates moisture sensor readings but does not itself
capture the data, so it requires that a moisture sensor data plugin be
installed and configured that does so, for example the Moisture Sensor
Data MQTT plugin.

## Dependencies

This plugin requires a moisture sensor data plugin to be installed and
configured, for example the Moisture Sensor Data MQTT plugin.

## For users

### Sensor
Select the moisture sensor that will be used to control the
station. The sensors must be configured in a moisture sensor data
plugin that is used to capture the moisture sensor data (e.g. Moisture
Sensor Data MQTT plugin).

### Suppress schedule

The suppress schedule feature of the plugin is triggered when a
program is automatically scheduled to run on a station (RUN ONCE and
RUN NOW schedules are ignored) and depending on the configuration will
suppress the schedule.

|Field |Description|
| :--- | :--- |
|Enable | Enable or disable the plugin's control of the station.|
|Threshold (required) | Schedules will be suppressed so long as the last available sensor reading is above this value (0 - 100%).|
|Stale reading (optional) | To protect against broken sensors the plugin will only interpret sensor reading younger than the configured number of minutes.|

If a required attribute is not set the plugin will quietly skip the station.

### Trigger schedule

The trigger schedule feature of the plugin is triggered when a
new sensor reading is received and depending on the
configuration will trigger a RUN ONCE program.

|Field |Description|
| :--- | :--- |
|Enable| Enable or disable the plugin's control of the station.|
|Threshold (required)| A RUN ONCE program will be started if the sensor reading is below the configured value (0 - 100%).|
|Duration (required)| The duration of the RUN ONCE program.|
|Pause (optional)| The duration between repeated run of the RUN ONCE program in order to give moisture sensors time to adjust.|

The increase moisture feature is only really useful in concurrent
station mode as in serial mode the triggering of a RUN ONCE program
would stop all other programs on all stations.

If a required attribute is not set the plugin will quietly skip the station.

### Limitations

The plugin does not currently store the last reading values so after a
restart it will be inactive until readings are received.

The plugin does not currently respect the option "Ignore Plugin
adjustments", mainly because I do not understand how to implement
the validation.

## For developers

On initialisation the plugin will list all the files in
./data/moisture\_sensor_data and use the file names to initialse a
list of available sensors. Sensors and readings can be add by
signaling the plugin.

This plugin listens for the signal "moisture\_sensor_data" with the
following values:

|Name | Message (data) |
| :--- | :--- |
|reading | {"timestamp": "Timestamp object", "value": "Integer in the range 0 - 100"} |
|add | {"sensor": "sensor name"} |
|delete | {"sensor": "sensor name"} |
|rename | {"sensor": "new name", "old_sensor": "old name"} |


## Version information

- v0.0.4
  - Fix issue with too many stations being triggered
- v0.0.3
  - Fix renamed sensor not being saved
- v0.0.2
  - Ignore RUN ONCE programs
  - Improved documentation
- v0.0.1
  - initial version
