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
import json
import pytest


pytestmark = pytest.mark.parametrize('path', harness.paths('measure'))


def _check(r, duration):
    assert r.returncode == 0, r
    s = json.loads(r.stdout)
    assert s is not None, r
    for signal in ['current', 'voltage', 'power']:
        for stat in ['avg', 'std', 'min', 'max', 'p2p']:
            assert isinstance(s['signals'][signal][stat]['value'], float)
    assert sorted(s['accumulators']) == ['charge', 'energy']
    s0, s1 = s['time']['samples']['value']
    fs = s['time']['sample_freq']['value']
    assert 0.5 * duration <= (s1 - s0) / fs <= 1.5 * duration + 0.1
    return s


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--duration', '--frequency', '--serial-number']:
        assert option in r.stdout


@pytest.mark.parametrize('args', [['--duration', 'x'], ['--frequency', '1.5']])
def test_invalid(path, args):
    r = harness.run(path, *args)
    assert r.returncode == 2, r
    assert f'argument {args[0]}' in r.stderr


def test_no_device(path):
    r = harness.run(path, '--duration', 1)
    assert r.returncode == 1, r
    assert r.lines == ['Device not found']


def test_duration(path, device_path, request):
    if device_path.model == 'js320':
        request.applymarker(pytest.mark.xfail(strict=True, reason='6.13 no JS320 model branch'))
    r = harness.run(path, '--duration', 1, visible=device_path)
    _check(r, 1.0)


def test_frequency(path, device_path, request):
    if device_path.model == 'js320':
        request.applymarker(pytest.mark.xfail(strict=True, reason='6.13 no JS320 model branch'))
    r = harness.run(path, '--duration', 1, '--frequency', 10, visible=device_path)
    _check(r, 1.0)


def test_ctrl_c(path, device_path, request):
    if device_path.model == 'js320':
        request.applymarker(pytest.mark.xfail(strict=True, reason='6.13 no JS320 model branch'))
    r = harness.run(path, visible=device_path, interrupt_after=2)
    assert r.interrupted and not r.killed, r
    _check(r, 2.0)


def test_serial_number(path, device_path):
    r = harness.run(path, '--duration', 0.5, '--serial-number', 'ZZZZ', visible=device_path)
    assert r.returncode == 1, r
    assert r.lines == ['Device not found']
    r = harness.run(path, '--duration', 0.5, '--serial-number', device_path.serial_number.lower(),
                    visible=device_path)
    assert r.returncode == 0, r


def test_several_devices(path, several_devices):
    r = harness.run(path, '--duration', 0.5, visible=several_devices)
    assert r.returncode == 1, r
    assert r.lines[0].startswith('Found multiple devices: [')
    assert r.lines[1] == 'Use "--serial-number" to specify the target Joulescope'
    serial_number = several_devices.split(',')[0].split('/')[-1]
    r = harness.run(path, '--duration', 0.5, '--serial-number', serial_number, visible=several_devices)
    assert r.returncode == 0, r
