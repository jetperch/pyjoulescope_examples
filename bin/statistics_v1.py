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

"""Display sensor-side statistics from the first connected Joulescope."""

from joulescope import scan
import time


def statistics_callback(stats):
    """The function called for each statistics.

    :param stats: The statistics data structure.
    """
    t = stats['time']['range']['value'][0]
    i = stats['signals']['current']['µ']
    v = stats['signals']['voltage']['µ']
    p = stats['signals']['power']['µ']
    c = stats['accumulators']['charge']
    e = stats['accumulators']['energy']

    # replace with your code to handle statistics.
    # Process here or put them in a queue.Queue instance
    # for processing on a separate thread.
    fmts = ['{x:.9f}', '{x:.3f}', '{x:.9f}', '{x:.9f}', '{x:.9f}']
    values = []
    for k, fmt in zip([i, v, p, c, e], fmts):
        value = fmt.format(x=k['value'])
        value = f'{value} {k["units"]}'
        values.append(value)
    ', '.join(values)
    print(f"{t:.1f}: " + ', '.join(values))


def run():
    devices = scan(config='off')
    if not len(devices):
        print('No Joulescope device found')
        return 1
    device = devices[0]
    device.statistics_callback_register(statistics_callback, 'sensor')
    device.open()
    try:
        device.parameter_set('i_range', 'auto')
        device.parameter_set('v_range', '15V')

        # no need to poll device.status() with the v1 backend
        time.sleep(10)   # replace with your code
    finally:
        device.close()


if __name__ == '__main__':
    run()
