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


pytestmark = pytest.mark.parametrize('path', harness.paths('capture_jls_v1'))
USAGE = 'usage: python3 capture_jls_v1.py [filename]'
START = 'Capturing data: type CTRL-C to stop'


@pytest.mark.parametrize('args', [[], ['a.jls', 'b.jls']])
def test_usage(path, args):
    r = harness.run(path, *args)
    assert r.lines == [USAGE]


def test_usage_exit_code(path):
    r = harness.run(path)
    assert r.returncode != 0, r


def test_no_device(path, tmp_path):
    r = harness.run(path, 'out.jls', cwd=tmp_path)
    assert r.returncode == 1, r
    assert 'No Joulescope found' in r.stderr


def test_ctrl_c(path, device_path, tmp_path):
    from joulescope.data_recorder import DataReader
    r = harness.run(path, 'out.jls', cwd=tmp_path, visible=device_path, interrupt_after=2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines == [START]
    reader = DataReader().open(str(tmp_path / 'out.jls'))
    try:
        fs = harness.SAMPLE_RATE[device_path.model]
        assert reader.sampling_frequency == fs
        s0, s1 = reader.sample_id_range
        assert s1 - s0 > 0
    finally:
        reader.close()
