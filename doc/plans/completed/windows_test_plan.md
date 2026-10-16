<!--
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
-->

# Windows test plan for the 2026 Oct 10 Linux stress fixes

Instructions for an agent, such as Claude Code, on the Windows bench with a
JS110, JS220 and JS320 attached.  A stress run on Linux, with a USB hub that
power cycled each instrument, found and fixed the defects in
`doc/plans/completed/refactor_v1.md` 6.40 to 6.52 and U.10 to U.12.
These steps repeat the parts that depend on the platform, and close the
one known Windows gap (step 3).

Report results as counts from logs and exit codes, never from memory.
Write each script below to a scratch directory, not to a repository.


## 1. Setup

Use these versions, all from `main` unless noted:

| Repository | Version | Notes |
| ---------- | ------- | ----- |
| joulescope_driver | 2.5.1 | Rebuild the extension: `python setup.py build_ext --inplace` |
| pyjoulescope | 1.7.1 | |
| pyjoulescope_examples | 1.0.1 | |
| jls (pyjls) | branch `fix/closed_handle` | Rebuild: `python setup.py build_ext --inplace` |

Put the four repository roots on `PYTHONPATH`, or install them editable.
Confirm with:

    python -c "import pyjoulescope_driver as d, joulescope as j; print(d.__version__,j.__version__)"
    python -m pyjoulescope_driver scan

The scan must list all three instruments.  Close the Joulescope UI and any
other program that uses them.


## 2. The examples suite

From pyjoulescope_examples:

    python -m pytest -rfEX

Expected: no failures.  On Linux this was 1258 passed and 70 skipped in 39
minutes.  The suite now includes `tests/test_unplug.py`, which simulates
an unplug in each streaming example, and runs each example with
`PYTHONWARNINGS=error::ResourceWarning`.

Then run it once more with every warning as an error, which on Linux
passed after the `statistics_logger.py` fix:

    set PYTHONWARNINGS=error
    python -m pytest -rfEX
    set PYTHONWARNINGS=

For any failure, record the test id and the example's stdout and stderr
from the pytest output, then rerun only that test three times to tell a
defect from an intermittent.


## 3. Opening an instrument that another program holds

On Linux, joulescope_driver 2.5.0 reported `-6 UNKNOWN` and leaked a file
handle for each failed open; 2.5.1 reports `21 IN_USE`.  The WinUSB backend
was not changed: `device_open()` in `src/backend/winusb/backend.c` returns
1 (`UNSPECIFIED`) when `CreateFile` or `WinUsb_Initialize` fails.  Expect
that here, and fix it.

Save as `busy_open.py`:

    import subprocess, sys, psutil
    from pyjoulescope_driver import Driver

    dev = sys.argv[1]
    holder = subprocess.Popen([sys.executable, '-c', (
        'import sys\nfrom pyjoulescope_driver import Driver\n'
        f'with Driver() as d:\n    d.open("{dev}", mode="restore")\n'
        '    print("held", flush=True)\n    sys.stdin.read()\n')],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == 'held'
    proc = psutil.Process()
    errors = {}
    with Driver() as d:
        h0 = proc.num_handles()
        for i in range(200):
            try:
                d.open(dev, mode='restore', timeout=3)
                d.close(dev)
                errors['OK'] = errors.get('OK', 0) + 1
            except Exception as ex:
                errors[str(ex)] = errors.get(str(ex), 0) + 1
        print(f'handles {h0} -> {proc.num_handles()}')
        print(errors)
        holder.stdin.close()
        holder.wait(timeout=10)
        d.open(dev, mode='restore', timeout=3)  # must work once released
        d.close(dev)
        print('reopen after release OK')

Run it for each instrument, such as `python busy_open.py u/js220/000415`,
using the paths from the scan.

Expected after the fix: 200 failures with `21 IN_USE`, each at once (well
under the 3 second timeout, including the JS320), no handle growth beyond
a few, and `reopen after release OK`.

To fix: in `device_open()`, log `GetLastError()` on each failure path to
learn the codes that Windows returns for a held device (likely
`ERROR_ACCESS_DENIED` from `CreateFile`), then return a jsdrv error code
instead of 1: `JSDRV_ERROR_IN_USE` for a held device,
`JSDRV_ERROR_NOT_FOUND` for `ERROR_FILE_NOT_FOUND` or
`ERROR_DEVICE_NOT_CONNECTED`, and `JSDRV_ERROR_IO` otherwise.  Keep the
existing `ERROR_BUSY` retry, which covers a device that Windows is still
resuming.  The libusb backend has the equivalent mapping in
`libusb_error_to_jsdrv()`.  The JS320 (`mb_device.c`) already forwards the
backend error to the API.  Add a CHANGELOG entry, rebuild, rerun the
script, and commit to main.


## 4. Unplug

Most of the defects were found by unplugging instruments while examples
ran.  Use the first method that the bench supports:

1. A USB hub with per-port power switching.
2. `pnputil`, from an administrator prompt.  It removes the device from
   Windows while it stays powered, which is close to an unplug for the
   host software.  Find the instance id with `pnputil /enum-devices
   /connected /class USBDevice` (look for VID_16D0), then
   `pnputil /disable-device "<id>"` and `pnputil /enable-device "<id>"`.
3. By hand, if the operator is available.

Note: on Linux, a JS110 did not return after its USB data lines dropped
while it stayed powered, and only a power cycle recovered it.  If method 2
leaves a JS110 missing, that is the same behavior, not a new defect.

For each command, start it, unplug the instrument after 4 seconds,
and plug it back in after 10 seconds.  Use `--device` to pick the
instrument, and run each row on the JS110, JS220 and JS320.

* `python examples/pyjoulescope_driver/record.py out.jls --device <dev>`:
  prints `<dev> removed: stop`, exits 1, and `out.jls` is readable.
* `python -m pyjoulescope_driver record --device <dev> out.jls`: the same.
* `python -m pyjoulescope_driver statistics --device <dev>`: prints
  `<dev> removed: stop` and exits 1.
* `python -m pyjoulescope_driver measure --device <dev> --duration 30`: the
  same.
* `python examples/pyjoulescope_driver/read.py -d 30 --device <dev>`:
  prints `<dev> removed during the read` and exits 1.
* `python examples/joulescope/statistics_logger.py --out out.csv`, with all
  three: prints `<MODEL>-<serial> removed: stop` and exits 1.
* `python examples/pyjoulescope_driver/downsample_logging.py --downsample 4`:
  keeps running.  Its log shows `DEVICE : CLOSE` then `DEVICE : OPEN`, with
  no `OPEN FAILED`, and charge and energy continue across the gap.

None may print a Python traceback or need a second Ctrl-C.  For
`downsample_logging.py`, also unplug once within its first 2 seconds:
before 1.0.1, an unplug before the first row stopped that instrument for
good.


## 5. Memory over repeated unplugs

On Linux, each unplug of an open instrument leaked 175 to 345 KB in the
libusb backend, fixed in joulescope_driver 2.5.1.  The WinUSB backend frees
its transfers when it closes each endpoint, so it should not leak, but
measure it if the bench can unplug automatically (step 4, method 1 or 2).

Run `downsample_logging.py` with all three instruments, unplug and replug
one instrument 30 times, and log the process memory once a minute with
`psutil.Process(pid).memory_info().rss`.  Expected: RSS grows by well under
1 MB over the 30 cycles.  On Linux before the fix, it grew by about 6 MB.


## 6. Hard kill and reopen

Kill a streaming process at a random time, then confirm that a new
process opens and streams.  On Linux, 300 of 300 passed, including kills
during the open.  On Windows, TerminateProcess is the hard kill.

    for 40 iterations per instrument:
        start a process that opens the device and streams s/i/!data
        after a random 0.05 to 3 seconds, kill it (Popen.kill())
        start a new process: open with timeout=3, stream s/i/!data for
          1 second, close; require at least 0.5 seconds of samples

Expected: 40 of 40 for each instrument.  Record any open that takes over
2 seconds; the JS320 took up to 1.9 seconds on Linux.


## 7. Report

Summarize each step with its counts, the failures with their exact
output, and the commits made.  Add a dated status line to
`doc/plans/completed/refactor_v1.md` section 12 in pyjoulescope_examples.
