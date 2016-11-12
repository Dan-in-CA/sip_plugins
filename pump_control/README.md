SIP Pump Control Plugin
=======================

A plugin to interface with an arduino based Pump Control, see pumpControlv2.ino for the arduino code. Its connected to the raspberry via I2C.

The arduino monitors that the pump is working correctly via some sensors and controls the relay of the pump.

The current version only checks for the pressure in the pipe.

It uses a Blinker alarm signal when detects some alarm on the pump