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

"""Perform an at-will unbounded statistics measurement.

Press Ctrl+C to stop or specify "--duration" on the command line.
"""

from pyjoulescope_driver import Driver, device_filter
import argparse
import json
import numpy as np
import sys
import time


class Measure:
    """Perform an at-will Joulescope measurement using statistics."""

    def __init__(self):
        self._capture = False
        self._statistics = None
        self._accumulator_offsets = {}
        
    def on_statistics(self, topic, value):
        if not self._capture:
            return
        stats = value
        if self._statistics is None:
            self._statistics = stats
            # initial accumulator offsets
            for field, v in stats['accumulators'].items():
                self._accumulator_offsets[field] = v['value']
        else:
            # Accumulate the new statistics value
            # The following code is from the Joulescope UI Multimeter/Value widget
            # https://github.com/jetperch/pyjoulescope_ui/blob/f6d2d5b1bf6d0de6f491e6dd36b6b915aa962bd3/joulescope_ui/widgets/value/value_widget.py#L593
            v_start, v_end = self._statistics['time']['samples']['value']
            v_duration = v_end - v_start
            x_start, x_end = stats['time']['samples']['value']
            x_duration = x_end - x_start
            for signal_name, v in self._statistics['signals'].items():
                x = stats['signals'][signal_name]
                x_min, x_max = x['min']['value'], x['max']['value']
                if np.isfinite(x_min) and np.isfinite(x_max):
                    v['min']['value'] = min(v['min']['value'], x_min)
                    v['max']['value'] = max(v['max']['value'], x_max)
                    v['p2p']['value'] = v['max']['value'] - v['min']['value']
                x_avg, x_std = x['avg']['value'], x['std']['value']
                if np.isfinite(x_avg) and np.isfinite(x_std):
                    v_avg, v_std = v['avg']['value'], v['std']['value']
                    avg = v_avg + ((x_avg - v_avg) * (x_duration / (x_duration + v_duration)))
                    v['avg']['value'] = avg
                    x_diff = x_avg - avg
                    v_diff = v_avg - avg
                    x_var = x_std * x_std
                    v_var = v_std * v_std
                    s = ((v_var + v_diff * v_diff) * v_duration +
                         (x_var + x_diff * x_diff) * x_duration)
                    v['std']['value'] = np.sqrt(s / (x_duration + v_duration - 1))
            self._statistics['time']['accum_samples'] = stats['time']['accum_samples']
            self._statistics['accumulators'] = stats['accumulators']
            self._statistics['time']['samples']['value'] = [v_start, x_end]

        # adjust accumulators by their initial offsets
        for field, v in self._statistics['accumulators'].items():
            v['value'] -= self._accumulator_offsets[field]
        
    def start(self):
        self._statistics = None
        self._capture = True
        
    def stop(self):
        self._capture = False
        return self._statistics
    
    def value(self):
        return self._statistics


def get_parser():
    p = argparse.ArgumentParser(
        description='Perform an at-will unbounded statistics measurement.')
    p.add_argument('--duration',
                   type=float,
                   default=60 * 60 * 24 * 365 * 250,  # 250 years = forever
                   help='The measurement duration in seconds.')
    p.add_argument('--frequency',
                   type=int,
                   default=100,
                   help='The internal statistics frequency.')
    p.add_argument('--device', '-d',
                   help='The Joulescope to use, such as "js220", "000415" or "js220-000415".')
    p.add_argument('--serial-number', '--serial_number', dest='device', help=argparse.SUPPRESS)
    return p


def run(args=None):
    parser = get_parser()
    args = parser.parse_args(args=args)

    with Driver() as jsdrv:
        try:
            device_path = jsdrv.find_one_device(args.device, brand='joulescope')
        except device_filter.DeviceFilterError as ex:
            print(ex)
            if len(ex.matches) > 1:
                print('Use "--device" to specify the desired device.')
            return 1

        measure = Measure()
        with jsdrv.open(device_path) as device:  # topics are relative to device_path
            if device_path.model == 'js110':
                device.publish('s/i/range/select', 'auto')
                device.publish('s/v/range/select', '15 V')
                # use host-side statistics
                device.publish('s/i/ctrl', 'on')
                device.publish('s/v/ctrl', 'on')
                device.publish('s/p/ctrl', 'on')
                scnt = int(round(2_000_000 / args.frequency))
                device.publish('s/stats/scnt', scnt)
                device.publish('s/stats/ctrl', 'on')
                device.subscribe('s/stats/value', 'pub', measure.on_statistics)
            else:
                device.publish('s/i/range/mode', 'auto')
                device.publish('s/v/range/mode', 'auto')
                # The JS220 and JS320 compute statistics on the instrument
                scnt = int(round(1_000_000 / args.frequency))
                device.publish('s/stats/scnt', scnt)
                device.publish('s/stats/ctrl', 1)
                device.subscribe('s/stats/value', 'pub', measure.on_statistics)

            measure.start()
            removed = []

            def on_remove(topic, value):  # an unplugged device sends no more data, so stop
                if value in [device_path]:
                    removed.append(value)

            # replace this loop and try/except with whatever your code needs to do
            t_stop = time.monotonic() + args.duration
            try:
                with jsdrv.subscribe('@/!remove', 'pub', on_remove):
                    while not removed and time.monotonic() < t_stop:
                        time.sleep(0.05)
            except KeyboardInterrupt:
                pass  # or use Ctrl-C

            statistics = measure.stop()
            if removed:
                print(f'{removed[0]} removed: stop')
                return 1
        # display statistics in a friendly format
        print(json.dumps(statistics, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(run())
