# !/usr/bin/env python

import thread
import json
import time

import web
import gv  # Get access to ospi's settings
from urls import urls  # Get access to ospi's URLs
from ospi import template_render
from webpages import ProtectedPage


# Add a new url to open the data entry page.
urls.extend([
    '/cama', 'plugins.california_monthly.monthly_percent',
    '/cauma', 'plugins.california_monthly.update_percents',
    '/cacalcma', 'plugins.california_monthly.calc_percents'
])

# Add this plugin to the home page plugins menu
gv.plugin_menu.append(['California Monthly', '/cama'])


def set_wl(run_loop=False):
    """Adjust irrigation time by percent based on historical California climate data."""
    if run_loop:
        time.sleep(2)  # Sleep some time to prevent printing before startup information

    last_month = 0
    while True:
        try:
            with open('./data/ca_levels.json', 'r') as f:  # Read the monthly percentages from file
                levels = json.load(f)
        except IOError as e:  # If file does not exist
            levels = [100] * 12
            with open('./data/ca_levels.json', 'w') as f:  # write default percentages to file
                json.dump(levels, f)
        month = time.localtime().tm_mon  # Get current month.
        if month != last_month:
            last_month = month
            gv.sd['wl_monthly_adj'] = levels[month-1]  # Set the water level% (levels list is zero based).
            print 'California Monthly Setting water level to {}%'.format(gv.sd['wl_monthly_adj'])

        if not run_loop:
            break
        time.sleep(3600)


class monthly_percent(ProtectedPage):
    """Load an html page for calculating or entering monthly irrigation time adjustments"""

    def GET(self):
        try:
            with open('./data/ca_levels.json', 'r') as f:  # Read the monthly percentages from file
                levels = json.load(f)
        except IOError as e:  # If file does not exist
            print "File error: ", e
            levels = [100] * 12
            with open('./data/ca_levels.json', 'w') as f:  # write default percentages to file
                json.dump(levels, f)
        return template_render.california_monthly(levels)
    
class calc_percents(ProtectedPage):
    """Calculate monthly irrigation time adjustments from ETo zone date"""
    
    zone_data = ( [[0.93, 1.40, 2.48, 3.30, 4.03, 4.50, 4.65, 4.03, 3.30, 2.48, 1.20 ,0.62], 
                [1.24, 1.68, 3.10, 3.90, 4.65, 5.10, 4.96, 4.65, 3.90, 2.79, 1.80, 1.24], 
                [1.86, 2.24, 3.72, 4.80, 5.27, 5.70, 5.58, 5.27, 4.20, 3.41, 2.40, 1.86], 
                [1.86, 2.24, 3.41, 4.50, 5.27, 5.70, 5.89, 5.58, 4.50, 3.41, 2.40, 1.86], 
                [0.93, 1.68, 2.79, 4.20, 5.58, 6.30, 6.51, 5.89, 4.50, 3.10, 1.50, 0.93], 
                [1.86, 2.24, 3.41, 4.80, 5.58, 6.30, 6.51, 6.20, 4.80, 3.72, 2.40, 1.86], 
                [0.62, 1.40, 2.48, 3.90, 5.27, 6.30, 7.44, 6.51, 4.80, 2.79, 1.20, .062], 
                [1.24, 1.68, 3.41, 4.80, 6.20, 6.90, 7.44, 6.51, 5.10, 3.41, 1.80, 0.93], 
                [2.17, 2.80, 4.03, 5.10, 5.89, 6.60, 7.44, 6.82, 5.70, 4.30, 2.70, 1.86], 
                [0.93, 1.68, 3.10, 4.50, 5.89, 7.20, 8.06, 7.13, 5.10, 3.10, 1.50, 0.93], 
                [1.55, 2.24, 3.10, 4.50, 5.89, 7.20, 8.06, 7.44, 5.70, 3.72, 2.10, 1.55], 
                [1.24, 1.96, 3.41, 5.10, 6.82, 7.80, 8.06, 7.13, 5.40, 3.72, 1.80, 0.93], 
                [1.24, 1.96, 3.10, 4.80, 6.51, 7.80, 8.99, 7.75, 5.70, 3.72, 1.80, 0.93], 
                [1.55, 2.24, 3.72, 5.10, 6.82, 7.80, 8.68, 7.75, 5.70, 4.03, 2.10, 1.55], 
                [1.24, 2.24, 3.72, 5.70, 7.44, 8.10, 8.68, 7.75, 5.70, 4.03, 2.10, 1.24], 
                [1.55, 2.52, 4.03, 5.70, 7.75, 8.70, 9.30, 8.37, 6.30, 4.34, 2.40, 1.55], 
                [1.86, 2.80, 4.65, 6.00, 8.06, 9.00, 9.92, 8.68, 6.60, 4.34, 2.70, 1.86], 
                [2.48, 3.36, 5.27, 6.90, 8.68, 9.60, 9.61, 8.68, 6.90, 4.96, 3.00, 2.17]])
                
                
    def GET(self):
        qdict = web.input()
        if qdict.has_key('etoZone') and qdict['etoZone']:
            z_vals = self.zone_data[int(qdict['etoZone'])-1]
        else:
            raise web.seeother('/cama')
        max_eto = max(z_vals)
        levels = []
        for i in range(12):
            levels.append(int(round((z_vals[i] / max_eto)*100)))
        if qdict.has_key('etoZone') and qdict['etoZone']:
            levels.append(int(qdict['etoZone']))
        else:
            levels.append('')
               
        return template_render.california_monthly(levels)    


class update_percents(ProtectedPage):
    """Save user input to levels.json file"""

    def GET(self):
        qdict = web.input()
        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        vals = []
        for m in months:
            vals.append(int(qdict[m]))
        if qdict.has_key('etoZone') and qdict['etoZone']:
            vals.append(int(qdict['etoZone']))
        else:
            vals.append(0)
        try:
            with open('./data/ca_levels.json', 'w') as f:  # write the monthly percentages to file
                json.dump(vals, f)
        except Exeption as e:
            print "File error: ", e
        set_wl()
        raise web.seeother('/')

thread.start_new_thread(set_wl, (True,))