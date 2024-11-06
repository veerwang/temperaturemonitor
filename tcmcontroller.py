import serial
from serial.tools import list_ports

import logging

from zlib import crc32

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class InstrumentStatus:
    def __init__(self):
        self.instrumentIndex = 0
        self.MAXinstrument = 0
        self.percent = 0
        self.reply = ''
        self.retry = 0
        self.MAXretry = 5
        # INIT:  
        # PROCESS:
        # OK
        # FAIL
        # FINISH
        # CONTINUE 
        self.status = 'INIT'


class TCMController:
    packet_serial = None

    def __init__(self, port, baud_rate = 57600):
        ports = [p.device for p in list_ports.comports() if port == p.device]

        if not ports:
            raise ValueError(f"No device found with serial number: {serial_number}")

        self.packet_serial = serial.Serial(ports[0], baudrate=baud_rate, timeout=1)

        self.instrumentstatus = InstrumentStatus()

        self.lock = threading.RLock()
        self.query_interval = 1.0  # Query interval in seconds
        self.running = False
        self.query_thread = None
        self.thread_read_received_packet = None

        # type A: means reply=1 is OK
        # type V: means reply is value
        # type S: means reply=8 is value save OK
        # type R: just display reply from TMC
        self.instruments = [ ]

        self.instrumentstatus.MAXinstrument = len(self.instruments)

    def __del__(self):
        if self.packet_serial is not None:
            self.packet_serial.close()

    def set_instruments_sets(self, instruments_list):
        self.instruments = instruments_list 
        self.instrumentstatus.reset_value()
        self.instrumentstatus.MAXinstrument = len(self.instruments)
        self.instrumentstatus.status = 'INIT'

    def get_instruments_return_value(self):
        return self.instrumentstatus.value

    def transparent_command(self, command):
        with self.lock:
            bytes_command = command.encode('utf-8')
            packet = bytes_command
            self.packet_serial.write(packet)
            self.packet_serial.write(b'\x0D')

    def analyze_TCM_reply(self, reply):
        # save reply
        self.instrumentstatus.reply = reply

        if self.instruments[self.instrumentstatus.instrumentIndex][1] == 'A':
            if reply[4:11] == 'REPLY=1':
                self.instrumentstatus.status = 'OK'
            else:
                self.instrumentstatus.status = 'FAIL'
        elif self.instruments[self.instrumentstatus.instrumentIndex][1] == 'P': 
            pos_1 = reply.find('=', 0)
            pos_2 = reply.find('@', 0)
            if pos_1 != -1 and pos_2 != -1:
                if reply[pos_1 + 1:pos_2] == '100':
                    self.instrumentstatus.percent = reply[pos_1 + 1:pos_2]
                    self.instrumentstatus.value = 100
                    self.instrumentstatus.status = 'OK'
                else:
                    self.instrumentstatus.percent = reply[pos_1 + 1:pos_2]
                    self.instrumentstatus.status = 'CONTINUE'
            else:
                self.instrumentstatus.status = 'FAIL'
        elif self.instruments[self.instrumentstatus.instrumentIndex][1] == 'V': 
            if reply[4:11] == 'REPLY=2':
                self.instrumentstatus.status = 'FAIL'
            else:
                pos_1 = reply.find('=', 0)
                pos_2 = reply.find('@', 0)
                if pos_1 != -1 and pos_2 != -1:
                    self.instrumentstatus.value = reply[pos_1 + 1:pos_2]
                    self.instrumentstatus.status = 'OK'
                else:
                    self.instrumentstatus.status = 'FAIL'
        elif self.instruments[self.instrumentstatus.instrumentIndex][1] == 'S': 
            if reply[4:11] == 'REPLY=8':
                self.instrumentstatus.status = 'OK'
            else:
                self.instrumentstatus.status = 'FAIL'
        elif self.instruments[self.instrumentstatus.instrumentIndex][1] == 'R': 
            if reply[4:11] == 'REPLY=1':
                self.instrumentstatus.status = 'OK'
            else:
                self.instrumentstatus.status = 'FAIL'
        else:
            self.instrumentstatus.status = 'FAIL'

    def on_packet_received(self, packet):
        self.analyze_TCM_reply(packet)

    def query_loop(self):
        while self.running:
            time.sleep(self.query_interval)

    def received_loop(self):
        msg = []
        while self.running:
            #msg.append(ord(self.packet_serial.read()))
            if self.packet_serial.in_waiting == 0:
                continue
            char = self.packet_serial.read(1)
            if char == b'\r':
                msg += char
                self.on_packet_received(bytearray(msg[:-1]).decode())
                msg = []
                continue
            msg += char

    def start(self):
        self.running = True
        self.query_thread = threading.Thread(target=self.query_loop)
        self.query_thread.start()

        self.thread_read_received_packet = threading.Thread(target=self.received_loop)
        self.thread_read_received_packet.start()

    def stop(self):
        self.running = False
        if self.query_thread:
            self.query_thread.join()
        if self.thread_read_received_packet:
            self.thread_read_received_packet.join()

    def run(self):
        try:
            self.start()
            while self.instrumentstatus.status != 'FINISH':
                self.transparent_command(
                        self.instruments[self.instrumentstatus.instrumentIndex][0])
                self.instrumentstatus.status = 'PROCESS'
                print('NO. ' + str(self.instrumentstatus.instrumentIndex + 1) 
                      + ' Retry: ' + str(self.instrumentstatus.retry + 1) + ' Instrument: ' + self.instruments[self.instrumentstatus.instrumentIndex][0])

                timeout = 10
                while self.instrumentstatus.status == 'PROCESS' and timeout != 0: 
                    time.sleep(0.5)
                    timeout = timeout - 1

                if self.instrumentstatus.status == 'OK':
                    self.instrumentstatus.instrumentIndex = self.instrumentstatus.instrumentIndex + 1
                    self.instrumentstatus.retry = 0
                    if self.instrumentstatus.instrumentIndex == self.instrumentstatus.MAXinstrument:
                        self.instrumentstatus.status = 'FINISH'
                        print('Instruction Excution Successfully')
                elif self.instrumentstatus.status == 'FAIL':
                    if self.instrumentstatus.retry < self.instrumentstatus.MAXretry: 
                        self.instrumentstatus.retry += 1
                    else:
                        self.instrumentstatus.status = 'FINISH'
                        print('Instruction Excution Fail: ' + self.instruments[self.instrumentstatus.instrumentIndex][0])
                        print('Reply: ' + self.instrumentstatus.reply)
                elif self.instrumentstatus.status == 'PROCESS':
                    self.instrumentstatus.status = 'FINISH'
                    print('Instruction Excution Timeout')
                elif self.instrumentstatus.status == 'CONTINUE':
                    print('PID arguments tuning: %' + self.instrumentstatus.percent)
                else:
                    print('Instruction Excution Unknown Error')

                time.sleep(1)

        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            self.stop()