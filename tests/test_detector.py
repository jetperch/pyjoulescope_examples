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
DETECTED = re.compile(r'^detected [12]$')


def test_help(path, tmp_path):
    r = harness.run(path, '--help', cwd=tmp_path)
    assert r.returncode == 0, r
    for option in ['--frequency', '-f', '--duration', '--device', '-d']:
        assert option in r.stdout


def test_invalid(path):
    r = harness.run(path, '--frequency', 'x')
    assert r.returncode == 2, r


def test_no_device(path):
    r = harness.run(path, '--duration', 1)
    assert r.returncode == 1, r
    assert len(r.lines) == 1 and 'not found' in r.lines[0], r


def test_duration(path, device_path):
    r = harness.run(path, '--duration', 1, visible=device_path)
    if device_path.model == 'js110':
        assert r.returncode == 1, r
        assert len(r.lines) == 1 and 'not found' in r.lines[0], r
        return
    assert r.returncode == 0, r
    for line in r.lines:
        assert DETECTED.match(line), r


def test_ctrl_c(path, device_path):
    if device_path.model == 'js110':
        pytest.skip('the JS110 is not supported')
    r = harness.run(path, '-f', 100000, visible=device_path, interrupt_after=2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r


@pytest.mark.parametrize('option', ['--device', '-d', '--serial_number', '--serial-number'])
def test_device_unknown(path, device_path, option):
    r = harness.run(path, '--duration', 0.5, option, 'ZZZZ', visible=device_path)
    assert r.returncode == 1, r
    assert r.lines == [f'Device "ZZZZ" not found in [{device_path!r}]']


def test_device_js110(path, device_path):
    if device_path.model != 'js110':
        pytest.skip('only the JS110 is unsupported')
    r = harness.run(path, '--duration', 0.5, '--device', device_path.serial_number, visible=device_path)
    assert r.returncode == 1, r
    assert len(r.lines) == 1 and r.lines[0].startswith(f'{device_path} is not supported'), r


def test_several_devices(path, several_devices):
    supported = [p for p in several_devices.split(',') if '/js110/' not in p]
    if len(supported) < 2:
        pytest.skip('Needs two supported instruments')
    r = harness.run(path, '--duration', 0.5, visible=several_devices)
    assert r.returncode == 1, r
    assert r.lines[-1] == 'Use "--device" to specify the desired device.'
    r = harness.run(path, '--duration', 0.5, '-d', supported[0].split('/')[-1], visible=several_devices)
    assert r.returncode == 0, r
