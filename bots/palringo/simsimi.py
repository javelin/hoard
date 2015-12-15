# -*- coding: utf-8 -*-

# simsimi.py
# Run a simsimi chatter bot in palringo
# Palringo connectivity and protocol
# Copyright (c) 2012 Mark Jundo P Documento

import json, random, re, sys, threading, urllib, urllib2
from twisted.web.client import getPage
from bot import PalBot

AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.19 (KHTML, like Gecko) Ubuntu/12.04 Chromium/18.0.1025.168 Chrome/18.0.1025.168 Safari/535.19'

MAX_SIMSIMI = 30
SIMSIMI_FILTERING = 0.0

class SimsimiBot(PalBot):
    def __init__(self, owner=None, useThreads=False):
        PalBot.__init__(self, 'Simsimi', owner=owner)
        self.simsimi = 0
        self.useThreads = useThreads

    def run(self, msg, toId, name, pm):
        acak = str(int(random.uniform(100000,300000)))
        data = {'av': 5.2, 'ft': SIMSIMI_FILTERING, 'lc': 'ph', 'os': 'i', 'req': msg, 'tz': "Asia/Manila", 'uid': acak}
        url = "http://app.simsimi.com/app/aicr/request.p?" + urllib.urlencode(data)
        req = urllib2.Request(url, headers={'User-Agent': AGENT})
        data = urllib2.urlopen(req).read()
        o = json.loads(data)
        res = o['sentence_resp']
        self.postReply(res, toId, name, pm)
        self.simsimi -= 1
    
    def onPrivateMesg(self, mesg):
        if PalBot.onPrivateMesg(self, mesg): return True
        if mesg.mime != 'text/plain': return
        print mesg
        msg = mesg.text().strip()
        if msg.startswith('@'):
            msg = msg[1:]
        return self.processChat(msg, mesg.sourceId, mesg.name, True)

    def onGroupMesg(self, mesg):
        if PalBot.onGroupMesg(self, mesg): return True
        if mesg.mime != 'text/plain': return
        print mesg
        msg = mesg.text().strip()
        if (msg.startswith('@') and
            len(msg) > 2):
            uid = mesg.sourceId
            if uid in self.contacts():
                name = self.contacts()[uid]['Nickname']
            else:
                name = ''
            return self.processChat(msg, mesg.groupId, name, False)
        else:
            return False

    def processChat(self, msg, toId, name, pm):
        if len(msg) > 1:
            if self.useThreads and self.simsimi < MAX_SIMSIMI:
                self.simsimi += 1
                t = threading.Thread(target=self.run, args=(msg, toId, name, pm))
                t.start()
            elif not self.useThreads:
                self.runTwisted(msg, toId, name, pm)
            return True
        else:
            return False

    def runTwisted(self, msg, toId, name, pm):
        acak = str(int(random.uniform(100000,300000)))
        data = {'av': 5.2, 'ft': SIMSIMI_FILTERING, 'lc': 'ph', 'os': 'i', 'req': msg[1:], 'tz': "Asia/Manila", 'uid': acak}
        url = "http://app.simsimi.com/app/aicr/request.p?" + urllib.urlencode(data)
        return getPage(url, agent=AGENT).addCallback(self.gotSimi(toId, name, pm)).addErrback(self.gotError)

    def gotSimi(self, toId, name, pm):
        def gotPage(data):
            o = json.loads(data)
            res = o['sentence_resp']
            self.postReply(res, toId, name, pm)
        return gotPage

    def postReply(self, reply, toId, name, pm):
        try:
            if pm:
                msg = reply.encode('utf-8')
                print name, msg
            elif name:
                msg = '@' + name + ', ' + reply.encode('utf-8')
                print msg
            else:
                msg = '@' + reply.encode('utf-8')
                print msg
            if pm:
                self.sendPrivate(toId, msg)
            else:
                self.sendToGroup(toId, msg)
        except UnicodeEncodeError as e:
            print e

    def gotError(self, err):
        print err

if __name__ == '__main__':
    pass
