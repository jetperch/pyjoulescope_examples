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


pytestmark = pytest.mark.parametrize('path', harness.paths('statistics_logger'))
NUMBER = r'-?\d+\.\d+'
ROW = re.compile(rf'^{NUMBER}(,{NUMBER},{NUMBER},{NUMBER})+$')


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--out', '-o', '--console-fmt', '--console-join', '--file-fmt', '--file-join']:
        assert option in r.stdout


def test_no_device(path, tmp_path):
    r = harness.run(path, '-o', 'out.csv', cwd=tmp_path, timeout=10)
    assert not r.interrupted, r
    assert r.returncode == 1, r
    assert r.lines == ['No Joulescope found']
    assert list(tmp_path.iterdir()) == []


def test_device(path, device_path, tmp_path):
    name = f'{device_path.model.upper()}-{device_path.serial_number}'
    r = harness.run(path, '--out', 'out.csv', cwd=tmp_path, visible=device_path,
                    interrupt_on=lambda out: out.count('\n') >= 4)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines[0] == f'Joulescopes: {name}'
    rows = r.lines[1:]
    assert len(rows) >= 3
    for row in rows:
        assert ROW.match(row), r
        assert len(row.split(',')) == 4
    lines = (tmp_path / 'out.csv').read_text().splitlines()
    assert len(lines) >= 3
    assert lines == rows[:len(lines)]
    assert 'Warning' not in r.stderr, r


def test_formats(path, device_path, tmp_path):
    r = harness.run(path, '--console-fmt', '{i:.3f}|{v:.2f}', '--console-join', ';',
                    '--file-join', ' ', '-o', 'out.csv', cwd=tmp_path, visible=device_path,
                    interrupt_on=lambda out: out.count('\n') >= 3)
    assert r.returncode == 0, r
    for row in r.lines[1:]:
        assert re.match(rf'^{NUMBER};{NUMBER}\|{NUMBER}$', row), r
    for line in (tmp_path / 'out.csv').read_text().splitlines():  # the default --file-fmt
        assert re.match(rf'^{NUMBER} {NUMBER},{NUMBER},{NUMBER}$', line), line


def test_file_fmt(path, device_path, tmp_path):
    r = harness.run(path, '--file_fmt', 'X', '-o', 'out.csv', cwd=tmp_path, visible=device_path,
                    interrupt_on=lambda out: out.count('\n') >= 3)
    assert r.returncode == 0, r
    for line in (tmp_path / 'out.csv').read_text().splitlines():
        assert re.match(rf'^{NUMBER},X$', line), line


def test_statistics_rate(path, statistics_100hz):
    r = harness.run(path, visible=statistics_100hz, interrupt_after=2.5)
    assert 2 <= len(r.lines) - 1 <= 7, r  # 2 Hz, after the "Joulescopes:" line


def test_several_devices(path, several_devices):
    count = len(several_devices.split(','))
    r = harness.run(path, visible=several_devices, interrupt_on=lambda out: out.count('\n') >= 3)
    assert r.returncode == 0, r
    names = sorted(r.lines[0][len('Joulescopes: '):].split(','))
    expect = sorted(f'{p.split("/")[1].upper()}-{p.split("/")[2]}' for p in several_devices.split(','))
    assert names == expect
    for row in r.lines[1:]:
        assert ROW.match(row), r
        assert len(row.split(',')) == 1 + 3 * count
