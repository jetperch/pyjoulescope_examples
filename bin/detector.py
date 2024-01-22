#!/usr/bin/env python3
# Copyright 2024 Jetperch LLC
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

"""Perform real-time current analysis on streaming sample data."""

from pyjoulescope_driver import Driver, time64
import argparse
import logging
import time
import sys
import os


# Force joulescope_examples package to be in Python import path
PROJECT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_PATH)
from joulescope_examples.detectors import WindowThresholdDetector


def get_parser():
    p = argparse.ArgumentParser(
        description='Analyze streaming sample data.')
    p.add_argument('--frequency', '-f',
                   type=int,
                   default=1_000_000,
                   help='The sampling frequency in Hz.')
    p.add_argument('--duration',
                   type=time64.duration_to_seconds,
                   help='The capture duration in float seconds. '
                        + 'Add a suffix for other units: s=seconds, m=minutes, h=hours, d=days')
    p.add_argument('--serial_number',
                   help='The serial number of the Joulescope JS220 to use.')
    return p


class DetectorRunner:

    def __init__(self):
        self._detectors = []

    def _on_data(self, topic, value):
        """Process a block of streaming sample data.

        :param topic: The data topic
        :param value: The streaming sample value dict.
        """
        # caution: called from joulescope_driver thread, do NOT block
        samples = value['data']
        for detector in self._detectors:
            if detector.process(samples):
                # todo perform any desired actions
                print(f'detected {detector.name}')

    def run(self):
        args = get_parser().parse_args()
        data_fn = self._on_data  # bind method for unsub
        frequency = int(args.frequency)

        self._detectors = [
            # todo configure your desired detectors
            WindowThresholdDetector(0.05, 0.5 * frequency, name='1'),
            WindowThresholdDetector(0.01, 1.0 * frequency, name='2'),
        ]

        with Driver() as d:
            devices = d.device_paths()
            devices = [device for device in devices if 'js220' in device]
            if args.serial_number is not None:
                devices = [p for p in devices if p.lower().endswith(args.serial_number.lower())]
            if len(devices) != 1:
                if len(devices) == 0:
                    print('No Joulescope JS220 found')
                    return 1
                else:
                    print('Multiple Joulescope JS220s found')
                    return 1
            device = devices[0]
            d.open(device)
            try:
                # Configure the device, adjust as needed
                d.publish(f'{device}/s/i/range/mode', 'auto')
                d.publish(f'{device}/s/v/range/mode', 'auto')
                d.publish(f'{device}/h/fs', frequency)

                # Subscribe to current data and start current data streaming
                d.subscribe(f'{device}/s/i/!data', ['pub'], data_fn, timeout=0)
                d.publish(f'{device}/s/i/ctrl', 1, timeout=0)

                # process incoming sample data indefinitely
                t_start = time.time()
                while True:
                    duration = time.time() - t_start
                    if args.duration is not None and duration >= args.duration:
                        break
                    try:
                        time.sleep(0.05)  # self._on_data may be called
                    except KeyboardInterrupt:
                        break  # normal CTRL-C exit
            finally:
                d.unsubscribe(f'{device}/s/i/!data', data_fn)
                d.publish(f'{device}/s/i/ctrl', 0, timeout=0)
                d.close(device)
        return 0


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s %(message)s', level=logging.WARNING)
    sys.exit(DetectorRunner().run())
