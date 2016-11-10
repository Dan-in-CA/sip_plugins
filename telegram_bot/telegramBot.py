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
import traceback
import sys





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

    def _botCmd_start(self, bot, update):
        b = self.bot.bot
        b.sendMessage(update.message.chat_id, text='Hi! Im a  ')

    def _botCmd_subscribe(self, bot, update):
        b = self.bot.bot
        if self.data['botAccessKey'] in update.message.text:
            chats = self.currentChats
            chats.add(update.message.chat_id)
            self.currentChats = chats

            b.sendMessage(update.message.chat_id, text='Hi! you are now added to the SIP announcement ')
        else:
            b.sendMessage(update.message.chat_id, text='Please enter the correct AccessKey ')


    def _initBot(self):
        updater = Updater(self.data['botToken'])
        self._currentChats = set(self.data['currentChats'])
        dp = updater.dispatcher
        dp.add_error_handler(self._botError)
        dp.add_handler(CommandHandler("start", self._botCmd_start))
        dp.add_handler(CommandHandler("subscribe", self._botCmd_subscribe))
        dp.add_handler(MessageHandler(Filters.text, self._echo))
        return updater

    def _announce(self, text):
        for id in self.currentChats:
            try:
                self.bot.bot.sendMessage(id, text=text)
            except:
                pass

    def _echo(self, bot, update):
        bot.sendMessage(update.message.chat_id, text=update.message.text)

    def run(self):
        time.sleep(randint(3, 10))  # Sleep some time to prevent printing before startup information
        print "telegramBot plugin is active"
        try:
            if self.data['use_telegram'] and self.data['botToken'] != '':
                self.bot = self._initBot()
                # Lets Start the bot
                self.bot.start_polling()
               # self.bot.idle()
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            err_string = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            print ('telegramBot plugin encountered error: ' + err_string)

    def notifyZoneChange(self,name,  **kw):
        txt = 'There has been a Zone Change: ' +  str(gv.srvals)
        # print 'notify: ', txt
        self._announce(txt)

    def notifyProgram_toggled(self, name,  **kw):
        txt = 'A program has been toggled: ' +  str(gv.pd)
        # print 'notify: ', txt
        self._announce(txt)



def get_telegramBot_options():
    data = {
        'botToken': '',
        'botAccessKey' : 'SIP',
        'use_telegram': False,
        'zoneChange': False,
        'programToggled': True,
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
            print data
            json.dump(data, f) # save to file
        print "save done!"
        return


def run_bot():
    bot = SipBot(gv)
    # Connect Signals
    print "Connecting Signals"
    program_toggled = signal('program_toggled')
    program_toggled.connect(bot.notifyProgram_toggled)

    zoneChange = signal('zone_change')
    zoneChange.connect(bot.notifyZoneChange)



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
        print qdict
        for k in qdict.keys():
            if k in ('use_telegram', 'zoneChange', 'programToggled'):
                v = qdict[k]
                if  v == "on":
                    qdict[k] = True
                else:
                    qdict[k] = False
        set_telegramBot_options(qdict)
        raise web.seeother('/')  # Return user to home page.

#  Run when plugin is loaded
run_bot()
