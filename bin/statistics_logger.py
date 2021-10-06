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
import argparse
import signal
import time
import queue


CONSOLE_FMT = '{t_delta:.3f},{i:.9f},{v:.3f}'
CONSOLE_JOIN = ','
FILE_FMT = '{t_delta:.3f},{i:.9f},{v:.3f}'
FILE_JOIN = ','


def get_parser():
    p = argparse.ArgumentParser(
        description='Display and record statistics data from multiple Joulescopes.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('--out', '-o',
                   help='The output file.')
    p.add_argument('--console_fmt',
                   default=CONSOLE_FMT,
                   help='The console formatting string')
    p.add_argument('--console_join',
                   default=CONSOLE_JOIN,
                   help='The console join string')
    p.add_argument('--file_fmt',
                   default=FILE_FMT,
                   help='The file formatting string')
    p.add_argument('--file_join',
                   default=FILE_JOIN,
                   help='The file join string')
    return p


def statistics_callback(serial_number, stats):
    """The function called for each statistics.

    :param serial_number: The serial number producing with this update.
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
    ', '.join(values)
    print(f"{serial_number} {t:.1f}: " + ', '.join(values))


def statistics_callback_factory(device, queue):
    def cbk(data, indicator=None):
        serial_number = str(device).split(':')[-1]
        data['time']['host'] = {'value': time.time(), 'units': 's'}  # from the POSIX epoch
        queue.put((serial_number, data))
    return cbk


def handle_queue(q):
    while True:
        try:
            args = q.get(block=False)
            statistics_callback(*args)
        except queue.Empty:
            return  # no more data


def run():
    _quit = False
    args = get_parser().parse_args()
    statistics_queue = queue.Queue()  # resynchronize to main thread
    f_out = None

    def stop_fn(*args, **kwargs):
        nonlocal _quit
        _quit = True

    signal.signal(signal.SIGINT, stop_fn)  # also quit on CTRL-C
    devices = scan(config='off')
    status_data = {}

    if args.out:
        f_out = open(args.out, 'wt')

    try:
        for device in devices:
            cbk = statistics_callback_factory(device, statistics_queue)
            device.statistics_callback_register(cbk, 'sensor')
            device.open()
            device.parameter_set('i_range', 'auto')
            device.parameter_set('v_range', '15V')
            serial_number = str(device).split(':')[-1]
            status_data[serial_number] = None

        print('Joulescopes: %s' % (','.join(status_data.keys()), ))
        t_start = time.time()

        while not _quit:
            for device in devices:
                device.status()

            # fetch data from the queue
            while not _quit:
                try:
                    serial_number, data = statistics_queue.get(block=False)
                    status_data[serial_number] = data
                except queue.Empty:
                    break  # no more data

            if all(status_data.values()):  # process update now
                t = time.time() - 0.5  # 2 Hz
                t_relative = t - t_start
                console_txt = ['{t:.3f}'.format(t=t_relative)]  # initialize with prefix
                file_txt = ['{t:.3f}'.format(t=t_relative)]     # initialize with prefix
                for serial_number, data in status_data.items():
                    fmt_data = {
                        't_delta': data['time']['host']['value'] - t,
                        'i': data['signals']['current']['µ']['value'],
                        'v': data['signals']['voltage']['µ']['value'],
                        'p': data['signals']['power']['µ']['value'],
                        'c': data['accumulators']['charge']['value'],
                        'e': data['accumulators']['energy']['value'],
                    }
                    console_txt.append(args.console_fmt.format(**fmt_data))
                    file_txt.append(args.console_fmt.format(**fmt_data))
                    status_data[serial_number] = None  # clear entry
                print(args.console_join.join(console_txt))
                if f_out:
                    f_out.write(args.file_join.join(file_txt) + '\n')

            time.sleep(0.01)

    finally:
        for device in devices:
            device.close()


if __name__ == '__main__':
    run()
