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
import numpy as np
import pytest


pytestmark = pytest.mark.parametrize('path', harness.paths('current_range_extract'))
SUMMARY = 'DataReader 2.00 seconds (200000 samples)'


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['filename', '--out', '-o', '--plot']:
        assert option in r.stdout


def test_no_args(path):
    r = harness.run(path)
    assert r.returncode == 2, r
    assert 'the following arguments are required: filename' in r.stderr


def test_summary_only(path, jls_v1, tmp_path):
    r = harness.run(path, jls_v1, cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.lines[0] == SUMMARY
    assert not r.plot_shown
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('ext', ['.txt', '.csv'])
def test_out_text(path, jls_v1, tmp_path, ext):
    r = harness.run(path, jls_v1, '--out', 'cr' + ext, cwd=tmp_path)
    assert r.returncode == 0, r
    lines = (tmp_path / ('cr' + ext)).read_text().splitlines()
    assert len(lines) == 200000
    assert set(lines) == {'4'}


def test_out_npy(path, jls_v1, tmp_path):
    r = harness.run(path, jls_v1, '-o', 'cr.npy', cwd=tmp_path)
    assert r.returncode == 0, r
    x = np.load(tmp_path / 'cr.npy')
    assert len(x) == 200000
    assert np.all(x == 4)


def test_out_unsupported(path, jls_v1, tmp_path):
    r = harness.run(path, jls_v1, '-o', 'cr.bad', cwd=tmp_path)
    assert r.returncode == 1, r
    assert r.lines[-1] == 'Unsupported save type: %s cr.bad'


def test_plot(path, jls_v1, tmp_path):
    r = harness.run(path, jls_v1, '--plot', cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.plot_shown


def test_v2_unsupported(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, cwd=tmp_path)
    assert r.returncode != 0, r


def test_large(path, tmp_path):
    # Over PLOT_POINTS_MAX and many chunks: read, written and plotted in pieces (6.47).
    jls_files.write_v1(tmp_path / 'big.jls', duration=15)  # 1.5 million samples
    r = harness.run(path, 'big.jls', '-o', 'cr.npy', '--plot', cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.plot_shown
    x = np.load(tmp_path / 'cr.npy')
    assert len(x) == 1_500_000
    assert np.all(x == 4)
