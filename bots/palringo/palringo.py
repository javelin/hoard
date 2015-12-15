# -*- coding: utf-8 -*-

# palringo.py
# Palringo connectivity and protocol
# Copyright (c) 2012 Mark Jundo P Documento

from hashlib import md5
from operator import itemgetter
from salsa20 import Salsa20
from sys import stdout
from struct import unpack
from twisted.internet import reactor, ssl, task
from twisted.internet.protocol import Protocol, ReconnectingClientFactory

import time, traceback, zlib


class PalDelegate:
    def onAuth(self, packet):
        pass

    def onBalanceQueryResult(self, packet):
        pass

    def onGroupAdmin(self, packet):
        pass

    def onGroupMesg(self, packet):
        pass

    def onLogonFailed(self, packet):
        pass

    def onMesg(self, packet):
        pass

    def onPrivateMesg(self, packet):
        pass

    def onProtocolConnected(self, protocol):
        pass

    def onProtocolDisconnected(self):
        pass

    def onResponse(self, rtype, what, mesgId, packet):
        pass

    def onSubProfile(self, headers, kvMap):
        pass

    def redirectCount(self):
        return 0


class PalPacket:
    NULL_HEADER = 'no-header'

    def __init__(self, command, payload='', headers={}, needsMid=False):
        self.command, self.payload, self.headers, self.needsMid = command, payload, headers, needsMid
        self.__compressed = False

    def isCompressed(self):
        return self.__compressed

    def length(self):
        return len(self.payload)

    def hasKeyI(self, key):
        for k, v in self.headers.iteritems():
            if key.lower() == k.lower():
                return True
        return False

    def hasValueI(self, key, value):
        for k, v in self.headers.iteritems():
            if key.lower() == k.lower():
                return value == v
        return False

    def setValueI(self, key, value):
        for k, v in self.headers.iteritems():
            if key.lower() == k.lower():
                key = k
                break
        self.headers[key] = value

    def getValueI(self, key):
        for k, v in self.headers.iteritems():
            if key.lower() == k.lower():
                return v
        return None

    def getValue(self, key):
        if key in self.headers:
            return self.headers[key]
        else:
            return None

    def toData(self):
        l = [self.command]
        if self.payload:
            l.append('content-length: %d' % len(bytearray(self.payload)))
            if self.__compressed:
                l.append('compression: 1')
        l.extend(['%s: %s' % (k, v) for k, v in self.headers.iteritems()
                  if k and v and k.lower() not in ['compression', 'content-length']])
        l.append('')
        l.append(self.payload)
        return '\n'.join(l)

    def __str__(self):
        pl = self.payload.encode('hex')
        if len(pl) > 64:
            pl = pl[:61] + "..."
        return {'command':self.command, 'headers':self.headers, 'payload':pl, 'needsMid':self.needsMid}.__str__()

    def compress(self):
        if not self.__compressed:
            self.payload = zlib.compress(self.payload)
            self.__compressed = True

    def decompress(self):
        if self.__compressed:
            self.payload = zlib.decompress(self.payload)
            self.__compressed = False

    @staticmethod
    def parse(data, decompress=False):
        try:
            try:
                plpos = data.index('\r\n\r\n')
                delim = '\r\n'
            except ValueError:
                plpos = data.index('\n\n')
                delim = '\n'
            split = data[:plpos].split(delim)
            cmd = split[0]
            headers = dict([kv.split(': ') for kv in split[1:]])
            payload = data[plpos + len(delim)*2:]
            p = PalPacket(cmd, payload=payload, headers=headers)
            if p.hasValueI('compression', '1'):
                p.__compressed = True
                if decompress:
                    p.decomp()
            return p
        except ValueError as e:
            traceback.print_exc()
            print 'Malformed packet?', data.encode('hex')
            return None

    @staticmethod
    def logon(email, redirect_count=0):
        headers={#'Client-ID':PalPacket.md5(email).encode('hex'),
            "Operator":"PC_CLIENT",
            "affiliate-id":"winpc",
            "app-identifier":"00000",
            "app-type":"Windows x86",
            "capabilities":"786437",
            "client-version":"2.8.0,  53947",
            "fw":"Win 5.1",
            #"client-version":"2.8.1,  60842",
            #"fw":"Win 6.2",
            "last":"1",
            "name":email,
            "protocol-version":"2.0"}
        if redirect_count > 0:
            headers['redirect-count'] = str(redirect_count)
        return PalPacket('LOGON',
                         headers=headers)

    @staticmethod
    def auth(password, data):
	return PalPacket("AUTH",
                         payload=PalPacket.generatePayload(password, data),
                         headers={"encryption-type":"1",
                                  "online-status":"1"})

    @staticmethod
    def message(target, to, payload, mime='text/plain', correlationId=None, last=True):
        if not mime: mime='text/plain'
        headers = {"Content-Type":mime,
                   #"mesg-id":"%d" % id
                   "Target-Id":to,
                   'Mesg-Target':target}
                   #'Timestamp':'%.6f' % time.time()}
        if correlationId is not None:
            headers['Correlation-Id'] = correlationId
        if last:
            headers['Last'] = 'T'
        if target:
            headers["Mesg-Target"] = target
	return PalPacket("MESG",
                         payload=payload,
                         headers=headers)

    @staticmethod
    def imageHeader(target, to, mesgId, length, payload):
        return PalPacket("MESG",
                         payload=payload,
                         headers={"content-type":"image/jpeg",
                                  "mesg-id":mesgId,
                                  "mesg-target":target,
                                  "target-id":to,
                                  "total-length":length})

    @staticmethod
    def image(target, to, correlation, mesgId, payload):
        return PalPacket("MESG",
                         payload=payload,
                         headers={"content-type":"image/jpeg",
                                  "correlation-id":correlation,
                                  "mesg-id":mesgId,
                                  "mesg-target":target,
                                  "target-id":to})

    @staticmethod
    def imageFinal(target, to, correlation, mesgId, payload):
        return PalPacket("MESG",
                         payload=payload,
                         headers={"content-type":"image/jpeg",
                                  "correlation-id":correlation,
                                  "last":"1",
                                  "mesg-id":mesgId,
                                  "mesg-target":target,
                                  "target-id":to})

    @staticmethod
    def admin(action, group, target):
        return PalPacket("GROUP ADMIN",
                         headers={"Action":action,
                                  "group-id":group,
                                  "last":"1",
                                  #"mesg-id":"1",                                  
                                  "target-id":target
                                  })

    @staticmethod
    def group_join(group, password=''):
        return PalPacket("GROUP SUBSCRIBE",
                         payload=password,
                         headers={"name":group,
                                  "last":'1'
                                  #"mesg-id":"1"
                                  },
                         needsMid=True)

    @staticmethod
    def group_leave(group):
        return PalPacket("GROUP UNSUB",
                         headers={"group-id":group,
                                  "last":'1'
                                  #"mesg-id":"1"
                                  },
                         needsMid=True)

    @staticmethod
    def ping(number):
        return PalPacket("P",
                         headers={"last":"1",
                                  "ps":"%d" % number
                                  })

    @staticmethod
    def generatePayload(password, data):
        payload = bytearray(data.payload)
	rnd = bytearray(data.headers["TIMESTAMP"].replace('.', ''))

	#create the IV
        IV = ''.join([chr(payload[i]) for i in range(16, 24)])

	#create some final keys for the salsa
	authKey	= PalPacket.dbMd5(password, IV)

	#finally create our data block to be hashed by salsa
	#this information gets hashed
        dte = ''.join([chr(payload[i]) for i in range(0, 16)] + [chr(rnd[i]) for i in range(0, 16)])

        s20 = Salsa20(authKey, IV, rounds=20)
	result = s20.encrypt(dte)
        return result

    @staticmethod
    def md5(s):
        m = md5()
        m.update(s)
        return m.digest()

    @staticmethod
    def dbMd5(a, b):
        m = md5()
        m.update(a)
        mm = md5()
        mm.update(m.digest())
        mm.update(b)
        return mm.digest()



class Mesg:
    def __init__(self, sourceId, name, mesgId, totalLength, msg, mime):
        self.sourceId, self.name, self.totalLength, self.mime = sourceId, name, totalLength, mime
        self.chunks = {mesgId : (-1, msg)}
        self.groupId = None
    
    def addChunk(self, mesgId, correlationId, msg):
        self.chunks[mesgId] = (correlationId, msg)

    def text(self):
        msg = ''
        lmid = None
        for mid, (cid, s) in sorted(self.chunks.iteritems(), key=itemgetter(0)):
            if not msg and cid > -1:
                print 'Warning: malformed mesg packet'
            elif cid > -1 and cid != lmid:
                print 'Warning: malformed mesg packet, out of sequence'
            msg += s
            lmid = mid
        return msg

    def __str__(self):
        return {'sourceId':self.sourceId,
                'name':self.name,
                'totalLength':self.totalLength,
                'text':self.text(),
                'mime':self.mime}.__str__()



class PalProtocol(Protocol):
    DEBUG = True

    def __init__(self, factory, login, password, delegate=None, autoDecompress=False):
        self.factory, self.login, self.password, self.delegate, self.autoDecompress = factory, login, password, delegate, autoDecompress
        self.packet = None
        self.mesg = None
        self.clen = 0
        self.commands = {
            'AUTH':self.doAuth,
            'BALANCE QUERY RESULT':self.doBalanceQueryResult,
            'GROUP ADMIN':self.doGroupAdmin,
            'LOGON FAILED':self.doLogonFailed,
            'MESG':self.doMesg,
            'P':self.doPing,
            'RESPONSE':self.doResponse,
            'SUB PROFILE':self.doSubProfile,
        }
        self.outbox = []
        self.looper = None

    def connectionMade(self):
        print 'Sending logon'
        redirect_count = 0 if not self.delegate else self.delegate.redirectCount()
        self.sendPacket(PalPacket.logon(self.login, redirect_count=redirect_count))
        self.pings = 0
        self.mesgId = 1
        if self.delegate:
            self.delegate.onProtocolConnected(self)
        self.looper = task.LoopingCall(self.sendFromOutbox)
        self.looper.start(1, now=True)

    def sendFromOutbox(self):
        if self.outbox:
            self.sendPacket(self.outbox[0])
            del self.outbox[0]

    def connectionLost(self, reason):
        if self.looper:
            self.looper.stop()
            self.looper = None

    def dataReceived(self, data):
        packet = self.parseData(data)
        if packet is not None:
            if PalProtocol.DEBUG:
                print 'Recv:', packet
            self.parsePacket(packet)

    def sendPacket(self, packet):
        mesgId = None
        if packet.needsMid:
            mesgId = self.mesgId
            packet.setValueI('mesg-id', mesgId)
            self.mesgId += 1
        if PalProtocol.DEBUG:
            print 'Sent:', packet
        self.transport.write(packet.toData())
        return mesgId

    def sendMesg(self, target, to, payload, mime=None):
        ofs = 0
        correlationId=None
        last = False
        while not last:
            currentPayload = payload[ofs:ofs+512]
            #if not currentPayload: break
            ofs += 512
            last = ofs > len(payload)
            p = PalPacket.message(target,
                                  to,
                                  currentPayload,
                                  mime=mime,
                                  correlationId=correlationId,
                                  last=last)
            p.setValueI('Mesg-Id', self.mesgId)
            correlationId = self.mesgId
            self.mesgId += 1
            self.outbox.append(p)
        return self.mesgId - 1

    def parseData(self, data):
        if self.packet is None:
            p = PalPacket.parse(data, self.autoDecompress)
            if p is None: return
            l = p.getValueI('content-length')
            if l is None or len(p.payload) == int(l):
                return p
            else:
                self.packet = p
                self.clen = int(l)
                if PalProtocol.DEBUG:
                    print 'Got', len(p.payload), 'bytes payload. Waiting for', l
                return None
        else:
            self.packet.payload += data
            if len(self.packet.payload) >= self.clen:
                p = self.packet
                p.payload = p.payload[:self.clen]
                self.packet = None
                self.clen = 0
                return p
            else:
                return None

    def parsePacket(self, packet):
        if packet.command in self.commands:
            self.commands[packet.command](packet)
 
    def doAuth(self, packet):
        self.sendPacket(PalPacket.auth(self.password, packet))
        if self.delegate:
            self.delegate.onAuth(packet)

    def doBalanceQueryResult(self, packet):
        if packet.isCompressed() and not self.autoDecompress:
            packet.decompress()
        if self.delegate:
            self.delegate.onBalanceQueryResult(packet)

    def doGroupAdmin(self, packet):
        if self.delegate:
            self.delegate.onGroupAdmin(packet)

    def doLogonFailed(self, packet):
        print 'Logon failed:', packet
        if packet.hasValueI('reason', '32'):
            print 'Changing host from ', self.factory.host, 'to', packet.payload
            self.factory.host = packet.payload
        if self.delegate:
            self.delegate.onLogonFailed(packet)

    def doMesg(self, packet):
        mesg = None
        if self.delegate:
            self.delegate.onMesg(packet)
            tlen = packet.getValueI('total-length')
            if tlen:
                try:
                    tlen = int(tlen)
                except ValueError:
                    tlen = None
            if tlen is None:
                if self.mesg is not None:
                    self.mesg.addChunk(packet.getValueI('mesg-id'),
                                       packet.getValueI('correlation-id'),
                                       packet.payload)
                    if packet.hasKeyI('last'):
                        mesg = self.mesg
                        self.mesg = None
                    else:
                        return
                else:
                    mesg = Mesg(packet.getValueI('source-id'),
                                packet.getValueI('name'),
                                packet.getValueI('mesg-id'),
                                len(packet.payload),
                                packet.payload,
                                packet.getValueI('content-type'))
            else:
                mesg = Mesg(packet.getValueI('source-id'),
                            packet.getValueI('nick'),
                            packet.getValueI('mesg-id'),
                            tlen,
                            packet.payload,
                            packet.getValueI('content-type'))
                if len(packet.payload) < tlen:
                    self.mesg = mesg
                    return
                else:
                    self.mesg = None

            if (packet.hasKeyI('target-id') and
                packet.getValueI('target-id') != packet.getValueI('source-id')):
                mesg.groupId = packet.getValueI('target-id')
                self.delegate.onGroupMesg(mesg)
            else:
                self.delegate.onPrivateMesg(mesg)

    def doPing(self, packet):
        self.sendPacket(PalPacket.ping(self.pings))
        self.pings += 1

    def doSubProfile(self, packet):
        if packet.isCompressed() and not self.autoDecompress:
            packet.decompress()
        data = packet.payload
        if packet.hasKeyI('iv'):
            data = data[int(packet.getValueI('iv')):]
        #print data.encode('hex')
        kvMap = self.parseWeirdData(data)
        if self.delegate:
            self.delegate.onSubProfile(packet.headers, kvMap)

    def doResponse(self, packet):
        if self.delegate:
            rtype = packet.getValueI('type')
            what = packet.getValueI('what')
            mesgId = packet.getValueI('mesg-id')
            self.delegate.onResponse(rtype, what, mesgId, packet)

    def parseWeirdData(self, data, ofs=0, bytesToParse=-1):
        kv = {}
        temp = ''
        bytesParsed = 0
        while bytesToParse < 0 or bytesToParse > bytesParsed:
            while True:
                s = data[ofs + bytesParsed:ofs + bytesParsed + 1]
                if len(s) < 1: return kv
                c, = unpack('c', data[ofs + bytesParsed:ofs + bytesParsed + 1])
                bytesParsed += 1
                if c == '\x00': break
                temp += c
                if len(temp) == bytesToParse: return temp
            btp, = unpack('!H', data[ofs + bytesParsed:ofs + bytesParsed + 2])
            bytesParsed += 2
            res = self.parseWeirdData(data, ofs + bytesParsed, btp)
            if temp in kv:
                recursiveUpdate(kv[temp], res)
            else:
                kv[temp] = res
            bytesParsed += btp
            temp = ''
        return kv



class PalClientFactory(ReconnectingClientFactory):
    def __init__(self, login, password, protocol=PalProtocol, delegate=None):
        self.login, self.password, self.protocol, self.delegate = login, password, protocol, delegate
        self.host = None
        
    def startedConnecting(self, connector):
        print 'Started to connect.'

    def buildProtocol(self, addr):
        print 'Connected.'
        print 'Resetting reconnection delay'
        self.resetDelay()
        return self.protocol(self, self.login, self.password, delegate=self.delegate)

    def clientConnectionLost(self, connector, reason):
        print 'Lost connection.  Reason:', reason
        if self.host is not None:
            connector.host = self.host
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        print 'Connection failed. Reason:', reason
        ReconnectingClientFactory.clientConnectionFailed(self, connector,
                                                         reason)



def palConnect(login, password, delegate=None, protocol=PalProtocol, ssl=False):
    host = 'primary.palringo.com'
    if ssl:
        port = 443
        assert(False)
    else:
        port = 12345
        reactor.connectTCP(host, port, PalClientFactory(login, password, delegate=delegate, protocol=protocol))



def recursiveUpdate(m1, m2):
    for k, v in m2.iteritems():
        if k in m1 and type(m1[k]) is dict and type(v) is dict:
            recursiveUpdate(m1[k], v)
        else:
            m1[k] = v


if __name__ == '__main__':
    palConnect('someemail@somedomain.com', 'somepassword')
    reactor.run()
