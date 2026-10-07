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

"""Implement host-side detection for driving the JS220 BNC trigger output."""

from pyjoulescope_driver import Driver
import argparse
import logging
import sys
import time
import numpy as np


def get_parser():
    p = argparse.ArgumentParser(
        description='Set trigger output based on data.')
    p.add_argument('--verbose', '-v',
                   action='store_true',
                   help='Display verbose information.')
    p.add_argument('--serial_number',
                   help='The serial number of the Joulescope to use.')
    p.add_argument('--signal',
                   default='i',
                   help='The signal for detection.')
    p.add_argument('--start-duration',
                   type=float,
                   default=0.001,
                   help='The start duration.')
    p.add_argument('--start-threshold',
                   type=float,
                   default=1.0,
                   help='The start threshold for the signal.')
    p.add_argument('--stop-duration',
                   type=float,
                   default=0.001,
                   help='The stop duration.')
    p.add_argument('--stop-threshold',
                   type=float,
                   default=0.1,
                   help='The stop threshold for the signal.')

    return p


# from joulescope_ui.widgets.trigger.condition_detector
class _DetectDuration:

    def __init__(self, duration, fn):
        self._duration = float(duration)
        self._d = 0.0
        self._fn = fn

    def clear(self):
        self._d = 0.0

    def __call__(self, fs, samples):
        s = self._fn(samples)
        edges = np.where(np.diff(s))[0]
        edges = np.concatenate((edges, np.array([len(s) - 1], dtype=edges.dtype)))
        v = s[0]
        edge_last = 0
        for edge in edges:
            if not v:
                self._d = 0.0
            else:
                d = (edge - edge_last + 1) / fs
                if (self._d + d) >= self._duration:
                    idx = int(np.ceil((self._duration - self._d) * fs))
                    self._d = 0.0
                    return edge_last + idx
                self._d += d
            v = not v
            edge_last = edge + 1


class DeviceHandler:

    def __init__(self, jsdrv, device_path, signal, start_condition, stop_condition, verbose):
        self._verbose = verbose
        self._jsdrv = jsdrv
        self.device_path = device_path
        self._mode = 0  # 0=start, 1=stop
        self._ctrl_topic = f"{device_path}/s/{signal}/ctrl"
        self._data_topic = f"{device_path}/s/{signal}/!data"
        self._set_topic = f"{device_path}/s/gpo/+/!set"
        self._clr_topic = f"{device_path}/s/gpo/+/!clr"
        self._trigger_topic = f"{device_path}/s/{signal}/ctrl"
        self._on_data_fn = self._on_data
        # Edit conditions below
        self._start_condition = start_condition
        self._stop_condition = stop_condition
        self._sample_id = None
        self.open()

    def open(self):
        self._jsdrv.subscribe(self._data_topic, ['pub'], self._on_data_fn)
        self._jsdrv.publish(self._ctrl_topic, 1, timeout=0)

    def close(self):
        self._jsdrv.unsubscribe(self._data_topic, self._on_data_fn, timeout=0)
        self._jsdrv.publish(self._ctrl_topic, 0, timeout=0)

    def _on_data(self, topic, value):
        decimate_factor = value['decimate_factor']
        sample_id = value['sample_id'] // decimate_factor
        samples = value['data']
        sample_rate = value['sample_rate'] // decimate_factor
        if self._sample_id is not None:
            if sample_id < self._sample_id:
                print('Unexpected repeat: unhandled')
                return
            elif sample_id > self._sample_id:
                print('Unexpected skip: unhandled')
        sample_count = len(samples)
        offset = 0
        while offset < sample_count:
            if self._mode == 0:  # start
                detector = self._start_condition
                detect_topic = self._set_topic
                state = 'start'
            else:
                detector = self._stop_condition
                detect_topic = self._clr_topic
                state = 'stop'
            k = detector(sample_rate, samples[offset:])
            if k is None:
                return
            self._verbose(f'detected {state}')
            self._jsdrv.publish(detect_topic, 1 << 7, timeout=0)
            offset += k
            self._mode = (self._mode + 1) & 1


def run():
    args = get_parser().parse_args()

    def verbose(msg):
        if args.verbose:
            print(msg)

    with Driver() as jsdrv:
        jsdrv.log_level = 'WARNING'

        verbose('Find the connected devices')
        device_paths = sorted(jsdrv.device_paths())
        if args.serial_number is not None:
            serial_number_suffix = '/' + args.serial_number.lower()
            device_paths = [p for p in device_paths if p.lower().endswith(serial_number_suffix)]
        if len(device_paths) == 0:
            print('Device not found')
            return 1
        verbose(f'Found devices: {device_paths}')

        verbose('Open and configure each device')
        handlers = []
        signal = 'i'
        for device_path in device_paths:
            if 'js220' in device_path:
                jsdrv.open(device_path, mode='defaults')
                jsdrv.publish(f'{device_path}/s/i/range/mode', 'auto')
                jsdrv.publish(f'{device_path}/s/v/range/mode', 'auto')
                jsdrv.publish(f'{device_path}/c/trigger/dir', 1)
                jsdrv.publish(f'{device_path}/s/gpo/+/!set', 1 << 7)
                start_condition = _DetectDuration(args.start_duration, lambda x: x > args.start_threshold)
                stop_condition = _DetectDuration(args.stop_duration, lambda x: x < args.stop_threshold)
                handler = DeviceHandler(jsdrv, device_path, signal, start_condition, stop_condition, verbose)
                handlers.append(handler)
            else:
                print(f'Unsupported device {device_path}: ignore')
                continue

        verbose('Perform the detection')
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            verbose('Closing')
            for handler in handlers:
                handler.close()
                jsdrv.close(handler.device_path)
    return 0


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s %(message)s', level=logging.INFO)
    sys.exit(run())
