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


pytestmark = pytest.mark.parametrize('path', harness.paths('hotplug'))


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--device', '-d', '--duration']:
        assert option in r.stdout


def test_invalid(path):
    r = harness.run(path, '--duration', 'x')
    assert r.returncode == 2, r


def test_no_device(path):
    r = harness.run(path, '--duration', 1)
    assert not r.interrupted, r
    assert r.returncode == 0, r
    assert r.stdout == ''


def test_ctrl_c(path):
    r = harness.run(path, interrupt_after=2)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r


def test_device(path, device_path):
    r = harness.run(path, '--duration', 1, visible=device_path)
    assert r.returncode == 0, r
    assert r.lines == [f'add {device_path}']


def test_hotplug(path, device_path):
    r = harness.run(path, '--duration', 5, visible=device_path, hotplug='add@2,remove@3,add@4')
    assert r.returncode == 0, r
    assert r.lines == [f'add {device_path}', f'remove {device_path}', f'add {device_path}']


def test_several_devices(path, several_devices):
    paths = sorted(several_devices.split(','))
    r = harness.run(path, '--duration', 1, visible=several_devices)
    assert r.returncode == 0, r
    assert sorted(r.lines) == [f'add {p}' for p in paths]
    for option in ['--device', '-d']:
        r = harness.run(path, '--duration', 1, option, paths[0].split('/')[-1], visible=several_devices)
        assert r.returncode == 0, r
        assert r.lines == [f'add {paths[0]}']
