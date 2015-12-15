# -*- coding: utf-8 -*-

# bot.py
# Palringo connectivity and protocol
# Copyright (c) 2012 Mark Jundo P Documento

from random import choice
from twisted.internet import reactor

import re

from palringo import PalDelegate, PalPacket, palConnect, recursiveUpdate


class PalBot(PalDelegate):
    def __init__(self, name, owner=None):
        self.name, self.owner = name, owner
        self.protocol = None
        self.userId = None
        self.profile = {}
        self.responses = {}
        self.redirect_count = 0

    def onProtocolConnected(self, protocol):
        self.protocol = protocol

    def onProtocolDisconnected(self):
        self.profile = {}

    def onLogonFailed(self, packet):
        if packet.hasValueI('reason', '32'):
            self.redirect_count += 1

    def redirectCount(self):
        return self.redirect_count

    def onGroupAdmin(self, packet):
        if (packet.getValueI('target-id') == self.userId and
            packet.getValueI('action') in ['1', '2']):
            self.sendToGroup(packet.getValueI('group-id'),
                             'Why, thanks for granting me this power. Now who shall I bully first? (6)')

    def onSubProfile(self, headers, kvMap):
        #print 'onSubProfile', kvMap
        recursiveUpdate(self.profile, kvMap)
        #self.profile.update(kvMap)
        if 'Sub-Id' in self.profile:
            self.userId = self.profile['Sub-Id']

    def contacts(self):
        return self.profile['contacts']

    @staticmethod
    def removePuncs(s, puncs='\'"!?,.()-'):
        return re.sub('[' + re.escape(puncs) + ']', '', s)

    def findGroup(self, group):
        if 'group_sub' in self.profile:
            res = [(data['name'], gid) for gid, data in self.profile['group_sub'].iteritems()
                   if data['name'] == group]
            if res:
                return res[0]
        return None, None

    def findGroupName(self, groupId):
        if 'group_sub' in self.profile:
            res = [(data['name'], gid) for gid, data in self.profile['group_sub'].iteritems()
                   if gid == groupId]
            if res:
                return res[0]
        return None, None

    def removeGroup(self, gid):
        def rem():
            if ('group_sub' in self.profile and
                gid in self.profile['group_sub']):
                self.profile['group_sub'].pop(gid, 0)
        return rem

    def onPrivateMesg(self, mesg):
        print mesg
        if mesg.sourceId != self.owner:
            return False
        msg = mesg.text().strip()
        if msg.lower() == '/groups':
            if 'group_sub' in self.profile:
                s = '\n'.join(sorted(['%s - %s' % (data['name'], gid)
                               for gid, data in self.profile['group_sub'].iteritems()]))
            else:
                s = ''
            if not s:
                s = 'Not subscribed to any group.'
            self.sendPrivate(self.owner, s)
            return True
        l = re.findall('/([a-zA-Z]+)\s+(.+)', msg)
        if l:
            cmd, data = l[0]
            if cmd.lower() == 'j':
                name, gid = self.findGroup(data)
                if name and gid:
                    self.sendPrivate(self.owner, 'Already subscribed to %s (%s).' % (name, gid))
                else:
                    self.sendPrivate(self.owner, 'Joining %s...' % data)
                    self.protocol.sendPacket(PalPacket.group_join(data))
                return True
            elif cmd.lower() == 'l':
                name, gid = self.findGroup(data)
                if name and gid:
                    self.sendPrivate(self.owner, 'Leaving %s (%s)...' % (name, gid))
                    mesgId = self.protocol.sendPacket(PalPacket.group_leave(gid))
                    self.responses[str(mesgId)] = self.removeGroup(gid)
                else:
                    self.sendPrivate(self.owner, 'Not subscribed to %s.' % data)
                return True
        else:
            return False

    def onGroupMesg(self, mesg):
        if mesg.sourceId in self.contacts():
            contact = self.contacts()[mesg.sourceId]
            if 'Nickname' in contact:
                mesg.name = contact['Nickname']
            elif 'nickname' in contact:
                mesg.name = contact['nickname']
            elif 'Name' in contact:
                mesg.name = contact['Name']
            elif 'name' in contact:
                mesg.name = contact['name']
            else:
                pass
                #print 'No name in', contact
        else:
            print 'onGroupMesg:', mesg.sourceId, 'not found in contacts!'
        return False

    def onResponse(self, rtype, what, mesgId, packet):
        print rtype, what, mesgId
        if rtype == '0' and what == '4':
            if mesgId in self.responses:
                self.responses[mesgId]()
                self.responses.pop(mesgId, 0)

    def sendPrivate(self, to, msg, mime=None):
        return self.protocol.sendMesg('0',
                                      to,
                                      msg,
                                      mime=mime)

    def sendToGroup(self, groupId, msg, mime=None):
        return self.protocol.sendMesg(groupId,
                                      groupId,
                                      msg,
                                      mime=mime)


if __name__ == '__main__':
    palConnect('someemail@somedomain.com', 'somepassword')
    reactor.run()
