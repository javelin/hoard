# -*- coding: utf-8 -*-

# simsimi.tac
# Twisted app file
# Run a simsimi chatter bot in palringo
# Palringo connectivity and protocol
# Copyright (c) 2012 Mark Jundo P Documento

from twisted.application import service, internet
from twisted.internet import reactor
from twisted.python.log import ILogObserver, FileLogObserver
from twisted.python.logfile import DailyLogFile

from palringo import PalClientFactory, PalProtocol
from simsimi import SimsimiBot

PalProtocol.DEBUG = False
factory = PalClientFactory('EMAIL HERE', 'PASSWORD HERE', delegate=SimsimiBot(owner='20209790'))
application = service.Application('simsimi')
internet.TCPClient('primary.palringo.com', 12345, factory).setServiceParent(application)
logfile = DailyLogFile('logs/simsimi.log', '.')
application.setComponent(ILogObserver, FileLogObserver(logfile).emit)
