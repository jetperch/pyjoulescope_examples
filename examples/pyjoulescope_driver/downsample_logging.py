#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2019-2024 Jetperch LLC
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

This script records statistics data to CSV files, one per Joulescope.
The CSV files are automatically named and stored under the
Documents/joulescope directory.  On Windows, this will typically be:

    C:\Users\{user_name}\Documents\joulescope

Each file is name like:

    jslog_{YYYYMMDD_hhmmss}_{pid}_{model}_{serial_number}.csv

The ".csv" file contains the capture data with columns:

    time,current,voltage,power,charge,energy,current_min,current_max

All values are in the International System of Units (SI):

    seconds,amperes,volts,watts,coulombs,joules,amperes,amperes

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

For very long-term logging, even 2 Hz downsampled data may still create
too much data:

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
"""

from pyjoulescope_driver import Driver, time64
import signal
import argparse
import time
import sys
import os
import datetime
import logging
import numpy as np
import queue
import threading


MAX_SAMPLES = 1000000000 / 5  # limit to 1 GB of RAM
CSV_SEEK = 4096
LAST_INITIALIZE = (None, 0.0, 0.0, 0.0, 0.0, 0.0)
USER_NOTIFY_INTERVAL_S = 10.0
FLOAT_MAX = np.finfo(float).max

try:
    from win32com.shell import shell, shellcon
    DOCUMENTS_PATH = shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, None, 0)
    BASE_PATH = os.path.join(DOCUMENTS_PATH, 'joulescope')
except Exception:
    BASE_PATH = os.path.expanduser('~/Documents/joulescope')


def downsample_type_check(string):
    value = int(string)
    if value < 1:
        raise argparse.ArgumentTypeError('%r must be >= 1' % (string, ))
    return value


def joulescope_count_to_str(count):
    if count == 0:
        return 'no Joulescopes'
    elif count == 1:
        return 'one Joulescope'
    else:
        return f'{count} Joulescopes'


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
                   help='The number of frequency samples (2 Hz by default) to '
                        'condense into a single sample. '
                        'For example, "--downsample 120" will write 1 sample '
                        'per minute.')
    p.add_argument('--frequency', '-f',
                   default=2,
                   type=int,
                   help='The base collection frequency in Hz.  Fixed to 2 for JS110.')
    p.add_argument('--duration',
                   type=time64.duration_to_seconds,
                   help='The capture duration in float seconds. '
                   + 'Add a suffix for other units: s=seconds, m=minutes, h=hours, d=days')
    p.add_argument('--time-format', '--time_format',
                   default='utc',
                   choices=['utc', 'relative'],
                   help='The time column format.')
    return p


def _find_files():
    flist = []
    for fname in os.listdir(BASE_PATH):
        if fname.startswith('jslog_') and fname.endswith('.txt'):
            flist.append(fname)
    return sorted(flist)


class Logger:
    """The downsampling logger instance.

    :param args: The parsed arguments.
    """
    def __init__(self, args):
        self.header = args.header
        self.resume = bool(args.resume)
        self.downsample = args.downsample
        self.frequency = args.frequency
        self._duration = args.duration
        self.time_format = args.time_format
        self._start_time_s = None
        self._f_event = None
        self._time_str = None
        self._quit = None
        self.driver = None
        self.log = logging.getLogger(__name__)
        self._devices = {}  # device_topic -> LoggerDevice
        self._user_notify_time_last = 0.0
        self._resync = queue.Queue()
        self.base_filename = None
        self._thread_id = threading.current_thread()

    def __str__(self):
        return f'Logger("{self._time_str}")'

    def _on_resume(self, devices_expected):
        devices = []
        flist = _find_files()
        if not len(flist):
            print('resume specified, but no existing logs found')
            return False
        fname = flist[-1]
        base_filename, _ = os.path.splitext(fname)
        self.base_filename = os.path.join(BASE_PATH, base_filename)
        event_filename = self.base_filename + '.txt'
        print('Resuming ' + event_filename)
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
                        self.downsample = int(value)
                    elif name == 'frequency':
                        self.frequency = int(value)
                    elif name == 'duration':
                        self._duration = None if value == str(None) else float(value)
                    elif name == 'time_format':
                        self.time_format = value
                    else:
                        print(f'PARAM skip {name}')
                if 'DEVICES ' in line:
                    devices = sorted(line.split(' DEVICES : ')[-1].split(','))
                if 'LOGGER : RUN' in line:
                    break
        self._f_event = open(event_filename, 'at')
        self.on_event('LOGGER', 'RESUME')
        if devices_expected is not None and devices != devices_expected:
            self.on_event('LOGGER', f'RESUME_MISMATCH: expected {devices_expected}, found {devices}')
        return True

    def _on_new(self, devices):
        self._start_time_s = time.time()
        self._time_str = datetime.datetime.now(datetime.UTC).strftime('%Y%m%d_%H%M%S')
        base_filename = 'jslog_%s_%s' % (self._time_str.split('.')[0], os.getpid())
        self.base_filename = os.path.join(BASE_PATH, base_filename)
        event_filename = self.base_filename + '.txt'
        self._f_event = open(event_filename, 'at')
        self.on_event('LOGGER', 'OPEN')
        self.on_event('PARAM', f'start_time={self._start_time_s}')
        self.on_event('PARAM', f'start_str={self._time_str}')
        self.on_event('PARAM', f'downsample={self.downsample}')
        self.on_event('PARAM', f'frequency={self.frequency}')
        self.on_event('PARAM', f'duration={self._duration}')
        self.on_event('PARAM', f'time_format={self.time_format}')
        self.on_event('DEVICES', ','.join(devices))

    def open(self):
        self._quit = None
        os.makedirs(BASE_PATH, exist_ok=True)
        self.driver = Driver()
        devices = sorted(self.driver.device_paths())
        self.log.info('Found %d Joulescopes', len(devices))
        print('Found ' + joulescope_count_to_str(len(devices)))
        if self.resume and self._on_resume(devices):
            pass
        else:
            self._on_new(devices)

        for device in devices:
            self._devices[device] = LoggerDevice(self, device, self._start_time_s)
        self.driver.subscribe('@/!add', 'pub', self._on_device_added)
        self.driver.subscribe('@/!remove', 'pub', self._on_device_removed)

    def _on_device_added(self, topic, value):
        self._resync.put(('device_added', value))

    def _on_device_removed(self, topic, value):
        self._resync.put(('device_removed', value))

    def _on_resync(self, resync):
        cmd, value = resync
        if cmd == 'event':
            self._handle_event(*value)
        elif cmd == 'device_added':
            if value in self._devices:
                return
            self._devices[value] = LoggerDevice(self, value, self._start_time_s)
        elif cmd == 'device_removed':
            if value in self._devices:
                self._devices.pop(value).close()
        else:
            print(f'Unsupported command {cmd}')

    def close(self):
        self.on_event('LOGGER', 'CLOSE')
        print(f'duration={time.time() - self._start_time_s:.1f} seconds')
        for device_topic in list(self._devices.keys()):
            msg = self._devices.pop(device_topic).close()
            print(msg)
            self.on_event('SUMMARY', msg)

        driver, self.driver = self.driver, None
        if driver is not None:
            driver.finalize()

        self.on_event('LOGGER', 'DONE')
        f_event, self._f_event = self._f_event, None
        if f_event is not None:
            f_event.close()

    def on_quit(self, *args, **kwargs):
        self.on_event('SIGNAL', 'SIGINT QUIT')

    def _handle_event(self, name, message):
        t_now = datetime.datetime.now(datetime.UTC).isoformat()
        s = f'{t_now} {name} : {message}\n'
        self._f_event.write(s)
        self._f_event.flush()
        if self.header in ['full', 'comment']:
            for device in self._devices.values():
                device.write(f'#& {s}')
        if name == 'SIGNAL':
            self._quit = 'quit from SIGNAL'

    def on_event(self, name, message):
        if self._f_event is None:
            return
        if self._thread_id == threading.current_thread():
            self._handle_event(name, message)
        else:
            self._resync.put(('event', (name, message)))

    def run(self):
        self.on_event('LOGGER', 'RUN_START')
        signal.signal(signal.SIGINT, self.on_quit)
        self.open()
        try:
            while not self._quit:
                duration = time.time() - self._start_time_s
                if self._duration is not None and duration > self._duration:
                    self._quit = True
                    continue
                try:
                    resync = self._resync.get(timeout=0.05)
                    self._on_resync(resync)
                except queue.Empty:
                    pass
        except Exception as ex:
            self.log.exception('while capturing data')
            self.on_event('FAIL', str(ex))
            return 1
        finally:
            self.on_event('LOGGER', 'RUN_DONE')
            self.close()


class LoggerDevice:

    def __init__(self, parent: Logger, device: str, start_time_s: float):
        self._subscribes = []
        self._parent: Logger = parent
        self.device = device
        self.name = device
        self._start_t64 = time64.as_time64(start_time_s)
        self._f_csv = None
        self._t_first = None

        self._stats_count = 0
        self._last = None  # (all values in csv)
        self._offset = [0.0, 0.0]  # [charge, energy]
        self._downsample_counter = 0
        self._downsample_state = {
            'avg': np.zeros(3, dtype=float),
            'min': np.zeros(1, dtype=float),
            'max': np.zeros(1, dtype=float),
        }
        self._downsample_state_reset()

        driver_str, model, sn = self.device.split('/')
        self.name = f'{model}_{sn}'
        fname = self._parent.base_filename + f'_{self.name}.csv'
        parent.on_event('DEVICE', 'OPEN ' + self.device)
        if os.path.isfile(fname):
            sz = os.path.getsize(fname)
            self._last = LAST_INITIALIZE
            with open(fname, 'rt') as f:
                f.seek(max(0, sz - CSV_SEEK))
                for line in f.readlines()[-1::-1]:
                    if line.startswith('#'):
                        continue
                    last_line = line.strip().split(',')
                    self._last = tuple([last_line[0]] + [float(x) for x in last_line[1:]])
                    self._offset = [self._last[-2], self._last[-1]]
                    break
        self._f_csv = open(fname, 'at+')
        d = parent.driver
        d.open(device, mode='restore')
        if model == 'js110':
            if parent.frequency != 2:
                print(f'JS110 only supports frequency 2.  Ignoring frequency {parent.frequency}')
            d.publish(f'{device}/s/i/range/select', 'auto')
            self.subscribe(f'{device}/s/sstats/value', 'pub', self._on_statistics)
        elif model == 'js220':
            d.publish(f'{device}/s/i/range/mode', 'auto')
            d.publish(f'{device}/s/v/range/mode', 'auto')
            scnt = int(round(1_000_000 / parent.frequency))
            d.publish(f'{device}/s/stats/scnt', scnt)
            d.publish(f'{device}/s/stats/ctrl', 1)
            self.subscribe(f'{device}/s/stats/value', 'pub', self._on_statistics)
        else:
            print(f'Skip unsupported device {device}')

    def __str__(self):
        return self.device

    def subscribe(self, topic, flags, fn):
        self._parent.driver.subscribe(topic, flags, fn)
        self._subscribes.append((topic, flags, fn))

    def _downsample_state_reset(self):
        self._downsample_state['avg'][:] = 0.0
        self._downsample_state['min'][:] = FLOAT_MAX
        self._downsample_state['max'][:] = -FLOAT_MAX

    def close(self):
        for topic, flags, fn in self._subscribes:
            self._parent.driver.unsubscribe(topic, fn)
        self._subscribes.clear()
        self._parent.on_event('DEVICE', 'CLOSE ' + self.device)
        if self._last is None:
            msg = f'{self.name}: no data'
        else:
            msg = f'{self.name}: charge={self._last[4]:g}, energy={self._last[5]:g}'
        self._last = None
        try:
            self._parent.driver.close(self.device)
        except Exception:
            pass
        f_csv, self._f_csv = self._f_csv, None
        if f_csv is not None:
            f_csv.close()
        return msg

    def write(self, text):
        if self._f_csv is not None:
            self._f_csv.write(text)

    def _on_statistics(self, topic, value):
        """Process the next Joulescope downsampled 2 Hz data.

        :param value: The Joulescope statistics data.
            See :meth:`joulescope.View.statistics_get` for details.
        """
        # called from the Joulescope device thread
        parent = self._parent
        if self._last is None:
            self._last = LAST_INITIALIZE

            columns = ['time', 'current', 'voltage', 'power', 'charge',
                       'energy', 'current_min', 'current_max']
            units = ['s',
                     value['signals']['current']['avg']['units'],
                     value['signals']['voltage']['avg']['units'],
                     value['signals']['power']['avg']['units'],
                     value['accumulators']['charge']['units'],
                     value['accumulators']['energy']['units'],
                     value['signals']['current']['avg']['units'],
                     value['signals']['current']['avg']['units'],
                     ]
            columns_csv = ','.join(columns)
            units_csv = ','.join(units)
            parent.on_event('PARAM', f'columns={columns_csv}')
            parent.on_event('PARAM', f'units={units_csv}')
            if parent.header in ['simple']:
                self._f_csv.write(f'{columns_csv}\n')
            elif parent.header in ['comment', 'full']:
                self._f_csv.write(f'#= header={columns_csv}\n')
                self._f_csv.write(f'#= units={units_csv}\n')
                self._f_csv.write(f'#= start_time={parent._start_time_s}\n')
                self._f_csv.write(f'#= start_str={parent._time_str}\n')
            self._f_csv.flush()
        t = value['time']['utc']['value'][-1]
        if self._parent.time_format == 'utc':
            t = time64.as_datetime(t).strftime('%Y%m%dT%H%M%S.%fZ')
        else:
            t = f'{(t - self._start_t64) / time64.SECOND:.3f}'
        i = value['signals']['current']['avg']['value']
        v = value['signals']['voltage']['avg']['value']
        p = value['signals']['power']['avg']['value']
        c = value['accumulators']['charge']['value']
        e = value['accumulators']['energy']['value']
        if self._stats_count == 0:
            self._offset[0] -= c
            self._offset[1] -= e
        c += self._offset[0]
        e += self._offset[1]
        i_min = value['signals']['current']['min']['value']
        i_max = value['signals']['current']['max']['value']
        self._stats_count += 1

        self._downsample_state['avg'] += [i, v, p]
        self._downsample_state['min'] = np.minimum([i_min], self._downsample_state['min'])
        self._downsample_state['max'] = np.maximum([i_max], self._downsample_state['max'])
        self._downsample_counter += 1
        if self._downsample_counter >= parent.downsample:
            s = self._downsample_state['avg'] / self._downsample_counter
            self._downsample_counter = 0
            self._last = (t, *s, c, e, *self._downsample_state['min'], *self._downsample_state['max'])
            self._downsample_state_reset()
            self._f_csv.write('%s,%g,%g,%g,%.4f,%g,%g,%g\n' % self._last)
            self._f_csv.flush()


def run():
    parser = get_parser()
    args = parser.parse_args()
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.WARNING,
        datefmt='%Y-%m-%dT%H:%M:%S')
    print(f'Starting logging {f"for {args.time} seconds" if args.duration is not None else ""} - press CTRL-C to stop')
    logger = Logger(args)
    return logger.run()


if __name__ == '__main__':
    sys.exit(run())
