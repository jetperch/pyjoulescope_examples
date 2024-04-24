#!/usr/bin/env python3

# Copyright 2020-2024 Jetperch LLC
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
import time
import sys


_USAGE = "usage: dut_power.py [on | off | ?]"


def _topic(device_path):
    if 'js110' in device_path:
        return device_path + '/s/i/range/select'
    else:
        return device_path + '/s/i/range/mode'


def dut_power_set(jsdrv, device_path, power_on):
    i_range = 'auto' if power_on else 'off'
    jsdrv.publish(_topic(device_path), i_range)


def dut_power_query(jsdrv, device_path):
    return 'off' if (0 == jsdrv.query(_topic(device_path))) else 'on'


def run():
    if len(sys.argv) != 2:
        print(_USAGE)
    arg = sys.argv[1].lower()
    with Driver() as jsdrv:
        for device_path in sorted(jsdrv.device_paths()):
            jsdrv.open(device_path, mode='restore')
            if arg in ['1', 'on', 'true', 'enable']:
                dut_power_set(jsdrv, device_path, True)
            elif arg in ['0', 'off', 'false', 'disable']:
                dut_power_set(jsdrv, device_path, False)
            elif arg in ['?']:
                print(f'{device_path}: {dut_power_query(jsdrv, device_path)}')
            else:
                print(_USAGE)
                return 1
            jsdrv.close(device_path)
    return 0


if __name__ == '__main__':
    sys.exit(run())
