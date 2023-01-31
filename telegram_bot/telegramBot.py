# !/usr/bin/env python

from __future__ import print_function
import web  # web.py framework
import gv  # Get access to sip's settings
from urls import urls  # Get access to sip's URLs
from sip import template_render  #  Needed for working with web.py templates
from webpages import ProtectedPage  # Needed for security
import json  # for working with data file
from telegram.ext import Updater, CommandHandler, MessageHandler, filters

from threading import Thread
from random import randint
import time
from blinker import signal
import gv
import traceback
import sys
from helpers import (
    get_ip,
    uptime,
    reboot,
    poweroff,
    timestr,
    jsave,
    restart,
    clear_mm,
    stop_stations,
    read_log,
)


json_data = u"./data/telegramBot.json"

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend(
    [
        u"/telegramBot-sp", u"plugins.telegramBot.settings",
        u"/telegramBot-save", u"plugins.telegramBot.save_settings",
    ]
)
# fmt: on

gv.plugin_menu.append([u"telegram Bot", u"/telegramBot-sp"])


class SipBot(Thread):
    def __init__(self, globals):
        Thread.__init__(self)
        self.daemon = True
        self.gv = globals
        self.bot = None
        self._currentChats = set([])
        self.start()
        self.status = ""

    @property
    def currentChats(self):
        return self._currentChats

    @currentChats.setter
    def currentChats(self, chatSet):
        d = self.data
        d[u"currentChats"] = list(chatSet)
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
        print(u'Update "%s" caused error "%s"' % (update, error))

    def _botCmd_start_chat(self, bot, update):
        b = self.bot.bot
        b.sendMessage(
            update.message.chat_id,
            text=u"Hi! Im a Bot to interface with " + gv.sd[u"name"],
        )

    async def _botCmd_subscribe(self, bot, update):
        if self.data[u"botAccessKey"] in update.message.text:
            chats = self.currentChats
            chats.add(update.message.chat_id)
            self.currentChats = chats
            await bot.sendMessage(
                update.message.chat_id,
                text=u"Hi! you are now added to the *"
                + gv.sd[u"name"]
                + u"* announcement ",
                parse_mode=u"Markdown",
            )
        else:
            await bot.sendMessage(
                update.message.chat_id,
                text=u"I'm sorry Dave I'm afraid I can't do that, Please enter the correct AccessKey",
            )

    async def _botCmd_info(self, bot, update):
        print(u"INFO!")
        chat_id = update.message.chat_id
        if chat_id in self.currentChats:
            txt = u"<b>Info:</b>"
            if gv.sd[u"en"] == 1:
                txt += u"\n{} System <b>ON</b>".format(gv.sd[u"name"])
            else:
                txt += u"\n{} System <b>OFF</b>".format(gv.sd[u"name"])
            if gv.sd[u"mm"] == 1:
                txt += u" - Manual Mode"
            else:
                txt += u" - Auto Mode"
            txt += get_running_programs_pon()
            txt += "\n--------------------------------------------"

            if gv.sd[u"lg"]:
                # Log is enabled, lets get the data from there
                log = read_log()
                if len(log) > 0:
                    txt += u"\nLast {} Programs:".format(str(len(log[:5])))
                    for l in log[:5]:
                        l[u"station"] = gv.snames[l[u"station"]]
                        txt += u"\n  <b>{station}</b> - Program: <i>{program}</i>".format(
                            **l
                        )
                        txt += u"\n      {date} {start} Duration: <i>{duration}</i>  ".format(
                            **l
                        )
                else:
                    txt += u"\nLast program <b>none</b>"
            else:
                if gv.lrun[1] == 98:
                    pgr = u"Run-once"
                elif gv.lrun[1] == 99:
                    pgr = u"Manual"
                else:
                    pgr = str(gv.lrun[1])
                start = time.gmtime(gv.now - gv.lrun[2])
                if pgr != u"0":
                    txt += (
                        u"\nLast program: <b>"
                        + pgr
                        + u"</b>,station: <b>"
                        + str(gv.lrun[0])
                        + u"</b>,duration: <b>"
                        + timestr(gv.lrun[2])
                        + u"</b>,start: <b>"
                        + time.strftime(u"%H:%M:%S - %Y-%m-%d", start)
                        + u"</b>"
                    )
                else:
                    txt += u"\nLast program <b>none</b>"
        else:
            txt = u"I'm sorry Dave I'm afraid I can't do that."
        await bot.sendMessage(chat_id, text=txt, parse_mode=u"HTML")

    async def _botCmd_help(self, bot, update):
        chat_id = update.message.chat_id
        if chat_id in self.currentChats:
            txt = u"""Help:
            */subscribe*: Subscribe to the Announcement list, need an access Key
            */{}*: Info Command
            */{}*: Enable Command
            */{}*: Disable Command
            */{}*: Run Once Command, use program number as argument""".format(
                self.data[u"info_cmd"],
                self.data[u"enable_cmd"],
                self.data[u"disable_cmd"],
                self.data[u"runOnce_cmd"],
            )
        else:
            txt = u"I'm sorry Dave I'm afraid I can't do that."

        await bot.sendMessage(chat_id, text=txt, parse_mode="Markdown")

    async def _botCmd_enable(self, bot, update):
        chat_id = update.message.chat_id
        if chat_id in self.currentChats:
            txt = u"{} System <b>ON</b>".format(gv.sd[u"name"])
            gv.sd[u"en"] = 1  # enable system SIP
            gv.sd[u"mm"] = 0  # Disable Manual Mode
            jsave(gv.sd, u"sd")  # save en = 1
        else:
            txt = u"I'm sorry Dave I'm afraid I can't do that."
        await bot.sendMessage(chat_id, text=txt, parse_mode=u"HTML")

    async def _botCmd_disable(self, bot, update):
        chat_id = update.message.chat_id
        if chat_id in self.currentChats:
            txt = u"{} System <b>OFF</b>".format(gv.sd[u"name"])
            gv.sd[u"en"] = 0  # disable system SIP
            jsave(gv.sd, u"sd")  # save en = 0
            stop_stations()
        else:
            txt = u"I'm sorry Dave I'm afraid I can't do that."

        await bot.sendMessage(chat_id, text=txt, parse_mode=u"HTML")

    async def _botCmd_runOnce(self, bot, update, args):
        chat_id = update.message.chat_id
        if chat_id in self.currentChats:
            txt = u"{} RunOnce: program {} Not yet Implemented!!!!!".format(
                gv.sd[u"name"], args
            )
        #               gv.sd['en'] = 0  # disable system SIP
        #               jsave(gv.sd, 'sd')  # save en = 0
        else:
            txt = u"I'm sorry Dave I'm afraid I can't do that."

        await bot.sendMessage(chat_id, text=txt)

    def _initBot(self):
        updater = Application.builder().token(self.data[u"botToken"]).build()
        self._currentChats = set(self.data[u"currentChats"])
        dp = updater.application
        dp.add_error_handler(self._botError)
        dp.add_handler(CommandHandler(u"start", self._botCmd_start_chat))
        dp.add_handler(CommandHandler(u"subscribe", self._botCmd_subscribe))
        dp.add_handler(CommandHandler(u"help", self._botCmd_help))
        dp.add_handler(CommandHandler(self.data[u"info_cmd"], self._botCmd_info))
        dp.add_handler(CommandHandler(self.data[u"enable_cmd"], self._botCmd_enable))
        dp.add_handler(CommandHandler(self.data[u"disable_cmd"], self._botCmd_disable))
        dp.add_handler(
            CommandHandler(
                self.data[u"runOnce_cmd"], self._botCmd_runOnce, pass_args=True
            )
        )
        dp.add_handler(MessageHandler(filters.TEXT, self._echo))
        return updater

    async def _announce(self, text, parse_mode=None):
        bot = self.bot.bot
        for chat_id in self.currentChats:
            if parse_mode is None:
                await bot.sendMessage(chat_id, text=text)
            else:
                await bot.sendMessage(chat_id, text=text, parse_mode=parse_mode)

    async def _echo(self, bot, update):
        await bot.sendMessage(update.message.chat_id, text=update.message.text)

    async def run(self):
        try:
            if self.data[u"botToken"] != "":
                time.sleep(
                    randint(3, 10)
                )  # Sleep some time to prevent printing before startup information
                print(u"telegramBot plugin is active")
                self.bot = self._initBot()
                self._announce(
                    u"Bot on *" + gv.sd[u"name"] + u"* has just started!",
                    parse_mode=u"Markdown",
                )
                # Lets Start the bot
                await self.bot.start_polling()

        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            err_string = u"".join(
                traceback.format_exception(exc_type, exc_value, exc_traceback)
            )
            print(u"telegramBot plugin encountered error: " + err_string)

    def notifyZoneChange(self, name, **kw):
        if self.data[u"zoneChange"] == u"on":
            txt = u"There has been a Zone Change: " + str(gv.srvals)
            self._announce(txt)

    def notifyStationScheduled(self, name, **kw):
        if self.data[u"stationScheduled"] == u"on":
            time.sleep(
                2
            )  # Sleep a couple of seconds to let SIP finish setting the gv variables
            txt = u"New Stations have been scheduled"
            txt += get_running_programs_rs()
            self._announce(txt, parse_mode=u"HTML")

    def notifyAlarmToggled(self, name, **kw):
        txt = u"""<b>ALARM!!!</b> from <i>{}</i>:
<pre>{}</pre>""".format(
            name, kw[u"txt"]
        )
        self._announce(txt, parse_mode=u"HTML")


def get_running_programs_rs():  # From the running schedule info
    txt = ""
    for i in range(len(gv.rs)):
        d = gv.rs[i]
        sname = gv.snames[i]
        start_time = time.strftime(u"%H:%M:%S", time.gmtime(d[0]))
        #        stop_time = time.strftime("%H:%M:%S", time.gmtime(d[1]))
        program = str(d[3])
        if d[2] == 0:
            duration = u"forever"
        else:
            min = int(round(d[2] / 60))
            sec = int(round(d[2] - 60 * min))
            if sec < 10:
                sec = 0
            duration = u"{}:{}".format(str(min).zfill(2), str(sec).zfill(2))

        if program != u"0":  # We have a running Station!
            txt += u"\n<b>{}</b> - ".format(sname)
            if program == u"99":
                # Run Once is running!
                txt += u"<i>Run Once </i>"
            elif program == u"98":
                # Manual Mode is running
                txt += u"<i>Manual Program </i>"
            else:
                # a Program is Running
                txt += u" Program: <i>{}</i>".format(program)

            if program != 98:
                txt += u"\n  Start: <i>{}</i>".format(start_time)
                txt += u"\n  Duration: <i>{}</i>".format(duration)
    return txt


def get_running_programs_pon():  # From the GUI info
    txt = u""
    if gv.pon == 99:
        # Run Once is running!
        txt += u"\n<b>Run Once </b>"
    elif gv.pon == 98:
        # Manual Mode is running
        txt += u"\n<b>Manual Program </b>"
    elif gv.pon is not None:
        # a Program is Running
        txt += u"\nRunning Program: <b>{}</b>".format(str(gv.pon))

    if gv.pon is not None:
        for i in range(len(gv.ps)):
            p, d = gv.ps[i]
            if p != 0:
                sname = gv.snames[i]
                if d == 0:
                    duration = u"forever"
                else:
                    min = int(round(d / 60))
                    sec = int(round(d - 60 * min))
                    if sec < 10:
                        sec = 0
                    duration = u"{}:{}".format(str(min).zfill(2), str(sec).zfill(2))
                txt += u"\n  <b>{}</b> - Duration: <b>{}</b>".format(sname, duration)
    return txt


def get_telegramBot_options():
    data = {
        u"botToken": u"",
        u"botAccessKey": u"SIP",
        u"zoneChange": u"off",
        u"stationScheduled": u"off",
        u"info_cmd": u"info",
        u"disable_cmd": u"disable",
        u"enable_cmd": u"enable",
        u"runOnce_cmd": u"runOnce",
        u"currentChats": [],
    }
    try:
        with open(json_data, u"r") as f:  # Read the settings from file
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
        data[k] = new_data[k]
    with open(u"./data/telegramBot.json", u"w") as f:
        json.dump(data, f)  # save to file
    return


async def run_bot():
    bot = SipBot(gv)
    # wait to the bot to start
    # time.sleep(10)    
    await asyncio.sleep(10)
    
    # Connect Signals
    program_started = signal(u"stations_scheduled")
    program_started.connect(bot.notifyStationScheduled)

    zoneChange = signal(u"zone_change")
    zoneChange.connect(bot.notifyZoneChange)

    alarm = signal(u"alarm_toggled")
    alarm.connect(bot.notifyAlarmToggled)


class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        return template_render.telegramBot(
            get_telegramBot_options()
        )  # open settings page


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def GET(self):
        qdict = web.input()
        if u"zoneChange" not in qdict:
            qdict[u"zoneChange"] = u"off"
        if u"programToggled" not in qdict:
            qdict[u"programToggled"] = u"off"

        set_telegramBot_options(qdict)
        raise web.seeother(u"/")  # Return user to home page.


#  Run when plugin is loaded
run_bot()
