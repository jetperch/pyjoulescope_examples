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

"""Test examples/pyjoulescope_driver/statistics.py."""

import harness
import pytest
import re


pytestmark = pytest.mark.parametrize('path', harness.paths('driver_statistics'))
LINE = re.compile(r'^(u/\w+/\w+): (-?\d+\.\d{9}) A, (-?\d+\.\d{3}) V, (-?\d+\.\d{9}) W, '
                  r'(-?\d+\.\d{9}) C, (-?\d+\.\d{9}) J$')


def _parse(r):
    rows = []
    for line in r.lines:
        m = LINE.match(line)
        assert m, f'unexpected line {line!r}\n{r}'
        rows.append(m.groups())
    return rows


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--device', '-d', '--duration', '--frequency']:
        assert option in r.stdout


def test_invalid(path):
    r = harness.run(path, '--frequency', 'x')
    assert r.returncode == 2, r


def test_no_device(path):
    r = harness.run(path, '--duration', 1)
    assert r.returncode == 1, r
    assert r.lines == ['No Joulescope found']


def test_duration(path, device_path):
    r = harness.run(path, '--duration', 2.2, visible=device_path)
    assert not r.interrupted, r
    assert r.returncode == 0, r
    rows = _parse(r)
    assert 3 <= len(rows) <= 6, r  # 2 Hz
    for row in rows:
        assert row[0] == device_path
    assert -1 < float(rows[-1][2]) < 16  # voltage


def test_frequency(path, device_path):
    r = harness.run(path, '--duration', 1.1, '--frequency', 10, visible=device_path)
    assert r.returncode == 0, r
    assert 8 <= len(_parse(r)) <= 13, r


def test_statistics_rate(path, statistics_100hz):
    r = harness.run(path, '--duration', 2.2, visible=statistics_100hz)
    assert r.returncode == 0, r
    assert 3 <= len(_parse(r)) <= 6, r  # 2 Hz, not the rate that another program left


def test_ctrl_c(path, device_path):
    r = harness.run(path, visible=device_path, interrupt_on=lambda out: out.count('\n') >= 2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert len(_parse(r)) >= 2


def test_several_devices(path, several_devices):
    paths = sorted(several_devices.split(','))
    r = harness.run(path, '--duration', 1.5, visible=several_devices)
    assert r.returncode == 0, r
    assert {row[0] for row in _parse(r)} == set(paths)
    r = harness.run(path, '--duration', 1.5, '-d', paths[0].split('/')[-1], visible=several_devices)
    assert r.returncode == 0, r
    assert {row[0] for row in _parse(r)} == {paths[0]}
