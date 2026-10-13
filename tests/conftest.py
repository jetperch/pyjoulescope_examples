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

"""Fixtures for the example tests.  See tests/README.md."""

import harness
import jls_files
import pytest


_bench = None


def _bench_devices():
    global _bench
    if _bench is None:
        _bench = harness.bench_devices()
    return _bench


def pytest_generate_tests(metafunc):
    """Run each device test once for each instrument under test."""
    if 'device_path' not in metafunc.fixturenames:
        return
    bench = _bench_devices()
    if not bench:
        params = [pytest.param(None, id='no_device')]
    else:
        params = [pytest.param(p, id=p.model if err is None else str(p)) for p, err in bench]
    metafunc.parametrize('device_path', params, indirect=True)


def pytest_collection_modifyitems(items):
    """Mark every test that uses an instrument, for "-m 'not device'"."""
    for item in items:
        fixtures = getattr(item, 'fixturenames', [])
        if 'device_path' in fixtures or 'several_devices' in fixtures:
            item.add_marker(pytest.mark.device)


@pytest.fixture
def device_path(request):
    """The DevicePath of the instrument under test."""
    path = request.param
    if path is None:
        pytest.skip(f'No Joulescope connected and {harness.ENV_BENCH} is not set')
    for p, err in _bench_devices():
        if p == path and err is not None:
            pytest.fail(err)
    _quiesce(path)
    yield path
    _quiesce(path)


# The settings that the examples change, which _quiesce returns to their
# metadata defaults.  The instruments keep settings between programs.
_RESET_TOPICS = [
    'h/fs', 's/i/ctrl', 's/v/ctrl', 's/p/ctrl', 's/stats/ctrl', 's/stats/scnt',
    's/gpi/0/ctrl', 's/gpi/1/ctrl', 's/gpi/2/ctrl', 's/gpi/3/ctrl', 's/gpi/7/ctrl',
    's/v/range/mode', 's/v/range/select',
    # JS110
    's/sstats/ctrl', 's/extio/voltage', 's/gpo/0/value', 's/gpo/1/value',
    's/i/lsb_src', 's/v/lsb_src', 's/i/range/mode', 's/i/range/pre', 's/i/range/post',
    's/i/range/win', 's/i/range/win_sz',
    # JS220 and JS320
    'c/trigger/dir', 'c/gpio/vref', 's/fuse/0/en', 's/fuse/0/engaged',
]


def _quiesce(path):
    """Prove the example released the instrument, and reset it.

    Return the settings that the examples change to their defaults, then
    turn on the output to the device under test with automatic ranging.
    """
    from pyjoulescope_driver import Driver
    meta = {}

    def on_metadata(topic, value):
        meta[topic[len(path) + 1:-1]] = value  # metadata topics end with "$"

    with Driver() as d:
        if path not in d.device_paths():
            pytest.fail(f'{path} is no longer connected')
        with d.open(path, mode='restore') as device:  # raises if the example still holds it
            with d.subscribe(path, 'metadata_rsp_retain', on_metadata):
                pass
            for topic in _RESET_TOPICS:
                if topic in meta and 'default' in meta[topic]:
                    device.publish(topic, meta[topic]['default'])
            if path.model == 'js110':
                device.publish('s/i/range/select', 'auto')
            else:
                device.publish('s/gpo/+/!clr', 0x83)  # trigger_out, gpo1, gpo0
                device.publish('s/i/range/mode', 'auto')


@pytest.fixture
def several_devices():
    """The device specification for every instrument under test.

    Skips unless there are at least two.
    """
    bench = _bench_devices()
    errors = [err for _, err in bench if err is not None]
    if errors:
        pytest.fail('\n'.join(errors))
    if len(bench) < 2:
        pytest.skip('Needs at least two instruments under test')
    paths = [p for p, _ in bench]
    yield ','.join(paths)
    for path in paths:
        _quiesce(path)


@pytest.fixture
def output_state(device_path):
    """Read or set the instrument's output to the device under test.

    output_state() returns 'off' or 'on'.  output_state('on') turns it on
    with automatic current ranging.
    """
    from pyjoulescope_driver import Driver
    topic = 's/i/range/select' if device_path.model == 'js110' else 's/i/range/mode'

    def fn(value=None):
        with Driver() as d:
            with d.open(device_path, mode='restore') as device:
                if value is not None:
                    device.publish(topic, 'auto' if value == 'on' else 'off')
                return 'off' if device.query(topic) == 0 else 'on'
    return fn


@pytest.fixture
def trigger_level(device_path):
    """Read the TRIGGER level, 0 or 1, on a JS220 or JS320.

    The trigger input reads the level that the trigger output drives.
    """
    from pyjoulescope_driver import Driver

    def fn():
        with Driver() as d:
            with d.open(device_path, mode='restore') as device:
                value = device.publish_and_wait('s/gpi/+/!req', 0, 's/gpi/+/!value', timeout=2)
                return (int(value) >> 7) & 1
    return fn


@pytest.fixture
def statistics_100hz(device_path):
    """Leave the instrument at 100 Hz statistics, as measure.py does."""
    from pyjoulescope_driver import Driver
    with Driver() as d:
        with d.open(device_path, mode='restore') as device:
            device.publish('s/stats/scnt', harness.SAMPLE_RATE[device_path.model] // 100)
    return device_path


@pytest.fixture
def model(device_path):
    """The instrument model under test, such as "js320"."""
    return device_path.model


@pytest.fixture(scope='session')
def jls_v2(tmp_path_factory):
    """A JLS v2 file with current, voltage and power.  See jls_files."""
    return jls_files.write_v2(tmp_path_factory.mktemp('jls') / 'v2.jls')


@pytest.fixture(scope='session')
def jls_v2_multi(tmp_path_factory):
    """A JLS v2 file from two Joulescopes with different time extents.  See jls_files."""
    return jls_files.write_v2_multi(tmp_path_factory.mktemp('jls') / 'v2_multi.jls')


@pytest.fixture(scope='session')
def jls_v1(tmp_path_factory):
    """A JLS v1 file with current, voltage and power.  See jls_files."""
    return jls_files.write_v1(tmp_path_factory.mktemp('jls') / 'v1.jls')
