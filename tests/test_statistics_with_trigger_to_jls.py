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

"""The trigger needs more than 1 mA, so the trigger tests skip without a load."""

import harness
import jls_files
import pytest
import re


pytestmark = pytest.mark.parametrize('path', harness.paths('statistics_with_trigger_to_jls'))
ROW = re.compile(r'^\d+\.\d,-?\d+\.\d{9},-?\d+\.\d{3},-?\d+\.\d{9},-?\d+\.\d{9},-?\d+\.\d{9}$')
NAME = re.compile(r'^\d{8}_\d{6}$')


def _run_trigger(path, device_path, tmp_path, *args):
    r = harness.run(path, *args, cwd=tmp_path, visible=device_path,
                    interrupt_on=lambda out: 'jls capture stop' in out or 'Traceback' in out,
                    timeout=8)
    if 'trigger' not in r.stdout:
        pytest.skip(f'{device_path} has no load above 1 mA to trigger')
    return r


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--duration', '--signals']:
        assert option in r.stdout


def test_no_device(path, tmp_path):
    r = harness.run(path, cwd=tmp_path)
    assert r.returncode == 1, r
    assert 'No Joulescope found' in r.stderr


def test_statistics(path, device_path, tmp_path):
    r = harness.run(path, '--duration', 1, cwd=tmp_path, visible=device_path, interrupt_after=3.5)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    csv = [f for f in tmp_path.iterdir() if f.suffix == '.csv']
    assert len(csv) == 1
    assert NAME.match(csv[0].stem)
    rows = csv[0].read_text().splitlines()
    assert len(rows) >= 2
    for row in rows:
        assert ROW.match(row), row
    assert rows[0].startswith('0.0,')
    assert 'Warning' not in r.stderr, r


def test_trigger(path, device_path, tmp_path):
    r = _run_trigger(path, device_path, tmp_path, '--duration', 1)
    assert r.lines == ['trigger', 'jls capture start', 'jls capture stop'], r
    jls = [f for f in tmp_path.iterdir() if f.suffix == '.jls']
    assert len(jls) == 1
    assert jls[0].stem.endswith('_0000')
    s = jls_files.summary(jls[0])
    assert sorted(s) == ['current', 'voltage']
    fs = harness.SAMPLE_RATE[device_path.model]
    assert s['current']['sample_rate'] == fs
    assert s['current']['length'] >= fs


def test_trigger_source_model(path, device_path, tmp_path):
    from pyjls import Reader
    _run_trigger(path, device_path, tmp_path, '--duration', 1)
    jls = [f for f in tmp_path.iterdir() if f.suffix == '.jls'][0]
    with Reader(str(jls)) as r:
        assert r.sources[1].model.lower() == device_path.model


def test_trigger_without_duration(path, device_path, tmp_path):
    r = _run_trigger(path, device_path, tmp_path)
    assert 'Traceback' not in r.stderr, r
