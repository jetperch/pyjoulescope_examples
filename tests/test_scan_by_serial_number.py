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

import ast
import harness
import pytest


pytestmark = pytest.mark.parametrize('path', harness.paths('scan_by_serial_number'))


def _name(device_path):
    return f'{device_path.model.upper()}-{device_path.serial_number}'


def _info(line):
    info = ast.literal_eval(line)
    assert info['type'] == 'info'
    return info


def test_no_device_serial_number(path):
    r = harness.run(path, '000415')
    assert r.returncode == 1, r
    assert not r.has_traceback, r
    assert '000415' in r.stdout


def test_no_device_list(path):
    r = harness.run(path)
    assert r.returncode == 0, r
    assert r.stdout == ''


def test_list(path, device_path):
    r = harness.run(path, visible=device_path)
    assert r.returncode == 0, r
    assert r.lines == [_name(device_path)]


@pytest.mark.parametrize('form', ['serial_number', 'lower', 'model', 'name'])
def test_device(path, device_path, form):
    spec = {
        'serial_number': device_path.serial_number,
        'lower': device_path.serial_number.lower(),
        'model': device_path.model,
        'name': _name(device_path),
    }[form]
    r = harness.run(path, spec, visible=device_path)
    assert r.returncode == 0, r
    assert len(r.lines) == 1, r
    info = _info(r.lines[0])
    assert info['model'] == device_path.model
    assert info['serial_number'] == device_path.serial_number


def test_serial_number_unknown(path, device_path):
    r = harness.run(path, 'ZZZZ', visible=device_path)
    assert r.returncode == 1, r
    assert not r.has_traceback, r
    assert 'ZZZZ' in r.stdout
    assert device_path in r.stdout  # lists the available devices


def test_extra_args_ignored(path, device_path):
    r = harness.run(path, device_path.serial_number, 'extra', visible=device_path)
    assert r.returncode == 0, r
    assert _info(r.lines[0])['serial_number'] == device_path.serial_number


def test_several_devices(path, several_devices):
    paths = several_devices.split(',')
    r = harness.run(path, visible=several_devices)
    assert r.returncode == 0, r
    assert sorted(r.lines) == sorted(f'{p.split("/")[1].upper()}-{p.split("/")[2]}' for p in paths)
    serial_number = paths[-1].split('/')[-1]
    r = harness.run(path, serial_number, visible=several_devices)
    assert r.returncode == 0, r
    assert _info(r.lines[0])['serial_number'] == serial_number
    r = harness.run(path, several_devices, visible=several_devices)
    assert r.returncode == 1, r  # matches more than one
    assert not r.has_traceback, r
