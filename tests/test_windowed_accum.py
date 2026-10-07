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

"""Windows need IN0 wiring.  See MANUAL.md."""

import harness
import pytest


pytestmark = pytest.mark.parametrize('path', harness.paths('windowed_accum'))
REASON = '6.19 imports joulescope.stream_buffer.stats_to_api, which joulescope 1.6 removed'


def test_import_fails(path):
    r = harness.run(path, '--help')
    assert r.returncode == 1, r
    assert 'stats_to_api' in r.stderr


@pytest.mark.xfail(strict=True, reason=REASON)
def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--io_voltage', '-v', '--out', '-o']:
        assert option in r.stdout


@pytest.mark.xfail(strict=True, reason=REASON)
def test_device(path, device_path, tmp_path):
    r = harness.run(path, '-o', 'out.csv', cwd=tmp_path, visible=device_path, interrupt_after=3)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines[:2] == ['Detecting triggers.  Press CTRL-C to exit.',
                           '#utc_timestamp,duration(s),charge(C),energy(J)']
    assert (tmp_path / 'out.csv').read_text().splitlines()[0] == \
        '#utc_timestamp,duration(s),charge(C),energy(J)'
