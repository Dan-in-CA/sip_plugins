#!/bin/sh
# Linux regression test execution file.
# pytest module is required for this (pip install pytest)
# To run, cd to the test directory, make this script executable, and then execute this script.
# Note: this is forced to python3 since pytest doesn't seem to work for python2
python3 -B -m pytest -c test.cfg
