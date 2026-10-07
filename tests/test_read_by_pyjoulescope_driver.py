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


pytestmark = pytest.mark.parametrize('path', harness.paths('read_by_pyjoulescope_driver'))
LINE = re.compile(r'^(u/\w+/\w+)\.(\w+(\[\d\])?): +(\S+) (\S*) \| (.+)$')
NO_JS320 = '6.22 no JS320 support: skips it, then waits forever'


def _parse(lines):
    rv = {}
    for line in lines:
        m = LINE.match(line)
        assert m, line
        rv[(m.group(1), m.group(2))] = {'mean': float(m.group(4)), 'units': m.group(5), 'msg': m.group(6)}
    return rv


def _samples(msg):
    m = re.match(r'^(\d+) samples$', msg)
    assert m, msg
    return int(m.group(1))


def _xfail_js320(request, device_path):
    if device_path.model == 'js320':
        request.applymarker(pytest.mark.xfail(strict=True, reason=NO_JS320))


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--verbose', '-v', '--duration', '-d', '--frequency', '-f', '--serial_number',
                   '--open', '-o', '--signals', '--no-progress']:
        assert option in r.stdout


@pytest.mark.parametrize('args', [['-d', 'x'], ['-f', '1.5'], ['--open', 'raw']])
def test_invalid(path, args):
    r = harness.run(path, *args)
    assert r.returncode == 2, r


def test_invalid_signal(path):
    r = harness.run(path, '--signals', 'bogus')
    assert r.returncode == 1, r
    assert 'bogus' in r.stderr


def test_no_device(path):
    r = harness.run(path)
    assert r.returncode == 1, r
    assert r.lines == ['Device not found']


def test_default(path, device_path, request):
    _xfail_js320(request, device_path)
    r = harness.run(path, visible=device_path, timeout=10)
    assert r.returncode == 0, r
    assert r.lines[0].startswith('[-----')
    assert '100%' in r.lines[-3]
    data = _parse(r.lines[-2:])
    assert sorted(data) == [(device_path, 'current'), (device_path, 'voltage')]
    assert data[(device_path, 'current')]['units'] == 'A'
    assert data[(device_path, 'voltage')]['units'] == 'V'
    fs = harness.SAMPLE_RATE[device_path.model]
    for value in data.values():
        assert abs(_samples(value['msg']) - fs) <= 0.01 * fs


def test_signals(path, device_path, request):
    _xfail_js320(request, device_path)
    r = harness.run(path, '-d', 0.5, '--no-progress', '--signals', 'i,v,p,r,0', visible=device_path,
                    timeout=10)
    assert r.returncode == 0, r
    data = _parse(r.lines)
    assert [k[1] for k in data] == ['current', 'voltage', 'power', 'current_range', 'gpi[0]']
    fs = harness.SAMPLE_RATE[device_path.model]
    for name in ['current', 'voltage', 'power']:
        assert abs(_samples(data[(device_path, name)]['msg']) - fs // 2) <= 0.01 * fs


def test_verbose(path, device_path, request):
    _xfail_js320(request, device_path)
    r = harness.run(path, '-v', '-d', 0.2, '--no-progress', visible=device_path, timeout=10)
    assert r.returncode == 0, r
    assert r.lines[:5] == [
        'Find the connected devices',
        f"Found devices: ['{device_path}']",
        'Open and configure each device',
        'Perform the sample read',
        'Display the mean (ignoring NaNs) for each signal',
    ]


def test_options(path, device_path):
    # "--open restore" skips the model check, so this also runs on the JS320.
    r = harness.run(path, '-d', 0.3, '--no-progress', '--serial_number', device_path.serial_number,
                    '-f', 100000, '--open', 'restore', visible=device_path, timeout=10)
    assert r.returncode == 0, r
    data = _parse(r.lines)
    for value in data.values():
        assert abs(_samples(value['msg']) - 30000) <= 300


def test_serial_number_unknown(path, device_path):
    r = harness.run(path, '--serial_number', 'ZZZZ', visible=device_path)
    assert r.returncode == 1, r
    assert r.lines == ['Device not found']


@pytest.mark.xfail(strict=True, reason='6.28 waits forever for an unavailable signal')
def test_unavailable_signal(path, device_path):
    if device_path.model != 'js110':
        pytest.skip('trigger_in is only unavailable on the JS110')
    r = harness.run(path, '-d', 0.2, '--signals', 'i,T', visible=device_path, timeout=10)
    assert not r.interrupted, r
    assert r.returncode != 0, r


def test_several_devices(path, several_devices):
    supported = [p for p in several_devices.split(',') if '/js320/' not in p]
    r = harness.run(path, '-d', 0.3, '--no-progress', visible=','.join(supported), timeout=15)
    assert r.returncode == 0, r
    data = _parse(r.lines)
    assert sorted(data) == sorted((p, s) for p in supported for s in ['current', 'voltage'])
