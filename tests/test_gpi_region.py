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

"""Regions need GPI wiring.  See MANUAL.md."""

import harness
import pytest


pytestmark = pytest.mark.parametrize('path', harness.paths('gpi_region'))
HEADER = ('device,signal,sample_id_start,sample_id_end,utc_start,utc_end,'
          'i.length,i.mean,i.std,i.min,i.max,'
          'v.length,v.mean,v.std,v.min,v.max,'
          'p.length,p.mean,p.std,p.min,p.max')


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--verbose', '-v', '--gpi', '--vref', '--serial_number']:
        assert option in r.stdout


def test_invalid(path):
    r = harness.run(path, '--vref', 'x')
    assert r.returncode == 2, r


def test_no_device(path):
    r = harness.run(path)
    assert r.returncode == 1, r
    assert r.lines == ['Device not found']


def test_device(path, device_path, request):
    if device_path.model == 'js320':
        request.applymarker(pytest.mark.xfail(strict=True, reason='6.22 no JS320 support'))
    r = harness.run(path, '--gpi', '0,1,T', '--vref', '3v3', visible=device_path, interrupt_after=2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    if device_path.model == 'js110':
        assert r.lines == [f'Unsupported device {device_path}: ignore']
    else:
        assert r.lines == [HEADER]


def test_verbose(path, device_path):
    if device_path.model != 'js220':
        pytest.skip('only runs on the JS220 on main')
    r = harness.run(path, '-v', visible=device_path, interrupt_after=2)
    assert r.returncode == 0, r
    assert r.lines == [
        'Find the connected devices',
        f"Found devices: ['{device_path}']",
        'Open and configure each device',
        HEADER,
        'Perform the detection',
        'Closing',
    ]


def test_serial_number(path, device_path):
    r = harness.run(path, '--serial_number', 'ZZZZ', visible=device_path)
    assert r.returncode == 1, r
    assert r.lines == ['Device not found']
