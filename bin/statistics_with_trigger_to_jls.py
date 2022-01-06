#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2019-2022 Jetperch LLC
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

"""Capture statistics data, analyze for trigger, and capture full-rate data
to JLS v2 file on trigger."""

from joulescope import scan_require_one, JlsWriter
from joulescope.units import duration_to_seconds
import argparse
import datetime
import signal
import time


def now_str():
    d = datetime.datetime.utcnow()
    s = d.strftime('%Y%m%d_%H%M%S')
    return s


class StatisticsWithTrigger:

    def __init__(self, device, duration=120.0, signals='current,voltage'):
        self._device = device
        self._duration = duration
        self._signals = signals
        self._base_filename = now_str()
        self._csv_filename = self._base_filename + '.csv'
        self._csv_file = open(self._csv_filename, 'wt')
        self._jls_writer = None
        self._jls_end = None
        self._jls_idx = 0

    def on_statistics(self, stats):
        """The function called for each statistic update.

        :param stats: The statistics data structure.
        """
        t = stats['time']['range']['value'][0]
        i = stats['signals']['current']['µ']['value']
        v = stats['signals']['voltage']['µ']['value']
        p = stats['signals']['power']['µ']['value']
        c = stats['accumulators']['charge']['value']
        e = stats['accumulators']['energy']['value']
        if self._csv_file:
            self._csv_file.write(f'{t:.1f},{i:.9f},{v:.3f},{p:.9f},{c:.9f},{e:.9f}\n')
            #self._csv_file.write(f'{t},{i},{v},{p},{c},{e}\n')

        # todo replace with custom trigger code
        if self._jls_writer is None and i > 0.001:
            self._capture_start()

    def _capture_start(self):
        print('jls capture start')
        fname = f'{self._base_filename}_{self._jls_idx:04d}.jls'
        self._jls_end = None
        self._jls_writer = JlsWriter(self._device, fname, self._signals)
        self._jls_writer.open()
        self._jls_idx += 1
        self._device.start()

    def _capture_stop(self):
        jls_writer, self._jls_writer = self._jls_writer, None
        if jls_writer is not None:
            print('jls capture stop')
            jls_writer.close()

    def stream_notify(self, stream_buffer):
        # called from USB thead, keep fast!
        # long-running operations will cause sample drops
        start_id, end_id = stream_buffer.sample_id_range
        if self._jls_end is None:
            self._jls_end = end_id + int(self._device.sampling_frequency * self._duration)
        if self._jls_writer is not None:
            self._jls_writer.stream_notify(stream_buffer)
            if end_id >= self._jls_end:
                self._capture_stop()
                return True
        return False

    def close(self):
        f, self._csv_file = self._csv_file, None
        if f is not None:
            f.close()
        if self._jls_writer is not None:
            self._jls_writer.close()


def get_parser():
    p = argparse.ArgumentParser(
        description='Capture Joulescope statistics and trigger to capture full-rate data to JLS v2.')
    p.add_argument('--duration',
                   type=duration_to_seconds,
                   help='The full-rate capture duration in float seconds. '
                   + 'Add a suffix for other units: s=seconds, m=minutes, h=hours, d=days')
    p.add_argument('--signals',
                   default='current,voltage',
                   help='The comma-separated list of signals to capture which include current, voltage, power. '
                   + 'Defaults to current,voltage')
    return p


def run():
    _quit = False

    def stop_fn(*args, **kwargs):
        nonlocal _quit
        _quit = True

    args = get_parser().parse_args()
    signal.signal(signal.SIGINT, stop_fn)  # also quit on CTRL-C
    device = scan_require_one(config='auto')
    try:
        s = StatisticsWithTrigger(device, duration=args.duration, signals=args.signals)
        device.parameter_set('buffer_duration', 2.0)
        device.open()
        device.statistics_callback_register(s.on_statistics, 'sensor')
        device.stream_process_register(s)
        device.parameter_set('i_range', 'auto')
        device.parameter_set('v_range', '15V')
        while not _quit:
            device.status()
            time.sleep(0.1)

    finally:
        device.close()
        s.close()


if __name__ == '__main__':
    run()
