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


pytestmark = pytest.mark.parametrize('path', harness.paths('jls_recode'))


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    assert 'infile' in r.stdout and 'outfile' in r.stdout


def test_no_args(path):
    r = harness.run(path)
    assert r.returncode == 2, r
    assert 'the following arguments are required: infile, outfile' in r.stderr


def test_recode(path, jls_v1, tmp_path):
    from joulescope.data_recorder import DataReader
    r = harness.run(path, jls_v1, 'out.jls', cwd=tmp_path)
    assert r.returncode == 0, r
    assert r.lines[0] == 'samples=200000, fs=100000.0'
    assert r.lines[-1].startswith('[====')
    assert '100.0%' in r.lines[-1]
    assert ' INFO ' in r.stderr  # logs at INFO by default
    reader = DataReader().open(str(tmp_path / 'out.jls'))
    try:
        assert reader.sample_id_range == [0, 200000]
        i = reader.samples_get(0, 200000, units='samples', fields=['current'])['signals']['current']['value']
        np.testing.assert_allclose(i, jls_files.signals()['current'], rtol=1e-4)
    finally:
        reader.close()


def test_v2_unsupported(path, jls_v2, tmp_path):
    r = harness.run(path, jls_v2, 'out.jls', cwd=tmp_path)
    assert r.returncode != 0, r
    assert 'invalid file' in r.stderr
