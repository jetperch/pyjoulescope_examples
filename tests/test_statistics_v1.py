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


pytestmark = pytest.mark.parametrize('path', harness.paths('statistics_v1'))
LINE = re.compile(r'^\d+\.\d: -?\d+\.\d{9} A, -?\d+\.\d{3} V, -?\d+\.\d{9} W, '
                  r'-?\d+\.\d{9} C, -?\d+\.\d{9} J$')


def test_no_device(path):
    r = harness.run(path)
    assert r.lines == ['No Joulescope device found']


def test_no_device_exit_code(path):
    r = harness.run(path)
    assert r.returncode == 1, r


def test_device(path, device_path):
    r = harness.run(path, visible=device_path, timeout=30)
    assert not r.interrupted, r
    assert r.returncode == 0, r
    assert 5 <= len(r.lines) <= 25, r
    for line in r.lines:
        assert LINE.match(line), r
    assert r.lines[0].startswith('0.0: ')
