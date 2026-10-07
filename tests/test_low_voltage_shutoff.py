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


pytestmark = pytest.mark.parametrize('path', harness.paths('low_voltage_shutoff'))
LINE = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+ : -?\d+\.\d{3} V$')
BELOW = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+ : input voltage below threshold$')


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    assert '--threshold' in r.stdout and '-t' in r.stdout


def test_invalid(path):
    r = harness.run(path, '-t', 'x')
    assert r.returncode == 2, r
    assert 'argument --threshold' in r.stderr


def test_no_device(path):
    r = harness.run(path)
    assert r.returncode == 1, r
    assert 'No Joulescope found' in r.stderr


def test_below_threshold(path, device_path, output_state):
    output_state('on')
    r = harness.run(path, '--threshold', 100, visible=device_path)
    assert r.returncode == 0, r
    assert LINE.match(r.lines[0]), r
    assert BELOW.match(r.lines[1]), r
    assert output_state() == 'off'
    output_state('on')


def test_ctrl_c(path, device_path, output_state):
    output_state('on')
    r = harness.run(path, '-t', -100, visible=device_path, interrupt_on=lambda out: out.count('\n') >= 2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    for line in r.lines:
        assert LINE.match(line), r
    assert output_state() == 'off'  # also turns the output off on Ctrl-C
    output_state('on')
