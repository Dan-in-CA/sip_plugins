# Moisture Sensor Data MQTT

## Introduction

The Moisture Sensor Data MQTT plugin subscribes to moisture sensor
readings sent to an MQTT topic and makes the readings available to the
Moisture Sensor Control plugin.

## Dependencies

This plugin requires the MQTT plugin to be installed.

## Configuring

|Field |Description|
| :--- | :--- |
| Enable | Enable or disable receiving data for the sensor.|
| Sensor (required)| The internal name of the sensor.|
| MQTT topic (required)| The MQTT topic that the sensor sends its data to.|
| Reading path (optional)| The JSON path of the reading value if required. See below |
| Driest value (required)| The raw driest value the sensor can send. |
| Wettest value (required)| The raw wettest vale the sensor can send. |
| Retention period(optional)| The amount of time readings will be saved. Not implemented yet.|

## Sensor

Sensor namess can be renamed by changing the name of the sensor
field. Sensors can be deleted by blanking out the name in the sensor
field.

## Reading path

When sensor reading value is published as a JSON message as opposed to
a simple value specify the JSON path of the reading value using a
[jmespath expression](https://jmespath.org/tutorial.html).

For example if the message is {"value1", "57", "battery": 27}, then
the reading path would need to be set to value1.

## Driest / wettest value

The plugin will convert the raw sensor reading values to a percentage
value (0 - 100%) using the configured driest and wettest values.
