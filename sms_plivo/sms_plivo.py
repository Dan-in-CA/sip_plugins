# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Python 2/3 compatibility imports
from __future__ import print_function

# *********************************************************
#
#  Everything at the top of this program down to the plivo specific
#  code can be used as a template for other plugins developed
#  for other sms and voice providers
#
# *********************************************************

# standard library imports
import json  # for working with data file

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  # Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security

SMS_ENABLED = True  # Toggles SMS option display to user
VOICE_ENABLED = True  # Toggles voice option display to user
BROADCAST_NAME = u"Plivo"  # App name broadcast to other plugins

sms_numbers = ""
voice_numbers = ""

# Add new URLs to access classes in this plugin.
urls.extend([
    u"/sms-plivo-sp", u"plugins.sms_plivo.settings",
    u"/sms-plivo-save", u"plugins.sms_plivo.save_settings",
    u"/sms-plivo-test", u"plugins.sms_plivo.Test"
])

# Add this plugin to the PLUGINS menu
gv.plugin_menu.append([_(u"SMS Plivo Plugin"), u"/sms-plivo-sp"])

"""
Event Triggers
"""


def advertise_presence(name, **kw):
    """
    Respond to query looking for notification plugins
    When a "notification_checkin" message is received, this plugin will advertise its ability
    to accept sms and voice notifications by responding with a "notification presence" message.
    """
    notification_presence = signal("notification_presence")

    # Notify that plivo_sms is listening for sms messages
    if SMS_ENABLED:
        notification_presence.send(BROADCAST_NAME, txt=u"sms")

    # Notify that plivo_sms is listening for voice messages
    if VOICE_ENABLED:
        notification_presence.send(BROADCAST_NAME, txt=u"voice")


notification_checkin = signal(u"notification_checkin")
notification_checkin.connect(advertise_presence)


def send_sms(name, **kw):
    """
    Send message to SMS provider
    """
    print(u"SMS message request received from {}: {}".format(name, kw[u"msg"]))
    if "dest" in kw.keys():
        phone = kw["dest"]
    else:
        phone = save_settings.voice_numbers
    response = sms.send_message(phone, kw[u"msg"])
    return response


sms_alert = signal(u"sms_alert")
sms_alert.connect(send_sms)


def send_voice(name, **kw):
    """
    Send message to voice provider
    """
    print(u"Voice message request received from {}: {}".format(name, kw[u"msg"]))
    if "dest" in kw.keys():
        phone = kw["dest"]
    else:
        phone = save_settings.voice_numbers
    response = voice.send_message(phone, kw[u"msg"])
    print("voice response", response)
    return response


voice_alert = signal(u"voice_alert")
voice_alert.connect(send_voice)

"""
Web page classes
"""


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open(
                    u"./data/sms_plivo.json", u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = {}  # Default settings. can be list, dictionary, etc.

        runtime_values = {
            'sms-enabled': SMS_ENABLED,
            'voice-enabled': VOICE_ENABLED,
        }

        return template_render.sms_plivo(settings, runtime_values)  # open settings page


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """
    sms_numbers = ""
    voice_numbers = ""

    def GET(self):
        qdict = (
            web.input()
        )  # Dictionary of values returned as query string from settings page.

        # Save the phone numbers to local variables and reformat for plivo
        if "text-sms" in qdict.keys():
            save_settings.sms_numbers = qdict["text-sms"].replace(" ", "")
            qdict["text-sms"] = save_settings.sms_numbers
        if "text-voice" in qdict.keys():
            save_settings.voice_numbers = qdict["text-voice"].replace(" ", "")
            qdict["text-voice"] = save_settings.voice_numbers
        with open(u"./data/sms_plivo.json", u"w") as f:  # Edit: change name of json file
            json.dump(qdict, f)  # save to file
        raise web.seeother(u"/")  # Return user to home page.


class Test(ProtectedPage):

    # Receives messages to send test SMS or Voice messages
    def POST(self):
        qdict = (
            json.loads(str(web.data(), "utf-8"))
        )  # Dictionary of values returned as query string .
        # print(str(web.data().decode('utf8').replace("'", '"')))
        # qdict = json.loads(web.data().decode('utf8').replace("'", '"'))
        if "type" in qdict.keys():
            if qdict["type"] == "SMS":
                response = (
                    send_sms(BROADCAST_NAME,
                             msg="This is a {} SMS test message from {}.".format(BROADCAST_NAME, gv.sd["name"]),
                             dest=qdict["dest"])
                )
            if qdict["type"] == "Voice":
                response = (
                    send_voice(BROADCAST_NAME,
                             msg="This is a {} voice test message from {}.".format(BROADCAST_NAME, gv.sd["name"]),
                             dest=qdict["dest"])
                )
            web.header(u"Content-Type", u"text/csv")
            return response

# load the saved settings
try:
    with open(
            u"./data/sms_plivo.json", u"r"
    ) as f:  # Read settings from json file if it exists
        loaded_settings = json.load(f)
except IOError:  # If file does not exist return empty value
    loaded_settings = {}  # Default settings. can be list, dictionary, etc.

if "text-sms" in loaded_settings.keys():
    save_settings.sms_numbers = loaded_settings["text-sms"]
if "text-voice" in loaded_settings.keys():
    save_settings.voice_numbers = loaded_settings["text-voice"]

# *********************************************************
#
#  Everything from here down is Plivo Specific
#  Plivo keys are stored in a configuration file and not exposed via settings.
#  This is by design to reduce the risk of the info being disclosed to the public internet
#
# *********************************************************

# Imports required for Plivo
import requests
from os.path import exists

PLIVO_VERSION = "v1"
KEY_DATA = u"./data/plivo_keys.json"

class PlivoKeys(object):
    # Loads the authentication keys from the KEY_DATA file
    def __init__(self, _keyfile):
        self.key_file = _keyfile
        self._auth_keys = {}
        self.load_keyfile()

    def load_keyfile(self):
        # Load the keys from the keyfile
        if exists(self.key_file):
            with open(self.key_file, u"r") as f:
                self._auth_keys = json.load(f)
        else:
            self._auth_keys = {}

    def auth_id(self):
        if u"auth-id" in self._auth_keys.keys():
            return self._auth_keys["auth-id"]
        else:
            return ""

    def auth_token(self):
        if u"auth-token" in self._auth_keys.keys():
            return self._auth_keys["auth-token"]
        else:
            return ""

    def auth_phlo(self):
        if u"auth-phlo" in self._auth_keys.keys():
            return self._auth_keys["auth-phlo"]
        else:
            return ""

    def src(self):
        if u"src" in self._auth_keys.keys():
            return self._auth_keys["src"]
        else:
            return ""


class SMSAPI(object):
    def __init__(self, plivokeys, url='https://api.plivo.com', version="v1"):
        self.version = version
        self.url = url.rstrip('/') + '/' + self.version
        self.auth_id = plivokeys.auth_id()
        self.auth_token = plivokeys.auth_token()
        self.src = plivokeys.src()
        self._api = self.url + '/Account/%s' % self.auth_id
        self.headers = {'User-Agent': 'PythonPlivo'}

    def _request(self, path, data={}):
        path = path.rstrip('/') + '/'
        headers = {'content-type': 'application/json'}
        headers.update(self.headers)
        r = requests.post(self._api + path, headers=headers,
                          auth=(self.auth_id, self.auth_token),
                          data=json.dumps(data))
        content = r.content
        if content:
            try:
                response = json.loads(content.decode("utf-8"))
            except ValueError:
                response = content
        else:
            response = content

        return response

    def send_message(self, phone, text_message):
        try:
            phone = phone.replace(",", "<")
            params = {
                'src': self.src,  # Sender's phone number with country code
                'dst': phone,  # Receiver's phone Number with country code
                'text': text_message,  # Your SMS Text Message - English
                'method': 'POST'  # The method used to call the url
            }
            response = self._request('/Message/', data=params)
            return response

        except Exception as inst:
            print('Unable to send SMS message')
            print(type(inst))  # the exception instance
            print(inst.args)  # arguments stored in .args
            print(inst)
            return str(inst.args)


class VoiceAPI(object):

    def __init__(self, plivokeys, url='https://phlorunner.plivo.com/v1', version="vi"):
        self.version = version
        self.url = url.rstrip('/') + '/'
        self.auth_id = plivokeys.auth_id()
        self.auth_token = plivokeys.auth_token()
        self.auth_phlo = plivokeys.auth_phlo()
        self.src = plivokeys.src()
        self._api = 'account/%s/phlo/%s' % (self.auth_id, self.auth_phlo)
        self.headers = {'User-Agent': 'PythonPlivo'}

    def _request(self, data={}):
        headers = {'content-type': 'application/json'}
        headers.update(self.headers)
        r = requests.post(self.url + self._api, headers=headers,
                          auth=(self.auth_id, self.auth_token),
                          data=json.dumps(data))

        content = r.content
        if content:
            try:
                response = json.loads(content.decode("utf-8"))
            except ValueError:
                response = content
        else:
            response = content
        return response

    def send_message(self, phone, voice_message):

        try:
            phone = phone.replace(",", "<")
            params = {
                'from': self.src,  # Sender's phone number with country code
                'to': phone,  # Receiver's phone Number with country code
                'items': voice_message,  # Your SMS Text Message - English
            }
            response = self._request(data=params)
            return response

        except Exception as inst:
            print('Unable to send voice message')
            print(type(inst))  # the exception instance
            print(inst.args)  # arguments stored in .args
            print(inst)
            return str(inst.args)


plivo_keys = PlivoKeys(KEY_DATA)
sms = SMSAPI(plivo_keys)
voice = VoiceAPI(plivo_keys)
