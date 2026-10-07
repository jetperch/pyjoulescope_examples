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

"""List the connected Joulescopes, or display the information for one.

usage: python scan.py
usage: python scan.py {device}

{device} selects one Joulescope by serial number, such as "000415",
by model, such as "js220", or by both, such as "js220-000415".
"""

import joulescope
import sys


def run():
    if len(sys.argv) < 2:
        for device in joulescope.scan():
            print(device)
        return 0
    try:
        device = joulescope.scan_require_one(sys.argv[1])
    except joulescope.ScanError as ex:
        print(ex)  # lists the available devices
        return 1
    with device:
        print(device.info())
    return 0


if __name__ == '__main__':
    sys.exit(run())
