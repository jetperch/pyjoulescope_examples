#!/usr/bin/env python3

# Copyright 2026 Jetperch LLC
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

"""Display Joulescopes as they connect and disconnect.

Press Ctrl+C to stop or specify "--duration" on the command line.
"""

from pyjoulescope_driver import Driver
import argparse
import queue
import sys
import time


def get_parser():
    p = argparse.ArgumentParser(
        description='Display Joulescopes as they connect and disconnect.')
    p.add_argument('--device', '-d',
                   help='The Joulescopes to watch, such as "js220", "000415" or "js220-000415".  '
                        + 'Defaults to all Joulescopes.')
    p.add_argument('--duration',
                   type=float,
                   help='The time to watch in seconds.  Defaults to until Ctrl+C.')
    return p


def run():
    args = get_parser().parse_args()
    # The driver calls on_add and on_remove from its own thread, where they
    # must not block.  Hand each change to this thread instead, which may
    # then open the device.
    changes = queue.Queue()

    def on_add(device_path):
        changes.put(('add', device_path))

    def on_remove(device_path):
        changes.put(('remove', device_path))

    with Driver() as d:
        # Calls on_add for each connected device, then on_add and
        # on_remove for each later change.  Exiting the block stops watching.
        with d.device_watch(on_add, on_remove, args.device, brand='joulescope'):
            t_stop = None if args.duration is None else time.monotonic() + args.duration
            try:
                while t_stop is None or time.monotonic() < t_stop:
                    try:
                        change, device_path = changes.get(timeout=0.1)
                    except queue.Empty:
                        continue  # the timeout keeps Ctrl+C responsive
                    print(f'{change} {device_path}')
            except KeyboardInterrupt:
                pass
    return 0


if __name__ == '__main__':
    sys.exit(run())
