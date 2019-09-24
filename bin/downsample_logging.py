#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2019 Jetperch LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

r"""
Capture downsampled data to a comma-separate values (CSV) file.

This script collects full-rate 2 MHz data from Joulescope, downsamples the data
to 2 Hz, and then records the downsampled data to a CSV file.  The CSV files 
are automatically named and stored under the Documents/joulescope directory. 
On Windows, this will typically be:

    C:\Users\{user_name}\Documents\joulescope\jslog_{YYYYMMDD_hhmmss}_{pid}.csv

The ".csv" file contains the capture data with columns:

    time,current,voltage,power,charge,energy

All values are in the International System of Units (SI):

    seconds,amperes,volts,watts,coulombs,joules

The script also creates a ".txt" file which contains the state information
for the logging session.
If something happens to the test setup (like the host computer reboots), 
use the "--resume" option to load the configured state for the most
recent session and resume logging. 
Any charge or energy consumed while the test setup was not logging will not 
be recorded to the CSV file.

This implementation handles failure modes including:

* Joulescope reset
* Joulescope unplug/replug
* Temporary loss of USB communication
* Temporary loss of system power (using --resume option)
* Host computer reset (using --resume option)

For long-term logging, even 2 Hz downsampled data can still create too much data:

    2 lines/second * (60 seconds/minute * 60 minutes/hour * 24 hours/day) = 
    172800 lines / day
    
Lines are typically around 80 bytes each which means that this script generates:

    172800 lines/day * 80 bytes/line = 12 MB/day
    12 MB/day * 30.4 days/month = 420 MB/month
    420 MB/month * 12 months/year = 5 GB/year
    
To further reduce the logging rate, use the "--downsample" option.  For example,
"--downsample 120" will log one (1) sample per minute and reduce the overall
file size by a factor of 120.

Here is the example CSV output with the "simple" header and "--downsample 120" for
a 3.3V supply and 1000 Ω resistive load (10.9 mW):

    time,current,voltage,power,charge,energy
    60.0608842,0.00329505,3.2998,0.0108731,0.197703,0.652385
    120.0572884,0.00329549,3.2997,0.0108743,0.395432,1.30484
    180.0513701,0.00329558,3.2998,0.0108748,0.593167,1.95733
    240.0502210,0.00329565,3.2998,0.0108751,0.790906,2.60984
    300.0581367,0.00329583,3.2997,0.0108751,0.988656,3.26234


List of requested future features:
* Specify save path (but can't break resume function!)
* Add higher sample rate (see forum https://forum.joulescope.com/t/joulescope-data-logging/130/10)

"""

import joulescope
import signal
import argparse
import time
import sys
import os
import datetime
import logging
import json
import numpy as np


try:
    from win32com.shell import shell, shellcon
    DOCUMENTS_PATH = shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, None, 0)
    BASE_PATH = os.path.join(DOCUMENTS_PATH, 'joulescope')

except:
    BASE_PATH = os.path.expanduser('~/Documents/joulescope')


MAX_SAMPLES = 1000000000 / 5  # limit to 1 GB of RAM
CSV_SEEK = 4096
LAST_INITIALIZE = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
USER_NOTIFY_INTERVAL_S = 10.0


def now_str():
    d = datetime.datetime.utcnow()
    s = d.strftime('%Y%m%d_%H%M%S')
    return s


def downsample_type_check(string):
    value = int(string)
    if value < 1:
        raise argparse.ArgumentTypeError('%r must be >= 1' % (string, ))
    return value


def get_parser():
    p = argparse.ArgumentParser(
        description='Capture downsampled data.')
    p.add_argument('--header',
                   default='simple',
                   choices=['none', 'simple', 'comment'],
                   help='CSV header option.  '
                        '"none" excludes all header information and just includes data.  '
                        '"simple" (default) adds a first line with column labels.  '
                        '"comment" contains multiple lines starting with "#" and also '
                        'inserts events into the CSV file.  ')
    p.add_argument('--resume', '-r',
                   action='store_true',
                   help='Resume the previous capture and append new data.')
    p.add_argument('--downsample', '-d',
                   default=1,
                   type=downsample_type_check,
                   help='The number of 2 Hz samples to condense into a single sample. '
                        'For example, "--downsample 120" will write 1 sample '
                        'per minute.')
    return p


def _find_files():
    flist = []
    for fname in os.listdir(BASE_PATH):
        if fname.startswith('jslog_') and fname.endswith('.txt'):
            flist.append(fname)
    return sorted(flist)


class Logger:
    """The downsampling logger instance.

    :param header: The CSV header format which is one of ['none', 'simple', 'comment']
    :param downsample: The downsampling factor in samples.
        1 performs no downsampling.
        120 records one sample per minute.
        None (default) is equivalent to 1.
    :param resume: Use False or None to start a new logging session.
        Provide True to resume the most recent logging session.
    """

    def __init__(self, header=None, downsample=None, resume=None):
        self._start_time_s = None
        self._f_csv = None
        self._f_event = None
        self._time_str = None
        self._quit = None
        self.log = logging.getLogger(__name__)
        self._device = None
        self._device_str = None
        self._user_notify_time_last = 0.0
        self._state = self.ST_IDLE
        self._faults = []
        self._resume = bool(resume)
        self._header = header

        self._last = None  # (all values in csv)
        self._offset = [0.0, 0.0, 0.0]  # [time, charge, energy]
        
        self._downsample = 1 if downsample is None else int(downsample)
        self._downsample_counter = 0
        self._downsample_state = np.zeros(3, dtype=np.float)

    ST_IDLE = 0
    ST_ACTIVE = 1

    def __str__(self):
        return f'Logger("{self._time_str}")'

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.close()
        except:
            self.log.exception('While closing during __exit__')

    def open(self):
        self._quit = None
        self._last = None
        os.makedirs(BASE_PATH, exist_ok=True)

        self._start_time_s = time.time()
        self._time_str = now_str()
        base_filename = 'jslog_%s_%s' % (self._time_str, os.getpid(),)
        event_filename = os.path.join(BASE_PATH, base_filename + '.txt')
        csv_filename = os.path.join(BASE_PATH, base_filename + '.csv')

        if self._resume:
            flist = _find_files()
            if not len(flist):
                print('resume specified, but no existing logs found')
            else:
                fname = flist[-1]
                base_filename, _ = os.path.splitext(fname)
                event_filename = os.path.join(BASE_PATH, base_filename + '.txt')
                csv_filename = os.path.join(BASE_PATH, base_filename + '.csv')
                with open(event_filename, 'rt') as f:
                    for line in f:
                        line = line.strip()
                        if ' PARAM : ' in line:
                            name, value = line.split(' PARAM : ')[-1].split('=')
                            if name == 'start_time':
                                self._start_time_s = float(value)
                            elif name == 'start_str':
                                self._time_str = value
                            elif name == 'downsample':
                                self._downsample = int(value)
                        if 'LOGGER : RUN' in line:
                            break
                sz = os.path.getsize(csv_filename)
                self._last = LAST_INITIALIZE
                with open(csv_filename, 'rt') as f:
                    f.seek(max(0, sz - CSV_SEEK))
                    for line in f.readlines()[-1::-1]:
                        if line.startswith('#'):
                            continue
                        self._last = tuple([float(x) for x in line.strip().split(',')])
                        self._offset = [0.0, self._last[-2], self._last[-1]]
                        break

        print(f'Filename: {csv_filename}')
        self._f_csv = open(csv_filename, 'at')
        self._f_event = open(event_filename, 'at')
        self.on_event('LOGGER', 'OPEN')
        self.on_event('PARAM', f'start_time={self._start_time_s}')
        self.on_event('PARAM', f'start_str={self._time_str}')
        self.on_event('PARAM', f'downsample={self._downsample}')

    def close(self):
        self.on_event('LOGGER', 'CLOSE')
        self.device_close()
        if self._f_csv is not None:
            self._f_csv.close()
            self._f_csv = None

        if self._f_event is not None:
            self._f_event.close()
            self._f_event = None

    def on_quit(self, *args, **kwargs):
        self.on_event('SIGNAL', 'SIGINT QUIT')
        self._quit = 'quit from SIGINT'

    def on_stop(self, event=0, message=''):
        # may be called from the Joulescope device thread
        self.on_event('SIGNAL', f'STOP')
        if event is not None and event > 0:
            # unexpected stop, such as device removal
            self._faults.append((event, message))
        else:
            self._quit = 'quit from device stop'

    def on_event(self, name, message):
        if self._f_event is not None:
            d = datetime.datetime.utcnow()
            s = d.strftime('%Y%m%d_%H%M%S.%f')
            s = f'{s} {name} : {message}\n'
            self._f_event.write(s)
            self._f_event.flush()
            if self._f_csv is not None and self._header in ['full', 'comment']:
                self._f_csv.write(f'#& {s}')

    def on_event_cbk(self, event=0, message=''):
        # called from the Joulescope device thread
        self._faults.append((event, message))

    def on_statistics(self, data):
        """Process the next Joulescope downsampled 2 Hz data.

        :param data: The Joulescope statistics data.
            See :meth:`joulescope.View.statistics_get` for details.
        """
        # called from the Joulescope device thread
        now = time.time()
        if self._last is None:
            self._last = LAST_INITIALIZE
            columns = ['time', 'current', 'voltage', 'power', 'charge', 'energy']
            units = ['s',
                     data['signals']['current']['units'],
                     data['signals']['voltage']['units'],
                     data['signals']['power']['units'],
                     data['accumulators']['charge']['units'],
                     data['accumulators']['energy']['units']]
            columns_csv = ','.join(columns)
            units_csv = ','.join(units)
            self.on_event('PARAM', f'columns={columns_csv}')
            self.on_event('PARAM', f'units={units_csv}')
            if self._header in ['simple']:
                self._f_csv.write(f'{columns_csv}\n')
            elif self._header in ['comment', 'full']:
                self._f_csv.write(f'#= header={columns_csv}\n')
                self._f_csv.write(f'#= units={units_csv}\n')
                self._f_csv.write(f'#= start_time={self._start_time_s}\n')
                self._f_csv.write(f'#= start_str={self._time_str}\n')
            self._f_csv.flush()
        t = now - self._start_time_s + self._offset[0]
        i = data['signals']['current']['statistics']['μ']
        v = data['signals']['voltage']['statistics']['μ']
        p = data['signals']['power']['statistics']['μ']
        c = data['accumulators']['charge']['value'] + self._offset[1]
        e = data['accumulators']['energy']['value'] + self._offset[2]
        self._downsample_state += [i, v, p]
        self._downsample_counter += 1
        if self._downsample_counter >= self._downsample:
            s = self._downsample_state / self._downsample_counter
            self._downsample_counter = 0
            self._last = (t, *s, c, e)
            self._downsample_state[:] = 0.0
            self._f_csv.write('%.7f,%g,%.4f,%g,%g,%g\n' % self._last)
            self._f_csv.flush()

    def _device_open(self, device):
        self.on_event('DEVICE', 'OPEN')
        device.open(event_callback_fn=self.on_event_cbk)
        info = device.info()
        self.on_event('DEVICE_INFO', json.dumps(info))
        device.statistics_callback = self.on_statistics
        device.parameter_set('source', 'raw')
        device.parameter_set('i_range', 'auto')
        device.start(stop_fn=self.on_stop)
        self._device = device
        self._device_str = str(self._device)
        self._state = self.ST_ACTIVE
        return self._device

    def device_scan_and_open(self):
        if self._state != self.ST_IDLE:
            return self._device
        devices = joulescope.scan()
        devices_length = len(devices)
        if devices_length == 0:
            time_now = time.time()
            if self._user_notify_time_last + USER_NOTIFY_INTERVAL_S <= time_now:
                self._user_notify_time_last = time_now
                self.log.warning('No Joulescope connected')
        elif devices_length == 1 and self._device_str is None:
            return self._device_open(devices[0])
        elif self._device_str is not None:
            for device in devices:
                if str(device) == self._device_str:
                    return self._device_open(device)
        else:
            self.on_event('SCAN', 'select first device')
            return self._device_open(devices[0])
        return None

    def device_close(self):
        self._state = self.ST_IDLE
        if self._device is None:
            return
        self.on_event('DEVICE', 'CLOSE')
        device, self._device = self._device, None
        try:
            device.close()
        except:
            self.log.exception('during device.close()')

    def run(self):
        self.on_event('LOGGER', 'RUN')
        signal.signal(signal.SIGINT, self.on_quit)
        try:
            while not self._quit:
                self.device_scan_and_open()
                time.sleep(0.1)  # data is received on device's thread
                while len(self._faults):  # handle faults on our thread
                    event, message = self._faults.pop(0)
                    self.on_event('EVENT', f'{event} {message}')
                    if event:
                        self.device_close()
            if self._device:
                try:
                    self._device.stop()
                except:
                    self.log.exception('during device.stop()')
        except Exception as ex:
            self.log.exception('while capturing data')
            self.on_event('FAIL', str(ex))
            return 1
        self.device_close()
        self.on_event('LOGGER', 'DONE')


def run():
    parser = get_parser()
    args = parser.parse_args()
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.WARNING,
        datefmt='%Y-%m-%dT%H:%M:%S')
    print('Starting logging - press CTRL-C to stop')
    with Logger(header=args.header, downsample=args.downsample, resume=args.resume) as logger:
        return logger.run()


if __name__ == '__main__':
    sys.exit(run())
