#!/usr/bin/env python3

# Copyright 2026 Jetperch LLC
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

"""Display statistics from Joulescopes with pyjoulescope_driver.

The JS220 and JS320 compute statistics on the instrument.  The JS110
computes them on the host from its current, voltage and power streams.
For the same data as CSV, use the statistics entry point:

    python -m pyjoulescope_driver statistics --help

Press Ctrl+C to stop or specify "--duration" on the command line.
"""

from pyjoulescope_driver import Driver
import argparse
import contextlib
import queue
import sys
import time


SAMPLE_RATE = {'js110': 2_000_000}  # Hz, the s/stats/scnt units.  Others use 1_000_000.


def get_parser():
    p = argparse.ArgumentParser(
        description='Display statistics from Joulescopes with pyjoulescope_driver.')
    p.add_argument('--device', '-d',
                   help='The Joulescopes to use, such as "js220", "000415" or "js220-000415".  '
                        + 'Defaults to all connected Joulescopes.')
    p.add_argument('--duration',
                   type=float,
                   help='The time to display in seconds.  Defaults to until Ctrl+C.')
    p.add_argument('--frequency',
                   type=float,
                   default=2.0,
                   help='The statistics frequency in Hz.')
    return p


def display(device_path, value):
    i = value['signals']['current']['avg']['value']
    v = value['signals']['voltage']['avg']['value']
    p = value['signals']['power']['avg']['value']
    c = value['accumulators']['charge']['value']
    e = value['accumulators']['energy']['value']
    print(f'{device_path}: {i:.9f} A, {v:.3f} V, {p:.9f} W, {c:.9f} C, {e:.9f} J')


def run():
    args = get_parser().parse_args()
    statistics = queue.Queue()  # hand values from the driver thread to this thread

    def on_statistics(topic, value):
        statistics.put((topic.split('/s/stats')[0], value))

    with Driver() as d:
        device_paths = d.find_devices(args.device, brand='joulescope')
        if not device_paths:
            print('No Joulescope found')
            return 1
        with contextlib.ExitStack() as stack:  # closes each device on exit
            for device_path in device_paths:
                device = stack.enter_context(d.open(device_path))
                if device_path.model == 'js110':
                    device.publish('s/i/range/select', 'auto')
                    for signal in ['i', 'v', 'p']:
                        device.publish(f's/{signal}/ctrl', 1)
                else:  # the JS220 and JS320 open with the current range off
                    device.publish('s/i/range/mode', 'auto')
                fs = SAMPLE_RATE.get(device_path.model, 1_000_000)
                device.publish('s/stats/scnt', int(round(fs / args.frequency)))
                device.publish('s/stats/ctrl', 1)
                device.subscribe('s/stats/value', 'pub', on_statistics)

            t_stop = None if args.duration is None else time.monotonic() + args.duration
            try:
                while t_stop is None or time.monotonic() < t_stop:
                    try:
                        display(*statistics.get(timeout=0.1))
                    except queue.Empty:
                        pass  # the timeout keeps Ctrl+C responsive
            except KeyboardInterrupt:
                pass
    return 0


if __name__ == '__main__':
    sys.exit(run())
