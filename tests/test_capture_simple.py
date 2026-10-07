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


pytestmark = pytest.mark.parametrize('path', harness.paths('capture_simple'))
LINE = re.compile(r'^(\S+) A, (\S+) V$')


def test_no_device(path):
    r = harness.run(path)
    assert r.returncode == 1, r
    assert 'No Joulescope found' in r.stderr


def test_ignores_args(path):
    r = harness.run(path, '--help')
    assert r.returncode == 1, r
    assert 'No Joulescope found' in r.stderr


def test_device(path, device_path):
    r = harness.run(path, visible=device_path)
    assert r.returncode == 0, r
    assert len(r.lines) == 1, r
    m = LINE.match(r.lines[0])
    assert m, r
    float(m.group(1))
    assert -1.0 < float(m.group(2)) < 16.0


def test_several_devices(path, several_devices):
    r = harness.run(path, visible=several_devices)
    assert r.returncode == 1, r
    assert 'Multiple Joulescopes found' in r.stderr
