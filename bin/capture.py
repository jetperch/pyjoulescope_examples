#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2020-2021 Jetperch LLC
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

"""Capture Joulescope data to a JLS v2 file.  See https://github.com/jetperch/jls"""

from joulescope import scan, scan_require_one, JlsWriter
from joulescope.data_recorder import DataRecorder
from joulescope.units import duration_to_seconds
import argparse
import signal
import time


SIGNALS = {
    'current': (1, 'A'),
    'voltage': (2, 'V'),
    'power': (3, 'W'),
}


def get_parser():
    p = argparse.ArgumentParser(
        description='Capture Joulescope samples to a JLS file.')
    p.add_argument('--duration',
                   type=duration_to_seconds,
                   help='The capture duration in float seconds. '
                   + 'Add a suffix for other units: s=seconds, m=minutes, h=hours, d=days')
    p.add_argument('--frequency', '-f',
                   help='The sampling frequency in Hz.')
    p.add_argument('--jls',
                   default=1,
                   type=int,
                   choices=[1, 2],
                   help='The JLS file format version.  For v2, see https://github.com/jetperch/jls')
    p.add_argument('--serial_number',
                   help='The serial number of the Joulescope for this capture.')
    p.add_argument('--signals',
                   default='current,voltage',
                   help='The comma-separated list of signals to capture which include current, voltage, power. '
                   + 'Defaults to current,voltage.  This setting only applies to jls v2.')
    p.add_argument('filename',
                   help='The JLS filename to record.')
    return p


def scan_by_serial_number(serial_number, name: str = None, config=None):
    devices = scan(name, config)
    for device in devices:
        if serial_number == device.device_serial_number:
            return device
    raise KeyError(f'Device not found with serial number {serial_number}')


def run():
    quit_ = False
    args = get_parser().parse_args()
    duration = args.duration

    def do_quit(*args, **kwargs):
        nonlocal quit_
        quit_ = 'quit from SIGINT'

    signal.signal(signal.SIGINT, do_quit)
    
    if args.serial_number is not None:
        device = scan_by_serial_number(args.serial_number, config='auto')
    else:
        device = scan_require_one(config='auto')

    if args.frequency:
        try:
            device.parameter_set('sampling_frequency', int(args.frequency))
        except Exception:
            # bad frequency selected, display warning & exit gracefully
            freqs = [f[2][0] for f in device.parameters('sampling_frequency').options]
            print(f'Unsupported frequency selected: {args.frequency}')
            print(f'Supported frequencies = {freqs}')
            return 1

    with device:
        if args.jls == 1:
            recorder = DataRecorder(args.filename, calibration=device.calibration)
        else:
            recorder = JlsWriter(device, args.filename, signals=args.signals)
            recorder.open()
        try:
            device.stream_process_register(recorder)
            t_stop = None if duration is None else time.time() + duration
            device.start()
            print(f'Capturing data from {device}: type CTRL-C to stop')
            while not quit_:
                time.sleep(0.01)
                if t_stop and time.time() > t_stop:
                    break
            device.stop()
        finally:
            recorder.close()
    return 0


if __name__ == '__main__':
    run()
