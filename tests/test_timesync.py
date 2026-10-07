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

"""Measuring time synchronization needs several instruments and a shared
GPI0 signal.  See MANUAL.md."""

import harness
import pytest


pytestmark = pytest.mark.parametrize('path', harness.paths('timesync'))


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--verbose', '-v', '--vref', '--out']:
        assert option in r.stdout


def test_invalid(path):
    r = harness.run(path, '--vref', 'x')
    assert r.returncode == 2, r


def test_no_device_waits(path, tmp_path):
    r = harness.run(path, '-v', '--out', 'out.csv', cwd=tmp_path, interrupt_after=2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines == ['Find the connected devices', 'Found devices: []',
                       'Open and configure each device', 'Monitor each device', 'Closing']
    assert (tmp_path / 'out.csv').read_text() == ''


def test_device(path, device_path, tmp_path):
    r = harness.run(path, '-v', '--vref', 'external', cwd=tmp_path, visible=device_path,
                    interrupt_after=2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines[:2] == ['Find the connected devices', f"Found devices: ['{device_path}']"]
    assert r.lines[-2:] == ['Monitor each device', 'Closing']
    if device_path.model == 'js110':
        assert r.lines[3] == f'Unsupported device {device_path}: ignore'
    else:
        assert r.lines[3] == 'Monitor each device'
