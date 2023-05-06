# !/usr/bin/env python

""" this plugin sends email to google gmail"""

from __future__ import print_function
from threading import Thread
from random import randint
import json
import time
import os
import sys
import traceback

import web
import gv  # Get access to SIP's settings
from urls import urls  # Get access to SIP's URLs
from sip import template_render
from webpages import ProtectedPage
from helpers import timestr

from email import encoders
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText

# Add a new url to open the data entry page.
# fmt: off
urls.extend(
    [
        u"/emla", u"plugins.email_adj.settings",
        u"/emlj", u"plugins.email_adj.settings_json",
        u"/uemla", u"plugins.email_adj.update",
        u"/uemltest", u"plugins.email_adj.send_test_email",
    ]
)
# fmt: on

# Add this plugin to the home page plugins menu
gv.plugin_menu.append([_(u"Email settings"), u"/emla"])

################################################################################
# Main function loop:                                                          #
################################################################################


class EmailSender(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()
        self.status = u""

        self._sleep_time = 0

    def add_status(self, msg):
        if self.status:
            self.status += u"\n" + msg
        else:
            self.status = msg
        print(msg)

    def update(self):
        self._sleep_time = 0

    def _sleep(self, secs):
        self._sleep_time = secs
        while self._sleep_time > 0:
            time.sleep(1)
            self._sleep_time -= 1

    def try_mail(self, subject, text, attachment=None):
        self.status = u""
        try:
            email(subject, text, attachment)  # send email with attachment from
            self.add_status(u"Email was sent: " + text)
        except Exception as err:
            self.add_status(u"Email was not sent! " + str(err))

    def run(self):
        time.sleep(
            randint(3, 10)
        )  # Sleep some time to prevent printing before startup information

        dataeml = get_email_options()  # load data from file
        subject = u"Report from " + gv.sd[u"name"]  # Subject in email
        last_rain = 0
        was_running = False

        self.status = u""
        self.add_status(u"Email plugin is started")

        if dataeml[u"emllog"] != u"off":  # if eml_log send email is enable (on)
            body = (
                u"On "
                + time.strftime(u"%d.%m.%Y at %H:%M:%S", time.localtime(time.time()))
                + u": System was powered on."
            )
            self.try_mail(subject, body, u"data/log.json")

        while True:
            try:
                # send if rain detected
                if dataeml[u"emlrain"] != u"off":  # if eml_rain send email is enable (on)
                    if (
                        gv.sd[u"rs"] != last_rain
                    ):  # send email only 1x if  gv.sd rs change
                        last_rain = gv.sd[u"rs"]

                        if (
                            gv.sd[u"rs"] and gv.sd[u"urs"]
                        ):  # if rain sensed and use rain sensor
                            body = (
                                u"On "
                                + time.strftime(
                                    u"%d.%m.%Y at %H:%M:%S", time.localtime(time.time())
                                )
                                + u": System detected rain."
                            )
                            self.try_mail(
                                subject, body
                            )  # send email without attachments

                if dataeml[u"emlrun"] != u"off":  # if eml_rain send email is enable (on)
                    running = False
                    for b in range(gv.sd[u"nbrd"]):  # Check each station once a second
                        for s in range(8):
                            sid = b * 8 + s  # station index
                            if gv.srvals[sid]:  # if this station is on
                                running = True
                                was_running = True

                    if was_running and not running:
                        was_running = False
                        if gv.lrun[1] == 98:
                            pgr = u"Run-once"
                        elif gv.lrun[1] == 99:
                            pgr = u"Manual"
                        else:
                            pgr = str(gv.lrun[1])

                        dur = str(timestr(gv.lrun[2]))
                        start = time.gmtime(gv.now - gv.lrun[2])
                        body = (
                            u"On "
                            + time.strftime(
                                u"%d.%m.%Y at %H:%M:%S", time.localtime(time.time())
                            )
                            + u"\n"
                            u"SIP has run: Station "
                            + str(gv.lrun[0] + 1)
                            + u", "
                            + gv.snames[gv.lrun[0]]
                            + u"\n"
                            u"Program: " + pgr + u"\n"
                            u"Start time: "
                            + time.strftime(u"%d.%m.%Y at %H:%M:%S", start)
                            + u"\n"
                            u"Duration: " + dur
                        )

                        self.try_mail(subject, body)  # send email without attachment

                self._sleep(1)

            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                err_string = "".join(
                    traceback.format_exception(exc_type, exc_value, exc_traceback)
                )
                self.add_status(u"Email plugin encountered an error: " + err_string)
                self._sleep(60)


checker = EmailSender()


################################################################################
# Helper functions:                                                            #
################################################################################


def get_email_options():
    """Returns the defaults data form file."""
    dataeml = {
        u"emlserver": u"",
        u"emlport": u"",
        u"emlusr": u"",
        u"emlpwd": u"",
        u"emladr": u"",
        u"emlsender": u"off",
        u"emllog": u"off",
        u"emlrain": u"off",
        u"emlrun": u"off",
        u"status": checker.status,
    }
    try:
        with open(u"./data/email_adj.json", u"r") as f:  # Read the settings from file
            file_data = json.load(f)
        for key, value in file_data.iteritems():
            if key in dataeml:
                dataeml[key] = value
    except Exception:
        pass

    return dataeml


def email(subject, text, attach=None):
    """Send email with with attachments"""
    dataeml = get_email_options()
    if dataeml[u"emlusr"] != "" and dataeml[u"emlpwd"] != "" and dataeml[u"emladr"] != "" and dataeml[
        u"emlserver"] != "" and dataeml[u"emlport"] != "":
        mail_user = dataeml[u"emlusr"]  # SMTP username
        mail_from = mail_user if dataeml[u"emlsender"] != u"off" else gv.sd[u"name"]  # From Name
        mail_pwd = dataeml[u"emlpwd"]  # SMTP password
        mail_server = dataeml[u"emlserver"]  # SMTP server address
        mail_port = dataeml[u"emlport"]  # SMTP port
        # --------------
        msg = MIMEMultipart()
        msg[u"From"] = mail_from
        msg[u"To"] = dataeml[u"emladr"]
        msg[u"Subject"] = subject
        msg.attach(MIMEText(text))
        if attach is not None:  # If insert attachments
            part = MIMEBase(u"application", u"octet-stream")
            part.set_payload(open(attach, u"rb").read())
            encoders.encode_base64(part)
            part.add_header(
                u"Content-Disposition",
                u'attachment; filename="%s"' % os.path.basename(attach),
            )
            msg.attach(part)
        mailServer = smtplib.SMTP(mail_server, int(mail_port))
        mailServer.ehlo()
        mailServer.starttls()
        mailServer.ehlo()
        mailServer.login(mail_user, mail_pwd)
        mailServer.sendmail(
            mail_from, dataeml[u"emladr"], msg.as_string()
        )  # name + e-mail address in the From: field
        mailServer.quit()
    else:
        raise Exception(u"E-mail plug-in is not properly configured!")


################################################################################
# Web pages:                                                                   #
################################################################################


class settings(ProtectedPage):
    """Load an html page for entering email adjustments."""

    def GET(self):
        return template_render.email_adj(get_email_options())


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format."""

    def GET(self):
        web.header(u"Access-Control-Allow-Origin", "*")
        web.header(u"Content-Type", u"application/json")
        return json.dumps(get_email_options())


class update(ProtectedPage):
    """Save user input to email_adj.json file."""

    def GET(self):
        qdict = web.input()
        if u"emllog" not in qdict:
            qdict[u"emllog"] = u"off"
        if u"emlrain" not in qdict:
            qdict[u"emlrain"] = u"off"
        if u"emlrun" not in qdict:
            qdict[u"emlrun"] = u"off"
        with open(u"./data/email_adj.json", u"w") as f:  # write the settings to file
            json.dump(qdict, f)
        raise web.seeother(u"/emla")


class send_test_email(ProtectedPage):
    """Send test, dummy, email"""

    def GET(self):
        checker.try_mail("Test e-mail from SIP", "This is a test email from SIP. You can ignore it.")
        raise web.seeother(u"/emla")
