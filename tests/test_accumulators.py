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


pytestmark = pytest.mark.parametrize('path', harness.paths('accumulators'))
SUMMARY = re.compile(r'^duration = (\d+) s, charge = -?[\d.]+ [pnµm]?C, energy = -?[\d.]+ [pnµm]?J$')


def _updated(out):
    return 'duration = ' in out


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--duration', '-d', '--update', '-u', '--source', '-s', 'stream_buffer', 'sensor']:
        assert option in r.stdout


@pytest.mark.parametrize('args', [['--duration', '1.5'], ['--update', 'x'], ['--source', 'host']])
def test_invalid(path, args):
    r = harness.run(path, *args)
    assert r.returncode == 2, r
    assert f'argument {args[0]}' in r.stderr


def test_no_device(path):
    r = harness.run(path)
    assert r.returncode == 1, r
    assert 'No Joulescope found' in r.stderr


def test_duration(path, device_path):
    for args in [['--duration', 3, '--update', 1], ['-d', 3, '-u', 1, '-s', 'stream_buffer']]:
        r = harness.run(path, *args, visible=device_path)
        assert r.returncode == 0, r
        assert r.lines[:3] == ['Accumulation in progress for 3 seconds.',
                               'Updates displayed every 1 seconds.',
                               'Press CTRL-C to stop.']
        assert r.lines[-2] == 'Capture duration completed.'
        for line in r.lines[3:-2] + [r.lines[-1]]:
            assert SUMMARY.match(line), r


def test_duration_updates(path, device_path, request):
    if device_path.model == 'js320':
        request.applymarker(pytest.mark.xfail(strict=True, reason=harness.U1))
    r = harness.run(path, '-d', 3, '-u', 1, visible=device_path)
    updates = [SUMMARY.match(x).group(1) for x in r.lines[3:-2]]
    assert updates in (['1', '2'], ['1', '2', '3']), r  # the update at 3 s may arrive before the stop


def test_ctrl_c(path, device_path):
    r = harness.run(path, '-u', 1, visible=device_path, interrupt_on=_updated)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines[:3] == ['Accumulation in progress.',
                           'Updates displayed every 1 seconds.',
                           'Press CTRL-C to stop.']
    assert r.lines[-2] == 'User exit requested.'
    assert SUMMARY.match(r.lines[-1]), r


def test_sensor(path, device_path):
    r = harness.run(path, '--source', 'sensor', '-u', 1, visible=device_path,
                    interrupt_on=_updated)
    assert r.interrupted and not r.killed, r
    assert r.lines[:3] == ['Accumulation in progress.',
                           'Updates displayed every 1 seconds.',
                           'Press CTRL-C to stop.']
    assert SUMMARY.match(r.lines[3]), r
    assert 'Warning' not in r.stderr, r


def test_sensor_duration(path, device_path):
    r = harness.run(path, '--source', 'sensor', '-d', 2, '-u', 1, visible=device_path, timeout=10)
    assert not r.interrupted, r
    assert r.returncode == 0, r
    assert r.lines[0] == 'Accumulation in progress for 2 seconds.'
    assert r.lines[-2] == 'Capture duration completed.'
    assert SUMMARY.match(r.lines[-1]), r


def test_sensor_ctrl_c(path, device_path):
    r = harness.run(path, '--source', 'sensor', '-u', 1, visible=device_path,
                    interrupt_on=_updated)
    assert r.returncode == 0, r
    assert r.lines[-2] == 'User exit requested.'
    assert SUMMARY.match(r.lines[-1]), r
