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


pytestmark = pytest.mark.parametrize('path', harness.paths('capture_all'))
START = 'Capturing data: type CTRL-C to stop'


def _v1(path):
    """Return (sampling_frequency, sample_count) for a JLS v1 file."""
    from joulescope.data_recorder import DataReader
    r = DataReader().open(str(path))
    try:
        s0, s1 = r.sample_id_range
        return r.sampling_frequency, s1 - s0
    finally:
        r.close()


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--duration', '-d', '--frequency', '-f', '--out', '-o']:
        assert option in r.stdout


def test_duration_invalid(path):
    r = harness.run(path, '--duration', 'x')
    assert r.returncode == 2, r
    assert 'argument --duration' in r.stderr


def test_no_device_waits(path, tmp_path):
    r = harness.run(path, '-d', 1, cwd=tmp_path, interrupt_after=3)
    assert r.interrupted and not r.killed, r
    assert r.lines == [START]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.xfail(strict=True, reason='6.12 waits forever with no instrument')
def test_no_device_exits(path, tmp_path):
    r = harness.run(path, '-d', 1, cwd=tmp_path, timeout=10)
    assert not r.interrupted, r
    assert r.returncode == 1, r


def test_device(path, device_path, tmp_path):
    r = harness.run(path, '--duration', 1, cwd=tmp_path, visible=device_path)
    assert r.returncode == 0, r
    assert r.lines == [START]
    files = sorted(f.name for f in tmp_path.iterdir())
    assert files == [f'out_{device_path.serial_number}.jls']
    fs, n = _v1(tmp_path / files[0])
    assert fs == harness.SAMPLE_RATE[device_path.model]
    assert 0.8 * fs <= n <= 1.5 * fs


def test_out(path, device_path, tmp_path):
    r = harness.run(path, '-d', 0.5, '-o', 'x.jls', cwd=tmp_path, visible=device_path)
    assert r.returncode == 0, r
    assert sorted(f.name for f in tmp_path.iterdir()) == [f'x_{device_path.serial_number}.jls']


def test_ctrl_c(path, device_path, tmp_path):
    r = harness.run(path, cwd=tmp_path, visible=device_path, interrupt_after=2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    fs, n = _v1(tmp_path / f'out_{device_path.serial_number}.jls')
    assert n > 0.5 * fs


def test_frequency_unsupported(path, device_path, tmp_path):
    r = harness.run(path, '-d', 1, '-f', 123, cwd=tmp_path, visible=device_path)
    assert r.lines[0] == 'Unsupported frequency selected: 123'
    assert r.lines[1].startswith('Supported frequencies = [')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.xfail(strict=True, reason='6.12 returns 0 after an unsupported --frequency')
def test_frequency_unsupported_exit_code(path, device_path, tmp_path):
    r = harness.run(path, '-d', 1, '-f', 123, cwd=tmp_path, visible=device_path)
    assert r.returncode != 0, r


@pytest.mark.xfail(strict=True, reason='6.26 records nothing at low --frequency')
def test_frequency(path, device_path, tmp_path):
    r = harness.run(path, '-d', 1, '-f', 1000, cwd=tmp_path, visible=device_path)
    assert r.returncode == 0, r
    assert 'Traceback' not in r.stderr, r
    fs, n = _v1(tmp_path / f'out_{device_path.serial_number}.jls')
    assert fs == 1000
    assert 800 <= n <= 1500


def test_several_devices(path, several_devices, tmp_path):
    r = harness.run(path, '-d', 1, cwd=tmp_path, visible=several_devices)
    assert r.returncode == 0, r
    expect = sorted(f'out_{p.split("/")[-1]}.jls' for p in several_devices.split(','))
    assert sorted(f.name for f in tmp_path.iterdir()) == expect
