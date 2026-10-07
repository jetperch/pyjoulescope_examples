#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2020 Jetperch LLC
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

"""Capture samples to JLS v2 files for all connected Joulescopes.  See https://github.com/jetperch/jls"""

from joulescope import scan, JlsWriter
import argparse
import os
import signal
import sys
import threading


def get_parser():
    p = argparse.ArgumentParser(
        description='Read data from Joulescope.')
    p.add_argument('--duration', '-d',
                   type=lambda d: d if d is None else float(d),
                   help='The capture duration in seconds.')
    p.add_argument('--frequency', '-f',
                   help='The sampling frequency in Hz.')
    p.add_argument('--out', '-o',
                   default='out.jls',
                   help='The output path including filename.')
    return p


def run():
    args = get_parser().parse_args()
    done = threading.Event()

    def on_stop(*args, **kwargs):  # on Ctrl-C, and on the USB thread when a device stops
        done.set()

    filename_base, filename_ext = os.path.splitext(args.out)
    signal.signal(signal.SIGINT, on_stop)
    devices = scan(config='auto')
    if not devices:
        print('No Joulescope found')
        return 1
    items = []

    try:
        for device in devices:
            if args.frequency:
                try:
                    device.parameter_set('sampling_frequency', int(args.frequency))
                except Exception:
                    # bad frequency selected, display warning & exit gracefully
                    freqs = [f[2][0] for f in device.parameters('sampling_frequency').options]
                    print(f'Unsupported frequency selected: {args.frequency}')
                    print(f'Supported frequencies = {freqs}')
                    return 1
            fname = f'{filename_base}_{device.device_serial_number}{filename_ext}'
            device.open()
            recorder = JlsWriter(device, fname)
            recorder.open()
            items.append([device, recorder])
            device.stream_process_register(recorder)

        for device, _ in items:
            device.start(stop_fn=on_stop, duration=args.duration)

        print('Capturing data: type CTRL-C to stop')
        while not done.wait(0.1):  # a timeout keeps Ctrl-C responsive
            pass
    finally:
        for device, recorder in items:
            try:
                device.stop()
                recorder.close()
                device.stream_process_unregister(recorder)
                device.close()
            except Exception:
                print('exception during close')
    return 0


if __name__ == '__main__':
    sys.exit(run())
