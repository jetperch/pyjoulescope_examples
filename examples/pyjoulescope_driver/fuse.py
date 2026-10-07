#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2022-2025 Jetperch LLC
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


from pyjoulescope_driver import Driver, device_filter
import argparse
import numpy as np
import sys
import time


def get_parser():
    p = argparse.ArgumentParser(
        description='Configure JS220 fuse.')
    p.add_argument('--verbose', '-v',
                   action='store_true',
                   help='Display verbose information.')
    p.add_argument('--device', '-d',
                   help='The Joulescope to use, such as "js220", "000415" or "js220-000415".')
    p.add_argument('--serial-number', '--serial_number', dest='device', help=argparse.SUPPRESS)
    p.add_argument('--threshold1',
                   type=float,
                   default=1.0,
                   help='The first fuse threshold.')
    p.add_argument('--threshold2',
                   type=float,
                   default=2.0,
                   help='The second fuse threshold.')
    p.add_argument('--duration',
                   type=float,
                   default=0.1,
                   help='The fuse duration.')
    p.add_argument('--start-threshold',
                   type=float,
                   default=1.0,
                   help='The start threshold for the signal.')
    return p


# ----
# from Joulescope UI: https://github.com/jetperch/pyjoulescope_ui/blob/main/joulescope_ui/devices/jsdrv/js220_fuse.py


def fuse_to_config(threshold1, threshold2, duration):
    """Configure thresholds and duration to K, T.

    :param threshold1: The first threshold.
    :param threshold2: The second threshold.
    :param duration: The duration to trip at constant threshold2 input.
    :return: dict containing keys K, T, F, tau
    """
    _I_SUM_LEN = 61
    _JS220_Fq = 14  # 4q14
    _JS220_Kq = 10  # 8q10
    _DT = 2**-14
    
    def to_q(value, q):
        return int(value * 2**int(q) + 0.5)
    
    t1 = threshold1
    t2 = threshold2
    d = duration
    L2 = t1 ** 2
    M2 = t2 ** 2
    K = (-1 / d) * np.log((M2 - L2) / M2)
    T = L2 / K
    F = 1 / (_I_SUM_LEN * np.sqrt(T))
    tau = - _DT / np.log(1 - K * _DT)
    return {
        'threshold1': t1,
        'threshold2': t2,
        'duration': d,
        'K': K,
        'T': T,
        'F': F,
        'tau': tau,
        'js220_fq': to_q(F, _JS220_Fq),
        'js220_kq': to_q(K, _JS220_Kq),
    }

# ----


def _run():
    args = get_parser().parse_args()
    
    def verbose(msg):
        if args.verbose:
            print(msg)
    
    with Driver() as jsdrv:
        try:
            device_path = jsdrv.find_one_device(args.device, brand='joulescope')
        except device_filter.DeviceFilterError as ex:
            print(ex)
            if len(ex.matches) > 1:
                print('Use "--device" to specify the desired device.')
            return 1
        if device_path.model == 'js110':
            print(f'{device_path} has no fuse: use a JS220 or JS320')
            return 1

        def _on_fuse_engaged(topic, value):
            # called from the driver thread, so publish with timeout=0
            if value:
                print('Fuse engaged!')
                # todo handle fuse engaged condition
                # ... insert your code here ...

                # clear fuse engaged
                jsdrv.publish(topic, 0, timeout=0)

        # Open the Joulescope and configure the fuse
        with jsdrv.open(device_path, mode='restore') as device:
            fuse_config = fuse_to_config(args.threshold1, args.threshold2, args.duration)
            device.publish('s/fuse/0/en', 0)  # fuse disabled for configuration
            device.publish('s/fuse/0/F', fuse_config['js220_fq'])
            device.publish('s/fuse/0/K', fuse_config['js220_kq'])
            device.subscribe('s/fuse/0/engaged', 'pub', _on_fuse_engaged)
            device.publish('s/fuse/0/en', 1)  # fuse enabled
            verbose(f'Fuse enabled on {device_path}.  Press CTRL-C to exit.')

            # Wait...
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass


if __name__ == '__main__':
    sys.exit(_run())
