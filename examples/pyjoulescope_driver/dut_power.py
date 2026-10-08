#!/usr/bin/env python3

# Copyright 2020-2026 Jetperch LLC
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

"""Control power to the device under test or query power status."""


from pyjoulescope_driver import Driver
import argparse
import sys


ON = ['1', 'on', 'true', 'enable']
OFF = ['0', 'off', 'false', 'disable']


def get_parser():
    p = argparse.ArgumentParser(
        description='Control power to the device under test or query power status.')
    p.add_argument('state',
                   type=str.lower,
                   choices=ON + OFF + ['?'],
                   metavar='state',
                   help='"on" or "off" to set the power, or "?" to display it.  '
                        + 'Also accepts 1, true, enable, 0, false and disable.')
    p.add_argument('--device', '-d',
                   help='The Joulescopes to use, such as "js220", "000415" or "js220-000415". '
                        + 'Defaults to all connected Joulescopes.')
    return p


def _topic(device):
    if device.device_path.model == 'js110':
        return 's/i/range/select'
    else:
        return 's/i/range/mode'


def dut_power_set(device, power_on):
    i_range = 'auto' if power_on else 'off'
    device.publish(_topic(device), i_range)


def dut_power_query(device):
    return 'off' if (0 == device.query(_topic(device))) else 'on'


def run():
    args = get_parser().parse_args()
    with Driver() as jsdrv:
        device_paths = jsdrv.find_devices(args.device, brand='joulescope')
        if not device_paths:
            print('No Joulescope found')
            return 1
        for device_path in device_paths:
            with jsdrv.open(device_path, mode='restore') as device:
                if args.state == '?':
                    print(f'{device_path}: {dut_power_query(device)}')
                else:
                    dut_power_set(device, args.state in ON)
    return 0


if __name__ == '__main__':
    sys.exit(run())
