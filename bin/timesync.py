#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2024-2025 Jetperch LLC
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

"""Quantify time synchronization performance between multiple Joulescopes."""

from pyjoulescope_driver import Driver, time64
import argparse
import logging
import sys
import time
import numpy as np


def get_parser():
    p = argparse.ArgumentParser(
        description='Quantify time synchronization.')
    p.add_argument('--verbose', '-v',
                   action='store_true',
                   help='Display verbose information.')
    p.add_argument('--vref',
                   choices=['external', '3v3'],
                   default='3v3',
                   help='Selected the GPI Vref source.')
    p.add_argument('--out',
                   help='The option output CSV file.')

    return p


def detect_match(data):
    for topic, d in data.items():
        detect = d['detect']
        if detect is None:
            return None

    # use python's infinite precision integer type (intentionally avoid numpy)
    t_raw = [d['detect'] for d in data.values()]
    t_mean = sum(t_raw) // len(t_raw)
    t = [(x - t_mean) * (1e6 / time64.SECOND) for x in t_raw]
    t_raw_str = ','.join([str(x) for x in t_raw])
    t_us_str = ','.join([f'{x:.1f}' for x in t])
    row = f'{time64.as_datetime(t_mean).isoformat()},{t_mean},{t_raw_str},{t_us_str}'

    for topic, d in data.items():
        d['detect'] = None

    return row


def run():
    args = get_parser().parse_args()
    data = {}
    row_idx = 0

    if args.out:
        fout = open(args.out, 'wt')
    else:
        fout = None

    def verbose(msg):
        if args.verbose:
            print(msg)

    def on_data(topic, value):
        nonlocal row_idx
        if topic not in data:
            data[topic] = {
                'value_last': 0,
                'detect': None,
            }
        d = data[topic]
        k = np.unpackbits(value['data'], bitorder='little')
        found = None
        if d['value_last'] == 0 and k[0] == 1:
            found = 0  # found first sample
        elif k[0] == 0:
            idx = np.where(k)[0]
            if len(idx):
                found = idx[0]
        if found:
            sample_id = value['sample_id'] + found
            time_map = value['time_map']
            dc = sample_id - time_map['offset_counter']
            utc = time_map['offset_time']
            utc += int(dc / time_map['counter_rate'] * time64.SECOND)
            d['detect'] = utc
            rv = detect_match(data)
            if rv is not None and fout:
                if row_idx == 0:
                    devices = []
                    for k in data.keys():
                        p = k.split('/')
                        devices.append(f'{p[1]}-{p[2]}')
                    devices_str = ','.join(devices)
                    fout.write(f'time,time64,{devices_str},{devices_str}')
                    fout.flush()
                fout.write(f'{rv}\n')
                row_idx += 1
                print(rv)

    with Driver() as jsdrv:
        jsdrv.log_level = 'WARNING'

        verbose('Find the connected devices')
        device_paths = sorted(jsdrv.device_paths())
        verbose(f'Found devices: {device_paths}')

        verbose('Open and configure each device')
        for device_path in device_paths:
            if 'js220' in device_path:
                jsdrv.open(device_path, mode='defaults')
                jsdrv.publish(f'{device_path}/s/i/range/mode', 'auto')
                jsdrv.publish(f'{device_path}/s/i/ctrl', 'on')
                jsdrv.publish(f'{device_path}/s/v/ctrl', 'on')
                jsdrv.publish(f'{device_path}/c/gpio/vref', args.vref)
                jsdrv.subscribe(f'{device_path}/s/gpi/0/!data', ['pub'], on_data)
                jsdrv.publish(f'{device_path}/s/gpi/0/ctrl', 'on')
            else:
                print(f'Unsupported device {device_path}: ignore')
                continue

        verbose('Monitor each device')
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            verbose('Closing')
            for device_path in device_paths:
                jsdrv.publish(f'{device_path}/s/gpi/0/ctrl', 'off')
                jsdrv.publish(f'{device_path}/s/i/ctrl', 'off')
                jsdrv.publish(f'{device_path}/s/v/ctrl', 'off')
                jsdrv.unsubscribe(f'{device_path}/s/gpi/0/!data', on_data)
                jsdrv.close(device_path)
    return 0


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s %(message)s', level=logging.INFO)
    sys.exit(run())
