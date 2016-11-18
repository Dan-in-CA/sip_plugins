# !/usr/bin/env python

import web  # web.py framework
import gv  # Get access to sip's settings
from urls import urls  # Get access to sip's URLs
from sip import template_render  #  Needed for working with web.py templates
from webpages import ProtectedPage  # Needed for security
import json  # for working with data file
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

from threading import Thread
from random import randint
import time
from blinker import signal
import gv
import traceback
import sys
from helpers import get_ip, uptime, reboot, poweroff, timestr, jsave, restart, clear_mm, stop_stations, read_log



json_data = './data/telegramBot.json'

# Add new URLs to access classes in this plugin.
urls.extend([
    '/telegramBot-sp', 'plugins.telegramBot.settings',
    '/telegramBot-save', 'plugins.telegramBot.save_settings'
    ])

gv.plugin_menu.append(['telegram Bot', '/telegramBot-sp'])


class SipBot(Thread):
    def __init__(self, globals):
        Thread.__init__(self)
        self.daemon = True
        self.gv = globals
        self.bot = None
        self._currentChats = set([])
        self.start()
        self.status = ''

    @property
    def currentChats(self):
        return self._currentChats

    @currentChats.setter
    def currentChats(self, chatSet):
        d = self.data
        d['currentChats'] = list(chatSet)
        self._currentChats = chatSet
        self.data = d

    @property
    def data(self):
        return get_telegramBot_options()

    @data.setter
    def data(self, new_data):
        set_telegramBot_options(new_data)
        return


    def _botError(self, bot, update, error):
        print 'Update "%s" caused error "%s"' % (update, error)

    def _botCmd_start_chat(self, bot, update):
        b = self.bot.bot
        b.sendMessage(update.message.chat_id, text='Hi! Im a Bot to interface with ' + gv.sd[u'name'])

    def _botCmd_subscribe(self, bot, update):
        if self.data['botAccessKey'] in update.message.text:
            chats = self.currentChats
            chats.add(update.message.chat_id)
            self.currentChats = chats
            bot.sendMessage(update.message.chat_id, text='Hi! you are now added to the *' + gv.sd[u'name'] +'* announcement ',
            parse_mode = 'Markdown' )
        else:
            bot.sendMessage(update.message.chat_id, text="I'm sorry Dave I'm afraid I can't do that, Please enter the correct AccessKey" )

    def _botCmd_info(self, bot, update):
        print "INFO!"
        chat_id = update.message.chat_id
        if chat_id in self.currentChats:
            txt = "<b>Info:</b>"
            if gv.sd['en'] == 1:
                txt += "\n{} System <b>ON</b>".format(gv.sd[u'name'])
            else:
                txt += "\n{} System <b>OFF</b>".format(gv.sd[u'name'])
            if gv.sd['mm'] == 1:
                txt += " - Manual Mode"
            else:
                txt += " - Auto Mode"
            txt += get_running_programs_pon()
            txt += '\n--------------------------------------------'

            if gv.sd['lg']:
                # Log is enabled, lets get the data from there
                log = read_log()
                if len(log) > 0:
                    txt += '\nLast {} Programs:'.format(str(len(log[:5])))
                    for l in log[:5]:
                        l['station'] = gv.snames[l['station']]
                        txt += "\n  <b>{station}</b> - Program: <i>{program}</i>".format(**l)
                        txt += "\n      {date} {start} Duration: <i>{duration}</i>  ".format(**l)
                else:
                    txt += '\nLast program <b>none</b>'
            else:
                if gv.lrun[1] == 98:
                    pgr = 'Run-once'
                elif gv.lrun[1] == 99:
                    pgr = 'Manual'
                else:
                    pgr = str(gv.lrun[1])
                start = time.gmtime(gv.now - gv.lrun[2])
                if pgr != '0':
                    txt += ('\nLast program: <b>' + pgr + '</b>,station: <b>' + str(gv.lrun[0]) + '</b>,duration: <b>' + timestr(
                        gv.lrun[2]) + '</b>,start: <b>' + time.strftime("%H:%M:%S - %Y-%m-%d", start) + '</b>')
                else:
                    txt += '\nLast program <b>none</b>'
        else:
            txt = "I'm sorry Dave I'm afraid I can't do that."
        bot.sendMessage(chat_id, text=txt,  parse_mode='HTML')

    def _botCmd_help(self, bot, update):
        chat_id = update.message.chat_id
        if chat_id in self.currentChats:
            txt = """Help:
            */subscribe*: Subscribe to the Announcement list, need an access Key
            */{}*: Info Command
            */{}*: Enable Command
            */{}*: Disable Command
            */{}*: Run Once Command, use program number as argument""".format(self.data['info_cmd'],
                                                                           self.data['enable_cmd'],
                                                                           self.data['disable_cmd'],
                                                                           self.data['runOnce_cmd'])
        else:
            txt = "I'm sorry Dave I'm afraid I can't do that."

        bot.sendMessage(chat_id, text=txt,  parse_mode='Markdown')

    def _botCmd_enable(self, bot, update):
        chat_id = update.message.chat_id
        if chat_id in self.currentChats:
            txt = "{} System <b>ON</b>".format(gv.sd[u'name'])
            gv.sd['en'] = 1  # enable system OSPi
            gv.sd['mm'] = 0 # Disable Manual Mode
            jsave(gv.sd, 'sd')  # save en = 1
        else:
            txt = "I'm sorry Dave I'm afraid I can't do that."
        bot.sendMessage(chat_id, text=txt, parse_mode='HTML')

    def _botCmd_disable(self, bot, update):
        chat_id = update.message.chat_id
        if chat_id in self.currentChats:
            txt = "{} System <b>OFF</b>".format(gv.sd[u'name'])
            gv.sd['en'] = 0  # disable system SIP
            jsave(gv.sd, 'sd')  # save en = 0
            stop_stations()
        else:
            txt = "I'm sorry Dave I'm afraid I can't do that."

        bot.sendMessage(chat_id, text=txt, parse_mode='HTML')

    def _botCmd_runOnce(self, bot, update, args):
        chat_id = update.message.chat_id
        if chat_id in self.currentChats:
            txt = "{} RunOnce: program {} Not yet Implemented!!!!!".format(gv.sd[u'name'], args)
#               gv.sd['en'] = 0  # disable system OSPi
#               jsave(gv.sd, 'sd')  # save en = 0
        else:
            txt = "I'm sorry Dave I'm afraid I can't do that."

        bot.sendMessage(chat_id, text=txt)


    def _initBot(self):
        updater = Updater(self.data['botToken'])
        self._currentChats = set(self.data['currentChats'])
        dp = updater.dispatcher
        dp.add_error_handler(self._botError)
        dp.add_handler(CommandHandler("start", self._botCmd_start_chat))
        dp.add_handler(CommandHandler("subscribe", self._botCmd_subscribe))
        dp.add_handler(CommandHandler("help", self._botCmd_help))
        dp.add_handler(CommandHandler(self.data['info_cmd'], self._botCmd_info))
        dp.add_handler(CommandHandler(self.data['enable_cmd'], self._botCmd_enable))
        dp.add_handler(CommandHandler(self.data['disable_cmd'], self._botCmd_disable))
        dp.add_handler(CommandHandler(self.data['runOnce_cmd'], self._botCmd_runOnce, pass_args=True))
        dp.add_handler(MessageHandler(Filters.text, self._echo))
        return updater

    def _announce(self, text, parse_mode=None ):
        bot= self.bot.bot
        for chat_id in self.currentChats:
            if parse_mode is None:
                bot.sendMessage(chat_id, text=text)
            else:
                bot.sendMessage(chat_id, text=text, parse_mode=parse_mode)

    def _echo(self, bot, update):
        bot.sendMessage(update.message.chat_id, text=update.message.text)

    def run(self):
        try:
            if  self.data['botToken'] != '':
                time.sleep(randint(3, 10))  # Sleep some time to prevent printing before startup information
                print "telegramBot plugin is active"
                self.bot = self._initBot()
                self._announce('Bot on *' + gv.sd[u'name'] + '* has just started!', parse_mode='Markdown')
                # Lets Start the bot
                self.bot.start_polling()

        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            err_string = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            print ('telegramBot plugin encountered error: ' + err_string)

    def notifyZoneChange(self,name,  **kw):
        if self.data['zoneChange'] == 'on':
            txt = 'There has been a Zone Change: ' + str(gv.srvals)
            self._announce(txt)

    def notifyStationScheduled(self, name,  **kw):
        if self.data['stationScheduled'] == 'on':
            time.sleep(2) # Sleep a couple of seconds to let SIP finish setting the gv variables
            txt = 'New Stations had been scheduled'
            txt += get_running_programs_rs()
            self._announce(txt, parse_mode='HTML')

    def notifyAlarmToggled(self, name,  **kw):
        txt = '''<b>ALARM!!!</b> from <i>{}</i>:
<pre>{}</pre>'''.format(name, kw["txt"])
        self._announce(txt, parse_mode='HTML')

def get_running_programs_rs(): # From the running schedule info
    txt = ''
    for i in range(len(gv.rs)):
        d = gv.rs[i]
        sname = gv.snames[i]
        start_time = time.strftime("%H:%M:%S", time.gmtime(d[0]))
#        stop_time = time.strftime("%H:%M:%S", time.gmtime(d[1]))
        program = str(d[3])
        if d[2] == 0:
            duration = "forever"
        else:
            min = int(round(d[2] / 60))
            sec = int(round(d[2] - 60 * min))
            if sec < 10:
                sec = 0
            duration = '{}:{}'.format(str(min).zfill(2), str(sec).zfill(2))

        if program != '0': # We have a running Station!
            txt += '\n<b>{}</b> - '.format(sname)
            if program == '99':
                # Run Once is running!
                txt += "<i>Run Once </i>"
            elif program == '98':
                # Manual Mode is running
                txt += "<i>Manual Program </i>"
            else:
                # a Program is Running
                txt += " Program: <i>{}</i>".format(program)

            if program != 98:
                txt += '\n  Start: <i>{}</i>'.format(start_time)
                txt += '\n  Duration: <i>{}</i>'.format(duration)
    return txt


def get_running_programs_pon(): # From the GUI info
    txt = ''
    if gv.pon == 99:
        # Run Once is running!
        txt += "\n<b>Run Once </b>"
    elif gv.pon == 98:
        # Manual Mode is running
        txt += "\n<b>Manual Program </b>"
    elif gv.pon is not None:
        # a Program is Running
        txt += "\nRunning Program: <b>{}</b>".format(str(gv.pon))

    if gv.pon is not None:
        for i in range(len(gv.ps)):
            p, d = gv.ps[i]
            if p != 0:
                sname = gv.snames[i]
                if d == 0:
                    duration = "forever"
                else:
                    min = int(round(d / 60))
                    sec = int(round(d - 60 * min))
                    if sec < 10:
                        sec = 0
                    duration = '{}:{}'.format(str(min).zfill(2), str(sec).zfill(2))
                txt += '\n  <b>{}</b> - Duration: <b>{}</b>'.format(sname, duration)
    return txt

def get_telegramBot_options():
    data = {
        'botToken': '',
        'botAccessKey' : 'SIP',
        'zoneChange': 'off',
        'stationScheduled': 'off',
        'info_cmd': 'info',
        'disable_cmd': 'disable',
        'enable_cmd': 'enable',
        'runOnce_cmd': 'runOnce',
        'currentChats' : []
        }
    try:
        with open(json_data, 'r') as f:  # Read the settings from file
            file_data = json.load(f)
        for key, value in file_data.iteritems():
            if key in data:
                data[key] = value
    except Exception:
        pass
    return data


def set_telegramBot_options(new_data):
        data = get_telegramBot_options()
        for k in new_data.keys():
            data[k] =  new_data[k]
        with open('./data/telegramBot.json', 'w') as f:
            json.dump(data, f) # save to file
        return

def run_bot():
    bot = SipBot(gv)
    # wait to the bot to start
    time.sleep(10)
    # Connect Signals
    program_started = signal('stations_scheduled')
    program_started.connect(bot.notifyStationScheduled)

    zoneChange = signal('zone_change')
    zoneChange.connect(bot.notifyZoneChange)

    alarm = signal('alarm_toggled')
    alarm.connect(bot.notifyAlarmToggled)



class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        return template_render.telegramBot(get_telegramBot_options())  # open settings page

class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):
        qdict = web.input()
        if 'zoneChange' not in qdict:
            qdict['zoneChange'] = 'off'
        if 'programToggled' not in qdict:
            qdict['programToggled'] = 'off'


        set_telegramBot_options(qdict)
        raise web.seeother('/')  # Return user to home page.

#  Run when plugin is loaded
run_bot()
