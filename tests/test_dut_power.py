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

import harness
import pytest


pytestmark = pytest.mark.parametrize('path', harness.paths('dut_power'))
USAGE = 'usage: dut_power.py [on | off | ?]'
ON = ['1', 'on', 'true', 'enable', 'ON', 'Enable', 'TRUE']
OFF = ['0', 'off', 'false', 'disable', 'OFF', 'Disable', 'FALSE']


def test_no_args_usage(path):
    r = harness.run(path)
    assert r.lines[0] == USAGE


@pytest.mark.xfail(strict=True, reason='6.16 raises IndexError when given no argument')
def test_no_args(path):
    r = harness.run(path)
    assert r.returncode != 0, r
    assert 'Traceback' not in r.stderr, r


@pytest.mark.parametrize('arg', ['on', 'off', '?', 'bogus'])
def test_no_device(path, arg):
    r = harness.run(path, arg)
    assert r.returncode == 0, r
    assert r.stdout == ''


def test_set_and_query(path, device_path, output_state):
    for arg in ON + OFF:
        expect = 'on' if arg in ON else 'off'
        output_state('off' if expect == 'on' else 'on')
        r = harness.run(path, arg, visible=device_path)
        assert r.returncode == 0, r
        assert r.stdout == ''
        assert output_state() == expect, arg
        r = harness.run(path, '?', visible=device_path)
        assert r.returncode == 0, r
        assert r.lines == [f'{device_path}: {expect}']
    output_state('on')


def test_invalid(path, device_path, output_state):
    output_state('on')
    r = harness.run(path, 'bogus', visible=device_path)
    assert r.returncode == 1, r
    assert r.lines == [USAGE]
    assert output_state() == 'on'


def test_several_devices(path, several_devices):
    paths = several_devices.split(',')
    r = harness.run(path, 'off', visible=several_devices)
    assert r.returncode == 0, r
    r = harness.run(path, '?', visible=several_devices)
    assert r.lines == [f'{p}: off' for p in sorted(paths)]
    r = harness.run(path, 'on', visible=several_devices)
    assert r.returncode == 0, r
    r = harness.run(path, '?', visible=several_devices)
    assert r.lines == [f'{p}: on' for p in sorted(paths)]
