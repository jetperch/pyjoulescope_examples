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


pytestmark = pytest.mark.parametrize('path', harness.paths('read_by_method'))
MEMORY = re.compile(r'^Memory usage: \d+\.\d MB$')
FOUND = re.compile(r'^found (\d+) NaN out of (\d+) samples \((\d+\.\d{3}) seconds\)$')


@pytest.mark.parametrize('cwd', [None, 'tmp'])
def test_runs_anywhere(path, tmp_path, cwd):
    r = harness.run(path, '--help', cwd=tmp_path if cwd else None)
    assert r.returncode == 0, r


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--duration', '-d', '--contiguous', '-c', '--plot']:
        assert option in r.stdout


def test_invalid(path):
    r = harness.run(path, '-d', 'x')
    assert r.returncode == 2, r
    assert 'argument --duration' in r.stderr


def test_duration_max(path):
    r = harness.run(path, '-d', 121)
    assert r.returncode == 0, r
    assert r.lines == ['To capture more than 120 seconds, see the read_by_callback.py example']


def test_no_device(path):
    r = harness.run(path, '-d', 0.1)
    assert r.returncode == 1, r
    assert 'No Joulescope found' in r.stderr


@pytest.mark.parametrize('args, duration', [(['--duration', 0.2], 0.2), (['-c', 0.1], 0.1)])
def test_read(path, device_path, args, duration):
    r = harness.run(path, *args, visible=device_path)
    assert r.returncode == 0, r
    assert MEMORY.match(r.lines[0]), r
    m = FOUND.match(r.lines[1])
    assert m, r
    assert int(m.group(2)) == round(duration * harness.SAMPLE_RATE[device_path.model])
    assert m.group(3) == f'{duration:.3f}'
    assert 'INFO     root read start' in r.stderr  # logs at INFO by default


def test_plot(path, device_path):
    r = harness.run(path, '-d', 0.1, '--plot', visible=device_path)
    assert r.returncode == 0, r
    assert r.plot_shown
