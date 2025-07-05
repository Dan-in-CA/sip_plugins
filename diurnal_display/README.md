SIP Diurnal Display Plugin
=======================

A plugin to indicate sunrise and sunset times in the home page schedule display.

![Screenshot](https://github.com/user-attachments/assets/9f9c539f-3dcb-40f8-98f0-fdb103a160f7)

Installation
============
This plugin requires a library called "suncalc.py".  More information is available at https://pypi.org/project/suncalc/.
To install type the following into a terminal window:

```
    pip3 install suncalc
```

This may raise an error "externally-managed-environment."  There are various ways to address this, but a simple solution
is to break the external management, with these two lines, and then try the installation again:

```
    cd /usr/lib/python3.11

    sudo rm EXTERNALLY-MANAGED
```

After installing suncalc, restart SIP, and use the Plugin Manager to enable the plugin, and set your precise coordinates.

This plugin is primarily a test of the new facility for plugins to alter the UI through script, it may prove a useful starting point
for other plugin authors.
