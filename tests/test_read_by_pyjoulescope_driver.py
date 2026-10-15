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

import contextlib
import harness
import importlib.util
import numpy as np
import os
import pytest
import re
from pyjoulescope_driver import time64


pytestmark = pytest.mark.parametrize('path', harness.paths('read_by_pyjoulescope_driver'))
LINE = re.compile(r'^(u/\w+/\w+)\.(\w+(\[\d\])?): +(\S+) (\S*) \| (.+)$')


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


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--verbose', '-v', '--duration', '-d', '--frequency', '-f', '--device',
                   '--open', '-o', '--signals', '--no-progress', '--stall-timeout']:
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


def test_default(path, device_path):
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


def test_signals(path, device_path):
    r = harness.run(path, '-d', 0.5, '--no-progress', '--signals', 'i,v,p,r,0', visible=device_path,
                    timeout=10)
    assert r.returncode == 0, r
    data = _parse(r.lines)
    assert [k[1] for k in data] == ['current', 'voltage', 'power', 'current_range', 'gpi[0]']
    fs = harness.SAMPLE_RATE[device_path.model]
    for name in ['current', 'voltage', 'power']:
        assert abs(_samples(data[(device_path, name)]['msg']) - fs // 2) <= 0.01 * fs


def test_verbose(path, device_path):
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
    r = harness.run(path, '-d', 0.3, '--no-progress', '--device', device_path.serial_number,
                    '-f', 100000, '--open', 'restore', visible=device_path, timeout=10)
    assert r.returncode == 0, r
    data = _parse(r.lines)
    for value in data.values():
        assert abs(_samples(value['msg']) - 30000) <= 300


@pytest.mark.parametrize('option', ['--device', '--serial_number', '--serial-number'])
def test_device_unknown(path, device_path, option):
    r = harness.run(path, option, 'ZZZZ', visible=device_path)
    assert r.returncode == 1, r
    assert r.lines == ['Device not found']


@pytest.mark.parametrize('option', ['--device', '--serial_number', '--serial-number'])
def test_device_spec(path, several_devices, option):
    device_path = several_devices.split(',')[0]
    model = device_path.split('/')[1]
    for spec in [device_path.split('/')[2].lower(), f'{model}-{device_path.split("/")[2]}']:
        r = harness.run(path, '-d', 0.2, '--no-progress', option, spec, visible=several_devices,
                        timeout=15)
        assert r.returncode == 0, r
        assert sorted(_parse(r.lines)) == [(device_path, 'current'), (device_path, 'voltage')]


def test_unavailable_signal(path, device_path):
    if device_path.model != 'js110':
        pytest.skip('trigger_in is only unavailable on the JS110')
    r = harness.run(path, '-d', 0.2, '--signals', 'i,T', visible=device_path, timeout=10)
    assert not r.interrupted, r
    assert r.returncode == 1, r
    assert not r.has_traceback, r
    assert 's/gpi/7/ctrl' in r.stdout


def test_dropped_samples(path, device_path):
    # GitHub #15: dropped samples read as NaN for float signals.
    r = harness.run(path, '-d', 0.5, '--no-progress', visible=device_path, timeout=10,
                    data_fault='drop@3')
    assert r.returncode == 0, r
    skips = [x for x in r.lines if x.startswith('Skip ')]
    assert sorted(x.split(':')[0] for x in skips) == [f'Skip {device_path}.current',
                                                      f'Skip {device_path}.voltage'], r
    data = _parse([x for x in r.lines if x not in skips])
    for value in data.values():
        m = re.match(r'^ignored (\d+) NaNs in (\d+) samples', value['msg'])
        assert m, r
        nan_count, sample_count = int(m.group(1)), int(m.group(2))
        assert 0 < nan_count < 0.25 * sample_count, r


def test_data_error(path, device_path):
    # GitHub #16: an error in the data callback stops the read.
    r = harness.run(path, '-d', 0.5, '--no-progress', visible=device_path, timeout=10,
                    data_fault='corrupt@3')
    assert not r.interrupted, r
    assert r.returncode == 1, r
    assert 'TypeError' in r.stderr, r


def _stall_lines(r, device_path, signal):
    return [x.strip() for x in r.lines if x.strip().startswith(f'{device_path}.{signal}:')]


def test_interrupt_reports_state(path, device_path):
    # Ctrl-C during a read that is still progressing shows each signal's state.
    r = harness.run(path, '-d', 30, '--no-progress', visible=device_path, interrupt_after=3,
                    timeout=10)
    assert r.interrupted and not r.killed, r
    assert r.returncode != 0, r
    assert r.lines[0].startswith('read interrupted: '), r
    for signal in ['current', 'voltage']:
        lines = _stall_lines(r, device_path, signal)
        assert len(lines) == 1 and ' messages, ' in lines[0], r
    assert any(x.strip().startswith('common window: +0.0') for x in r.lines), r


def test_stall_no_data(path, device_path):
    # An instrument that acknowledges the stream but never sends data: fail
    # with the state of each signal instead of waiting forever.
    r = harness.run(path, '-d', 0.5, '--no-progress', '--stall-timeout', 1, visible=device_path,
                    timeout=10, data_fault='mute@1')
    assert not r.interrupted, r
    assert r.returncode == 1, r
    assert r.lines[0] == 'read stalled: 0.000 of 0.5 s, no progress for 1.0 s', r
    for signal in ['current', 'voltage']:
        assert _stall_lines(r, device_path, signal) == [f'{device_path}.{signal}: no data'], r
    assert not any('common window' in x for x in r.lines), r


def test_stall_after_data(path, device_path):
    # Data that stops after two messages: report the count, age and window.
    r = harness.run(path, '-d', 2, '--no-progress', '--stall-timeout', 1, visible=device_path,
                    timeout=10, data_fault='mute@3')
    assert not r.interrupted, r
    assert r.returncode == 1, r
    assert r.lines[0].startswith('read stalled: 0.'), r
    for signal in ['current', 'voltage']:
        lines = _stall_lines(r, device_path, signal)
        assert len(lines) == 1, r
        # the signals start a few ms apart, so only the earliest is at +0.000
        m = re.match(rf'^{re.escape(device_path)}\.{signal}: 2 messages, (\d+) samples, '
                     r'last ([\d.]+) s ago, utc \+([\d.]+) to \+([\d.]+) s$', lines[0])
        assert m, r
        assert int(m.group(1)) > 0, r
        assert 1.0 <= float(m.group(2)) < 5.0, r
        assert float(m.group(3)) < float(m.group(4)) < 1.0, r
    assert any(x.strip().startswith('common window: +0.0') for x in r.lines), r


def _read_module():
    """Import read.py in-process, for read() with a fake driver.

    The bin/ wrapper runs the example on import, so always load the module
    from examples/, and the module-level parametrization runs each
    in-process test once per path.
    """
    spec = importlib.util.spec_from_file_location(
        'read_example', os.path.join(harness.REPO_PATH, 'examples', 'pyjoulescope_driver', 'read.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeDriver:
    """Delivers 5 messages of 100 samples at 1 kHz on each ctrl=1, with a
    UTC offset per device, so the devices' windows can be made disjoint."""

    def __init__(self, offsets):
        self.offsets = offsets  # device_path -> UTC offset in seconds
        self.fns = {}
        self.published = []  # (topic, value) for each ctrl publish
        self.t0 = time64.now()

    def subscribe(self, topic, flags, fn, timeout=None):
        self.fns[topic] = fn
        return contextlib.nullcontext()

    def unsubscribe(self, topic, fn, timeout=None):
        self.fns.pop(topic, None)

    def publish(self, topic, value, timeout=None):
        if not topic.endswith('/ctrl'):
            return
        self.published.append((topic, value))
        if value != 1:
            return
        device_path, _, ctrl = topic.partition('/s/')
        data_topic = f'{device_path}/s/{ctrl[:-len("ctrl")]}!data'
        offset = self.offsets[device_path]
        for i in range(5):
            self.fns[data_topic](data_topic, {
                'sample_id': i * 100,
                'utc': self.t0 + int((offset + i * 0.1) * time64.SECOND),
                'decimate_factor': 1,
                'sample_rate': 1000,
                'data': np.zeros(100, dtype=np.float32),
            })


def test_read_in_process_two_devices(path):
    read = _read_module().read
    signals = [('u/js220/1', 'current'), ('u/js320/2', 'current')]
    data = read(_FakeDriver({'u/js220/1': 0.0, 'u/js320/2': 0.1}), signals, duration=0.3,
                stall_timeout=0.5)
    assert sorted(data) == signals
    assert len(data[signals[0]]['samples']) > 0


def test_read_in_process_fails_on_disjoint_utc(path):
    # Both devices deliver data, but one device's UTC is 10 s ahead, so the
    # common window is far from the duration: fail at once and show why.
    read = _read_module().read
    signals = [('u/js220/1', 'current'), ('u/js320/2', 'current')]
    driver = _FakeDriver({'u/js220/1': 0.0, 'u/js320/2': 10.0})
    with pytest.raises(RuntimeError) as ex:
        read(driver, signals, duration=0.3, stall_timeout=0.3)
    # the error path leaves the instruments idle
    assert [x for x in driver.published if x[1] == 0] == [('u/js220/1/s/i/ctrl', 0), ('u/js320/2/s/i/ctrl', 0)]
    assert not any(k.endswith('!data') for k in driver.fns)
    lines = [x.strip() for x in str(ex.value).split('\n')]
    assert lines[0] == "read failed: -9.500 of 0.3 s, the signals' UTC windows do not overlap"
    assert lines[1].startswith('u/js220/1.current: 5 messages, 500 samples, last 0.')
    assert lines[1].endswith(' s ago, utc +0.000 to +0.500 s')
    assert lines[2].endswith(' s ago, utc +10.000 to +10.500 s')
    assert lines[3].startswith('common window: +10.000 to +0.500 s from 20')


def test_several_devices(path, several_devices):
    paths = several_devices.split(',')
    r = harness.run(path, '-d', 0.3, '--no-progress', visible=several_devices, timeout=15)
    assert r.returncode == 0, r
    data = _parse(r.lines)
    assert sorted(data) == sorted((p, s) for p in paths for s in ['current', 'voltage'])


def test_unplug_stops_read(path, device_path):
    # An unplugged instrument never sends the rest of the data, so the read stops.
    r = harness.run(path, '-d', 30, '--no-progress', visible=device_path, hotplug='unplug@3',
                    timeout=15)
    assert not r.interrupted, r
    assert r.returncode == 1, r
    assert f'{device_path} removed during the read' in r.stdout, r
    assert not r.has_traceback, r
