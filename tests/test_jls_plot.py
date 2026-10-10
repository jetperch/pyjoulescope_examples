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


PROBE_TEXT = 'mpl_show_probe text: '  # see shim/mpl_show_probe.py

pytestmark = pytest.mark.parametrize('path', harness.paths('jls_plot'))
PNG = b'\x89PNG\r\n\x1a\n'


def _png(path):
    with open(path, 'rb') as f:
        return f.read(8) == PNG


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['input', '--out', '--stats', '--show', '--sample-count']:
        assert option in r.stdout


def test_no_args(path):
    r = harness.run(path)
    assert r.returncode == 2, r
    assert 'the following arguments are required: input' in r.stderr


def test_v2_out(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, '--out', 'out.png', '--stats', cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.lines == [f'Reading JLS v2: {jls_v2}']
    assert _png(tmp_path / 'out.png')
    assert not r.plot_shown


@pytest.mark.parametrize('option', ['--sample-count', '--sample_count'])
def test_v1_out(path, jls_v1, tmp_path, option):
    r = harness.run(path, jls_v1, '--out', 'out.png', '--stats', option, 500, cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.lines == [f'Reading JLS v1: {jls_v1}']
    assert _png(tmp_path / 'out.png')


def test_show(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, '--show', cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.plot_shown
    assert list(tmp_path.iterdir()) == []


def test_default_shows(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.plot_shown
    assert list(tmp_path.iterdir()) == []


def test_out_and_show(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, '--out', 'out.png', '--show', cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.plot_shown
    assert _png(tmp_path / 'out.png')


def test_sample_count_type(path, jls_v2):
    r = harness.run(path, jls_v2, '--sample-count', '1.5')
    assert r.returncode == 2, r
    assert "invalid int value: '1.5'" in r.stderr


def test_no_current(path, tmp_path):
    jls = jls_files.write_v2(tmp_path / 'v.jls', names=['voltage'])
    r = harness.run(path, jls, '--out', 'out.png', cwd=tmp_path)
    assert r.returncode == 1, r
    assert '"current" signal not found' in r.stdout


def test_not_jls(path, tmp_path):
    (tmp_path / 'x.jls').write_bytes(b'not a jls file at all')
    r = harness.run(path, 'x.jls', cwd=tmp_path)
    assert r.returncode == 1, r
    assert 'Unsupported file format' in r.stdout


def test_missing_file(path, tmp_path):
    r = harness.run(path, 'missing.jls', cwd=tmp_path)
    assert r.returncode != 0, r
    assert 'missing.jls' in r.stdout + r.stderr


def test_short_file(path, tmp_path):
    jls = jls_files.write_v2(tmp_path / 's.jls', duration=0.005)  # 500 samples
    r = harness.run(path, jls, '--out', 'out.png', cwd=tmp_path)
    assert r.returncode == 0, r
    assert _png(tmp_path / 'out.png')


@pytest.mark.parametrize('count', [2, 1000])
def test_stats_v2(path, jls_v2, count):
    # The duration and charge cover the whole file, whatever the plot resolution (6.46).
    r = harness.run(path, jls_v2, '--stats', '--show', '--sample-count', count)
    assert r.returncode == 0, r
    text = [x[len(PROBE_TEXT):] for x in r.stderr.splitlines() if x.startswith(PROBE_TEXT)]
    assert 't = 2.0 s' in text, r
    assert '∫=+4.00000 mC' in text, r
