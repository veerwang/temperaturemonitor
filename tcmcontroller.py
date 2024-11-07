import serial
from serial.tools import list_ports

import logging
import threading
import time

from zlib import crc32

from PyQt5.QtCore import QThread, pyqtSignal

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class InstrumentStatus:
    def __init__(self):
        self.reset_value()

    def reset_value(self):
        self.instrumentIndex = 0
        self.MAXinstrument = 0
        self.percent = 0
        self.reply = ''
        self.retry = 0
        self.MAXretry = 5
        self.value = 0
        # INIT:  
        # PROCESS:
        # OK
        # FAIL
        # FINISH
        # CONTINUE 
        self.status = 'FINISH'


class TCMController(QThread):
    processResult = pyqtSignal(str)

    packet_serial = None

    def __init__(self, port, baud_rate = 57600):
        super().__init__()

        ports = [p.device for p in list_ports.comports() if port == p.device]

        if not ports:
            raise ValueError(f"No device found with serial number: {serial_number}")

        self.packet_serial = serial.Serial(ports[0], baudrate=baud_rate, timeout=1)

        self.instrumentstatus = InstrumentStatus()

        self.lock = threading.RLock()
        self.query_interval = 1.0  # Query interval in seconds
        self.thread_read_received_packet = None

        # type A: means reply=1 is OK
        # type V: means reply is value
        # type S: means reply=8 is value save OK
        # type R: just display reply from TMC
        self.instruments = []

        self.instrumentstatus.MAXinstrument = len(self.instruments)

        self.running = True
        self.thread_read_received_packet = threading.Thread(target=self.received_loop)
        self.thread_read_received_packet.start()

    def set_commands(self, instruments_list):
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

    def stop(self):
        self.running = False
        if self.thread_read_received_packet:
            self.thread_read_received_packet.join()

        if self.packet_serial is not None:
            self.packet_serial.close()

    def run(self):
        try:
            while self.running is True:
                if self.instrumentstatus.status != 'FINISH':
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
                            self.processResult.emit('OK')
                            print('Instruction Excution Successfully')
                    elif self.instrumentstatus.status == 'FAIL':
                        if self.instrumentstatus.retry < self.instrumentstatus.MAXretry: 
                            self.instrumentstatus.retry += 1
                        else:
                            self.instrumentstatus.status = 'FINISH'
                            print('Instruction Excution Fail: ' + self.instruments[self.instrumentstatus.instrumentIndex][0])
                            print('Reply: ' + self.instrumentstatus.reply)
                            self.processResult.emit('FAIL')
                    elif self.instrumentstatus.status == 'PROCESS':
                        self.instrumentstatus.status = 'FINISH'
                        print('Instruction Excution Timeout')
                        self.processResult.emit('TIMEOUT')
                    elif self.instrumentstatus.status == 'CONTINUE':
                        print('PID arguments tuning: %' + self.instrumentstatus.percent)
                    else:
                        print('Instruction Excution Unknown Error')
                        self.processResult.emit('ERROR')

                time.sleep(1)

        except KeyboardInterrupt:
            print("Stopping...")
            self.stop()


class ControllerWrapper(): 

    name_map_to_parameters_request_command = {
            'temperature1':'TC1:TCACTUALTEMP?@0',
            'temperature2':'TC2:TCACTUALTEMP?@0',
            'voltage1':'TC1:TCACTUALVOLTAGE@0',
            'voltage2':'TC2:TCACTUALVOLTAGE@0',
            'current1':'TC1:TCACTCUR@0',
            'current2':'TC2:TCACTCUR@0',
            'adjusttemperature1':'TC1:TCADJTEMP?@0',
            'adjusttemperature2':'TC2:TCADJTEMP?@0',
            'protectHitemperature1':'TC1:TCOTPHT?@0',
            'protectHitemperature2':'TC2:TCOTPHT?@0'
            }

    controller = None

    def __init__(self, simulation = False):
        self.simulation = simulation
        if self.simulation is not True:
            self.controller = TCMController("/dev/ttyUSB0", 57600)
            self.controller.start()

    def close(self):
        if self.simulation is not True:
            self.controller.stop()

    def _assemble_commands(self, parameters_dict):
        command_sets = []
        address = parameters_dict['Address']
        moduletype = parameters_dict['ModuleType']
        if moduletype == 'M207':
            adjusttemp1 = parameters_dict['AdjustTemperature1']
            command_sets.append([f'TC1:TCADJTEMP={adjusttemp1}@{address}', 'A'])
            command_sets.append([f'TC1:TCADJTEMP!@{address}', 'S'])
            adjusttemp2 = parameters_dict['AdjustTemperature2']
            command_sets.append([f'TC2:TCADJTEMP={adjusttemp2}@{address}', 'A'])
            command_sets.append([f'TC2:TCADJTEMP!@{address}', 'S'])
        return command_sets

    def write_parameters(self, parameters_dict): 
        commands_sets = []
        for item in parameters_dict:
            _sets = self._assemble_commands(item)
            for cmd in _sets:
                commands_sets.append(cmd)
        if self.simulation is not True:
            self.controller.set_commands(commands_sets)

    def read_parameters(self, parameter_name):
        '''
        parameter_name:
            temperature1
            temperature2
            voltage1
            voltage2
            current1
            current2
            adjusttemperature1
            adjusttemperature2
            protectHitemperature1
            protectHitemperature2
        '''
        commands_sets = [[self.name_map_to_parameters_request_command[parameter_name], 'V']]

        if self.simulation is not True:
            self.controller.set_commands(commands_sets)

