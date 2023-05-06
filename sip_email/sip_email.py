# !/usr/bin/env python

""" 
This plugin sends email to google gmail
Runs under Python3.

to set up a a local SMTP debugging server in a separate terminal instance:
sudo python -m smtpd -c DebuggingServer -n localhost:1025
"""

# standard library imports
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from email.message import EmailMessage

import json
import os
# from random import randint
import smtplib
import re
import ssl
import sys
from threading import Thread
import time
import traceback

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from helpers import timestr
from sip import template_render
from urls import urls  # Get access to SIP's URLs
import web
from webpages import ProtectedPage


# Add a new url to open the data entry page.
# fmt: off
urls.extend(
    [
        "/emls", "plugins.sip_email.settings",
        "/emljson", "plugins.sip_email.settings_json",
        "/emlu", "plugins.sip_email.update",
        "/emltst", "plugins.sip_email.send_test_email",
    ]
)
# fmt: on

# Add this plugin to the home page plugins menu
gv.plugin_menu.append([_("Email settings"), "/emls"])

sent = 0
send_lst = []
status = ""
stn_sum = 0
prog_name = ""
p_num = 0

################################################################################
# Helper functions:                                                            #
################################################################################

def get_email_options():
    """Returns options data from file if it exists
        or creates a new file with empty values.
    ."""
    global send_lst
    try:
        with open("./data/sip_email.json", "r") as f:  # Read the settings from file
            email_dat = json.load(f)
    except IOError: #  if file not found
        email_dat = {
            "sendList": "",
            "emlSender": "",
            "appPwd": "",
            "sendTo":"",
            "smtpServer": "smtp.gmail.com",
            "smtpPort": 465
        }
        with open("./data/sip_email.json", "w") as f:
            json.dump(email_dat, f, indent=4, sort_keys=True)   
    email_dat["status"] = ""
    send_lst = email_dat["sendList"]
    return email_dat


def email(subject, msg): #  Send an email message
    """Send email"""
    email_dat = get_email_options()
    # fmt: off
    if (email_dat["emlSender"]
        and email_dat["appPwd"] 
        and email_dat["sendTo"] 
        ):
        mail_from = email_dat["emlSender"]  # Gmail address
        app_pwd = email_dat["appPwd"]  # Gmail app password
        mail_to = email_dat["sendTo"]  # Recipient address (can be same as mail_from)
        smtp_server = email_dat["smtpServer"] # SMTP server
        port = email_dat["smtpPort"] # SMTP port
    # fmt: on
        message = EmailMessage()
        message.set_content(msg)
        message["Subject"] = subject
        message["From"] = mail_from
        message["To"] = mail_to      
         
        # Create a secure SSL context      
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(mail_from, app_pwd)
            server.sendmail(
                mail_from, mail_to, message.as_string()
            )                    
    else:
        raise Exception("E-mail plug-in is not properly configured!")

################################################################################
# Message functions:                                                                   #
################################################################################
    
def send_restart_notice():  # Notice 1
    if "1" in send_lst:
        global sent
        if(
           not sent 
            ):
            subject = "SIP has restarted"
            message = f"SIP restarted on {time.strftime('%d.%m.%Y at %H:%M:%S', time.localtime(time.time()))} \n"
            message += "This could indicate a loss of power or other problem. \n\n"
            message += "In case running or scheduled programs were interrupted please check SIP's log page.\n"
            message += "The last 5 log entries are shown below for quick reference. \n\n"
            message += "Date\t\tStartTime\tDuration\tProgram\tStation\n"
            try:
                with open("./data/log.json") as logf:
                    i = 0
                    while i < 5:
                        line_dict = json.loads(logf.readline())
                        message += f"{line_dict['date']}\t{line_dict['start']}\t{line_dict['duration']}\t\t{line_dict['program']}\t{gv.snames[line_dict['station']]}\n"
                        i += 1
            except IOError:
                pass
            email(subject, message)
            sent = 1

    
def email_start_stop(name, **kw):  # Notice 2 and 3
    global stn_sum, prog_name
    if ("2" in send_lst
        or "3" in send_lst
        ):         
        if (gv.pon  # program has started
            ):
            p_num = gv.pon
            if p_num == 98:
                prog_name = _(u"Run-once")
            elif p_num == 99:
                prog_name = _(u"Manual")
            else:           
                p_idx = p_num - 1
                if gv.pd[p_idx]["name"]:
                    prog_name = gv.pd[p_idx]["name"] 
                    subject = f"SIP program {prog_name} started."
                    message = f"The {prog_name} program started at {gv.nowt.tm_hour:02d}:{gv.nowt.tm_min:02d}.\n\n"
                else:
                    prog_name = ""
                    subject = f"SIP program {p_num} started."
                    message = f"Program {p_num} started at {gv.nowt.tm_hour:02d}:{gv.nowt.tm_min:02d}.\n\n"
                message += "Scheduled in this program:\n"
                for i, e in enumerate(gv.rs):
                    if any(e):
                        message += f"{gv.snames[i]} for {int(e[2]//60)}m {int(e[2] % 60)}s\n"
                        stn_sum += 1
                if "2" in send_lst:
                    email(subject, message)
        elif (not gv.pon  # program has ended
              and "3" in send_lst
              ):          
            if prog_name:
                subject = f"SIP program {prog_name} completed."
                message = f"The {prog_name} program ended at {gv.nowt.tm_hour:02d}:{gv.nowt.tm_min:02d}.\n\n"
            else:
                subject = f"SIP program {gv.lrun[1]} completed."
                message = f"Program {gv.lrun[1]} ended at {gv.nowt.tm_hour:02d}:{gv.nowt.tm_min:02d}.\n\n"
            message += "Stations logged in this program:\n"
            message += "Date\t\tStartTime\tDuration\tStation\n"
            
            try:
                with open("./data/log.json") as logf:
                    i = 0
                    while i < stn_sum:
                        line_dict = json.loads(logf.readline())
                        message += f"{line_dict['date']}\t{line_dict['start']}\t{line_dict['duration']}\t\t{gv.snames[line_dict['station']]}\n"
                        i += 1
            except IOError:
                pass
            stn_sum = 0
            email(subject, message)
    
program_change = signal("running_program_change")
program_change.connect(email_start_stop) 


def email_rain_delay_expired(name, **kw):  # Notice 4
    if "4" in send_lst:
        subject = "SIP Rain delay has expired"
        message = f"SIP's manually set rain delay expired on {time.strftime('%d.%m.%Y at %H:%M:%S', time.localtime(time.time()))}.\n"
        message += "Scheduled irrigation programs are now active."
        email(subject, message)
    
delay_expired = signal("rain_delay_change")
delay_expired.connect(email_rain_delay_expired) 


def email_rain_sensor(name, **kw):  # Notice 5 and 6
    if ("5" in send_lst
        or "6" in send_lst
        ):
        if (gv.sd['rs']
            and "5" in send_lst
            ):
            subject = "SIP rain sensor on"
            message = f"SIP's rain sensor detected rain 0n {time.strftime('%d.%m.%Y at %H:%M:%S', time.localtime(time.time()))}.\n"
            message += "Stations controlled by rain sensor are now on hold"
        elif (not gv.sd['rs']
              and "6" in send_lst
              ):
            subject = "SIP rain sensor off"
            message = f"SIP's rain sensor stopped suppressing stations on {time.strftime('%d.%m.%Y at %H:%M:%S', time.localtime(time.time()))}.\n"
            message += "Station controlled by rain sensor are now active"  
        email(subject, message)          
    
rain_sensor = signal("rain_changed")
rain_sensor.connect(email_rain_sensor)

def plugin_alert(name, **kw):  # Notice 7
    """
    Sends an alert generated by another plugin
    and received via a blinker signal
    """
    if "7" in send_lst:
        if kw["subj"]:
            subject = kw["subj"]
        else:
            subject = "SIP alert!"
        if kw["msg"]:
            message = kw["msg"]
        else:
            message = "SIP plugin " + name + " has reported a problem. Please check your system"
        email(subject, message)

plugin_alarm = signal("email_alert") # expected blinker signal name from plugin
plugin_alarm.connect(plugin_alert)  # Run plugin_alert() to send email when signal is received. 


################################################################################
# Web pages:                                                                   #
################################################################################


class settings(ProtectedPage):
    """Load an html page for entering email settings."""
    def GET(self):
        opts = get_email_options()
        if status:
            opts["status"] = status   
        return template_render.sip_email(opts)


class update(ProtectedPage):
    """Save user input to email.json file."""
    def GET(self):
        global status
        status = ""
        qdict = web.input()
        with open("./data/sip_email.json", "w") as f:  # write the settings to file
            json.dump(qdict, f, indent=4, sort_keys=True)
        raise web.seeother("/emls")


class send_test_email(ProtectedPage):
    """Send test email"""  
    def GET(self):
        global status
        status = ""
        regex = re.compile(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+')
        opts = get_email_options()
        mail_from = opts["emlSender"] 
        mail_to = opts["sendTo"]
       
        if not re.fullmatch(regex, mail_from):
            status = "Sender email address appears to be invalid\n"
        if not re.fullmatch(regex, mail_to):
            status = "Send-to email address appears to be invalid\n"      
             
        subject = "SIP test message"
        message = "The sip_email plugin is set up and working properly"
       
        try:
            email(subject, message)
        except Exception as e:
            status += "email failed " + str(e)
        else:
            status = "Test message was sent"          
        raise web.seeother("/emls")

get_email_options()
send_restart_notice()