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

"""Observing the trigger output needs wiring.  See MANUAL.md."""

import harness
import pytest


pytestmark = pytest.mark.parametrize('path', harness.paths('trigger_host_pyjoulescope_driver'))


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--verbose', '-v', '--device', '-d', '--signal', '--start-duration',
                   '--start-threshold', '--stop-duration', '--stop-threshold']:
        assert option in r.stdout


def test_invalid(path):
    r = harness.run(path, '--start-duration', 'x')
    assert r.returncode == 2, r


def test_invalid_signal(path):
    r = harness.run(path, '--signal', 'x')
    assert r.returncode == 2, r


@pytest.mark.parametrize('signal', ['v', 'p'])
def test_signal(path, device_path, signal):
    if device_path.model == 'js110':
        pytest.skip('the JS110 has no trigger output')
    r = harness.run(path, '--signal', signal, visible=device_path, interrupt_after=2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert not r.has_traceback, r


def test_no_device(path):
    r = harness.run(path)
    assert r.returncode == 1, r
    assert r.lines == ['Device not found']


def test_device(path, device_path):
    r = harness.run(path, '-v', visible=device_path, interrupt_after=2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines[:3] == ['Find the connected devices', f"Found devices: ['{device_path}']",
                           'Open and configure each device']
    if device_path.model == 'js110':
        assert r.lines[3] == f'Unsupported device {device_path}: ignore'
    else:
        assert r.lines[3] == 'Perform the detection'
    assert r.lines[-1] == 'Closing'


def test_starts_low(path, device_path, trigger_level):
    if device_path.model == 'js110':
        pytest.skip('the JS110 has no trigger output')
    # The bench load never reaches the 1 A start threshold, so the output stays at its start level.
    r = harness.run(path, visible=device_path, interrupt_after=2)
    assert r.returncode == 0, r
    assert trigger_level() == 0


@pytest.mark.parametrize('option', ['--device', '-d', '--serial_number', '--serial-number'])
def test_device_unknown(path, device_path, option):
    r = harness.run(path, option, 'ZZZZ', visible=device_path)
    assert r.returncode == 1, r
    assert r.lines == ['Device not found']
