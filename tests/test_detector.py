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

"""Detection needs more than 10 mA, so these tests do not check detections."""

import harness
import pytest
import re


pytestmark = pytest.mark.parametrize('path', harness.paths('detector'))
NOT_FOUND = 'No Joulescope JS220 found'
DETECTED = re.compile(r'^detected [12]$')


def test_help(path, tmp_path):
    r = harness.run(path, '--help', cwd=tmp_path)
    assert r.returncode == 0, r
    for option in ['--frequency', '-f', '--duration', '--serial_number']:
        assert option in r.stdout


def test_invalid(path):
    r = harness.run(path, '--frequency', 'x')
    assert r.returncode == 2, r


def test_no_device(path):
    r = harness.run(path, '--duration', 1)
    assert r.returncode == 1, r
    assert r.lines == [NOT_FOUND]


def test_duration(path, device_path, request):
    if device_path.model == 'js320':
        request.applymarker(pytest.mark.xfail(strict=True, reason='6.22 no JS320 support'))
    r = harness.run(path, '--duration', 1, visible=device_path)
    if device_path.model == 'js110':
        assert r.returncode == 1, r
        assert r.lines == [NOT_FOUND]
        return
    assert r.returncode == 0, r
    for line in r.lines:
        assert DETECTED.match(line), r


def test_ctrl_c(path, device_path):
    if device_path.model != 'js220':
        pytest.skip('only runs on the JS220 on main')
    r = harness.run(path, '-f', 100000, visible=device_path, interrupt_after=2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r


def test_serial_number(path, device_path):
    r = harness.run(path, '--duration', 0.5, '--serial_number', 'ZZZZ', visible=device_path)
    assert r.returncode == 1, r
    assert r.lines == [NOT_FOUND]
