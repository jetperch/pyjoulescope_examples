#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2019-2020 Jetperch LLC
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

"""Display statistics from all connected Joulescopes."""

from joulescope import scan
import signal
import sys
import queue


def statistics_callback(name, stats):
    """The function called for each statistics.

    :param name: The name of the Joulescope producing this update.
    :param stats: The statistics data structure.
    """
    t = stats['time']['range']['value'][0]
    i = stats['signals']['current']['µ']
    v = stats['signals']['voltage']['µ']
    p = stats['signals']['power']['µ']
    c = stats['accumulators']['charge']
    e = stats['accumulators']['energy']

    fmts = ['{x:.9f}', '{x:.3f}', '{x:.9f}', '{x:.9f}', '{x:.9f}']
    values = []
    for k, fmt in zip([i, v, p, c, e], fmts):
        value = fmt.format(x=k['value'])
        value = f'{value} {k["units"]}'
        values.append(value)
    print(f"{name} {t:.1f}: " + ', '.join(values))


def statistics_callback_factory(device, queue):
    def cbk(data):
        queue.put((str(device), data))  # called from the USB thread
    return cbk


def run():
    _quit = False
    statistics_queue = queue.Queue()  # resynchronize to main thread

    def stop_fn(*args, **kwargs):
        nonlocal _quit
        _quit = True

    signal.signal(signal.SIGINT, stop_fn)  # also quit on CTRL-C
    devices = scan(config='off')
    if not devices:
        print('No Joulescope found')
        return 1
    try:
        for device in devices:
            device.open()
            device.parameter_set('reduction_frequency', '2 Hz')
            device.parameter_set('i_range', 'auto')
            device.parameter_set('v_range', '15V')
            cbk = statistics_callback_factory(device, statistics_queue)
            device.statistics_callback_register(cbk)
        while not _quit:
            removed = [str(device) for device in devices if not device.is_open]
            if removed:  # unplugged, so no more statistics
                print(f'{removed[0]} removed: stop')
                return 1
            try:
                statistics_callback(*statistics_queue.get(timeout=0.1))
            except queue.Empty:
                pass
    finally:
        for device in devices:
            device.close()
    return 0


if __name__ == '__main__':
    sys.exit(run())
