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

"""Test the test infrastructure itself."""

import harness
import jls_files
import numpy as np
import os
import pytest


def _script(tmp_path, code):
    path = tmp_path / 'script.py'
    path.write_text(code, encoding='utf-8')
    return os.path.relpath(path, harness.REPO_PATH)


def test_bin_wrappers_are_current():
    names = sorted(f[:-3] for f in os.listdir(os.path.join(harness.REPO_PATH, 'bin'))
                   if f.endswith('.py'))
    assert names == sorted(harness.EXAMPLES)
    r = harness.run('tools/gen_bin_wrappers.py', '--check')
    assert r.returncode == 0, r


def test_every_example_is_listed():
    examples = set()
    for d in os.listdir(os.path.join(harness.REPO_PATH, 'examples')):
        for f in os.listdir(os.path.join(harness.REPO_PATH, 'examples', d)):
            if f.endswith('.py'):
                examples.add(f'examples/{d}/{f}')
    assert examples == {p[0] for p in harness.EXAMPLES.values()}


def test_output_args_and_returncode(tmp_path):
    path = _script(tmp_path, 'import sys\nprint("out", sys.argv[1:])\n'
                             'print("err µ", file=sys.stderr)\nsys.exit(3)\n')
    r = harness.run(path, 'a', 2)
    assert r.returncode == 3, r
    assert r.stdout == "out ['a', '2']\n"
    assert r.stderr == 'err µ\n'
    assert not r.interrupted and not r.killed


def test_cwd(tmp_path):
    path = _script(tmp_path, 'open("x.txt", "w").write("hi")\n')
    r = harness.run(path, cwd=tmp_path)
    assert r.returncode == 0, r
    assert (tmp_path / 'x.txt').read_text() == 'hi'


def test_stdin_is_empty_by_default(tmp_path):
    path = _script(tmp_path, 'print(repr(input("prompt: ")))\n')
    r = harness.run(path, timeout=20)
    assert 'EOFError' in r.stderr, r
    assert not r.interrupted
    r = harness.run(path, stdin='hello\n')
    assert r.stdout == "prompt: 'hello'\n", r


def test_ctrl_c_raises_keyboard_interrupt(tmp_path):
    path = _script(tmp_path, 'import time\nprint("ready")\n'
                             'try:\n    time.sleep(30)\nexcept KeyboardInterrupt:\n'
                             '    print("interrupted")\n')
    r = harness.run(path, interrupt_on='ready', timeout=20)
    assert r.interrupted and not r.killed, r
    assert r.returncode == 0, r
    assert r.stdout == 'ready\ninterrupted\n'
    assert r.elapsed < 15


def test_ctrl_c_calls_sigint_handler(tmp_path):
    path = _script(tmp_path, 'import signal, time\nquit_ = False\n'
                             'def on_sigint(*args):\n    global quit_\n    quit_ = True\n'
                             'signal.signal(signal.SIGINT, on_sigint)\nprint("ready")\n'
                             'while not quit_:\n    time.sleep(0.01)\nprint("done")\n')
    r = harness.run(path, interrupt_after=1.0, timeout=20)
    assert r.interrupted and not r.killed, r
    assert r.stdout == 'ready\ndone\n'


def test_timeout_escalates_to_kill(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, 'INTERRUPT_GRACE', 1.0)
    path = _script(tmp_path, 'import signal, time\nsignal.signal(signal.SIGINT, signal.SIG_IGN)\n'
                             'print("ready")\ntime.sleep(60)\n')
    r = harness.run(path, timeout=2.0)
    assert r.interrupted and r.killed, r
    assert r.elapsed < 10


def test_plot_shown(tmp_path):
    path = _script(tmp_path, 'import matplotlib.pyplot as plt\nplt.figure()\nplt.show()\n')
    r = harness.run(path)
    assert r.returncode == 0, r
    assert r.plot_shown
    path = _script(tmp_path, 'import matplotlib.pyplot as plt\nplt.figure()\n')
    assert not harness.run(path).plot_shown


def test_lines_split_progress_bars(tmp_path):
    path = _script(tmp_path, 'import sys\nsys.stdout.write("[--] 0%\\r[==] 100%\\r")\nprint("done")\n')
    assert harness.run(path).lines == ['[--] 0%', '[==] 100%', 'done']


_LIST = ('from pyjoulescope_driver import Driver\nimport joulescope\n'
         'with Driver() as d:\n    print(sorted(d.device_paths()))\n'
         'print(sorted(str(x.device_path) for x in joulescope.scan()))\n')


def test_visible_hides_devices(tmp_path):
    r = harness.run(_script(tmp_path, _LIST))
    assert r.returncode == 0, r
    assert r.lines == ['[]', '[]']


def test_visible_hides_devices_from_device_watch(tmp_path):
    code = ('from pyjoulescope_driver import Driver\nadded = []\n'
            'with Driver() as d:\n'
            '    w = d.device_watch(added.append, print)\n'
            '    w.unsubscribe()\n'
            'print(added)\n')
    r = harness.run(_script(tmp_path, code))
    assert r.returncode == 0, r
    assert r.lines == ['[]']


def test_visible_selects_device(tmp_path, device_path):
    r = harness.run(_script(tmp_path, _LIST), visible=device_path)
    assert r.returncode == 0, r
    assert r.lines == [f"['{device_path}']", f"['{device_path}']"]


def test_hotplug(tmp_path, device_path):
    code = ('import time\nfrom pyjoulescope_driver import Driver\n'
            'with Driver() as d:\n'
            '    print("list", d.device_paths(), flush=True)\n'
            '    w = d.device_watch(lambda p: print("add", p, flush=True),\n'
            '                       lambda p: print("remove", p, flush=True))\n'
            '    d.subscribe("@/!remove", "pub", lambda t, v: print("topic", t, v, flush=True))\n'
            '    time.sleep(3.5)\n'
            '    print("list", d.device_paths(), flush=True)\n'
            '    w.unsubscribe()\n')
    r = harness.run(_script(tmp_path, code), visible=device_path, hotplug='add@1.5,remove@2.5')
    assert r.returncode == 0, r
    assert r.lines == ['list []', f'add {device_path}', f'remove {device_path}',
                       f'topic @/!remove {device_path}', 'list []']


def test_jls_v2(jls_v2):
    from pyjls import Reader
    with Reader(str(jls_v2)) as r:
        names = sorted(s.name for s in r.signals.values() if s.signal_id)
        assert names == ['current', 'power', 'voltage']
        s = r.signal_lookup('current')
        assert s.sample_rate == jls_files.SAMPLE_RATE
        assert s.length == jls_files.SAMPLE_RATE * jls_files.DURATION
        stats = r.fsr_statistics(s.signal_id, 0, s.length, 1)[0]
        assert stats[0] == pytest.approx(jls_files.CURRENT_MEAN, rel=1e-5)
        assert r.sample_id_to_timestamp(s.signal_id, 0) == jls_files.UTC_START


def test_jls_v1(jls_v1):
    from joulescope.data_recorder import DataReader
    r = DataReader().open(str(jls_v1))
    try:
        assert r.sampling_frequency == jls_files.SAMPLE_RATE
        assert r.sample_id_range == [0, jls_files.SAMPLE_RATE * jls_files.DURATION]
        s = r.statistics_get(*r.sample_id_range, units='samples')
        assert s['signals']['current']['µ']['value'] == pytest.approx(jls_files.CURRENT_MEAN, rel=1e-4)
        i = r.samples_get(0, 10, units='samples', fields=['current'])['signals']['current']['value']
        np.testing.assert_allclose(i, jls_files.CURRENT_LOW, rtol=1e-4)
    finally:
        r.close()
