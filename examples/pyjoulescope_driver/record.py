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

"""Record samples from a Joulescope to a JLS v2 file.

This example shows the pyjoulescope_driver Record class.  The record entry
point has more options, such as recording several Joulescopes:

    python -m pyjoulescope_driver record --help

Read the file with pyjls, see https://github.com/jetperch/jls, or plot it
with ../pyjls/jls_plot.py.
"""

from pyjoulescope_driver import Driver, Record, device_filter, time64
import argparse
import sys
import time


def get_parser():
    p = argparse.ArgumentParser(
        description='Record samples from a Joulescope to a JLS v2 file.')
    p.add_argument('filename',
                   help='The JLS filename to record.')
    p.add_argument('--duration',
                   type=time64.duration_to_seconds,
                   help='The recording duration in float seconds. '
                        + 'Add a suffix for other units: s=seconds, m=minutes, h=hours, d=days. '
                        + 'Defaults to until Ctrl+C.')
    p.add_argument('--signals',
                   default='current,voltage',
                   help='The comma-separated signals to record: current, voltage, power, '
                        + 'current_range, gpi[0] to gpi[3] and trigger_in, '
                        + 'or the short names i, v, p, r, 0 to 3 and T.  Defaults to current,voltage.')
    p.add_argument('--device', '-d',
                   help='The Joulescope to use, such as "js220", "000415" or "js220-000415".')
    return p


def run():
    args = get_parser().parse_args()
    with Driver() as d:
        try:
            device_path = d.find_one_device(args.device, brand='joulescope')
        except device_filter.DeviceFilterError as ex:
            print(ex)
            if len(ex.matches) > 1:
                print('Use "--device" to specify the desired device.')
            return 1
        with d.open(device_path, mode='defaults') as device:
            if device_path.model == 'js110':
                device.publish('s/i/range/select', 'auto')
            else:  # the JS220 and JS320 open with the current range off
                device.publish('s/i/range/mode', 'auto')
            try:
                recorder = Record(d, device_path, args.signals)
            except KeyError as ex:
                print(f'Unknown signal {ex}')
                return 1
            recorder.open(args.filename)  # enables the signals and starts recording
            print('Recording.  Press CTRL-C to stop.')
            t_stop = None if args.duration is None else time.monotonic() + args.duration
            try:
                while t_stop is None or time.monotonic() < t_stop:
                    time.sleep(0.05)
            except KeyboardInterrupt:
                pass
            finally:
                recorder.close()  # disables the signals and finishes the file
    return 0


if __name__ == '__main__':
    sys.exit(run())
