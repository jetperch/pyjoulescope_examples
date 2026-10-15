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
import time
import numpy as np


SIGNAL_MAP = _signal_name_map()
STALL_TIMEOUT = 3.0  # seconds without progress before read() raises


def _time_info(read_state):
    """The window common to every signal, from the UTC ranges seen so far.

    :return: {'duration': seconds, 'utc_range': [start, end]}, both zero
        until every signal has delivered data.
    """
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


def _state_message(read_state, duration, now, reason, detail=''):
    """Describe an incomplete read, one line per signal.

    The lines show each signal's message count, time since its last data,
    and its UTC window relative to the earliest signal start, which tells
    a signal that never delivered data from signals whose UTC windows do
    not overlap and grow together.
    """
    info = _time_info(read_state)
    starts = [s['utc_range'][0] for s in read_state.values() if 'utc_range' in s]
    t0 = min(starts) if starts else 0
    lines = [f'read {reason}: {info["duration"]:.3f} of {duration} s{detail}']
    for s in read_state.values():
        name = f'{s["device_path"]}.{s["signal"]}'
        if 'utc_range' not in s:
            lines.append(f'  {name}: no data')
            continue
        k0, k1 = s['sample_id_range']
        u0, u1 = s['utc_range']
        lines.append(f'  {name}: {s["data_count"]} messages, {k1 - k0} samples, '
                     f'last {now - s["last_data"]:.1f} s ago, '
                     f'utc {(u0 - t0) / time64.SECOND:+.3f} to {(u1 - t0) / time64.SECOND:+.3f} s')
    if starts:
        c0, c1 = info['utc_range']
        lines.append(f'  common window: {(c0 - t0) / time64.SECOND:+.3f} to '
                     f'{(c1 - t0) / time64.SECOND:+.3f} s from {time64.as_isostr(t0)}')
    return '\n'.join(lines)


def _stall_message(read_state, duration, stall_timeout, now):
    return _state_message(read_state, duration, now, 'stalled', f', no progress for {stall_timeout} s')


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
    p.add_argument('--frequency', '-f',
                   type=int,
                   help='The sampling frequency in Hz.')
    p.add_argument('--device',
                   help='The Joulescopes to use, such as "js220", "000415" or "js220-000415". '
                        + 'Defaults to all connected Joulescopes.')
    p.add_argument('--serial-number', '--serial_number', dest='device', help=argparse.SUPPRESS)
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
    p.add_argument('--stall-timeout',
                   type=float,
                   default=STALL_TIMEOUT,
                   help='The seconds without new data or progress before the read fails '
                        f'and reports the state of each signal.  Defaults to {STALL_TIMEOUT}.')
    p.add_argument('--no-progress',
                   action='store_const',
                   default=_on_progress,
                   const=None,
                   help='Skip progress display.')
    return p


def read(jsdrv: Driver, signals, duration: float, on_progress=None, stall_timeout=None):
    """Read data from one or more Joulescopes.

    :param jsdrv: The pyjoulescope_driver.Driver instance.
    :param signals: The list of signals strings given as either
        signal (presumes only one device connected) or
        tuple of (device_prefix, signal).
    :param duration: The capture duration in float seconds.
    :param on_progress: The optional callable(fract) to call with
        progress updates.
    :param stall_timeout: The seconds without progress before this read
        raises RuntimeError with the state of every signal.  None (default)
        uses STALL_TIMEOUT.
    :raise RuntimeError: If the read stalls, the signals' UTC windows do
        not overlap, or a device is removed.
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
            'data_count': 0,
            'last_data': None,  # time.monotonic() of the latest message
        }
        read_state[signal_full] = signal_state

        def data_fn(topic, value):
            # The driver calls this from its own thread, where an exception
            # would only be logged, so pass it to read() to raise.
            try:
                on_data(value)
            except Exception as ex:
                queue.put(ex)

        def on_data(value):
            # ['sample_id', 'utc', 'field_id', 'index', 'sample_rate', 'decimate_factor', 'time_map', 'data']
            # print(list(value.keys()))
            signal_state['data_count'] += 1
            signal_state['last_data'] = time.monotonic()
            decimate_factor = value['decimate_factor']
            sample_id = value['sample_id'] // decimate_factor
            samples = value['data']
            is_digital = (info['signal_type'] == 'u1')  # 8 bits per u8 dtype
            if 'utc_range' not in signal_state:
                signal_state['utc_range'] = [value['utc'], value['utc']]
                signal_state['sample_id_range'] = [sample_id, sample_id]
                signal_state['sample_rate'] = value['sample_rate'] // decimate_factor
                sample_count = int((duration + 1.0) * signal_state['sample_rate'] + 1_000_000)  # over-allocate
                signal_state['decimate_factor'] = decimate_factor
                if is_digital:
                    sample_count //= 8
                signal_state['samples'] = np.empty(sample_count, dtype=samples.dtype)
            sample_id_expect = signal_state['sample_id_range'][-1]
            if sample_id < sample_id_expect:
                print('Unexpected repeat: unhandled')
                return
            elif sample_id > sample_id_expect:
                print(f'Skip {device_path}.{signal_name}: {sample_id} > {sample_id_expect}')
                k0 = signal_state['sample_id_range'][0]
                g0, g1 = sample_id_expect - k0, sample_id - k0
                if is_digital:
                    g0, g1 = g0 // 8, g1 // 8
                is_float = samples.dtype in [np.float32, np.float64, float]
                signal_state['samples'][g0:g1] = np.nan if is_float else 0
            sample_count = len(samples)
            sample_id_offset = sample_id - signal_state['sample_id_range'][0]
            if is_digital:
                sample_id_offset //= 8
                sample_count *= 8
            if sample_id_offset < len(signal_state['samples']):
                e = sample_id_offset + len(samples)
                if e > len(signal_state['samples']):
                    # should not happen since we overallocate the sample buffer
                    signal_state['samples'][sample_id_offset:e] = \
                        samples[:(len(signal_state['samples']) - sample_id_offset)]
                else:
                    signal_state['samples'][sample_id_offset:e] = samples

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
            z0 = int((s0 / n) * (a1 - a0)) + a0
            z1 = int((s1 / n) * (a1 - a0)) + a0
            sample_id_range = [k0 + s0, k0 + s1]
            signal_state['sample_id_range_decimated'] = sample_id_range
            signal_state['sample_id_range'] = [s * signal_state['decimate_factor'] for s in sample_id_range]
            signal_state['utc_range'] = [z0, z1]
            signal_state['samples'] = samples[s0:s1]

        def stop():
            # Leave the instrument idle on an error: a JS220 closed while
            # streaming resets itself a few seconds later.  Wait for the
            # instrument to confirm, or the close can still arrive first.
            jsdrv.unsubscribe(data_topic, data_fn, timeout=0)
            jsdrv.publish(ctrl_topic, 0)

        signal_state['close'] = close
        signal_state['stop'] = stop
        jsdrv.subscribe(data_topic, ['pub'], data_fn)
        jsdrv.publish(ctrl_topic, 1)  # blocking, so it raises if the signal is unavailable

    def time_info():
        return _time_info(read_state)

    if stall_timeout is None:
        stall_timeout = STALL_TIMEOUT
    try:
        for signal in signals:
            signal_configure(signal)
        _wait(jsdrv, read_state, queue, duration, on_progress, stall_timeout, time_info)
    except BaseException:
        for signal_state in read_state.values():
            try:
                signal_state['stop']()
            except Exception:
                pass  # the device may be gone
        raise

    u0, u1 = time_info()['utc_range']
    z1 = u0 + int(duration * time64.SECOND)
    utc_range = [u0, min(u1, z1)]
    for signal in read_state.values():
        signal['close'](utc_range)

    return read_state


def _wait(jsdrv, read_state, queue, duration, on_progress, stall_timeout, time_info):
    """Wait until the window common to every signal reaches the duration."""
    device_paths = {signal['device_path'] for signal in read_state.values()}

    def on_remove(topic, value):  # an unplugged device never sends the remaining data
        if value in device_paths:
            queue.put(RuntimeError(f'{value} removed during the read'))

    duration_prev = None
    t_progress = time.monotonic()
    with jsdrv.subscribe('@/!remove', 'pub', on_remove):
        try:
            while True:
                try:
                    item = queue.get(timeout=0.1)
                except Empty:
                    item = None
                if isinstance(item, Exception):
                    raise item
                duration_now = time_info()['duration']
                if duration_now >= duration:
                    on_progress(1.0)
                    break
                now = time.monotonic()
                if duration_now < -stall_timeout:
                    # Every signal has data, but their UTC windows are far apart: an
                    # instrument's clock is wrong, and the read would wait that long.
                    raise RuntimeError(_state_message(read_state, duration, now, 'failed',
                                                      ", the signals' UTC windows do not overlap"))
                if duration_prev is None or duration_now > duration_prev:
                    duration_prev, t_progress = duration_now, now
                elif now - t_progress >= stall_timeout:
                    # Waiting forever hides which signal stopped, so name them.
                    raise RuntimeError(_stall_message(read_state, duration, stall_timeout, now))
                if item is not None:
                    on_progress(duration_now / duration)
        except KeyboardInterrupt:
            # A read that progresses too slowly, as when the signals' UTC
            # windows start far apart, never stalls: show why on Ctrl-C.
            print(_state_message(read_state, duration, time.monotonic(), 'interrupted'))
            raise


def run():
    args = get_parser().parse_args()
    signals = [SIGNAL_MAP[s.lower()] for s in args.signals.split(',')]

    def verbose(msg):
        if args.verbose:
            print(msg)

    with Driver() as jsdrv:
        jsdrv.log_level = 'WARNING'

        verbose('Find the connected devices')
        device_paths = jsdrv.find_devices(args.device, brand='joulescope')
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
                if device_path.model == 'js110':
                    jsdrv.publish(f'{device_path}/s/i/range/select', 'auto')
                    jsdrv.publish(f'{device_path}/s/v/range/select', '15 V')
                else:  # JS220 and JS320
                    jsdrv.publish(f'{device_path}/s/i/range/mode', 'auto')
                    jsdrv.publish(f'{device_path}/s/v/range/mode', 'auto')
            if args.frequency is not None:
                jsdrv.publish(f'{device_path}/h/fs', int(args.frequency))
            signals_full.extend([(device_path, signal) for signal in signals])
            device_paths_success.append(device_path)
        device_paths = device_paths_success

        verbose('Perform the sample read')
        try:
            data = read(jsdrv, signals_full, duration=args.duration, on_progress=args.no_progress,
                        stall_timeout=args.stall_timeout)
        except RuntimeError as ex:
            print(ex)
            return 1
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
