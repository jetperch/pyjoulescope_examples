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

When JOULESCOPE_EXAMPLES_DOCUMENTS is set, it also stands in for the
user's Documents folder, so that examples that write there, such as
downsample_logging.py, never touch the real one.
"""

import os

_SPEC = os.environ.get('JOULESCOPE_EXAMPLES_VISIBLE')
_DOCUMENTS = os.environ.get('JOULESCOPE_EXAMPLES_DOCUMENTS')


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


def _install(spec):
    import pyjoulescope_driver
    from pyjoulescope_driver import DevicePath, device_filter

    def visible(device_path):
        return bool(spec) and bool(device_filter.find([DevicePath(device_path)], spec))

    class _Filtered:
        """A device add or remove callback that only sees visible devices."""

        def __init__(self, fn):
            self.fn = fn

        def __call__(self, topic, value):
            if visible(value):
                self.fn(topic, value)

        def __eq__(self, other):
            # Driver.unsubscribe matches the callback given to subscribe
            # by identity or equality.
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
                fn = _Filtered(fn)
            return super().subscribe(topic, flags, fn, timeout)

    pyjoulescope_driver.Driver = Driver


if _SPEC is not None:
    _install(_SPEC.strip())
if _DOCUMENTS:
    _documents_install(_DOCUMENTS)
