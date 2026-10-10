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

"""Unplug the instrument while each streaming example runs.

The shim simulates the unplug (see shim/sitecustomize.py), as the bench
cannot unplug an instrument.  Each example stops by itself, without a
traceback, and says why.  This module covers many examples, since they share
the requirement.  A real unplug, with a USB hub that power cycles the
instrument, showed the same behavior.
"""

import harness
import pytest


UNPLUG = 'unplug@3'
REMOVED = '{path} removed: stop'
STOPPED = 'Capture stopped: device removed'

# name: (args, models, (returncode, the last line of stdout) or None for exit only)
CASES = {
    'driver_statistics': ([], None, (1, REMOVED)),
    'record': (['out.jls'], None, (1, REMOVED)),
    'read_by_pyjoulescope_driver': (['-d', 30, '--no-progress'], None,
                                    (1, '{path} removed during the read')),
    'measure': (['--duration', 30], None, (1, REMOVED)),
    'monitor': ([], None, (1, REMOVED)),
    'detector': (['--duration', 30], ['js220', 'js320'], (1, REMOVED)),
    'gpi_region': (['--gpi', '0', '--vref', '3v3'], ['js220', 'js320'], (1, REMOVED)),
    'timesync': ([], ['js220', 'js320'], (1, REMOVED)),
    'trigger_host_pyjoulescope_driver': ([], ['js220', 'js320'], (1, REMOVED)),
    'statistics': ([], None, (1, '{model_upper}-{serial} removed: stop')),
    'statistics_logger': (['--out', 'out.csv'], None, (1, '{model_upper}-{serial} removed: stop')),
    'capture_jls_v2': (['out.jls'], None, None),
    'energy_printer_host': ([], None, None),
    'accumulators': ([], None, (1, None)),
    'read_by_callback': (['--duration', 30], None, (1, STOPPED)),
    'statistics_with_trigger_to_jls': ([], None, (1, '{model_upper}-{serial} removed: stop')),
}


@pytest.mark.parametrize('name, args, models, expect',
                         [pytest.param(k, *v, id=k) for k, v in CASES.items()])
def test_unplug(name, args, models, expect, device_path, tmp_path):
    if models is not None and device_path.model not in models:
        pytest.skip(f'{name} does not support the {device_path.model}')
    path = harness.paths(name)[0]
    r = harness.run(path, *args, cwd=tmp_path, visible=device_path, hotplug=UNPLUG, timeout=20)
    assert not r.interrupted, r  # it stopped by itself
    assert not r.has_traceback, r
    if expect is not None:
        returncode, line = expect
        assert r.returncode == returncode, r
        if line is not None:
            line = line.format(path=device_path, model_upper=device_path.model.upper(),
                               serial=device_path.serial_number)
            assert line in r.lines, r
