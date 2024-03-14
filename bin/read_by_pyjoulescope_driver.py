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

"""Implement a blocking read for pyjoulescope_driver.

The read duration must fit into RAM!  For longer captures, consider
capturing (recording) to a JLS file.
"""

from pyjoulescope_driver import Driver, time64
from pyjoulescope_driver.record import _SIGNALS, _signal_name_map  # refactoring needed!
import argparse
import logging
from queue import Queue, Empty
import sys
import numpy as np


SIGNAL_MAP = _signal_name_map()




def _on_progress(fract):
    # The MIT License (MIT)
    # Copyright (c) 2016 Vladimir Ignatev
    #
    # Permission is hereby granted, free of charge, to any person obtaining
    # a copy of this software and associated documentation files (the "Software"),
    # to deal in the Software without restriction, including without limitation
    # the rights to use, copy, modify, merge, publish, distribute, sublicense,
    # and/or sell copies of the Software, and to permit persons to whom the Software
    # is furnished to do so, subject to the following conditions:
    #
    # The above copyright notice and this permission notice shall be included
    # in all copies or substantial portions of the Software.
    #
    # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
    # INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
    # PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
    # FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT
    # OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
    # OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
    fract = min(max(float(fract), 0.0), 1.0)
    bar_len = 25
    filled_len = int(round(bar_len * fract))
    percents = int(round(100.0 * fract))
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    msg = f'[{bar}] {percents:3d}%\r'
    sys.stdout.write(msg)
    sys.stdout.flush()


def get_parser():
    p = argparse.ArgumentParser(
        description='Read data from connected Joulescopes into RAM.')
    p.add_argument('--verbose', '-v',
                   action='store_true',
                   help='Display verbose information.')
    p.add_argument('--duration', '-d',
                   default=1.0,
                   type=time64.duration_to_seconds,
                   help='The capture duration in float seconds. '
                        + 'Add a suffix for other units: s=seconds, m=minutes, h=hours, d=days. '
                        + 'The available RAM limits the duration.')
    p.add_argument('--serial_number',
                   help='The serial number of the Joulescope for this capture.')
    p.add_argument('--open', '-o',
                   choices=['defaults', 'restore'],
                   default='defaults',
                   help='The device open mode.  Defaults to "defaults".')
    p.add_argument('--signals',
                   default='current,voltage',
                   help='The comma-separated list of signals to capture which include '
                        + 'current, voltage, power, current_range, gpi[0], gpi[1], gpi[2], gpi[3], trigger_in. '
                        + 'You can also use the short form i, v, p, r, 0, 1, 2, 3, T. '
                        + 'Defaults to current,voltage.')
    p.add_argument('--no-progress',
                   action='store_const',
                   default=_on_progress,
                   const=None,
                   help='Skip progress display.')
    return p


def read(jsdrv: Driver, signals, duration: float, on_progress=None):
    """Read data from one or more Joulescopes.

    :param jsdrv: The pyjoulescope_driver.Driver instance.
    :param signals: The list of signals strings given as either
        signal (presumes only one device connected) or
        tuple of (device_prefix, signal).
    :param duration: The capture duration in float seconds.
    :param on_progress: The optional callable(fract) to call with
        progress updates.
    :return: The mapping of (device_prefix, signal) to the data
        for each signal.  Each signal is also a map with keys:
        * device_path
        * signal
        * info
        * utc_range
        * sample_id_range
        * samples: The samples read from the device.
    """
    queue = Queue()
    read_state = {}
    if not callable(on_progress):
        on_progress = lambda x: None

    def signal_configure(signal_full):
        if isinstance(signal_full, str):
            device_path = jsdrv.device_paths()[0]
            signal_name = signal_full
        else:
            device_path, signal_name = signal_full
        info = _SIGNALS[signal_name]
        data_topic = f"{device_path}/{info['data_topic']}"
        ctrl_topic = f"{device_path}/{info['ctrl_topic']}"
        signal_state = {
            'device_path': device_path,
            'signal': signal_name,
            'info': info,
            'data_topic': data_topic,
            'ctrl_topic': ctrl_topic,
        }
        read_state[signal_full] = signal_state

        def data_fn(topic, value):
            # ['sample_id', 'utc', 'field_id', 'index', 'sample_rate', 'decimate_factor', 'time_map', 'data']
            # print(list(value.keys()))
            decimate_factor = value['decimate_factor']
            sample_id = value['sample_id'] // decimate_factor
            samples = value['data']
            if 'utc_range' not in signal_state:
                signal_state['utc_range'] = [value['utc'], value['utc']]
                signal_state['sample_id_range'] = [sample_id, sample_id]
                signal_state['sample_rate'] = value['sample_rate'] // decimate_factor
                sample_count = int((duration + 1.0) * signal_state['sample_rate'] + 1_000_000)
                signal_state['decimate_factor'] = decimate_factor
                signal_state['samples'] = np.empty(sample_count, dtype=samples.dtype)
            sample_id_expect = signal_state['sample_id_range'][-1]
            if sample_id < sample_id_expect:
                print('Unexpected repeat: unhandled')
                return
            elif sample_id > sample_id_expect:
                print(f'Skip: {sample_id} > {sample_id_expect}')
                signal_state['samples'][sample_id_expect:sample_id] = np.nan
            sample_count = len(samples)
            if info['signal_type'] == 'u1':
                sample_count *= 8
            sample_id_offset = sample_id - signal_state['sample_id_range'][0]
            signal_state['samples'][sample_id_offset:(sample_id_offset + len(samples))] = samples
            sample_id_next = sample_id + sample_count
            signal_state['sample_id_range'][-1] = sample_id_next
            signal_state['utc_range'][-1] = (value['utc'] +
                                             int((sample_count / signal_state['sample_rate']) * time64.SECOND))
            queue.put(signal_full)

        def close(utc_range):
            jsdrv.unsubscribe(data_topic, data_fn, timeout=0)
            jsdrv.publish(ctrl_topic, 0)
            signal_state.pop('close', None)

            u0, u1 = utc_range
            a0, a1 = signal_state['utc_range']
            k0, k1 = signal_state['sample_id_range']
            n = k1 - k0
            samples = signal_state['samples']
            if signal_state['info']['signal_type'] == 'u1':
                samples = np.unpackbits(samples, bitorder='little')
            s0 = int(n * ((u0 - a0) / (a1 - a0)))
            s1 = int(n * ((u1 - a0) / (a1 - a0)))
            z0 = int(((s0 - k0) / n) * (a1 - a0)) + a0
            z1 = int(((s1 - k0) / n) * (a1 - a0)) + a0
            sample_id_range = [k0 + s0, k0 + s1]
            signal_state['sample_id_range_decimated'] = sample_id_range
            signal_state['sample_id_range'] = [s * signal_state['decimate_factor'] for s in sample_id_range]
            signal_state['utc_range'] = [z0, z1]
            signal_state['samples'] = samples[s0:s1]

        signal_state['close'] = close
        jsdrv.subscribe(data_topic, ['pub'], data_fn)
        jsdrv.publish(ctrl_topic, 1, timeout=0)

    def time_info():
        utc_entries = [value.get('utc_range') for value in read_state.values()]
        if None in utc_entries:
            utc_start, utc_end = 0, 0
        else:
            utc_start = max([x[0] for x in utc_entries])
            utc_end = min([x[-1] for x in utc_entries])
        return {
            'duration': (utc_end - utc_start) / time64.SECOND,
            'utc_range': [utc_start, utc_end]
        }

    for signal in signals:
        signal_configure(signal)

    while True:
        try:
            queue.get(timeout=0.1)
        except Empty:
            continue
        duration_now = time_info()['duration']
        if duration_now >= duration:
            on_progress(1.0)
            break
        on_progress(duration_now / duration)

    u0, u1 = time_info()['utc_range']
    z1 = u0 + int(duration * time64.SECOND)
    utc_range = [u0, min(u1, z1)]
    for signal in read_state.values():
        signal['close'](utc_range)

    return read_state


def run():
    args = get_parser().parse_args()
    signals = [SIGNAL_MAP[s.lower()] for s in args.signals.split(',')]

    def verbose(msg):
        if args.verbose:
            print(msg)

    with Driver() as jsdrv:
        verbose('Find the connected devices')
        device_paths = sorted(jsdrv.device_paths())
        if args.serial_number is not None:
            serial_number_suffix = '/' + args.serial_number.lower()
            device_paths = [p for p in device_paths if p.lower().endswith(serial_number_suffix)]
        if len(device_paths) == 0:
            print('Device not found')
            return 1
        verbose(f'Found devices: {device_paths}')
        signals_full = []

        verbose('Open and configure each device')
        device_paths_success = []
        for device_path in device_paths:
            jsdrv.open(device_path, mode=args.open)
            if args.open == 'defaults':
                if 'js110' in device_path:
                    jsdrv.publish(f'{device_path}/s/i/range/select', 'auto')
                    jsdrv.publish(f'{device_path}/s/v/range/select', '15 V')
                elif 'js220' in device_path:
                    jsdrv.publish(f'{device_path}/s/i/range/mode', 'auto')
                    jsdrv.publish(f'{device_path}/s/v/range/mode', 'auto')
                else:
                    print(f'Unsupported device {device_path}: ignore')
                    jsdrv.close(device_path)
                    continue
            signals_full.extend([(device_path, signal) for signal in signals])
            device_paths_success.append(device_path)
        device_paths = device_paths_success

        verbose('Perform the sample read')
        try:
            data = read(jsdrv, signals_full, duration=args.duration, on_progress=args.no_progress)
        finally:
            for device_path in device_paths:
                jsdrv.close(device_path)

        verbose('Display the mean (ignoring NaNs) for each signal')
        for key, value in data.items():
            samples = value['samples']
            samples_finite = np.isfinite(samples)
            sample_count = len(samples)
            nan_count = len(samples) - np.count_nonzero(samples_finite)
            nan_percent = nan_count / sample_count * 100

            if nan_count == 0:
                msg = f'{sample_count} samples'
            else:
                msg = f'ignored {nan_count} NaNs in {sample_count} samples => {nan_percent:.2f}%'
            v = np.mean(samples[samples_finite], dtype=np.float64)
            units = value['info']['units']
            print(f'{".".join(key)}: {v:24} {units} | {msg}')

    return 0


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s %(message)s', level=logging.INFO)
    sys.exit(run())
