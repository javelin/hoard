# -*- coding: utf-8 -*-

# qplay.py
# Demo of how to subclass QIODevice to create an audio source
# and use this to play an audio file (mp3, wav, etc.) through 
# QAudoOutput in pull mode. Also demonstrates de-interleaving
# of the audio buffer to just play either in stereo or just
# the left or right channels. This uses the audioread library
# for decoding audio files because I can't make QAudioDecoder
# work in Mac OS.
#
# Tested to work in Mac OS X 10.12.4 only.
#
# Dual License: GPL, MIT
#
# Author: Mark Documento
#
# Copyright (c) 2017 Mark J. P. Documento

import builtins, logging, struct, sys
from itertools import chain
import audioread
from PyQt5.QtCore import (pyqtSignal,
                          pyqtSlot,
                          QIODevice,
                          QObject)
from PyQt5.QtMultimedia import (QAudio,
                                QAudioFormat,
                                QAudioOutput)

LOG = logging.debug


class AudioSource(QIODevice):
    BLOCKSIZE = 8192
    noDataLeft = pyqtSignal(name="noDataRemaining")
    
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.audio_file = None
        self.data = None
        self.buffer = b''

            
    def bytesAvailabel(self):
        return self.BLOCKSIZE + super().bytesAvailable()


    def _getChannelData(self, data, channel):
        assert(channel == 0 or channel == 1)
        _data = [data[offset::4] for offset in range(4)]
        b =  bytearray(int(len(data)/2))
        b[::2] = _data[channel*2]
        b[1::2] = _data[channel*2 + 1]
        shorts = struct.unpack('<' + ('h'*int(len(b)/2)), bytes(b))
        return struct.pack('<' + ('h'*len(b)), *list(chain(*zip(shorts, shorts))))

    
    def getLeft(self, data):
        return self._getChannelData(data, 0)


    def getRight(self, data):
        return self._getChannelData(data, 1)


    def open(self, mode):
        assert(mode == QIODevice.ReadOnly)
        self.audio_file = audioread.audio_open(self.path)
        self.data = b''
        for data in self.audio_file.read_data(blocksize=65536*16):
            self.data += data            
        
        self.channel = 0
        self.ptr = 0
        return super().open(mode)
    

    def readData(self, size):
        dataLen = len(self.data)
        ptr = 0
        if self.ptr == dataLen:
            self.noDataLeft.emit()
            return b''

        else:
            if self.ptr + size < dataLen:
                ptr = self.ptr
                self.ptr += size

            else:
                ptr = self.ptr
                self.ptr = dataLen
                
            if self.channel == 0:
                return self.data[ptr:self.ptr]
        
            elif self.channel == 1:
                return self.getLeft(self.data[ptr:self.ptr])

            elif self.channel == 2:
                return self.getRight(self.data[ptr:self.ptr])


    def reset(self):
        self.ptr = 0
        
            
    def setChannel(self, channel):
        self.channel = channel



class AudioPlayer(QObject):
    State = builtins.int
    StoppedState = State(0)
    PlayingState = State(1)
    PausedState = State(2)

    Channel = builtins.int
    Stereo = Channel(0)
    Left = Channel(1)
    Right = Channel(2)
    Mono = Channel(3)

    channelChanged = pyqtSignal(Channel, name="channelChanged")
    positionChanged = pyqtSignal(int, name="positionChanged")
    mutedChanged = pyqtSignal(bool, name="mutedChanged")
    stateChanged = pyqtSignal(State, name="stateChanged")
    volumeChanged = pyqtSignal(int, name="volumeChanged")
    
    def __init__(self, path, parent=None):
        super().__init__(parent=parent)
        self.path = path
        self.source = AudioSource(path)
        self.noDataLeft = False

        self.source.open(QIODevice.ReadOnly)

        self._muted = False
        self._volume = 100
        
        @pyqtSlot()
        def onNoDataLeft():
            self.noDataLeft = True

        self.source.noDataLeft.connect(onNoDataLeft)

        format = QAudioFormat()
        format.setSampleRate(self.source.audio_file.samplerate)
        format.setChannelCount(self.source.audio_file.channels)
        format.setSampleSize(16)
        format.setCodec("audio/pcm")
        format.setByteOrder(QAudioFormat.LittleEndian)
        format.setSampleType(QAudioFormat.SignedInt)

        self.output = QAudioOutput(format)
        self.state = AudioPlayer.StoppedState

        @pyqtSlot()
        def onNotify():
            self.positionChanged.emit(int(self.output.processedUSecs()/1000))
        
        self.output.notify.connect(onNotify)

        @pyqtSlot(QAudio.State)
        def onStateChanged(state):
            if state == QAudio.ActiveState:
                LOG('Active')
                if self.state != AudioPlayer.PlayingState:
                    self.state = AudioPlayer.PlayingState
                    self.stateChanged.emit(self.state)

            elif state == QAudio.SuspendedState:
                LOG('Suspended')
                if self.state != AudioPlayer.PausedState:
                    self.state = AudioPlayer.PausedState
                    self.stateChanged.emit(self.state)
            
            elif state == QAudio.StoppedState:
                LOG('Stopped')
                if self.state != AudioPlayer.StoppedState:
                    self.state = AudioPlayer.StoppedState
                    self.stateChanged.emit(self.state)
                    self.source.reset()

            elif state == QAudio.IdleState:
                LOG('Idle')
                if self.noDataLeft:
                    self.output.stop()
    
        self.output.stateChanged.connect(onStateChanged)


    def duration(self):
        return int(self.source.audio_file.duration*1000)


    def isMuted(self):
        return self._muted

    
    @pyqtSlot()
    def play(self):
        if self.state == AudioPlayer.StoppedState:
            self.output.start(self.source)

        elif self.state == AudioPlayer.PausedState:
            self.output.resume()


    @pyqtSlot()
    def pause(self):
        if self.state == AudioPlayer.PlayingState:
            self.output.suspend()


    @pyqtSlot(Channel)
    def setChannel(self, channel):
        self.source.setChannel(self.Stereo if channel == self.Mono else channel)
        self.channelChanged.emit(channel)


    @pyqtSlot(bool)
    def setMuted(self, muted):
        self._muted = muted
        self.output.setVolume(0 if muted else self._volume)
        self.mutedChanged.emit(self._muted)
        

    @pyqtSlot(int)
    def setVolume(self, volume):
        self._volume = max(0, min(volume, 100))
        self.output.setVolume(self._volume/100)
        self.volumeChanged.emit(self._volume)
        if self._muted:
            self._muted = False
            self.mutedChanged.emit(self._muted)

        
    def volume(self):
        return self._volume
        

if __name__ == '__main__':
    import signal
    from PyQt5.QtCore import QTime
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)

    try:
        path = sys.argv[1]
        player = AudioPlayer(path)
        if len(sys.argv) > 2:
            channel = int(sys.argv[2])
            if channel < 0 or channel > 2:
                raise ValueError('Invalid channel')
        else:
            channel = 0
    except (IndexError, ValueError):
        print('Usage:', sys.argv[0], 'audio_file [channel]')
        print('  channel: 0 - Stereo, 1 - Left, 2 - Right')
        exit(1)

    except FileNotFoundError:
        print("File '{}' not found.".format(path))
        exit(2)


    msg = ''
    @pyqtSlot(int)
    def onPositionChanged(msecs):
        global msg
        sys.stdout.write('\b'*len(msg))
        elapsed = QTime.fromMSecsSinceStartOfDay(msecs)
        msg = elapsed.toString('hh:mm:ss:zzz')
        sys.stdout.write(msg)
        sys.stdout.flush()


    @pyqtSlot(AudioPlayer.State)
    def onStateChanged(state):
        if state == AudioPlayer.PlayingState:
            print('Playing {} audio of {}...'.format('stereo' if channel == 0 else
                                                      ('left' if channel == 1 else 'right'),
                                                      path))
            duration = QTime.fromMSecsSinceStartOfDay(player.duration())
            print('Duration:', duration.toString('hh:mm:ss:zzz'))
        if state == AudioPlayer.StoppedState:
            print()
            print('Stopped.')
            app.quit()

    player.positionChanged.connect(onPositionChanged)
    player.stateChanged.connect(onStateChanged)
    player.setChannel(AudioPlayer.State(channel))
    player.play()

    # Catch signals from terminal, ie, Ctrl+C, etc.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    sys.exit(app.exec_())
