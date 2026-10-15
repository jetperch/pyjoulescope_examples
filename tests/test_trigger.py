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

"""The GPI triggers need wiring, so these tests use the duration triggers.
See MANUAL.md."""

import harness
import jls_files
import pytest
import re


pytestmark = pytest.mark.parametrize('path', harness.paths('trigger'))
COLUMNS = 'start_time(samples),start_time(iso),end_time(samples),end_time(iso),' + \
          'current_mean(A),current_std(A),current_min(A),current_max(A),current_length(samples),' + \
          'voltage_mean(V),voltage_std(V),voltage_min(V),voltage_max(V),voltage_length(samples),' + \
          'power_mean(W),power_std(W),power_min(W),power_max(W),power_length(samples),' + \
          'charge(C),charge(Ah),' + \
          'energy(J),energy(Wh)'
WINDOWS = ['--start', 'duration', '--start_duration', 0.2,
           '--end', 'duration', '--capture_duration', 0.3, '--count', 2]


def _rows(lines):
    rows = []
    for line in lines:
        parts = line.split(',')
        assert len(parts) == 23, line
        assert re.match(r'^\d{4}-\d\d-\d\dT', parts[1]), line
        rows.append(parts)
    return rows


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--record', '-r', '--jls_version', '--jls_signals', '--csv', '--start',
                   '--start_signal', '--start_duration', '--end', '--end_signal',
                   '--capture_duration', '--current_range', '--voltage_range', '--init_power_off',
                   '--power_off', '--count', '--io_voltage', '-v', '--display_trigger',
                   '--display_stats', '--self_test', '--sampling_frequency']:
        assert option in r.stdout, option


@pytest.mark.parametrize('args', [['--start', 'x'], ['--end', 'x'], ['--start_signal', 'in2'],
                                  ['--jls_version', 3], ['--count', 'x']])
def test_invalid(path, args):
    r = harness.run(path, *args)
    assert r.returncode == 2, r
    assert f'argument {args[0]}' in r.stderr


def test_no_device(path):
    r = harness.run(path)
    assert r.returncode == 1, r
    assert 'No Joulescope found' in r.stderr


def test_display(path, device_path, tmp_path):
    r = harness.run(path, *WINDOWS, '--display_trigger', '--display_stats', '--csv', 'out.csv',
                    cwd=tmp_path, visible=device_path)
    assert r.returncode == 0, r
    lines = r.lines
    assert re.match(r'^start \d+$', lines[0]), r
    assert re.match(r'^stop \d+$', lines[1]), r
    assert lines[2] == COLUMNS
    assert re.match(r'^start \d+$', lines[4]), r
    assert re.match(r'^stop \d+$', lines[5]), r
    rows = _rows([lines[3], lines[6]])
    fs = harness.SAMPLE_RATE[device_path.model]
    for row in rows:
        assert int(row[2]) - int(row[0]) == int(0.3 * fs)
        assert abs(int(row[8]) - int(0.3 * fs)) <= 2  # current_length
        for mean, std in [(row[4], row[5]), (row[9], row[10]), (row[14], row[15])]:
            assert std != 'nan' or mean == 'nan', row  # 6.53
    csv =(tmp_path / 'out.csv').read_text().splitlines()
    assert csv[0] == '#' + COLUMNS
    assert csv[1:] == [lines[3], lines[6]]
    assert 'DeprecationWarning' not in r.stderr, r


def test_quiet(path, device_path, tmp_path):
    r = harness.run(path, *WINDOWS, cwd=tmp_path, visible=device_path)
    assert r.returncode == 0, r
    assert r.stdout == ''
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('version', [1, 2])
def test_record(path, device_path, tmp_path, version):
    r = harness.run(path, *WINDOWS, '--record', '--jls_version', version,
                    cwd=tmp_path, visible=device_path)
    assert r.returncode == 0, r
    files = sorted(f.name for f in tmp_path.iterdir())
    assert len(files) == 2, files
    assert files[0].endswith('_0001.jls') and files[1].endswith('_0002.jls')
    fs = harness.SAMPLE_RATE[device_path.model]
    if version == 2:
        s = jls_files.summary(tmp_path / files[0])
        assert sorted(s) == ['current', 'voltage']
        assert s['current']['sample_rate'] == fs
        assert abs(s['current']['length'] - 0.3 * fs) < 0.01 * fs
    else:
        from joulescope.data_recorder import DataReader
        reader = DataReader().open(str(tmp_path / files[0]))
        try:
            assert reader.sampling_frequency == fs
        finally:
            reader.close()


def test_ctrl_c(path, device_path, tmp_path):
    r = harness.run(path, '--display_trigger', '--csv', 'out.csv', cwd=tmp_path,
                    visible=device_path, interrupt_on='start ')
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert re.match(r'^start \d+$', r.lines[0]), r
    assert re.match(r'^stop \d+$', r.lines[1]), r
    csv = (tmp_path / 'out.csv').read_text().splitlines()
    assert len(csv) == 2
    _rows(csv[1:])


def test_power_off(path, device_path, output_state):
    output_state('on')
    r = harness.run(path, *WINDOWS, '--power_off', visible=device_path)
    assert r.returncode == 0, r
    assert output_state() == 'off'
    output_state('on')
