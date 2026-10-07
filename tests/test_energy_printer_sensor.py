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


pytestmark = pytest.mark.parametrize('path', harness.paths('energy_printer_sensor'))
ENERGY = re.compile(r'^-?\d+(\.\d+)? [pnµm]?J$')


def test_no_device(path):
    r = harness.run(path)
    assert r.returncode == 1, r
    assert 'No Joulescope found' in r.stderr


def test_device(path, device_path):
    r = harness.run(path, visible=device_path, interrupt_on=lambda out: out.count('\n') >= 4)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines[0] == 'CTRL-C to exit'
    assert r.lines[1] == '0.000 J'
    for line in r.lines[1:]:
        assert ENERGY.match(line), r
    assert 'DeprecationWarning' not in r.stderr, r
