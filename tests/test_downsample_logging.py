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

"""The example writes to Documents/joulescope, so each test gives it a
Documents folder of its own.  Hotplug and host reboot are in MANUAL.md."""

import datetime
import harness
import pytest
import re


pytestmark = pytest.mark.parametrize('path', harness.paths('downsample_logging'))
START = 'Starting logging  - press CTRL-C to stop'
COLUMNS = 'time,current,voltage,power,charge,energy,current_min,current_max'
NUMBER = r'-?\d+(\.\d+)?(e[-+]\d+)?'
UTC = r'\d{8}T\d{6}\.\d{6}Z'
ROW = re.compile(rf'^({UTC}|{NUMBER})(,{NUMBER}){{7}}$')


@pytest.fixture
def documents(tmp_path):
    """The env and the log directory for the example."""
    env = {
        'JOULESCOPE_EXAMPLES_DOCUMENTS': str(tmp_path / 'Documents'),
        'HOME': str(tmp_path),
        'USERPROFILE': str(tmp_path),
    }
    return env, tmp_path / 'Documents' / 'joulescope'


def _logs(log_dir):
    """Return the (txt, [csv]) contents for each session, oldest first."""
    rv = []
    for txt in sorted(log_dir.glob('jslog_*.txt')):
        csv = sorted(log_dir.glob(txt.stem + '_*.csv'))
        rv.append((txt.read_text(), [c.read_text() for c in csv]))
    return rv


def _run(path, documents, *args, device_path='', rows=4, **kwargs):
    """Run until a CSV file gains rows data rows, then Ctrl-C.

    With no device, run for 3 seconds.
    """
    env, log_dir = documents
    if not device_path:
        return harness.run(path, *args, env=env, visible='', interrupt_after=3, **kwargs)

    def counts():
        return {f: len(_rows(f.read_text())) for f in log_dir.glob('*.csv')}

    before = counts()

    def ready(out):
        return any(n - before.get(f, 0) >= rows for f, n in counts().items())

    return harness.run(path, *args, env=env, visible=device_path, interrupt_on=ready,
                       timeout=10, **kwargs)


def _rows(csv):
    return [x for x in csv.splitlines() if x and not x.startswith('#') and x != COLUMNS]


def test_help(path):
    r = harness.run(path, '--help')
    assert r.returncode == 0, r
    for option in ['--header', '--resume', '-r', '--downsample', '-d', '--frequency', '-f',
                   '--duration', '--time-format', '--time_format', '--device']:
        assert option in r.stdout


@pytest.mark.parametrize('args', [['--header', 'full'], ['-d', 0], ['-f', 'x'],
                                  ['--time-format', 'local']])
def test_invalid(path, args):
    r = harness.run(path, *args)
    assert r.returncode == 2, r


def test_no_device_waits(path, documents):
    r = _run(path, documents)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines[:2] == [START, 'Found no Joulescopes']
    assert re.match(r'^duration=\d+\.\d seconds$', r.lines[2])
    logs = _logs(documents[1])
    assert len(logs) == 1
    txt, csv = logs[0]
    assert csv == []
    for event in ['LOGGER : OPEN', 'PARAM : downsample=1', 'PARAM : frequency=2', 'PARAM : duration=None',
                  'PARAM : time_format=utc', 'DEVICES : \n', 'SIGNAL : SIGINT QUIT', 'LOGGER : DONE']:
        assert event in txt, event


def test_hotplug(path, documents, device_path):
    # Start with no instrument, then plug, unplug and plug it again.
    env, log_dir = documents
    r = harness.run(path, '--time-format', 'relative', env=env, visible=device_path,
                    hotplug='add@3,remove@6,add@8', interrupt_after=11)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.lines[1] == 'Found no Joulescopes'
    txt, csv = _logs(log_dir)[0]
    events = [x.split(' ', 1)[1] for x in txt.splitlines() if ' DEVICE' in x]
    assert events[:4] == ['DEVICES : ', f'DEVICE : OPEN {device_path}', f'DEVICE : CLOSE {device_path}',
                          f'DEVICE : OPEN {device_path}']
    # A JS320 may also drop off USB as it reopens (U.8), which adds OPEN FAILED, then OPEN.
    assert events[-1] == f'DEVICE : CLOSE {device_path}'
    assert len(csv) == 1  # both connections log to the same file
    t = [float(row.split(',')[0]) for row in _rows(csv[0])]
    gaps = [b - a for a, b in zip(t[:-1], t[1:])]
    assert max(gaps) > 1.5, t  # unplugged from 6 to 8 seconds
    assert len(t) >= 6, t


def test_hotplug_open_fails(path, documents, device_path):
    # The instrument disappears while the logger opens it on the replug at 8 seconds,
    # then appears again at 10.5 seconds.
    env, log_dir = documents
    r = harness.run(path, '--time-format', 'relative', env=env, visible=device_path,
                    hotplug='add@3,remove@6,add@8,remove@9.5,add@10.5', open_fail='2',
                    interrupt_after=14)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    txt, csv = _logs(log_dir)[0]
    assert ' FAIL ' not in txt
    assert f'DEVICE : OPEN FAILED {device_path}: jsdrv_open timed out' in txt
    t = [float(row.split(',')[0]) for row in _rows(csv[0])]
    assert t[-1] > 11, t  # logging again after the instrument reappears


def test_device_filter(path, documents, several_devices):
    env, log_dir = documents
    target = sorted(several_devices.split(','))[-1]
    r = harness.run(path, '--device', target.split('/')[-1], env=env, visible=several_devices,
                    interrupt_after=4)
    assert r.returncode == 0, r
    assert r.lines[1] == 'Found one Joulescope'
    txt, csv = _logs(log_dir)[0]
    assert f'DEVICES : {target}\n' in txt
    assert len(csv) == 1


def test_device(path, documents, device_path):
    name = f'{device_path.model}_{device_path.serial_number}'
    r = _run(path, documents, device_path=device_path)
    assert r.returncode == 0, r
    assert r.lines[:2] == [START, 'Found one Joulescope']
    assert re.match(rf'^{name}: charge={NUMBER}, energy={NUMBER}$', r.lines[-1]), r
    txt, csv = _logs(documents[1])[0]
    assert f'DEVICES : {device_path}\n' in txt
    assert f'SUMMARY : {r.lines[-1]}' in txt
    assert csv[0].splitlines()[0] == COLUMNS
    rows = _rows(csv[0])
    assert 3 <= len(rows) <= 8, csv
    for row in rows:
        assert ROW.match(row), row
        assert re.match(UTC, row), row
    t = [datetime.datetime.strptime(row.split(',')[0], '%Y%m%dT%H%M%S.%fZ') for row in rows]
    assert 0.4 < (t[-1] - t[-2]).total_seconds() < 0.6  # 2 Hz


@pytest.mark.parametrize('header', ['none', 'simple', 'comment'])
def test_header(path, documents, device_path, header):
    r = _run(path, documents, '--header', header, device_path=device_path)
    assert r.returncode == 0, r
    csv = _logs(documents[1])[0][1][0].splitlines()
    if header == 'none':
        assert ROW.match(csv[0]), csv
    elif header == 'simple':
        assert csv[0] == COLUMNS
    else:
        assert csv[0] == f'#= header={COLUMNS}'
        assert csv[1] == '#= units=s,A,V,W,C,J,A,A'
        assert csv[2].startswith('#= start_time=')
        assert csv[3].startswith('#= start_str=')
        assert any(x.startswith('#& ') and 'SIGNAL : SIGINT QUIT' in x for x in csv)


def test_time_format(path, documents, device_path):
    for option in ['--time-format', '--time_format']:
        r = _run(path, documents, option, 'relative', device_path=device_path)
        assert r.returncode == 0, r
    for txt, csv in _logs(documents[1]):
        assert 'PARAM : time_format=relative' in txt
        assert _rows(csv[0])
        for row in _rows(csv[0]):
            assert re.match(r'^\d+\.\d{3},', row), row


def test_downsample(path, documents, device_path):
    r = _run(path, documents, '--downsample', 2, device_path=device_path, rows=3)
    assert r.returncode == 0, r
    txt, csv = _logs(documents[1])[0]
    assert 'PARAM : downsample=2' in txt
    rows = _rows(csv[0])
    t = [datetime.datetime.strptime(row.split(',')[0], '%Y%m%dT%H%M%S.%fZ') for row in rows]
    assert 0.9 < (t[-1] - t[-2]).total_seconds() < 1.1  # 1 Hz


def test_frequency(path, documents, device_path):
    r = _run(path, documents, '-f', 4, device_path=device_path)
    assert r.returncode == 0, r
    txt, csv = _logs(documents[1])[0]
    assert 'PARAM : frequency=4' in txt
    rows = _rows(csv[0])
    t = [datetime.datetime.strptime(row.split(',')[0], '%Y%m%dT%H%M%S.%fZ') for row in rows]
    dt = (t[-1] - t[-2]).total_seconds()
    if device_path.model == 'js110':
        assert 'JS110 only supports frequency 2.  Ignoring frequency 4' in r.stdout
        assert 0.4 < dt < 0.6
    else:
        assert 0.2 < dt < 0.3


def test_duration(path, documents, device_path):
    env, log_dir = documents
    r = harness.run(path, '--duration', 2, env=env, visible=device_path, timeout=15)
    assert not r.interrupted, r
    assert r.returncode == 0, r
    assert r.lines[0] == 'Starting logging for 2.0 seconds - press CTRL-C to stop'
    rows = _rows(_logs(log_dir)[0][1][0])
    assert 2 <= len(rows) <= 6, rows


def test_resume(path, documents, device_path):
    r = _run(path, documents, device_path=device_path)
    assert r.returncode == 0, r
    k = len(_rows(_logs(documents[1])[0][1][0]))
    r = _run(path, documents, '--resume', device_path=device_path)
    assert r.returncode == 0, r
    logs = _logs(documents[1])
    assert len(logs) == 1  # resumed the same session
    txt, csv = logs[0]
    assert 'LOGGER : RESUME' in txt
    rows = [row.split(',') for row in _rows(csv[0])]
    assert len(rows) > k
    # charge and energy continue, with the precision written to the CSV file
    assert [float(x) for x in rows[k][4:6]] == pytest.approx([float(x) for x in rows[k - 1][4:6]])


def test_hotplug_before_first_row(path, documents, device_path):
    # With --downsample, the CSV file has only its header when the
    # instrument is unplugged before the first row.  The replug continues it.
    env, log_dir = documents
    r = harness.run(path, '--time-format', 'relative', '--downsample', '4', env=env,
                    visible=device_path, hotplug='add@1,remove@2.5,add@4', interrupt_after=10)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    txt, csv = _logs(log_dir)[0]
    assert 'OPEN FAILED' not in txt, txt
    assert csv[0].splitlines()[0] == COLUMNS
    rows = _rows(csv[0])
    assert len(rows) >= 1, csv[0]
    assert all(ROW.match(row) for row in rows), csv[0]


def test_resume_after_truncated_row(path, documents, device_path):
    # A crash or power loss can cut the last row short.  Resume continues
    # from the last complete row, on a line of its own.
    r = _run(path, documents, device_path=device_path)
    assert r.returncode == 0, r
    csv_path = sorted(documents[1].glob('*.csv'))[0]
    text = csv_path.read_text()
    csv_path.write_text(text[:-12])  # cut the last row inside its last fields
    complete = _rows(text)[-2]
    r = _run(path, documents, '--resume', device_path=device_path)
    assert r.returncode == 0, r
    txt, csv = _logs(documents[1])[0]
    assert 'OPEN FAILED' not in txt, txt
    rows = _rows(csv[0])
    k = rows.index(complete)
    resumed = [row for row in rows[k + 1:] if ROW.match(row)]
    assert len(resumed) >= 1, csv[0]
    assert len(rows) - len(resumed) == k + 2  # only the cut row does not match
    assert [float(x) for x in resumed[0].split(',')[4:6]] == \
        pytest.approx([float(x) for x in complete.split(',')[4:6]])


def test_charge_format(path, documents, device_path):
    # Charge has 6 decimal places, 1 µC, so a small current still accumulates (6.41).
    r = _run(path, documents, device_path=device_path)
    assert r.returncode == 0, r
    rows = [row.split(',') for row in _rows(_logs(documents[1])[0][1][0])]
    assert rows, r
    for row in rows:
        assert re.match(r'^-?\d+\.\d{6}$', row[4]), row
