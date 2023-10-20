# !/usr/bin/env python
# -*- coding: utf-8 -*-

import web  # web.py framework
import gv  # Get access to SIP's settings
import time
from urls import urls  # Get access to SIP's URLs
from sip import template_render  #  Needed for working with web.py templates
from webpages import ProtectedPage  # Needed for security
from helpers import read_log
from pathlib import Path
import json  # for working with data file

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/backup", u"plugins.backup_settings.backup",
    u"/download", u"plugins.backup_settings.download"
    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"Backup/Restore Settings"), u"/backup"])

class download(ProtectedPage):
    """
    Download all data files as a single JSON archive file.
    """

    def GET(self):
        try:
            restorePoint = time.strftime('%Y-%m-%dT%H:%M:%SZ', gv.nowt)
            data = {
                '__restorePoint' : restorePoint,
            }
            
            dataFiles = Path('./data')
            for filename in list(dataFiles.glob('**/*.json')):
                filename = str(filename)[5:] # convert path to the filename string by stripping off "data/"
                with open(
                    u"./data/" + filename, u"r"
                ) as f:
                    if (filename != "log.json"):
                        data[filename[:-5]] = json.load(f) # strip off the ".json" for the key name
                    else:
                        data["log"] = read_log()
                    print("Backing up " + filename)

            web.header('Content-Type','text/json')       
            web.header('Content-disposition', 'attachment; filename=SIP-backup-%s.json'%restorePoint)
            return json.dumps(data)  # return data as json txt file
        except IOError:  # If file does not exist return empty value
            raise web.seeother('/backup?success=false')

class backup(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def POST(self):
        try:
            upload = web.input(myfile={})
            data = json.loads(upload['myfile'].file.read())
            # break the master data into individual components corresponding to files
            
            for d in data:
                if d == "__restorePoint":
                    restorePoint = data["__restorePoint"]
                elif d == "log":
                    log = data["log"]
                    lines = []
                    for r in log:
                        lines.append(json.dumps(r) + "\n")
                        with open("./data/log.json", "w", encoding="utf-8") as f:
                            f.writelines(lines)
                    print("Restored log.json")
                else:
                    with open(u"./data/" + d + ".json", u"w") as f:
                        json.dump(data[d], f, indent=4, sort_keys=True)
                    print("Restored " + d + ".json")

            raise web.seeother('/backup?success=true&restorePoint=' + restorePoint)
        except IOError:
            raise web.seeother('/backup?success=false')
       
    
    def GET(self):
        user_data = web.input(success="unknown", restorePoint="")
        status = {"success" : user_data.success, "restorePoint" : user_data.restorePoint }  # report the status 
        return template_render.backup_settings(status)  # open backup/restore page
