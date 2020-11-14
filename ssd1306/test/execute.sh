#!/bin/sh
# Linux regression test execution file.
# To run, cd to the test directory, make this script executable, and then execute this script.
python -B -m pytest -c test.cfg
