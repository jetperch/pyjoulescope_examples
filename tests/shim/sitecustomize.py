# SPDX-FileCopyrightText: Copyright 2026 Jetperch LLC
# SPDX-License-Identifier: Apache-2.0
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

"""Limit the devices that an example under test can see.

The test runner puts this directory on PYTHONPATH, so Python imports this
module at startup, before the example.  When JOULESCOPE_EXAMPLES_VISIBLE is
set, it replaces pyjoulescope_driver.Driver with a subclass that only
reports the devices matching that device specification.  An empty value
hides every device.

This stands in for the USB bus, not for the example: the example still
runs unmodified, against the real driver, with real devices.  It lets the
tests show the behavior with no instrument attached while one is attached,
and keeps an example that uses every device away from bench devices that
are not under test.

When JOULESCOPE_EXAMPLES_HOTPLUG is also set, such as "add@2,remove@5",
the visible devices appear and disappear at those times in seconds after
startup.  The shim reports each change to "@/!add" and "@/!remove"
subscribers, the same as the driver does for a USB hotplug.  It does not
stop the device, so a stream continues, unlike a real unplug.  The
visible specification must list full device paths.

When JOULESCOPE_EXAMPLES_OPEN_FAIL is set, such as "2", those calls to
Driver.open, counting from 1, raise TimeoutError, as when an instrument
disappears while it opens.

When JOULESCOPE_EXAMPLES_DATA_FAULT is set, such as "drop@3" or
"corrupt@3", each subscriber to a "!data" topic loses that message,
counting from 1, as when USB drops a packet, or receives it with
"data" set to None, as a malformed message.

When JOULESCOPE_EXAMPLES_DOCUMENTS is set, it also stands in for the
user's Documents folder, so that examples that write there, such as
downsample_logging.py, never touch the real one.
"""

import os
import threading
import time

_SPEC = os.environ.get('JOULESCOPE_EXAMPLES_VISIBLE')
_HOTPLUG = os.environ.get('JOULESCOPE_EXAMPLES_HOTPLUG')
_OPEN_FAIL = os.environ.get('JOULESCOPE_EXAMPLES_OPEN_FAIL')
_DOCUMENTS = os.environ.get('JOULESCOPE_EXAMPLES_DOCUMENTS')
_DATA_FAULT = os.environ.get('JOULESCOPE_EXAMPLES_DATA_FAULT')


def _documents_install(path):
    try:
        from win32com.shell import shell, shellcon
    except ImportError:
        return  # examples fall back to ~/Documents, so the tests set HOME
    get_folder_path = shell.SHGetFolderPath

    def fn(hwnd, csidl, token, flags):
        if csidl == shellcon.CSIDL_PERSONAL:
            return path
        return get_folder_path(hwnd, csidl, token, flags)

    shell.SHGetFolderPath = fn


def _install(spec, hotplug=None, open_fail=None, data_fault=None):
    import pyjoulescope_driver
    from pyjoulescope_driver import DevicePath, device_filter

    open_fail = [int(x) for x in (open_fail or '').split(',') if x.strip()]
    opens = [0]

    events = []  # (time, 'add' or 'remove')
    for item in (hotplug or '').split(','):
        if item.strip():
            kind, t = item.strip().split('@')
            events.append((float(t), kind))
    present = [not events or events[0][1] != 'add']
    wrappers = []  # every _Filtered instance, for the simulated hotplug events
    faults = {}  # message number: 'drop' or 'corrupt'
    for item in (data_fault or '').split(','):
        if item.strip():
            kind, n = item.strip().split('@')
            faults[int(n)] = kind

    def visible(device_path):
        return present[0] and bool(spec) and bool(device_filter.find([DevicePath(device_path)], spec))

    class _Filtered:
        """A device add or remove callback that only sees visible devices."""

        def __init__(self, topic, fn):
            self.topic = topic
            self.fn = fn
            self.active = True

        def __call__(self, topic, value):
            if self.active and visible(value):
                self.fn(topic, value)

        def __eq__(self, other):
            # Driver.unsubscribe matches the callback given to subscribe
            # by identity or equality.
            return other is self or other is self.fn or other == self.fn

        def __hash__(self):
            return hash(self.fn)

    class _DataFault:
        """A "!data" callback that loses or corrupts the selected messages."""

        def __init__(self, fn):
            self.fn = fn
            self.count = 0

        def __call__(self, topic, value):
            self.count += 1
            kind = faults.get(self.count)
            if kind == 'drop':
                return
            if kind == 'corrupt':
                value = dict(value, data=None)
            self.fn(topic, value)

        def __eq__(self, other):
            return other is self or other is self.fn or other == self.fn

        def __hash__(self):
            return hash(self.fn)

    class Driver(pyjoulescope_driver.Driver):

        def query(self, topic, timeout=None):
            value = super().query(topic, timeout)
            if topic == '@/list':
                value = ','.join([p for p in value.split(',') if p and visible(p)])
            return value

        def subscribe(self, topic, flags, fn, timeout=None):
            if topic in ['@/!add', '@/!remove']:
                fn = _Filtered(topic, fn)
                wrappers.append(fn)
            elif faults and topic.endswith('!data'):
                fn = _DataFault(fn)
            return super().subscribe(topic, flags, fn, timeout)

        def unsubscribe(self, topic, fn, timeout=None):
            for w in wrappers:
                if w.topic == topic and (w is fn or w.fn is fn or w.fn == fn):
                    w.active = False
            return super().unsubscribe(topic, fn, timeout)

        def finalize(self, timeout=None):
            for w in wrappers:
                w.active = False
            return super().finalize(timeout)

        def open(self, device_prefix, mode=None, timeout=None):
            opens[0] += 1
            if opens[0] in open_fail:
                raise TimeoutError(f'jsdrv_open timed out | {device_prefix} (simulated)')
            return super().open(device_prefix, mode, timeout)

    def hotplug_run():
        t_start = time.monotonic()
        device_paths = [p.strip() for p in spec.split(',') if p.strip()]
        for t, kind in events:
            time.sleep(max(0.0, t_start + t - time.monotonic()))
            present[0] = (kind == 'add')
            topic = f'@/!{kind}'
            for w in list(wrappers):
                if w.topic == topic and w.active:
                    for device_path in device_paths:
                        w.fn(topic, device_path)

    pyjoulescope_driver.Driver = Driver
    if events:
        threading.Thread(target=hotplug_run, name='shim_hotplug', daemon=True).start()


if _SPEC is not None:
    _install(_SPEC.strip(), _HOTPLUG, _OPEN_FAIL, _DATA_FAULT)
if _DOCUMENTS:
    _documents_install(_DOCUMENTS)
