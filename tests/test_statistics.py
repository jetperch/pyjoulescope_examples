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


pytestmark = pytest.mark.parametrize('path', harness.paths('statistics'))
LINE = re.compile(r'^(JS\d+)-(\S+) (\d+\.\d): (-?\d+\.\d{9}) A, (-?\d+\.\d{3}) V, '
                  r'(-?\d+\.\d{9}) W, (-?\d+\.\d{9}) C, (-?\d+\.\d{9}) J$')


def _parse(r):
    rows = []
    for line in r.lines:
        m = LINE.match(line)
        assert m, f'unexpected line {line!r}\n{r}'
        rows.append(m.groups())
    return rows


def test_no_device_waits(path):
    r = harness.run(path, interrupt_after=3)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.stdout == ''


def test_ignores_args(path):
    r = harness.run(path, '--help', interrupt_after=3)
    assert r.returncode == 0, r
    assert r.stdout == ''


def test_device(path, device_path):
    r = harness.run(path, visible=device_path, interrupt_on=lambda out: out.count('\n') >= 4)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    rows = _parse(r)
    assert len(rows) >= 4
    for row in rows:
        assert row[0] == device_path.model.upper()
        assert row[1] == device_path.serial_number
    assert rows[0][2] == '0.0'
    assert float(rows[0][6]) == 0.0  # charge
    assert float(rows[0][7]) == 0.0  # energy
    assert 'Warning' not in r.stderr, r


def test_device_2hz(path, device_path, request):
    if device_path.model == 'js320':
        request.applymarker(pytest.mark.xfail(strict=True, reason=harness.U1))
    r = harness.run(path, visible=device_path, interrupt_on=lambda out: out.count('\n') >= 4)
    times = [float(row[2]) for row in _parse(r)]
    assert times[:4] == [0.0, 0.5, 1.0, 1.5]


def test_statistics_rate(path, statistics_100hz, request):
    if statistics_100hz.model == 'js220':
        request.applymarker(pytest.mark.xfail(strict=True, reason=harness.STATS_RATE))
    r = harness.run(path, visible=statistics_100hz, interrupt_after=2.5)
    assert 2 <= len(_parse(r)) <= 7, r  # 2 Hz


def test_several_devices(path, several_devices):
    count = len(several_devices.split(','))
    r = harness.run(path, visible=several_devices,
                    interrupt_on=lambda out: out.count('\n') >= 3 * count)
    assert r.returncode == 0, r
    rows = _parse(r)
    found = {f'u/{row[0].lower()}/{row[1]}' for row in rows}
    assert found == set(several_devices.split(','))
