# Monthly Adjust per Station Plugin

## Introduction

Alter the amount of water the station delivers by adjusting the
watering time. This plugin allows a more fine grained level of control
than the water level setting on the home page.

## Configuration

The plugin will only have an effect on schedules started by programs
triggered automatically and will ignore schedules/programs started with RUN
NOW or RUN ONCE.

Adjustment levels can be entered per station per month to indicate
the % adjustment to be applied to the watering time.

If no value is entered for the station/month the value set in "Default
Adjustment" is used. If the "Default Adjustment" is not set then the
plugin will take no action for the station/month.

## Limitations

The plugin does not currently respect the option "Ignore Plugin adjustments".

## Version information

- v0.0.2
  - Ignore RUN ONCE programs
- v0.0.1
  - initial version
