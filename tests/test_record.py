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


pytestmark = pytest.mark.parametrize('path', harness.paths('record'))
START = 'Recording.  Press CTRL-C to stop.'


def _check(jls, device_path, signals, duration_min, duration_max):
    s = jls_files.summary(jls)
    assert sorted(s) == sorted(signals)
    fs = harness.SAMPLE_RATE[device_path.model]
    for name in ['current', 'voltage', 'power']:
        if name in s:
            assert s[name]['source'] == f'{device_path.model.upper()}-{device_path.serial_number}'
            assert s[name]['sample_rate'] == fs
            assert duration_min * fs <= s[name]['length'] <= duration_max * fs, s
    return s


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['filename', '--duration', '--signals', '--device', '-d']:
        assert option in r.stdout


def test_no_args(path):
    r = harness.run(path)
    assert r.returncode == 2, r
    assert 'the following arguments are required: filename' in r.stderr


def test_no_device(path, tmp_path):
    r = harness.run(path, 'out.jls', '--duration', 1, cwd=tmp_path)
    assert r.returncode == 1, r
    assert r.lines == ['No Joulescope found']
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('duration', ['1', '1s'])
def test_duration(path, device_path, tmp_path, duration):
    r = harness.run(path, 'out.jls', '--duration', duration, cwd=tmp_path, visible=device_path)
    assert r.returncode == 0, r
    assert r.lines == [START]
    s = _check(tmp_path / 'out.jls', device_path, ['current', 'voltage'], 0.5, 1.5)
    assert s['current']['mean'] is not None


def test_signals(path, device_path, tmp_path):
    r = harness.run(path, 'out.jls', '--duration', 0.5, '--signals', 'i,v,p', cwd=tmp_path,
                    visible=device_path)
    assert r.returncode == 0, r
    _check(tmp_path / 'out.jls', device_path, ['current', 'voltage', 'power'], 0.2, 1.0)


@pytest.mark.xfail(strict=True, reason='6.37 raises KeyError for an unknown signal')
def test_signals_invalid(path, device_path, tmp_path):
    r = harness.run(path, 'out.jls', '--duration', 0.5, '--signals', 'current,volts', cwd=tmp_path,
                    visible=device_path)
    assert r.returncode == 1, r
    assert not r.has_traceback, r
    assert 'volts' in r.stdout


def test_ctrl_c(path, device_path, tmp_path):
    r = harness.run(path, 'out.jls', cwd=tmp_path, visible=device_path, interrupt_after=2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    _check(tmp_path / 'out.jls', device_path, ['current', 'voltage'], 0.5, 3.0)


def test_several_devices(path, several_devices, tmp_path):
    r = harness.run(path, 'out.jls', '--duration', 0.5, cwd=tmp_path, visible=several_devices)
    assert r.returncode == 1, r
    assert r.lines[-1] == 'Use "--device" to specify the desired device.'
    target = sorted(several_devices.split(','))[0]
    r = harness.run(path, 'out.jls', '--duration', 0.5, '-d', target.split('/')[-1], cwd=tmp_path,
                    visible=several_devices)
    assert r.returncode == 0, r
    s = jls_files.summary(tmp_path / 'out.jls')
    model, serial_number = target.split('/')[1:]
    assert s['current']['source'] == f'{model.upper()}-{serial_number}'
