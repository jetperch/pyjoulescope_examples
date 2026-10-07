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

"""capture.py wraps the pyjoulescope_driver record entry point, so its
command line follows that entry point."""

import harness
import jls_files
import pytest
import re


pytestmark = pytest.mark.parametrize('path', harness.paths('capture'))
START = 'Start recording.  Press CTRL-C to stop.'


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['filename', '--jsdrv_log_level', '--duration', '--frequency', '--signals']:
        assert option in r.stdout


def test_no_device(path, tmp_path):
    r = harness.run(path, '--duration', 0.5, 'out.jls', cwd=tmp_path)
    assert r.returncode == 1, r
    assert r.lines == ['Device not found']
    assert list(tmp_path.iterdir()) == []


def test_duration(path, device_path, tmp_path):
    r = harness.run(path, '--duration', 1, 'out.jls', cwd=tmp_path, visible=device_path)
    assert r.returncode == 0, r
    assert r.lines == [START]
    s = jls_files.summary(tmp_path / 'out.jls')
    assert sorted(s) == ['current', 'voltage']
    fs = harness.SAMPLE_RATE[device_path.model]
    assert s['current']['sample_rate'] == fs
    assert 0.8 * fs <= s['current']['length'] <= 1.2 * fs


def test_default_filename(path, device_path, tmp_path):
    r = harness.run(path, '--duration', 0.5, cwd=tmp_path, visible=device_path)
    assert r.returncode == 0, r
    files = [f.name for f in tmp_path.iterdir()]
    assert len(files) == 1
    assert re.match(r'^\d{8}_\d{6}\.jls$', files[0])
