# !/usr/bin/env python
# -*- coding: utf-8 -*-

# Python 2/3 compatibility imports
from __future__ import print_function


# standard library imports
# import json  # for working with data file

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  # Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security

# *****
# Twilio Specific imports
from base64 import b64encode
import urllib.request, urllib.parse
import datetime
import json

# *****

SMS_ENABLED = True  # Toggles SMS option display to user
VOICE_ENABLED = True  # Toggles voice option display to user
BROADCAST_NAME = u"Twilio"  # App name broadcast to other plugins
SETTINGS_FILENAME = u"./data/sms_twilio.json"
TWILIO_FLOW_NAME = "SIP 1"
PAUSE_NOTIFICATIONS = False  # Stops requests from going to Twilio. Used for testing
voice_obj = object
sms_obj = object

# Add new URLs to access classes in this plugin.
urls.extend([
    u"/sms-twilio-sp", u"plugins.sms_twilio.settings",
    u"/sms-twilio-save", u"plugins.sms_twilio.save_settings",
    u"/sms-twilio-test", u"plugins.sms_twilio.Test"
])

# Add this plugin to the PLUGINS menu
gv.plugin_menu.append([_(u"Twilio"), u"/sms-twilio-sp"])

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

    # Notify that the plugin is listening for sms messages
    if SMS_ENABLED:
        notification_presence.send(BROADCAST_NAME, txt=u"sms")

    # Notify that plugin is listening for voice messages
    if VOICE_ENABLED:
        notification_presence.send(BROADCAST_NAME, txt=u"voice")


notification_checkin = signal(u"notification_checkin")
notification_checkin.connect(advertise_presence)


def load_settings():
    try:
        with open(
                SETTINGS_FILENAME, u"r"
        ) as f:  # Read settings from json file if it exists
            saved_settings = json.load(f)
    except IOError:  # If file does not exist return empty value
        saved_settings = {}  # Default settings. can be list, dictionary, etc.
    return saved_settings


def send_sms(name, **kwargs):
    """
    Send message to SMS provider
    """
    print(u"SMS message request received from {}: {}".format(name, kwargs[u"msg"]))
    if PAUSE_NOTIFICATIONS or sms_obj.pause_messaging:
        print(u"SMS message not sent as messages have been paused")
        return u"SMS message not sent as messages have been paused"
    if "dest" in kwargs.keys():
        phone = kwargs["dest"]
    else:
        phone = sms_obj.outgoing_number
    response = sms_obj.send_message(phone, kwargs["msg"], **kwargs)
    return response


sms_alert = signal(u"sms_alert")
sms_alert.connect(send_sms)


def send_voice(name, **kwargs):
    """
    Send message to voice provider
    """
    print(u"Voice message request received from {}: {}".format(name, kwargs[u"msg"]))
    if PAUSE_NOTIFICATIONS or voice_obj.pause_messaging:
        print(u"Voice message not sent as messages have been paused")
        return u"Voice message not sent as messages have been paused"
    if "dest" in kwargs.keys():
        phone = kwargs["dest"]
    else:
        phone = voice_obj.outgoing_number
    response = voice_obj.send_message(phone, kwargs[u"msg"], **kwargs)
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

    def __init__(self):
        web.header('Access-Control-Allow-Origin', '*')

    def GET(self):
        acct = ""
        auth = ""
        twilio_num = ""
        try:
            with open(
                    SETTINGS_FILENAME, u"r"
            ) as f:  # Read settings from json file if it exists
                settings = json.load(f)
                if "text-auth-token" in settings:
                    auth = settings["text-auth-token"]
                    settings["text-auth-token"] = "PLACEHOLDER"
                if "text-account-id" in settings:
                    acct = settings["text-account-id"]
                if "text-twilio-number" in settings:
                    twilio_num = settings["text-twilio-number"]

                success, _ = Voice.validate_credentials(acct, auth)

        except IOError:  # If file does not exist return empty value
            settings = {}  # Default settings. can be list, dictionary, etc.
            success = False

        runtime_values = {
            'sms-enabled': SMS_ENABLED,
            'voice-enabled': VOICE_ENABLED,
            'auth-valid': success
        }

        return template_render.sms_twilio(settings, runtime_values)  # open settings page


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

        saved_settings = load_settings()
        # Save the phone numbers to local variables and reformat for plivo
        print("saving settings", qdict)
        if "text-sms" in qdict.keys():
            self.sms_numbers = qdict["text-sms"].replace(" ", "")
            qdict["text-sms"] = self.sms_numbers
        if "text-voice" in qdict.keys():
            self.voice_numbers = qdict["text-voice"].replace(" ", "")
            qdict["text-voice"] = save_settings.voice_numbers
        if "text-auth-token" in qdict.keys() and (not qdict["text-auth-token"].strip() or qdict["text-auth-token"] ==
                                                  "PLACEHOLDER") and "text-auth-token" in saved_settings.keys():
            qdict["text-auth-token"] = saved_settings["text-auth-token"]
        if "text-auth-token" in qdict.keys() and "text-account-id" in qdict.keys() and "text-twilio-number" in qdict.keys():
            _, qdict["text-flow-id"], _ = voice_obj.number_flow_sids(qdict["text-twilio-number"],
                                                                                 qdict["text-account-id"],
                                                                                 qdict["text-auth-token"])
        with open(SETTINGS_FILENAME, u"w") as f:
            json.dump(qdict, f)  # save to file
        voice_obj.load_settings(qdict)
        sms_obj.load_settings(qdict)
        raise web.seeother(u"sms-twilio-sp")  # Return user to home page.


class Test(ProtectedPage):

    # Receives messages to send test SMS or Voice messages
    def POST(self):
        qdict = (
            json.loads(str(web.data(), "utf-8"))
        )
        response = {}
        response["textbox"] = "1"
        if "type" in qdict.keys():
            if qdict["type"] == "SMS":
                auth_token = qdict["auth"]
                if auth_token == "PLACEHOLDER":
                    # we need to use the stored auth code
                    settings = load_settings()
                    if "text-auth-token" in settings:
                        auth_token = settings["text-auth-token"]
                response["msg"] = (
                    send_sms(BROADCAST_NAME,
                             msg="This is a {} SMS test message from {}.  Congratulations, you have successfully "
                                 "configured the Twilio plugin for SMS messaging".format(BROADCAST_NAME, gv.sd["name"]),
                             dest=qdict["dest"],
                             account_sid=qdict["acct"],
                             auth_token=auth_token,
                             twilio_number=qdict["twilio-num"],
                             override=True
                             )
                )
                response["type"] = "SMS"
            elif qdict["type"] == "Voice":
                auth_token = qdict["auth"]
                if auth_token == "PLACEHOLDER":
                    # we need to use the stored auth code
                    settings = load_settings()
                    if "text-auth-token" in settings:
                        auth_token = settings["text-auth-token"]
                response["msg"] = (send_voice(
                    BROADCAST_NAME,
                    msg="This is a {} voice test message from {}. Congratulations, you have successfully "
                        "configured the Twilio plugin for voice messaging".format(BROADCAST_NAME,
                                                                           gv.sd["name"]),
                    dest=qdict["dest"],
                    account_sid=qdict["acct"],
                    auth_token=auth_token,
                    twilio_number=qdict["twilio-num"],
                    override=True)
                )
                response["type"] = "Voice"

            elif qdict["type"] == "CreateFlowID":
                response["textbox"] = "2"
                account_sid = qdict["acct"]
                twilio_number = qdict["twilio-num"]
                auth_token = qdict["auth"]
                if auth_token == "PLACEHOLDER":
                    # we need to use the stored auth code
                    settings = load_settings()
                    if "text-auth-token" in settings:
                        auth_token = settings["text-auth-token"]

                response["msg"] = voice_obj.update_flow(account_sid, auth_token, twilio_number)
                response["type"] = "CreateFlowID"

            elif qdict["type"] == "ValidateCredentials":
                msg = ""
                # Load response coming in from web page
                response["textbox"] = "2"
                account_sid = qdict["acct"]
                twilio_number = qdict["twilio-num"]
                auth_token = qdict["auth"]

                if auth_token == "PLACEHOLDER":
                    # we need to use the stored auth code
                    settings = load_settings()
                    if "text-auth-token" in settings:
                        auth_token = settings["text-auth-token"]

                validate_response = voice_obj.validate_twilio_setup(account_sid, auth_token, twilio_number)
                if qdict["voice"]:
                    validate_str = validate_response["final_msg_voice"]
                elif qdict["sms"]:
                    validate_str = validate_response["final_msg_sms"]
                else:
                    validate_str = ""

                response["type"] = "ValidateCredentials"

                if validate_str:
                    response["msg"] = validate_str
                    response["auth_valid"] = validate_response["auth_valid"]
                    response["twilio_number_valid"] = validate_response["twilio_number_valid"]

            else:
                response["msg"] = ""
        else:
            response["msg"] = "There is an unidentified problem validating credentials"
            response["auth_valid"] = False
            response["twilio_number_valid"] = False

        web.header(u"Content-Type", u"text/csv")
        return json.dumps(response).encode()

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
# Twilio objects
# *********************************************************
def get_headers(account_sid, auth_token):
    login_str = b64encode("{}:{}".format(account_sid, auth_token).encode("utf-8")).decode("ascii")
    headers = {
        'Authorization': 'Basic %s' % login_str,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    return headers


class SMS(object):
    def __init__(self, passed_settings):
        # Get settings
        self.auth_token = ""
        self.account_sid = ""
        self.twilio_number = ""
        self.headers = ""
        self.outgoing_number = ""
        self.pause_messaging = False
        self.load_settings(passed_settings)

    def load_settings(self, passed_settings):
        if "text-auth-token" in passed_settings.keys():
            self.auth_token = passed_settings["text-auth-token"]
        else:
            self.auth_token = ""
        if "text-account-id" in passed_settings.keys():
            self.account_sid = passed_settings["text-account-id"]
        else:
            self.account_sid = ""
        if "text-twilio-number" in passed_settings.keys():
            self.twilio_number = passed_settings["text-twilio-number"]
        else:
            self.twilio_number = ""
        if "text-sms-phone" in passed_settings.keys():
            self.outgoing_number = passed_settings["text-sms-phone"]
        else:
            self.outgoing_number = ""
        if "pause-messaging" in passed_settings.keys():
            self.pause_messaging = passed_settings["pause-messaging"]
        else:
            self.pause_messaging = False


        self.headers = get_headers(self.account_sid, self.auth_token)

    def send_message(self, phone, message, **kwargs):
        if "override" in kwargs and kwargs["override"]:

            if "twilio_number" in kwargs:
                twilio_number = kwargs["twilio_number"]
            else:
                twilio_number = ""

            if "auth_token" in kwargs:
                auth_token = kwargs["auth_token"]
            else:
                auth_token = ""

            if "account_sid" in kwargs:
                account_sid = kwargs["account_sid"]
            else:
                account_sid = ""

            headers = get_headers(account_sid, auth_token)

        else:
            if self.pause_messaging:
                return "SMS message not sent. Messages have been paused by Twilio plugin"
            twilio_number = self.twilio_number
            auth_token = self.auth_token
            account_sid = self.account_sid
            headers = self.headers

        data = {
            'From': twilio_number,
            'To': phone,
            'Body': message
        }

        # Data must be bytes (we're url encoding it)
        data = urllib.parse.urlencode(data).encode('ascii')
        url = 'https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json'.format(account_sid)

        # create Request object for POST
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")

        # Send the request and get the response
        try:
            response = urllib.request.urlopen(request)
            response_str = response.read().decode('utf-8')
        except Exception as e:
            response_str = "SMS send request failed: {}".format(e)
        return response_str


class Voice(object):

    def __init__(self, passed_settings):

        self.auth_token = ""
        self.account_sid = ""
        self.twilio_number = ""
        self.outgoing_number = ""
        self.flow_sid = ""
        self.pause_messaging = False
        self.headers = ""
        self.load_settings(passed_settings)

        self.flow_definition = (
            '{"states": [{"transitions": [{"event": "incomingMessage"}, {"event": "incomingCall"}, {"event": '
            '"incomingConversationMessage"}, {"event": "incomingRequest", "next": "make_the_call"}, '
            '{"event": "incomingParent"}], "type": "trigger", "name": "Trigger", "properties": {"offset": {'
            '"y": 0, "x": 0}}}, {"transitions": [{"event": "audioComplete"}], "type": "say-play", '
            '"name": "play_the_message", "properties": {"say": "{{flow.data.my_message}}", '
            '"voice": "Polly.Nicole", "language": "en-AU", "loop": 1, "offset": {"y": 480, "x": 10}}}, '
            '{"transitions": [{"event": "answered", "next": "play_the_message"}, {"event": "busy"}, '
            '{"event": "noAnswer"}, {"event": "failed"}], "type": "make-outgoing-call-v2", '
            '"name": "make_the_call", "properties": {"trim": "do-not-trim", '
            '"machine_detection_silence_timeout": "5000", "from": "{{flow.channel.address}}", '
            '"recording_status_callback": "", "record": false, "machine_detection_speech_threshold": "2400", '
            '"to": "{{contact.channel.address}}", "detect_answering_machine": false, "sip_auth_username": "", '
            '"machine_detection": "Enable", "send_digits": "", "machine_detection_timeout": "30", "timeout": '
            '60, "offset": {"y": 220, "x": -10}, "machine_detection_speech_end_threshold": "1200", '
            '"sip_auth_password": "", "recording_channels": "mono"}}], "initial_state": "Trigger", '
            '"flags": {"allow_concurrent_calls": true}, "description": "A New Flow"}')
        self.flow_definition_json = json.loads(self.flow_definition)

    def load_settings(self, passed_settings):
        if "text-auth-token" in passed_settings.keys():
            self.auth_token = passed_settings["text-auth-token"]
        else:
            self.auth_token = ""
        if "text-account-id" in passed_settings.keys():
            self.account_sid = passed_settings["text-account-id"]
        else:
            self.account_sid = ""
        if "text-twilio-number" in passed_settings.keys():
            self.twilio_number = passed_settings["text-twilio-number"]
        else:
            self.twilio_number = ""
        if "text-flow-id" in passed_settings.keys():
            self.flow_sid = passed_settings["text-flow-id"]
        else:
            self.flow_sid = ""
        if "text-voice-phone" in passed_settings.keys():
            self.outgoing_number = passed_settings["text-voice-phone"]
        else:
            self.outgoing_number = ""
        if "pause-messaging" in passed_settings.keys():
            self.pause_messaging = passed_settings["pause-messaging"]
        else:
            self.pause_messaging = False
        self.headers = get_headers(self.account_sid, self.auth_token)

    def get_sip_sid(self, account_sid, auth_token):
        # Returns the flow SID associated with TWILIO_FLOW_NAME
        # Returns an empty string if there is no FLOW with TWILIO_FLOW_NAME
        # Will return a string starting with "ERROR:" if there is a problem
        url = "https://studio.twilio.com/v2/Flows"
        voice_sid = ""
        continue_loop = True
        method_failed = False
        response_str = ""
        headers = get_headers(account_sid, auth_token)

        while continue_loop:
            req = urllib.request.Request(url, headers=headers)
            # Send the request and read the response
            try:
                with urllib.request.urlopen(req) as response:
                    data = response.read()
            except Exception as e:
                if e.reason == "Unauthorized":
                    response_str = "ERROR:Authentication Error.  Please check your Twilio account ID and auth token."
                else:
                    response_str = ('ERROR:An error occurred sending voice request. '
                                    'Please check your Twilio account ID, auth token, '
                                    'and Twilio phone number: {}').format(e)
                method_failed = True
                break
            # Decoding the response to string format
            data = data.decode('utf-8')
            json_response = json.loads(data)
            flows = json_response['flows']
            for flow in flows:
                # Iterate through the returned flows and look for the SIP flow
                if flow['friendly_name'] == TWILIO_FLOW_NAME:
                    voice_sid = flow['sid']
                    break

            url = json_response['meta']['next_page_url']
            if voice_sid or str(url) == 'None':
                continue_loop = False

        if method_failed:
            return response_str
        else:
            return voice_sid

    def is_flow_config_current(self, flow_sid, account_sid, auth_token):
        headers = get_headers(account_sid, auth_token)
        url = "https://studio.twilio.com/v2/Flows/%s" % flow_sid
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = response.read()
        twilio_data_json = json.loads(data.decode('utf-8'))
        if self.flow_definition_json == twilio_data_json['definition']:
            return True
        else:
            return False

    @staticmethod
    def number_flow_sids(twilio_number, account_sid, auth_token):
        """
        Get sids for twilio number and its attached flow
        Returns tuple: (number sid, flow sid, error message)
        """
        phone_sid = ""
        err_msg = ""
        headers = get_headers(account_sid, auth_token)
        url = ("https://api.twilio.com/2010-04-01/Accounts/%s/IncomingPhoneNumbers.json?PhoneNumber=%s"
               % (account_sid, twilio_number))
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                data = response.read()
        except Exception as e:
            err_msg = str(e)
            return "", "", err_msg

        json_response = json.loads(data.decode('utf-8'))
        if "incoming_phone_numbers" in json_response.keys() and "sid" in json_response["incoming_phone_numbers"][0]:
            phone_sid = json_response["incoming_phone_numbers"][0]['sid']
        if phone_sid == "":
            err_msg = ("Unable to find twilio phone number %s configured to twilio account" % twilio_number)
            return "", "", err_msg

        # Now check the flow attached to the number
        if (not ("voice_url" in json_response["incoming_phone_numbers"][0].keys()) or
                len(json_response["incoming_phone_numbers"][0]['voice_url']) == 0 or
                len(json_response["incoming_phone_numbers"][0]["voice_url"].split("Flows/")) == 0):
            err_msg = "No voice flow is attached to the twilio phone number."
            return phone_sid, "", err_msg

        parsed_url = json_response["incoming_phone_numbers"][0]["voice_url"].split("Flows/")
        flow_sid = parsed_url[1]
        return phone_sid, flow_sid, err_msg

    @staticmethod
    def validate_credentials(account_sid, auth_token):
        success = False
        headers = get_headers(account_sid, auth_token)
        url = "https://api.twilio.com/2010-04-01/Accounts/%s/IncomingPhoneNumbers.json" % account_sid
        req = urllib.request.Request(url, headers=headers)
        # Send the request and read the response
        try:
            with urllib.request.urlopen(req) as response:
                data = response.read()
                success = True
                response_str = data.decode('utf-8')
        except Exception as e:
            response_str = str(e)

        return success, response_str

    def validate_twilio_setup(self, account_sid, auth_token, twilio_number):
        # Create headers with the passed credentials
        response_dict = {}
        response_dict["auth_valid"] = False
        response_dict["auth_token"] = ""
        response_dict["twilio_number_valid"] = False
        response_dict["twilio_number_msg"] = ""
        response_dict["flow_attached"] = False
        response_dict["flow_attached_msg"] = ""
        response_dict["flow_current"] = False
        response_dict["final_msg_voice"] = ""
        response_dict["final_msg_sms"] = ""

        success, error_msg = self.validate_credentials(account_sid, auth_token)
        if not success:
            response_dict["auth_message"] = error_msg
            response_dict["final_msg_voice"] = ("Unable to log in to your Twilio account.  "
                                                "Please check your Twilio account ID and auth token. / %s") % error_msg
            response_dict["final_msg_sms"] = response_dict["final_msg_voice"]
            return response_dict

        # If we've gotten this far, credentials are valid.  Need to check the phone number next

        phone_sid, flow_sid, err_msg = self.number_flow_sids(twilio_number, account_sid, auth_token)

        if phone_sid == "":
            response_dict["twilio_number_msg"] = (
                "Unable to find twilio phone number %s configured in your twilio account. Error: " % twilio_number,
                err_msg)
            response_dict["final_msg_voice"] = ("Credentials validated but unable to find twilio phone number %s "
                                                "configured in your twilio account" % twilio_number)
            response_dict["final_msg_sms"] = response_dict["final_msg_voice"]
            return response_dict
        else:
            response_dict["final_msg_voice"] = "Twilio credentials and phone number validated successfully."
            response_dict["final_msg_sms"] = response_dict["final_msg_voice"]
            response_dict["twilio_number_valid"] = True

        # Now check the flow attached to the number
        if flow_sid == "":
            response_dict["flow_attached_msg"] = "No voice flow is attached to the twilio phone number."
            response_dict["final_msg_voice"] = (
                    "There is no voice flow attached to the twilio phone number %s, use the "
                    "create/ update button to create a new flow in your Twilio account and"
                    " attach it to your phone number." % twilio_number)
            return response_dict

        response_dict["flow_attached"] = True

        # Check that the attached flow matches current flow
        url = "https://studio.twilio.com/v2/Flows/%s" % flow_sid
        headers = get_headers(account_sid, auth_token)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                data = response.read()
        except Exception as e:
            response_str = str(e)
            response_dict["flow_attached_msg"] = ("An unexpected error occurred fetching the Twilio flow information."
                                                  " / " % response_str)
            response_dict["final_msg_voice"] = response_dict["flow_attached_msg"]
            return response_dict

        json_response = json.loads(data.decode('utf-8'))
        flow_name = json_response.get('friendly_name')
        if flow_name != TWILIO_FLOW_NAME:
            response_dict["flow_attached_msg"] = "Attached flow name does not match Twilio flow"
            response_dict["final_msg_voice"] = ("Credentials and phone validated, however the flow attached to your "
                                                "Twilio phone number was not created by the "
                                                "SIP Twilio plug-in and may not work properly with this app. "
                                                "Use the create/update button to create a new flow and attach it to "
                                                "your Twilio phone number. This operation will not delete the current "
                                                "flow. It will create a new flow and attach it to your Twilio phone "
                                                "number. If another application is using this phone number as well, "
                                                "the SIP flow may not work properly for that application once "
                                                "attached to your Twilio phone number.")
            return response_dict

        response_dict["flow_attached_msg"] = "Flow was created by SIP plug-in"
        response_dict["final_msg_voice"] = "Flow was created by SIP plug-in"

        # Flow is found and was created by SIP.  Check to see if it is current
        if json_response["definition"] != self.flow_definition_json:
            response_dict["flow_attached_msg"] = "Flow was created by SIP plug-in and does not match current flow"
            response_dict["final_msg_voice"] = ("Your flow was created by the SIP plug-in, but isn't current.  Use the "
                                                "create/update button to update the %s flow configuration on your Twilio "
                                                "account") % TWILIO_FLOW_NAME
            response_dict["flow_current"] = False
            return response_dict
        else:
            response_dict["flow_current"] = True

        response_dict["final_msg_voice"] = "Credentials validated, phone number validated, flow is up to date."
        return response_dict

    def update_flow(self, account_sid, auth_token, twilio_number):

        headers = get_headers(account_sid, auth_token)
        flow_created = False
        flow_updated = False
        sip_sid = self.get_sip_sid(account_sid, auth_token)

        if sip_sid.startswith("ERROR:"):

            response_str = ("An error was encountered creating/updating the voice flow: %s" %
                            sip_sid.split("ERROR:", 1)[1])
            return response_str

        elif sip_sid:
            # Flow exists.  Fetching the flow resource to compare against current configuration
            if self.is_flow_config_current(sip_sid, account_sid, auth_token):
                # Why isn't this response_str being used?
                response_str = "Flow configured on Twilio is current"
            else:
                url = 'https://studio.twilio.com/v2/Flows/%s' % sip_sid
                data = {
                    'Status': 'published',
                    'Definition': self.flow_definition,
                    'CommitMessage': 'Updated by SIP Twilio_SMS plugin'
                }
                # Data must be bytes (we're url encoding it)
                data = urllib.parse.urlencode(data).encode('ascii')

                try:
                    request = urllib.request.Request(url, data=data, headers=self.headers, method="POST")
                    response = urllib.request.urlopen(request)
                except Exception as e:
                    return "There was an error updating the Twilio flow: %s" % str(e)
                response_str = response.read().decode('utf-8')
                response_json = json.loads(response_str)
                if "status" in response_json.keys() and response_json['status'] == 'published':
                    flow_updated = True
                else:
                    response_str = "There was a problem updating the Twilio flow. " + response_str
                    return response_str

        else:
            # flow doesn't exist, need to create it and read back the flow id
            url = "https://studio.twilio.com/v2/Flows"
            data = {
                'FriendlyName': TWILIO_FLOW_NAME,
                'Status': 'published',
                'Definition': self.flow_definition,
                'CommitMessage': 'Set up by SIP Twilio_SMS plugin on %s' % datetime.datetime.now().strftime(
                    "%m/%d/%Y, %I:%M:%S %p")
            }
            data = urllib.parse.urlencode(data).encode('ascii')

            try:
                request = urllib.request.Request(url, data=data, headers=self.headers, method="POST")
                response = urllib.request.urlopen(request)
            except Exception as e:
                return "There was an error creating the new Twilio flow: %s" % str(e)
            response_str = response.read().decode('utf-8')
            response_json = json.loads(response_str)
            if "status" in response_json.keys() and response_json['status'] == 'published':
                # A flow configuration has been created.  Need to save the flow ID to our settings:
                flow_created = True
                saved_settings = load_settings()
                # Save back the flow id to plugin settings
                saved_settings['text-flow-id'] = response_json["sid"]
                sip_sid = response_json["sid"]
                with open(SETTINGS_FILENAME, u"w") as f:
                    json.dump(saved_settings, f)  # save to file
            else:
                response_str = "There was a problem updating the Twilio flow. " + response_str
                return response_str

        # We've created/updated the SIP flow, now we need to ensure it is connected to the phone number
        url = ("https://api.twilio.com/2010-04-01/Accounts/%s/IncomingPhoneNumbers.json?PhoneNumber=%s"
               % (account_sid, twilio_number))
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                response_str = response.read().decode('utf-8')
        except Exception as e:
            response_str = str(e)
            return response_str

        response_json = json.loads(response_str)
        voice_url = response_json["incoming_phone_numbers"][0]['voice_url']
        twilio_number_sid = response_json["incoming_phone_numbers"][0]['sid']
        split_string = voice_url.split("/Flows/")
        if len(split_string) > 1:
            attached_flow_sid = split_string[1]
        else:
            attached_flow_sid = None

        if attached_flow_sid:
            if attached_flow_sid == sip_sid:
                if flow_updated:
                    # Flow has been updated and is attached to the Twilio number
                    response_str = "Flow has been updated and confirmed connected to your Twilio phone number."
                    return response_str
            else:
                # A different flow is attached to the phone number.  Need to replace it.
                # First need to get the friendly name of the attached flow
                url = "https://studio.twilio.com/v2/Flows/%s" % attached_flow_sid
                try:
                    req = urllib.request.Request(url, headers=self.headers)
                    with urllib.request.urlopen(req) as response:
                        data = response.read()
                    attached_flow_friendly = json.loads(data.decode('utf-8'))["friendly_name"]
                except Exception as e:
                    return "There was a problem attaching the new Twilio flow to your Twilio phone number: %s" % str(e)
                print("Friendly name of currently attached Twilio flow:", attached_flow_friendly)

                # Now attach the SIP flow to the Twilio number
                url = ("https://api.twilio.com/2010-04-01/Accounts/%s/IncomingPhoneNumbers/%s.json"
                       % (account_sid, twilio_number_sid))
                voice_url = ("https://webhooks.twilio.com/v1/Accounts/%s/Flows/%s"
                             % (account_sid, sip_sid))
                data = {
                    'VoiceUrl': voice_url
                }

                data = urllib.parse.urlencode(data).encode('ascii')

                try:
                    request = urllib.request.Request(url, data=data, headers=self.headers, method="POST")
                    urllib.request.urlopen(request)
                except Exception as e:
                    return "There was an error attaching the Twilio flow to the Twilio phone number: %s" % str(e)

                if flow_updated:
                    response_str = ("Flow updated and attached to Twilio phone number, replacing the %s "
                                    "flow previously attached" % attached_flow_friendly)
                elif flow_created:
                    response_str = ("A new flow was created and attached to Twilio phone number, replacing the %s flow."
                                    "previously attached." % attached_flow_friendly)
                else:
                    response_str = ("SIP flow attached to Twilio phone number, replacing the %s flow "
                                    "previously attached." % attached_flow_friendly)

        return response_str

    def send_message(self, phone, message, **kwargs):
        if "override" in kwargs and kwargs["override"]:

            if "twilio_number" in kwargs:
                twilio_number = kwargs["twilio_number"]
            else:
                twilio_number = ""

            if "auth_token" in kwargs:
                auth_token = kwargs["auth_token"]
            else:
                auth_token = ""

            if "account_sid" in kwargs:
                account_sid = kwargs["account_sid"]
                phone_sid, flow_sid, _ = self.number_flow_sids(twilio_number, account_sid, auth_token)
            else:
                account_sid = ""
                flow_sid = ""

            headers = get_headers(account_sid, auth_token)
        else:
            if self.pause_messaging:
                return "Voice message not sent. Messages have been paused by Twilio plugin"
            flow_sid = self.flow_sid
            twilio_number = self.twilio_number
            headers = self.headers

        data = {
            'To': phone,
            'From': twilio_number,
            'Parameters': json.dumps(
                {'my_message': message})
        }

        data = urllib.parse.urlencode(data).encode('ascii')
        url = 'https://studio.twilio.com/v2/Flows/{}/Executions'.format(flow_sid)

        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                response_body = response.read().decode()
                response_str = str(response_body)
        except Exception as e:
            response_str = ('An error occurred sending voice request. '
                            'Please check your Twilio account ID, auth token, '
                            'and Twilio phone number: {}'.format(e))

        return response_str

# Get the currently loaded settings and instantiate the messaging objects
try:
    with open(
            SETTINGS_FILENAME, u"r"
    ) as f:
        stored_settings = json.load(f)
except IOError:
    stored_settings = {}

voice_obj = Voice(stored_settings)
sms_obj = SMS(stored_settings)
stored_settings = None
