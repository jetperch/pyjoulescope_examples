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

"""The current ranging filter is a JS110 feature."""

import harness
import pytest


pytestmark = pytest.mark.parametrize('path', harness.paths('current_ranging_filter'))


def test_no_device(path):
    r = harness.run(path)
    assert r.returncode == 1, r
    assert 'No Joulescope found' in r.stderr


def test_device(path, device_path):
    r = harness.run(path, visible=device_path)
    if device_path.model == 'js110':
        assert r.returncode == 0, r
        assert r.lines == ['read 1: mean_1_3_1', 'read 2: mean_4_8_4', 'read 3: NaN_0_1_0']
    else:
        assert r.returncode == 1, r
        assert 'value mean_1_3_1 not allowed for parameter current_ranging' in r.stderr
