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
import jls_files
import pytest


pytestmark = pytest.mark.parametrize('path', harness.paths('capture_jls_v2'))
START = 'Capturing data: type CTRL-C to stop'


def _check(jls, device_path, signals, duration_min, duration_max):
    s = jls_files.summary(jls)
    assert sorted(s) == sorted(signals)
    fs = harness.SAMPLE_RATE[device_path.model]
    for name, units in [('current', 'A'), ('voltage', 'V'), ('power', 'W')]:
        if name not in s:
            continue
        x = s[name]
        assert x['source'] == f'{device_path.model.upper()}-{device_path.serial_number}'
        assert x['sample_rate'] == fs
        assert x['units'] == units
        assert duration_min * fs <= x['length'] <= duration_max * fs, s


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['filename', '--duration', '--signals']:
        assert option in r.stdout


def test_no_args(path):
    r = harness.run(path)
    assert r.returncode == 2, r
    assert 'the following arguments are required: filename' in r.stderr


def test_duration_invalid(path, tmp_path):
    r = harness.run(path, 'out.jls', '--duration', 'abc', cwd=tmp_path)
    assert r.returncode == 2, r
    assert 'argument --duration' in r.stderr


def test_no_device(path, tmp_path):
    r = harness.run(path, 'out.jls', cwd=tmp_path)
    assert r.returncode == 1, r
    assert 'No Joulescope found' in r.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('duration', ['1', '1.0', '1s'])
def test_duration(path, device_path, tmp_path, duration):
    r = harness.run(path, 'out.jls', '--duration', duration, cwd=tmp_path, visible=device_path)
    assert r.returncode == 0, r
    assert r.lines == [START]
    _check(tmp_path / 'out.jls', device_path, ['current', 'voltage'], 1.0, 1.05)


def test_signals(path, device_path, tmp_path):
    r = harness.run(path, 'out.jls', '--duration', 0.5, '--signals', 'current,voltage,power',
                    cwd=tmp_path, visible=device_path)
    assert r.returncode == 0, r
    _check(tmp_path / 'out.jls', device_path, ['current', 'voltage', 'power'], 0.5, 0.55)


def test_ctrl_c(path, device_path, tmp_path):
    r = harness.run(path, 'out.jls', cwd=tmp_path, visible=device_path,
                    interrupt_on=START, timeout=30)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines == [START]
    _check(tmp_path / 'out.jls', device_path, ['current', 'voltage'], 0.0, 30.0)


def test_several_devices(path, several_devices, tmp_path):
    r = harness.run(path, 'out.jls', '--duration', 1, cwd=tmp_path, visible=several_devices)
    assert r.returncode == 1, r
    assert 'Multiple Joulescopes found' in r.stderr
