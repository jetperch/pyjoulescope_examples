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

"""Run examples the way a user does, as a subprocess with real arguments.

The tests never import an example.  They run it, then check what it
printed, wrote and returned.  See tests/README.md.
"""

import ctypes
import dataclasses
import os
import re
import signal
import subprocess
import sys
import threading
import time


TESTS_PATH = os.path.dirname(os.path.abspath(__file__))
REPO_PATH = os.path.dirname(TESTS_PATH)
SHIM_PATH = os.path.join(TESTS_PATH, 'shim')
ENV_VISIBLE = 'JOULESCOPE_EXAMPLES_VISIBLE'
ENV_BENCH = 'JOULESCOPE_EXAMPLES_BENCH'
ENV_EXCLUDE = 'JOULESCOPE_EXAMPLES_EXCLUDE'
INTERRUPT_GRACE = 10.0  # seconds from Ctrl-C to kill
TRACEBACK = 'Traceback (most recent call last)'
PLOT_SHOWN = 'FigureCanvasAgg is non-interactive, and thus cannot be shown'


# The examples by their historical bin/ name, mapped to the paths that run
# them, relative to the repository.  Every test runs through each path.
EXAMPLES = {
    'accumulators': ['bin/accumulators.py'],
    'battery_discharge': ['bin/battery_discharge.py'],
    'capture': ['bin/capture.py'],
    'capture_all': ['bin/capture_all.py'],
    'capture_jls_v1': ['bin/capture_jls_v1.py'],
    'capture_jls_v2': ['bin/capture_jls_v2.py'],
    'capture_simple': ['bin/capture_simple.py'],
    'current_range_extract': ['bin/current_range_extract.py'],
    'current_ranging_filter': ['bin/current_ranging_filter.py'],
    'detector': ['bin/detector.py'],
    'downsample_logging': ['bin/downsample_logging.py'],
    'dut_power': ['bin/dut_power.py'],
    'energy_printer_host': ['bin/energy_printer_host.py'],
    'energy_printer_sensor': ['bin/energy_printer_sensor.py'],
    'fuse_js220': ['bin/fuse_js220.py'],
    'gpi_region': ['bin/gpi_region.py'],
    'gpi_synchronized': ['bin/gpi_synchronized.py'],
    'gpio': ['bin/gpio.py'],
    'jls_energy_plot': ['bin/jls_energy_plot.py'],
    'jls_export_points': ['bin/jls_export_points.py'],
    'jls_plot': ['bin/jls_plot.py'],
    'jls_recode': ['bin/jls_recode.py'],
    'low_voltage_shutoff': ['bin/low_voltage_shutoff.py'],
    'measure': ['bin/measure.py'],
    'monitor': ['bin/monitor.py'],
    'read_by_callback': ['bin/read_by_callback.py'],
    'read_by_method': ['bin/read_by_method.py'],
    'read_by_pyjoulescope_driver': ['bin/read_by_pyjoulescope_driver.py'],
    'scan_by_serial_number': ['bin/scan_by_serial_number.py'],
    'statistics': ['bin/statistics.py'],
    'statistics_logger': ['bin/statistics_logger.py'],
    'statistics_v1': ['bin/statistics_v1.py'],
    'statistics_with_trigger_to_jls': ['bin/statistics_with_trigger_to_jls.py'],
    'timesync': ['bin/timesync.py'],
    'trigger': ['bin/trigger.py'],
    'trigger_host_pyjoulescope_driver': ['bin/trigger_host_pyjoulescope_driver.py'],
    'windowed_accum': ['bin/windowed_accum.py'],
}


def paths(name):
    """The repository-relative paths that run an example.

    :param name: The example's historical bin/ name, without ".py".
    :return: The list of paths, to use with pytest.mark.parametrize.
    """
    return list(EXAMPLES[name])


@dataclasses.dataclass
class Result:
    """The outcome of one example run."""
    path: str
    args: list
    returncode: int
    stdout: str
    stderr: str
    elapsed: float
    interrupted: bool = False  # sent Ctrl-C
    killed: bool = False       # did not exit after Ctrl-C

    @property
    def has_traceback(self):
        return TRACEBACK in self.stderr

    @property
    def plot_shown(self):
        """True when the example called matplotlib.pyplot.show()."""
        return PLOT_SHOWN in self.stderr

    @property
    def lines(self):
        """The stdout lines, with progress bars split at carriage returns."""
        return [x for x in re.split(r'[\r\n]+', self.stdout) if x]

    def __str__(self):
        """A failure message with enough context to act on."""
        return '\n'.join([
            f'$ {self.path} {" ".join(self.args)}',
            f'returncode={self.returncode} elapsed={self.elapsed:.1f}s '
            f'interrupted={self.interrupted} killed={self.killed}',
            '--- stdout ---', self.stdout[-4000:],
            '--- stderr ---', self.stderr[-4000:],
        ])


def environ(visible=None, env=None):
    """The environment for an example.

    :param visible: The device specification for the devices the example
        may see.  '' (default) hides every device.  None does not limit
        the devices.
    :param env: Additional environment variables.
    """
    e = dict(os.environ)
    e.pop(ENV_VISIBLE, None)
    e['PYTHONUNBUFFERED'] = '1'
    e['PYTHONIOENCODING'] = 'utf-8'
    e['PYTHONDONTWRITEBYTECODE'] = '1'
    e['PYTHONFAULTHANDLER'] = '1'
    e['MPLBACKEND'] = 'Agg'  # plt.show() warns instead of opening a window
    if visible is not None:
        e[ENV_VISIBLE] = visible
        e['PYTHONPATH'] = os.pathsep.join([SHIM_PATH] + [p for p in [e.get('PYTHONPATH')] if p])
    if env:
        e.update(env)
    return e


def _reader(stream, chunks):
    fd = stream.fileno()
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            return
        chunks.append(chunk)


def _text(chunks):
    text = b''.join(chunks).decode('utf-8', errors='replace')
    return text.replace('\r\n', '\n')


def _interrupt(process):
    """Send Ctrl-C, the same as a user pressing it."""
    if sys.platform == 'win32':
        subprocess.run([sys.executable, os.path.join(TESTS_PATH, 'ctrl_c.py'), str(process.pid)],
                       timeout=10, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass


def run(path, *args, cwd=None, timeout=60.0, interrupt_after=None, interrupt_on=None,
        visible='', env=None, stdin=None):
    """Run an example as a subprocess.

    :param path: The example path, relative to the repository.
    :param args: The command-line arguments.
    :param cwd: The working directory.  None (default) uses the repository.
    :param timeout: The time in seconds before Ctrl-C, then kill.
        A run that needs the kill is a test failure, not a skip.
    :param interrupt_after: Send Ctrl-C after this many seconds.
    :param interrupt_on: Send Ctrl-C once stdout contains this text, or
        once this callable(stdout) returns True.
    :param visible: The device specification for the devices that the
        example may see.  '' (default) hides every device, which is the
        offline tier.  See tests/shim/sitecustomize.py.
    :param env: Additional environment variables.
    :param stdin: The text for stdin.  None (default) provides an empty
        stdin, so a prompt reads end-of-file rather than blocking.
    :return: The :class:`Result`.
    """
    args = [str(a) for a in args]
    cmd = [sys.executable, os.path.join(REPO_PATH, path)] + args
    kwargs = {}
    if sys.platform == 'win32':
        # Children inherit "ignore Ctrl-C", which some launchers, such as
        # IDEs and agents, set.  Clear it, as in a user's terminal.
        ctypes.WinDLL('kernel32').SetConsoleCtrlHandler(None, False)
        # A hidden console of its own, so that Ctrl-C reaches only this example.
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE
        kwargs['startupinfo'] = si
    else:
        kwargs['start_new_session'] = True
    if isinstance(interrupt_on, str):
        text = interrupt_on
        interrupt_on = lambda out: text in out

    t_start = time.monotonic()
    p = subprocess.Popen(cmd, cwd=REPO_PATH if cwd is None else cwd, env=environ(visible, env),
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         **kwargs)
    stdout, stderr = [], []
    threads = [threading.Thread(target=_reader, args=(p.stdout, stdout), daemon=True),
               threading.Thread(target=_reader, args=(p.stderr, stderr), daemon=True)]
    for t in threads:
        t.start()
    try:
        if stdin:
            p.stdin.write(stdin.encode('utf-8'))
        p.stdin.close()
    except OSError:
        pass  # the example exited without reading stdin

    interrupted = False
    killed = False
    t_interrupt = None
    while p.poll() is None:
        t_now = time.monotonic() - t_start
        if not interrupted:
            if t_now >= timeout \
                    or (interrupt_after is not None and t_now >= interrupt_after) \
                    or (interrupt_on is not None and interrupt_on(_text(stdout))):
                _interrupt(p)
                interrupted = True
                t_interrupt = time.monotonic()
        elif time.monotonic() - t_interrupt > INTERRUPT_GRACE or t_now > timeout + INTERRUPT_GRACE:
            p.kill()
            killed = True
            break
        time.sleep(0.02)
    p.wait()
    for t in threads:
        t.join(timeout=5)
    return Result(path=path, args=args, returncode=p.returncode,
                  stdout=_text(stdout), stderr=_text(stderr),
                  elapsed=time.monotonic() - t_start,
                  interrupted=interrupted, killed=killed)


def bench_devices():
    """List the device paths of the instruments under test.

    :return: The list of (DevicePath, error) for the instruments under
        test.  error is None, or the reason that the configured instrument
        is not available.

    JOULESCOPE_EXAMPLES_BENCH lists the device specifications of the
    instruments under test, such as "js320-31NB,js220-000415".  Each must
    be connected, or its tests fail.  When unset, use every connected
    Joulescope except those matching JOULESCOPE_EXAMPLES_EXCLUDE, such as
    an instrument that only supplies power to the bench.
    """
    from pyjoulescope_driver import Driver, device_filter
    bench = os.environ.get(ENV_BENCH, '').strip()
    exclude = os.environ.get(ENV_EXCLUDE, '').strip()
    with Driver() as d:
        connected = d.find_devices(brand='joulescope')
    if exclude:
        excluded = device_filter.find(connected, exclude)
        connected = [p for p in connected if p not in excluded]
    if not bench:
        return [(p, None) for p in connected]
    rv = []
    for spec in [s.strip() for s in bench.split(',') if s.strip()]:
        matches = device_filter.find(connected, spec)
        if len(matches) == 1:
            rv.append((matches[0], None))
        else:
            rv.append((spec, f'{ENV_BENCH} lists "{spec}", which matches {len(matches)} '
                             f'connected instruments: {connected}'))
    return rv
