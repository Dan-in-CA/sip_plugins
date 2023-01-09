# Advance Control to SIP controller
SIP [SIP core program](https://dan-in-ca.github.io/SIP/) is an open platform for irrigation.
This plug in allow to extent the types of output for valves. Put all the valves in the same places sometimes it is not easy, WI-FI relays could be the best solution. Possibility to use network devices allow much more flexible infrastructure.
Shelly or Son-Off are an inexpensive WI-FI relay with direct HTTP commands. For now Son-Off is not tested, before use must be proper test.

![Shelly connection to valves](https://raw.githubusercontent.com/PedroFRCSantos/SIP_extension_advance_control/main/ShellyValveSchematic.png)

In this example you can see the device Shelly 1 connect to an electro valve. Shelly 1 has one simple relay, outputs "0" and "1", the working voltage could be anything, ex: 24VAC, 12VAC or 24VDC. The transformer is optional, depending of valve operation voltage. The switch is also optional, if you want to have an physical button near the valve.

For non support devices the extension allow to add direct command in Linux terminal.
Son-Off devices the code is not proper tested.

## Installation
Before use the plug in you need to guaranty the following packages are install. To install run the following commands:

sudo pip3 install requests

Copy advance_control.py to plugins folder.
Copy advance_control.html and advance_control_status.html copy to templates.
All files in image folder copy to static\images.
