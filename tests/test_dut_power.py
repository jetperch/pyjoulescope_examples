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
ON = ['1', 'on', 'true', 'enable', 'ON', 'Enable', 'TRUE']
OFF = ['0', 'off', 'false', 'disable', 'OFF', 'Disable', 'FALSE']


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['state', '--device', '-d']:
        assert option in r.stdout


def test_no_args(path):
    r = harness.run(path)
    assert r.returncode == 2, r
    assert not r.has_traceback, r
    assert 'the following arguments are required: state' in r.stderr


@pytest.mark.xfail(strict=True, reason='6.34 exits 0 silently when no instrument matches')
@pytest.mark.parametrize('arg', ['on', 'off', '?'])
def test_no_device(path, arg):
    r = harness.run(path, arg)
    assert r.returncode == 1, r
    assert r.lines == ['No Joulescope found']


def test_invalid(path):
    r = harness.run(path, 'bogus')
    assert r.returncode == 2, r
    assert "invalid choice: 'bogus'" in r.stderr


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


def test_invalid_leaves_state(path, device_path, output_state):
    output_state('on')
    r = harness.run(path, 'bogus', visible=device_path)
    assert r.returncode == 2, r
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


@pytest.mark.parametrize('option', ['--device', '-d'])
def test_device(path, several_devices, option):
    paths = sorted(several_devices.split(','))
    target = paths[0]
    serial_number = target.split('/')[-1]
    r = harness.run(path, 'off', option, serial_number, visible=several_devices)
    assert r.returncode == 0, r
    r = harness.run(path, '?', visible=several_devices)
    assert r.lines == [f'{p}: {"off" if p == target else "on"}' for p in paths]
    r = harness.run(path, '?', option, target.split('/')[1], visible=several_devices)
    assert r.lines == [f'{target}: off']
    r = harness.run(path, 'on', option, serial_number, visible=several_devices)
    assert r.returncode == 0, r
