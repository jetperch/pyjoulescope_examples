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


def get_parser():
    p = argparse.ArgumentParser(
        description='Discharge a battery.')
    p.add_argument('voltage',
                   type=float,
                   help='The battery discharge voltage threshold.')
    return p


def run():
    args = get_parser().parse_args()
    devices = scan(config='off')
    if not len(devices):
        print('No Joulescope device found')
        return 1
    device = devices[0]
    device.open()
    try:
        device.parameter_set('i_range', 'auto')
        device.parameter_set('v_range', '15V')
        first = None
        for stats in device.statistics_iter():  # on this thread, at 2 Hz
            if first is None:
                first = stats
            t = stats['time']['range']['value'][0]
            i = stats['signals']['current']['µ']['value']
            v = stats['signals']['voltage']['µ']['value']
            p = stats['signals']['power']['µ']['value']
            c = stats['accumulators']['charge']['value'] - first['accumulators']['charge']['value']
            e = stats['accumulators']['energy']['value'] - first['accumulators']['energy']['value']
            duration = t - first['time']['range']['value'][0]
            print(f'{duration:.1f}: current={i:.9f}, voltage={v:.3f}, power={p:.9f}, charge={c:.9f}, energy={e:.9f}')
            if v <= args.voltage:
                device.parameter_set('i_range', 'off')  # disconnect the battery
                break
    except KeyboardInterrupt:
        print('Interrupted by user')
    finally:
        device.close()


if __name__ == '__main__':
    run()
