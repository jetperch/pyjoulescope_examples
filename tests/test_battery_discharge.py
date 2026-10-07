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
import re


pytestmark = pytest.mark.parametrize('path', harness.paths('battery_discharge'))
LINE = re.compile(r'^\d+\.\d: current=-?\d+\.\d{9}, voltage=-?\d+\.\d{3}, power=-?\d+\.\d{9}, '
                  r'charge=-?\d+\.\d{9}, energy=-?\d+\.\d{9}$')


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    assert 'voltage' in r.stdout


def test_no_args(path):
    r = harness.run(path)
    assert r.returncode == 2, r
    assert 'the following arguments are required: voltage' in r.stderr


def test_invalid(path):
    r = harness.run(path, 'x')
    assert r.returncode == 2, r
    assert 'argument voltage' in r.stderr


def test_no_device(path):
    r = harness.run(path, 3.0)
    assert r.lines == ['No Joulescope device found']


def test_no_device_exit_code(path):
    r = harness.run(path, 3.0)
    assert r.returncode == 1, r


def test_below_threshold(path, device_path, output_state):
    output_state('on')
    r = harness.run(path, 100, visible=device_path)
    assert r.returncode == 0, r
    assert r.lines[0].startswith('0.0: ')
    for line in r.lines:
        assert LINE.match(line), r
    assert 'Warning' not in r.stderr, r
    assert output_state() == 'off'  # discharge done: disconnect the battery
    output_state('on')


def test_ctrl_c(path, device_path, output_state):
    output_state('on')
    r = harness.run(path, -100, visible=device_path, interrupt_on=lambda out: out.count('\n') >= 3)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines[-1] == 'Interrupted by user'
    for line in r.lines[:-1]:
        assert LINE.match(line), r
    assert output_state() == 'on'  # interrupted: leave the battery connected


def test_statistics_rate(path, statistics_100hz, request):
    if statistics_100hz.model == 'js220':
        request.applymarker(pytest.mark.xfail(strict=True, reason=harness.STATS_RATE))
    r = harness.run(path, -100, visible=statistics_100hz, interrupt_after=2.5)
    assert 2 <= len(r.lines) - 1 <= 7, r  # 2 Hz, then "Interrupted by user"


def test_2hz(path, device_path, request):
    if device_path.model == 'js320':
        request.applymarker(pytest.mark.xfail(strict=True, reason=harness.U1))
    r = harness.run(path, -100, visible=device_path, interrupt_on=lambda out: out.count('\n') >= 3)
    assert [line.split(':')[0] for line in r.lines[:3]] == ['0.0', '0.5', '1.0']
