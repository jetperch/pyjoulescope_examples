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

from pyjoulescope_driver import Driver
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
    p.add_argument('--serial-number',
                   help='The serial number of the Joulescope to use.')
    return p


def run(args=None):
    parser = get_parser()
    args = parser.parse_args(args=args)

    with Driver() as jsdrv:
        # Find and open the first Joulescope
        device_paths = sorted(jsdrv.device_paths())
        if args.serial_number is not None:
            serial_number_suffix = '/' + args.serial_number.lower()
            device_paths = [p for p in device_paths if p.lower().endswith(serial_number_suffix)]
        if len(device_paths) == 0:
            print('Device not found')
            return 1
        if len(device_paths) > 1:
            print(f'Found multiple devices: {device_paths}')
            print('Use "--serial-number" to specify the target Joulescope')
            return 1

        device_path = device_paths[0]
        jsdrv.open(device_path)

        # Configure the instrument
        measure = Measure()
        if 'js110' in device_path:
            jsdrv.publish(f'{device_path}/s/i/range/select', 'auto')
            jsdrv.publish(f'{device_path}/s/v/range/select', '15 V')
            # use host-side statistics
            jsdrv.publish(device_path + '/s/i/ctrl', 'on')
            jsdrv.publish(device_path + '/s/v/ctrl', 'on')
            jsdrv.publish(device_path + '/s/p/ctrl', 'on')
            scnt = int(round(2_000_000 / args.frequency))
            jsdrv.publish(device_path + '/s/stats/scnt', scnt)
            jsdrv.publish(device_path + '/s/stats/ctrl', 'on')
            jsdrv.subscribe(device_path + '/s/stats/value', 'pub', measure.on_statistics)            
        elif 'js220' in device_path:
            jsdrv.publish(f'{device_path}/s/i/range/mode', 'auto')
            jsdrv.publish(f'{device_path}/s/v/range/mode', 'auto')
            # JS220, always sensor-side statistics
            scnt = int(round(1_000_000 / args.frequency))
            jsdrv.publish(device_path + '/s/stats/scnt', scnt)
            jsdrv.publish(device_path + '/s/stats/ctrl', 1)
            jsdrv.subscribe(device_path + '/s/stats/value', 'pub', measure.on_statistics)            

        measure.start()
        
        # replace this sleep and try/except with whatever your code needs to do
        try:
            time.sleep(args.duration)
        except KeyboardInterrupt:
            pass  # or use Ctrl-C

        statistics = measure.stop()
        # display statistics in a friendly format
        print(json.dumps(statistics, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(run())
