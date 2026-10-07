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


pytestmark = pytest.mark.parametrize('path', harness.paths('jls_energy_plot'))
PNG = b'\x89PNG\r\n\x1a\n'


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['infile', '--verbose', '-v', '--sample-count', '--out', '--show']:
        assert option in r.stdout


def test_no_args(path):
    r = harness.run(path)
    assert r.returncode == 2, r
    assert 'the following arguments are required: infile' in r.stderr


def test_default_shows(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.stdout == ''
    assert r.plot_shown
    assert list(tmp_path.iterdir()) == []


def test_verbose(path, jls_v2, tmp_path):
    for verbose in ['-v', '--verbose']:
        r = harness.run(path, jls_v2, verbose, cwd=tmp_path)
        assert r.returncode == 0, r
        assert r.lines == [
            f'Opening JLS file {jls_v2}',
            'Extract data: dt=1e-05 s, incr=1, length=200000 | 200000 of 200000 samples',
            'Create plot',
            'Show plot',
        ]


@pytest.mark.parametrize('option', ['--sample-count', '--sample_count'])
def test_out(path, jls_v2, tmp_path, option):
    r = harness.run(path, jls_v2, '--out', 'e.png', '-v', option, 1000, cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.lines == [
        f'Opening JLS file {jls_v2}',
        'Extract data: dt=0.002 s, incr=200, length=1000 | 200000 of 200000 samples',
        'Create plot',
        'Save plot to e.png',
    ]
    assert not r.plot_shown
    assert (tmp_path / 'e.png').read_bytes()[:8] == PNG


def test_out_and_show(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, '--out', 'e.png', '--show', cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.plot_shown
    assert (tmp_path / 'e.png').read_bytes()[:8] == PNG


def test_no_power(path, tmp_path):
    jls = jls_files.write_v2(tmp_path / 'v.jls', names=['current', 'voltage'])
    r = harness.run(path, jls, cwd=tmp_path)
    assert r.returncode == 1, r
    assert r.lines[0] == 'Could not find power signal.  For JLS info, type:'
    assert r.lines[1].endswith(f' -m pyjls info {jls}')
    assert not r.plot_shown


def test_v1_unsupported(path, jls_v1, tmp_path):
    r = harness.run(path, jls_v1, '--out', 'e.png', cwd=tmp_path)
    assert r.returncode != 0, r
    assert not (tmp_path / 'e.png').exists()
