# Simple Chart Plugin

## Introduction

The Simple Chart plugin displays line charts using data and
configuration options provided by other plugins such as the Moisture
Sensor Data MQTT plugin.

The plugin also provides the ability to customise the chart display
options.

## Dependencies

This plugin requires at least one other plugin, such as the Moisture
Sensor Data MQTT or Scheduled Data Collector plugins, that provide
the data to be displayed.

## For users

### Display chart

Displays one or more configured charts. The initial chart window show
data for either the current week (Mo - So) or day (00:00 -
00:00). This can be changed using the drop down to the left of the
chart.

The chart can be scrolled backwards or forwards.

### Configure chart

Displays the configuration options for all the available line charts.

Chart visibility can be enabled or disabled using the checkbox next to
the chart name.

You may change the line chart display options to your hearts content
and in the process possibly break the chart display. To
revert to the original display options clear the text box. If you
discover a better display format please feel free to share.

The plugin uses the following libraries to display the charts:

- [chart.js](https://www.chartjs.org/docs/latest/)
  - [Line charts](https://www.chartjs.org/docs/latest/charts/line.html)
- [luxon](https://moment.github.io/luxon/#/?id=luxon)
  - [formatting](https://moment.github.io/luxon/#/formatting)

## For developers

The Simple Chart plugin requires chart data and a chart
configuration in order to display a chart.

The chart data should be store in the ./static/data folder. Each file
will be displayed as a time series either as a separate chart or
combined in one chart depending on the configuration.

The chart data is loaded using [d3.js](https://d3js.org/). As d3 loads
the data values as strings a utility function is called to convert the
values to integers if possible. This only works for top level
dictionary values.

The chart configurations should be installed under the
./data/simple_chart folder. Each chart configuration consists of the
following dictionary:

- data (list): path to the chart data ./static/data/...
  - Directory: The chart will consist on multiple series, one for each file in the directory
  - File: The chart will consist one series
  - Glob: The chart will consist on multiple series, one for each file matching the glob
- options (string): The JavaScript options for the chart. Will be templated directly into the chart function as is.
- window (string): The portion of the data set to display at one time, either "day" or "week" (default)

## Limitations

- Currently only line charts are supported
- x-axis is time based

## Version information

- v0.0.2
  - Improve documentation
- v0.0.1
  - initial version
