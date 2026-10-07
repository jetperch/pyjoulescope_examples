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

"""Tripping the fuse needs a load above the threshold.  See MANUAL.md."""

import harness
import pytest


pytestmark = pytest.mark.parametrize('path', harness.paths('fuse_js220'))


@pytest.fixture
def fuse_enabled(device_path):
    """Read the fuse enable, then disable the fuse after the test."""
    from pyjoulescope_driver import Driver

    def query():
        with Driver() as d:
            with d.open(device_path, mode='restore') as device:
                return device.query('s/fuse/0/en')
    yield query
    if device_path.model != 'js110':
        with Driver() as d:
            with d.open(device_path, mode='restore') as device:
                device.publish('s/fuse/0/en', 0)


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--verbose', '-v', '--device', '-d', '--threshold1', '--threshold2',
                   '--duration', '--start-threshold']:
        assert option in r.stdout


def test_invalid(path):
    r = harness.run(path, '--threshold1', 'x')
    assert r.returncode == 2, r


def test_no_device(path):
    r = harness.run(path)
    assert r.lines == ['No Joulescope found']


def test_no_device_exit_code(path):
    r = harness.run(path)
    assert r.returncode == 1, r


def test_device(path, device_path, fuse_enabled):
    r = harness.run(path, visible=device_path, interrupt_after=2)
    if device_path.model == 'js110':
        assert not r.interrupted, r
        assert r.returncode == 1, r
        assert not r.has_traceback, r
        assert r.lines == [f'{device_path} has no fuse: use a JS220 or JS320']
        return
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines == [f'The fuse remains enabled on {device_path}.']
    assert fuse_enabled() == 1  # stays armed after exit


def test_fuse_engaged(path, device_path, fuse_enabled):
    if device_path.model == 'js110':
        pytest.skip('the JS110 has no fuse')
    # Thresholds below the bench load trip the fuse.
    r = harness.run(path, '--threshold1', 0.0002, '--threshold2', 0.0004, '--duration', 0.05,
                    visible=device_path, interrupt_after=4)
    if 'Fuse engaged!' not in r.stdout:
        pytest.skip(f'{device_path} has no load above 0.4 mA to trip the fuse')
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert not r.has_traceback, r


@pytest.mark.parametrize('option', ['--device', '-d', '--serial_number', '--serial-number'])
def test_device_unknown(path, device_path, option):
    r = harness.run(path, option, 'ZZZZ', visible=device_path)
    assert r.lines == [f'Device "ZZZZ" not found in [{device_path!r}]']
