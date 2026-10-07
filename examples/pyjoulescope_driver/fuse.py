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


from pyjoulescope_driver import Driver
import argparse
import numpy as np
import time


def get_parser():
    p = argparse.ArgumentParser(
        description='Configure JS220 fuse.')
    p.add_argument('--verbose', '-v',
                   action='store_true',
                   help='Display verbose information.')
    p.add_argument('--serial_number',
                   help='The serial number of the Joulescope to use.')
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
        # find device
        device_paths = sorted(jsdrv.device_paths())
        if args.serial_number is not None:
            serial_number_suffix = '/' + args.serial_number.lower()
            device_paths = [p for p in device_paths if p.lower().endswith(serial_number_suffix)]
        if len(device_paths) == 0:
            print('Device not found')
            return 1
        elif len(device_paths) > 1:
            print(f'Too many devices found: {device_paths}')
            return 1
        device_path = device_paths[0]
        
        def _on_fuse_engaged(topic, value):
            if value:
                print('Fuse engaged!')
                # todo handle fuse engaged condition
                # ... insert your code here ...

                # clear fuse engaged
                jsdrv.publish(topic, 0)
        
        # Open the Joulescope and configure the fuse
        jsdrv.open(device_path, mode='restore')
        fuse_config = fuse_to_config(args.threshold1, args.threshold2, args.duration)
        jsdrv.publish(f'{device_path}/s/fuse/0/en', 0)  # fuse disabled for configuration
        jsdrv.publish(f'{device_path}/s/fuse/0/F', fuse_config['js220_fq'])
        jsdrv.publish(f'{device_path}/s/fuse/0/K', fuse_config['js220_kq'])
        jsdrv.subscribe(f'{device_path}/s/fuse/0/engaged', ['pub'], _on_fuse_engaged)
        jsdrv.publish(f'{device_path}/s/fuse/0/en', 1)  # fuse enabled
        
        # Wait...
        try:
            while 1:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            jsdrv.close(device_path)


if __name__ == '__main__':
    _run()
