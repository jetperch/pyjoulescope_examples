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
PROMPT = 'Type number and enter: '


def _info(line):
    info = ast.literal_eval(line)
    assert info['type'] == 'info'
    return info


def test_no_device_serial_number(path):
    r = harness.run(path, '000415')
    assert r.returncode == 1, r
    assert 'Device not found with serial number 000415' in r.stderr


def test_no_device_prompt(path):
    r = harness.run(path)
    assert r.returncode == 1, r
    assert r.stdout == PROMPT
    assert 'EOFError' in r.stderr


def test_serial_number(path, device_path):
    r = harness.run(path, device_path.serial_number, visible=device_path)
    assert r.returncode == 0, r
    assert len(r.lines) == 1, r
    info = _info(r.lines[0])
    assert info['model'] == device_path.model
    assert info['serial_number'] == device_path.serial_number


def test_serial_number_unknown(path, device_path):
    r = harness.run(path, 'ZZZZ', visible=device_path)
    assert r.returncode == 1, r
    assert 'Device not found with serial number ZZZZ' in r.stderr


def test_serial_number_case_sensitive(path, device_path):
    serial_number = device_path.serial_number.lower()
    if serial_number == device_path.serial_number:
        pytest.skip('serial number has no letters')
    r = harness.run(path, serial_number, visible=device_path)
    assert r.returncode == 1, r
    assert f'Device not found with serial number {serial_number}' in r.stderr


def test_prompt(path, device_path):
    r = harness.run(path, stdin='1\n', visible=device_path)
    assert r.returncode == 0, r
    assert r.lines[0] == f'1: {device_path.serial_number}'
    assert r.lines[1].startswith(PROMPT)
    info = _info(r.lines[1][len(PROMPT):])
    assert info['serial_number'] == device_path.serial_number


def test_prompt_eof(path, device_path):
    r = harness.run(path, visible=device_path)
    assert r.returncode == 1, r
    assert r.stdout == f'1: {device_path.serial_number}\n{PROMPT}'
    assert 'EOFError' in r.stderr


def test_too_many_args_prompts(path, device_path):
    r = harness.run(path, device_path.serial_number, 'extra', stdin='1\n', visible=device_path)
    assert r.returncode == 0, r
    assert r.lines[0] == f'1: {device_path.serial_number}'


def test_several_devices(path, several_devices):
    serial_numbers = [p.split('/')[-1] for p in several_devices.split(',')]
    r = harness.run(path, stdin='2\n', visible=several_devices)
    assert r.returncode == 0, r
    listed = r.lines[:len(serial_numbers)]
    assert [x.split(': ')[0] for x in listed] == [str(k + 1) for k in range(len(serial_numbers))]
    assert sorted(x.split(': ')[1] for x in listed) == sorted(serial_numbers)
    info = _info(r.lines[len(serial_numbers)][len(PROMPT):])
    assert info['serial_number'] == listed[1].split(': ')[1]
    r = harness.run(path, serial_numbers[-1], visible=several_devices)
    assert r.returncode == 0, r
    assert _info(r.lines[0])['serial_number'] == serial_numbers[-1]
