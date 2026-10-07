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

"""A capture needs more than 1 mA, so the capture tests skip without a load."""

import harness
import jls_files
import pytest
import re


pytestmark = pytest.mark.parametrize('path', harness.paths('monitor'))
START = re.compile(r'^\d{4}-\d\d-\d\dT[\d:.]+: Current threshold exceeded\.  Start capture$')
END = re.compile(r'^\d{4}-\d\d-\d\dT[\d:.]+: Current returned to normal\.  End capture$')


def _capture(path, device_path, tmp_path):
    r = harness.run(path, cwd=tmp_path, visible=device_path, interrupt_after=4)
    assert r.interrupted and not r.killed, r
    if not r.lines:
        pytest.skip(f'{device_path} has no load above 1 mA to capture')
    return r


def test_no_device(path, tmp_path):
    r = harness.run(path, cwd=tmp_path)
    assert r.lines == ['No Joulescope found']
    assert list(tmp_path.iterdir()) == []


@pytest.mark.xfail(strict=True, reason='6.25 exits 0 when no instrument is found')
def test_no_device_exit_code(path, tmp_path):
    r = harness.run(path, cwd=tmp_path)
    assert r.returncode == 1, r


def test_several_devices(path, several_devices, tmp_path):
    r = harness.run(path, cwd=tmp_path, visible=several_devices)
    assert r.lines == ['Multiple Joulescope found']


def test_device(path, device_path, tmp_path):
    r = harness.run(path, cwd=tmp_path, visible=device_path, interrupt_after=3)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    for line in r.lines:
        assert START.match(line) or END.match(line), r


def test_capture(path, device_path, tmp_path):
    import openpyxl
    r = _capture(path, device_path, tmp_path)
    assert START.match(r.lines[0]), r
    jls = sorted(f for f in tmp_path.iterdir() if f.name.endswith('_summary.jls'))
    xlsx = sorted(f for f in tmp_path.iterdir() if f.name.endswith('_summary.xlsx'))
    assert len(jls) >= 1 and len(xlsx) >= 1
    s = jls_files.summary(jls[0])
    assert sorted(s) == ['current', 'voltage']
    assert s['current']['sample_rate'] == 50
    assert s['current']['source'] == f'{device_path.model.upper()}-{device_path.serial_number}'
    wb = openpyxl.load_workbook(xlsx[0])
    rows = list(wb.active.values)
    assert rows[0] == ('SampleID', 'Current A', 'Voltage V')
    assert len(rows) > 50


def test_capture_voltage(path, device_path, tmp_path):
    import openpyxl
    _capture(path, device_path, tmp_path)
    jls = sorted(f for f in tmp_path.iterdir() if f.name.endswith('_summary.jls'))
    s = jls_files.summary(jls[0])
    assert s['voltage']['mean'] != s['current']['mean']
    xlsx = sorted(f for f in tmp_path.iterdir() if f.name.endswith('_summary.xlsx'))
    rows = list(openpyxl.load_workbook(xlsx[0]).active.values)[1:]
    assert any(row[1] != row[2] for row in rows)
