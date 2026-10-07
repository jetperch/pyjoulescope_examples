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

from joulescope import scan_require_one, JlsWriter
from joulescope.units import duration_to_seconds
import argparse
import signal
import sys
import threading


def get_parser():
    p = argparse.ArgumentParser(
        description='Capture Joulescope samples to a JLS v2.  See https://github.com/jetperch/jls')
    p.add_argument('--duration',
                   type=duration_to_seconds,
                   help='The capture duration in float seconds. '
                   + 'Add a suffix for other units: s=seconds, m=minutes, h=hours, d=days')
    p.add_argument('--signals',
                   default='current,voltage',
                   help='The comma-separated list of signals to capture which include current, voltage, power. '
                   + 'Defaults to current,voltage')
    p.add_argument('filename',
                   help='The JLS filename to record.')
    return p


def run():
    args = get_parser().parse_args()
    done = threading.Event()

    def on_stop(*args, **kwargs):  # on Ctrl-C, and on the USB thread when the device stops
        done.set()

    signal.signal(signal.SIGINT, on_stop)
    device = scan_require_one(config='auto')
    with device:
        with JlsWriter(device, args.filename, signals=args.signals) as p:
            device.stream_process_register(p)
            device.start(stop_fn=on_stop, duration=args.duration)
            print('Capturing data: type CTRL-C to stop')
            while not done.wait(0.1):  # a timeout keeps Ctrl-C responsive
                pass
            device.stop()
            device.stream_process_unregister(p)
    return 0


if __name__ == '__main__':
    sys.exit(run())
