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


pytestmark = pytest.mark.parametrize('path', harness.paths('jls_export_points'))
SPAN = '2024-01-01T00:00:00+00:00 to 2024-01-01T00:00:01.999990+00:00'


def _csv(path):
    with open(path, 'rt') as f:
        lines = f.read().splitlines()
    header = lines[0] if lines[0].startswith('#') else None
    data = np.loadtxt(path, delimiter=',', ndmin=2)
    return header, data


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['input', 'output', '--verbose', '-v', '--columns', '--offset', '--duration',
                   '--ratio', '--no-header', '--count']:
        assert option in r.stdout


def test_no_args(path):
    r = harness.run(path)
    assert r.returncode == 2, r
    assert 'the following arguments are required: input, output' in r.stderr


def test_defaults(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, 'out.csv', cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.stdout == ''
    header, data = _csv(tmp_path / 'out.csv')
    assert header == '# voltage,current'
    assert data.shape == (100, 2)
    np.testing.assert_allclose(data[:, 0], jls_files.VOLTAGE, rtol=1e-6)
    # each point covers 0.02 s, a fifth of a PERIOD
    assert np.mean(data[:, 1]) == pytest.approx(jls_files.CURRENT_MEAN, rel=1e-3)
    assert np.all(data[:, 1] >= jls_files.CURRENT_LOW * 0.999)
    assert np.all(data[:, 1] <= jls_files.CURRENT_HIGH * 1.001)


def test_verbose(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, 'out.csv', '-v', '--count', 4, cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.lines == [
        'Columns to export:',
        f'  voltage: {SPAN}',
        f'  current: {SPAN}',
        f'Export 4 points over {SPAN}',
    ]
    assert _csv(tmp_path / 'out.csv')[1].shape == (4, 2)


def test_columns(path, jls_v2, tmp_path):
    columns = 'time,current,1.power,JS220-000415.voltage,2'
    r = harness.run(path, jls_v2, 'out.csv', '--columns', columns, '--count', 5, '--no-header',
                    cwd=tmp_path)
    assert r.returncode == 0, r
    header, data = _csv(tmp_path / 'out.csv')
    assert header is None
    assert data.shape == (5, 5)
    np.testing.assert_allclose(data[:, 0], np.arange(5) * 0.4, rtol=1e-4)
    np.testing.assert_allclose(data[:, 1], jls_files.CURRENT_MEAN, rtol=1e-4)
    np.testing.assert_allclose(data[:, 2], jls_files.POWER_MEAN, rtol=1e-4)
    np.testing.assert_allclose(data[:, 3:], jls_files.VOLTAGE, rtol=1e-6)


def test_header_names(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, 'out.csv', '--columns', 'time,power', cwd=tmp_path)
    assert r.returncode == 0, r
    assert _csv(tmp_path / 'out.csv')[0] == '# time,power'


def test_offset_duration(path, jls_v2, tmp_path):
    # Each point covers 0.05 s, half of a PERIOD, so alternates low and high.
    r = harness.run(path, jls_v2, 'out.csv', '--columns', 'current', '--count', 4,
                    '--offset', '2024-01-01T00:00:01Z', '--duration', '0.2s', cwd=tmp_path)
    assert r.returncode == 0, r
    data = _csv(tmp_path / 'out.csv')[1][:, 0]
    np.testing.assert_allclose(data, [jls_files.CURRENT_LOW, jls_files.CURRENT_HIGH] * 2, rtol=1e-3)


def test_ratio(path, jls_v2, tmp_path):
    # ratio 0.5 uses the first half of each point, which is always low.
    r = harness.run(path, jls_v2, 'out.csv', '--columns', 'current', '--count', 20, '--ratio', 0.5,
                    cwd=tmp_path)
    assert r.returncode == 0, r
    data = _csv(tmp_path / 'out.csv')[1][:, 0]
    np.testing.assert_allclose(data[1:], jls_files.CURRENT_LOW, rtol=1e-3)


def test_ratio_invalid(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, 'out.csv', '--ratio', 2, cwd=tmp_path)
    assert r.returncode == 2, r
    assert 'argument --ratio' in r.stderr


def test_offset_out_of_range(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, 'out.csv', '--offset', '2023-01-01T00:00:00Z', cwd=tmp_path)
    assert r.returncode == 1, r
    assert r.stderr.startswith('ERROR: offset 2023-01-01T00:00:00+00:00 out of range: ')
    assert not (tmp_path / 'out.csv').exists()


def test_duration_exceeded(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, 'out.csv', '--duration', 5, cwd=tmp_path)
    assert r.returncode == 1, r
    assert r.stderr.startswith('ERROR: Duration exceeded: ')
    assert not (tmp_path / 'out.csv').exists()


def test_duration_exceeded_in_seconds(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, 'out.csv', '--duration', 5, cwd=tmp_path)
    assert r.stderr.startswith('ERROR: Duration exceeded: 5.0 > 1.99'), r


def test_unknown_column(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, 'out.csv', '--columns', 'nope', cwd=tmp_path)
    assert r.returncode != 0, r
    assert 'nope' in r.stderr
    assert not (tmp_path / 'out.csv').exists()


def test_different_extents(path, jls_v2_multi, tmp_path):
    # two Joulescopes recorded together: export the window common to both
    r = harness.run(path, jls_v2_multi, 'out.csv', '--columns', 'time,1.current,2.current',
                    '--count', 10, cwd=tmp_path)
    assert r.returncode == 0, r
    header, data = _csv(tmp_path / 'out.csv')
    assert header == '# time,JS220-000415.current,JS110-000197.current'
    assert data.shape == (10, 3)
    # the common window: 10 ms after the JS220 start to the JS220 end
    np.testing.assert_allclose(data[:, 0], np.arange(10) * ((jls_files.DURATION - 0.01) / 10), rtol=1e-3)
    np.testing.assert_allclose(data[:, 2], jls_files.CURRENT_HIGH, rtol=1e-6)
    assert np.mean(data[:, 1]) == pytest.approx(jls_files.CURRENT_MEAN, rel=0.05)
