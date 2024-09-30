#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

"""Discharge a battery to calculate charge and energy."""

from joulescope import scan
import argparse
import threading


def get_parser():
    p = argparse.ArgumentParser(
        description='Discharge a battery.')
    p.add_argument('voltage',
                   type=float,
                   help='The battery discharge voltage threshold.')
    return p


class BatteryDischargeState:

    def __init__(self, voltage_threshold):
        self.voltage_threshold = voltage_threshold
        self.lock = threading.Lock()
        self.lock.acquire()
        self._stat_first = None
        self._stat_now = None

    def statistics_callback(self, stats):
        """The function called for each statistics.

        :param stats: The statistics data structure.
        """
        if self._stat_first is None:
            self._stat_first = stats
        self._stat_now = stats
        t = stats['time']['range']['value'][0]
        i = stats['signals']['current']['µ']['value']
        v = stats['signals']['voltage']['µ']['value']
        p = stats['signals']['power']['µ']['value']
        c = stats['accumulators']['charge']['value'] - self._stat_first['accumulators']['charge']['value']
        e = stats['accumulators']['energy']['value'] - self._stat_first['accumulators']['energy']['value']
        duration = t - self._stat_first['time']['range']['value'][0]
        print(f'{duration:.1f}: current={i:.9f}, voltage={v:.3f}, power={p:.9f}, charge={c:.9f}, energy={e:.9f}')

        if v <= self.voltage_threshold:
            self.lock.release()

    def wait_for_done(self):
        while not self.lock.acquire(timeout=0.1):
            continue


def run():
    args = get_parser().parse_args()
    devices = scan(config='off')
    if not len(devices):
        print('No Joulescope device found')
        return 1
    device = devices[0]
    s = BatteryDischargeState(args.voltage)
    device.statistics_callback_register(s.statistics_callback, 'sensor')
    device.open()
    try:
        device.parameter_set('i_range', 'auto')
        device.parameter_set('v_range', '15V')
        s.wait_for_done()
        device.parameter_set('i_range', 'off')
    except KeyboardInterrupt:
        print('Interrupted by user')
    finally:
        device.close()


if __name__ == '__main__':
    run()
