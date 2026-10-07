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
    yield path
    _quiesce(path)


def _quiesce(path):
    """Prove the example released the instrument, and leave it usable."""
    from pyjoulescope_driver import Driver
    with Driver() as d:
        if path not in d.device_paths():
            pytest.fail(f'{path} is no longer connected')
        with d.open(path, mode='restore'):  # raises if the example still holds it
            pass


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
def model(device_path):
    """The instrument model under test, such as "js320"."""
    return device_path.model


@pytest.fixture(scope='session')
def jls_v2(tmp_path_factory):
    """A JLS v2 file with current, voltage and power.  See jls_files."""
    return jls_files.write_v2(tmp_path_factory.mktemp('jls') / 'v2.jls')


@pytest.fixture(scope='session')
def jls_v1(tmp_path_factory):
    """A JLS v1 file with current, voltage and power.  See jls_files."""
    return jls_files.write_v1(tmp_path_factory.mktemp('jls') / 'v1.jls')
